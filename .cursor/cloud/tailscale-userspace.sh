#!/usr/bin/env bash
# Idempotent userspace Tailscale. Safe to run twice. Never prints or writes TAILSCALE_AUTH_KEY.
set +x
set +o xtrace 2>/dev/null || true
if [[ $- == *x* ]]; then
  echo "tailscale-userspace.sh refuses to run with xtrace enabled" >&2
  exit 1
fi
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROXY_HELPER="${ROOT}/.cursor/cloud/tailscale-proxy.env"
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/tailscale"
SOCKET="${STATE_DIR}/tailscaled.sock"
RUNTIME_HELPER="${STATE_DIR}/tailscale-proxy.env"

if [[ $- == *x* ]]; then
  echo "tailscale-userspace.sh refuses to run with xtrace enabled" >&2
  exit 1
fi

if [ -z "${TAILSCALE_AUTH_KEY:-}" ]; then
  echo "TAILSCALE_AUTH_KEY unset; skipping userspace Tailscale"
  exit 0
fi

if ! command -v tailscaled >/dev/null || ! command -v tailscale >/dev/null; then
  echo "tailscale is not installed; run the environment install script first" >&2
  exit 1
fi

mkdir -p "${STATE_DIR}"
if [ -f "${PROXY_HELPER}" ]; then
  cp "${PROXY_HELPER}" "${RUNTIME_HELPER}"
fi

if command -v systemctl >/dev/null; then
  if systemctl is-active --quiet tailscaled 2>/dev/null; then
    sudo systemctl stop tailscaled || true
  fi
  sudo systemctl disable tailscaled 2>/dev/null || true
fi

proxy_listening() {
  python3 - <<'PY'
import socket
import sys

for port in (1054, 1055):
    try:
        with socket.create_connection(("127.0.0.1", port), 1):
            pass
    except OSError:
        sys.exit(1)
PY
}

if ! proxy_listening; then
  setsid tailscaled \
    --tun=userspace-networking \
    --outbound-http-proxy-listen=localhost:1054 \
    --socks5-server=localhost:1055 \
    --statedir="${STATE_DIR}" \
    --socket="${SOCKET}" \
    </dev/null >"${STATE_DIR}/tailscaled.log" 2>&1 &
  ready=0
  for _ in $(seq 1 50); do
    if proxy_listening; then
      ready=1
      break
    fi
    sleep 0.2
  done
  if [ "${ready}" -ne 1 ]; then
    echo "userspace tailscaled did not open the local proxy ports" >&2
    exit 1
  fi
fi

backend_state() {
  tailscale --socket="${SOCKET}" status --json 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState",""))' \
    2>/dev/null || true
}

if [ "$(backend_state)" = "Running" ]; then
  echo "userspace Tailscale already connected"
  echo "source ${PROXY_HELPER}"
  exit 0
fi

# Auth key stays in this process environment. It is not written to disk or printed.
set +x
tailscale --socket="${SOCKET}" up \
  --auth-key="${TAILSCALE_AUTH_KEY}" \
  --hostname=dartsnut-cloud \
  --accept-dns=false

if [ "$(backend_state)" != "Running" ]; then
  echo "tailscale up did not reach a running backend" >&2
  exit 1
fi

echo "userspace Tailscale is connected"
echo "source ${PROXY_HELPER}"
