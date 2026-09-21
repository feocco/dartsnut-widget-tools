#!/usr/bin/env bash
# Idempotent Cloud Agent install. Must terminate. Do not start long-running processes.
set -euo pipefail
set +x

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export DEBIAN_FRONTEND=noninteractive

APT_PACKAGES=(
  ca-certificates
  curl
  git
  python3
  python3-pip
  python3-venv
)

curl_fetch() {
  curl -fsSL --connect-timeout 15 --max-time 120 --retry 3 --retry-delay 5 "$@"
}

package_installed() {
  dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q 'install ok installed'
}

install_apt_packages() {
  local missing=()
  local pkg
  for pkg in "${APT_PACKAGES[@]}"; do
    if ! package_installed "$pkg"; then
      missing+=("$pkg")
    fi
  done
  if [ "${#missing[@]}" -eq 0 ]; then
    echo "apt packages already installed"
    return 0
  fi
  echo "installing apt packages: ${missing[*]}"
  if ! sudo apt-get update; then
    echo "apt-get update failed. Cloud egress must allow archive.ubuntu.com and security.ubuntu.com." >&2
    exit 1
  fi
  sudo apt-get install -y --no-install-recommends "${missing[@]}"
}

install_tailscale() {
  if command -v tailscale >/dev/null && command -v tailscaled >/dev/null; then
    echo "tailscale already installed"
  else
    local ts_arch tmp
    case "$(uname -m)" in
      x86_64) ts_arch=amd64 ;;
      aarch64 | arm64) ts_arch=arm64 ;;
      *)
        echo "unsupported architecture for Tailscale: $(uname -m)" >&2
        exit 1
        ;;
    esac
    tmp="$(mktemp -d)"
    # Static tarball avoids Ubuntu apt mirrors (often blocked on Cloud egress).
    # pkgs.tailscale.com is already covered by *.tailscale.com.
    curl_fetch "https://pkgs.tailscale.com/stable/tailscale_latest_${ts_arch}.tgz" \
      -o "${tmp}/tailscale.tgz"
    tar -xzf "${tmp}/tailscale.tgz" -C "${tmp}"
    sudo install -m 0755 "${tmp}"/tailscale_*/tailscale "${tmp}"/tailscale_*/tailscaled /usr/local/bin/
    rm -rf "${tmp}"
  fi
  # Package install may enable systemd tailscaled. Builds must not leave it running.
  if command -v systemctl >/dev/null; then
    sudo systemctl disable --now tailscaled 2>/dev/null || true
  fi
}

install_node_and_pnpm() {
  if command -v node >/dev/null; then
    node_major="$(node -p 'parseInt(process.versions.node, 10)')"
  else
    node_major=0
  fi
  if [ "${node_major}" -lt 20 ]; then
    echo "Node.js ${node_major} is below 20; installing 22.x from NodeSource requires deb.nodesource.com egress."
    curl_fetch https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt-get install -y nodejs
  fi
  if ! command -v pnpm >/dev/null; then
    if command -v corepack >/dev/null; then
      sudo corepack enable
      corepack prepare pnpm@9 --activate
    else
      sudo npm install -g pnpm
    fi
  fi
}

install_repo_venv() {
  python3 -m venv .venv
  .venv/bin/pip install -U pip
  .venv/bin/pip install -e ".[dev]"
}

install_emulator() {
  local emulator_dir="${DARTSNUT_EMULATOR_DIR:-/opt/dartsnut_emulator}"
  if [ ! -d "${emulator_dir}/.git" ]; then
    sudo mkdir -p "$(dirname "${emulator_dir}")"
    sudo rm -rf "${emulator_dir}"
    sudo git clone --depth 1 https://github.com/Dartsnut/dartsnut_emulator.git "${emulator_dir}"
  else
    # Shallow clones cannot reliably fast-forward after origin moves. Fetch the
    # current tip and reset to it so later installs pick up emulator updates.
    sudo git -C "${emulator_dir}" fetch --depth 1 origin HEAD
    sudo git -C "${emulator_dir}" reset --hard FETCH_HEAD
  fi
  sudo chown -R "$(id -un):$(id -gn)" "${emulator_dir}"
  (
    cd "${emulator_dir}"
    pnpm install --frozen-lockfile
    pnpm run setup:python
  )
}

install_apt_packages
install_tailscale
install_node_and_pnpm
install_repo_venv
install_emulator

echo "cloud install complete"
