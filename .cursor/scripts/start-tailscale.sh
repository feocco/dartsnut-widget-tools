#!/usr/bin/env bash
set -euo pipefail
set +x

export PATH="${HOME}/.local/bin:${PATH}"

if [[ -z "${TS_AUTHKEY:-}" ]]; then
  echo "TS_AUTHKEY is required to join the tailnet." >&2
  exit 2
fi
if ! command -v tailscale >/dev/null 2>&1 || ! command -v tailscaled >/dev/null 2>&1; then
  echo "Tailscale is not installed; run .cursor/scripts/install-tailscale.sh." >&2
  exit 2
fi

state_dir="${TAILSCALE_STATE_DIR:-${HOME}/.local/state/cursor-tailscale}"
runtime_dir="${TAILSCALE_RUNTIME_DIR:-/tmp/cursor-tailscale-${UID}}"
socket="${runtime_dir}/tailscaled.sock"
daemon_log="${runtime_dir}/tailscaled.log"
lock_dir="${runtime_dir}/start.lock"
auth_file=""
install -d -m 0700 "${state_dir}" "${runtime_dir}"

lock_acquired="false"
for _ in $(seq 1 30); do
  if mkdir "${lock_dir}" 2>/dev/null; then
    lock_acquired="true"
    break
  fi
  sleep 1
done
if [[ "${lock_acquired}" != "true" ]]; then
  echo "Timed out waiting for another Tailscale startup." >&2
  exit 1
fi
cleanup() {
  rm -rf "${lock_dir}"
  [[ -z "${auth_file}" ]] || rm -f "${auth_file}"
}
trap cleanup EXIT

tailscale_cli=(tailscale --socket="${socket}")

daemon_ready() {
  [[ -S "${socket}" ]] && "${tailscale_cli[@]}" status --json >/dev/null 2>&1
}

if ! daemon_ready; then
  rm -f "${socket}"
  nohup tailscaled \
    --state="${state_dir}/tailscaled.state" \
    --socket="${socket}" \
    --tun=userspace-networking \
    --outbound-http-proxy-listen=127.0.0.1:1054 \
    --socks5-server=127.0.0.1:1055 \
    >"${daemon_log}" 2>&1 &

  for _ in $(seq 1 30); do
    daemon_ready && break
    sleep 1
  done
  if ! daemon_ready; then
    echo "tailscaled did not become ready; see ${daemon_log}." >&2
    exit 1
  fi
fi

connected() {
  "${tailscale_cli[@]}" status --json 2>/dev/null |
    python3 -c '
import json
import sys

status = json.load(sys.stdin)
self_node = status.get("Self") or {}
connected = (
    status.get("BackendState") == "Running"
    and self_node.get("Online") is True
    and self_node.get("Tags") == ["tag:cursor-cloud"]
)
raise SystemExit(0 if connected else 1)
'
}

if ! connected; then
  auth_file="$(mktemp "${runtime_dir}/auth-key.XXXXXX")"
  chmod 0600 "${auth_file}"
  printf '%s' "${TS_AUTHKEY}" >"${auth_file}"
  short_id="$(
    printf '%s' "${CURSOR_AGENT_ID:-${HOSTNAME:-$(hostname)}}" |
      shasum -a 256 |
      awk '{print substr($1, 1, 8)}'
  )"
  "${tailscale_cli[@]}" up \
    --reset \
    --auth-key="file:${auth_file}" \
    --hostname="cursor-cloud-${short_id}" \
    --accept-routes=false \
    --advertise-routes= \
    --advertise-exit-node=false \
    --exit-node= \
    --ssh=false \
    --timeout=60s
  rm -f "${auth_file}"
  auth_file=""
fi

for _ in $(seq 1 60); do
  connected && {
    echo "Tailscale is online as tag:cursor-cloud; SOCKS5 is listening on 127.0.0.1:1055."
    exit 0
  }
  sleep 1
done

echo "Tailscale connected without the required tag:cursor-cloud identity, or did not come online." >&2
exit 1
