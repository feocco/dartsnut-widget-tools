import os
import signal
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / ".cursor" / "scripts" / "start-tailscale.sh"


class CloudTailscaleScriptTests(unittest.TestCase):
    def test_start_requires_auth_key_without_echoing_environment(self):
        env = os.environ.copy()
        env.pop("TS_AUTHKEY", None)

        result = subprocess.run(
            ["bash", str(START_SCRIPT)],
            capture_output=True,
            check=False,
            env=env,
            text=True,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("TS_AUTHKEY is required", result.stderr)

    def test_start_joins_once_with_auth_key_file(self):
        secret = "test-auth-key-never-log"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / "bin"
            runtime_dir = root / "runtime"
            state_dir = root / "state"
            bin_dir.mkdir()
            tailscaled = bin_dir / "tailscaled"
            tailscale = bin_dir / "tailscale"
            tailscaled.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    socket=""
                    for argument in "$@"; do
                      case "${argument}" in
                        --socket=*) socket="${argument#--socket=}" ;;
                      esac
                    done
                    printf 'launch\\n' >>"${FAKE_LAUNCH_FILE}"
                    exec python3 - "${socket}" "${FAKE_PID_FILE}" <<'PY'
                    import os
                    import signal
                    import socket
                    import sys
                    import time

                    path, pid_file = sys.argv[1:]
                    server = socket.socket(socket.AF_UNIX)
                    server.bind(path)
                    open(pid_file, "w").write(str(os.getpid()))
                    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
                    while True:
                        time.sleep(1)
                    PY
                    """
                )
            )
            tailscale.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    socket="${1#--socket=}"
                    shift
                    case "${1:-}" in
                      status)
                        [[ -S "${socket}" ]]
                        if [[ -f "${FAKE_JOINED_FILE}" ]]; then
                          printf '%s\\n' '{"BackendState":"Running","Self":{"Online":true,"Tags":["tag:cursor-cloud"]}}'
                        else
                          printf '%s\\n' '{"BackendState":"NeedsLogin","Self":{"Online":false,"Tags":[]}}'
                        fi
                        ;;
                      up)
                        auth_file=""
                        for argument in "$@"; do
                          case "${argument}" in
                            --auth-key=file:*) auth_file="${argument#--auth-key=file:}" ;;
                          esac
                        done
                        [[ -n "${auth_file}" ]]
                        [[ "$(cat "${auth_file}")" == "${FAKE_AUTH_KEY}" ]]
                        touch "${FAKE_JOINED_FILE}"
                        ;;
                      *)
                        exit 2
                        ;;
                    esac
                    """
                )
            )
            tailscaled.chmod(0o755)
            tailscale.chmod(0o755)

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:{env['PATH']}",
                    "TS_AUTHKEY": secret,
                    "TAILSCALE_RUNTIME_DIR": str(runtime_dir),
                    "TAILSCALE_STATE_DIR": str(state_dir),
                    "FAKE_AUTH_KEY": secret,
                    "FAKE_JOINED_FILE": str(root / "joined"),
                    "FAKE_LAUNCH_FILE": str(root / "launches"),
                    "FAKE_PID_FILE": str(root / "pid"),
                    "CURSOR_AGENT_ID": "test-cloud-agent",
                }
            )

            try:
                try:
                    first = subprocess.run(
                        ["bash", str(START_SCRIPT)],
                        capture_output=True,
                        check=False,
                        env=env,
                        text=True,
                        timeout=10,
                    )
                except subprocess.TimeoutExpired as exc:
                    daemon_log = runtime_dir / "tailscaled.log"
                    diagnostics = {
                        "stdout": exc.stdout,
                        "stderr": exc.stderr,
                        "runtime_entries": sorted(path.name for path in runtime_dir.iterdir()),
                        "daemon_log": daemon_log.read_text() if daemon_log.exists() else "",
                        "joined": (root / "joined").exists(),
                    }
                    self.fail(f"startup timed out: {diagnostics!r}")
                second = subprocess.run(
                    ["bash", str(START_SCRIPT)],
                    capture_output=True,
                    check=False,
                    env=env,
                    text=True,
                    timeout=10,
                )
                combined_output = first.stdout + first.stderr + second.stdout + second.stderr
                self.assertEqual(first.returncode, 0, combined_output)
                self.assertEqual(second.returncode, 0, combined_output)
                self.assertNotIn(secret, combined_output)
                self.assertEqual((root / "launches").read_text().splitlines(), ["launch"])
                self.assertEqual(list(runtime_dir.glob("auth-key.*")), [])
            finally:
                pid_file = root / "pid"
                if pid_file.exists():
                    os.kill(int(pid_file.read_text()), signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
