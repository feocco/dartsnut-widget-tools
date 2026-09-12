#!/usr/bin/env bash
# Idempotent Cloud Agent install. Must terminate. Do not start long-running processes.
set -euo pipefail
set +x

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export DEBIAN_FRONTEND=noninteractive

sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  python3 \
  python3-pip \
  python3-venv

install_tailscale() {
  if command -v tailscale >/dev/null && command -v tailscaled >/dev/null; then
    echo "tailscale already installed"
  else
    . /etc/os-release
    sudo mkdir -p --mode=0755 /usr/share/keyrings
    curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/${VERSION_CODENAME}.noarmor.gpg" \
      | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
    curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/${VERSION_CODENAME}.tailscale-keyring.list" \
      | sudo tee /etc/apt/sources.list.d/tailscale.list >/dev/null
    sudo apt-get update
    sudo apt-get install -y tailscale
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
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
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
    sudo git -C "${emulator_dir}" fetch --depth 1 origin
    sudo git -C "${emulator_dir}" merge --ff-only FETCH_HEAD || true
  fi
  sudo chown -R "$(id -un):$(id -gn)" "${emulator_dir}"
  (
    cd "${emulator_dir}"
    pnpm install --frozen-lockfile
    pnpm run setup:python
  )
}

install_tailscale
install_node_and_pnpm
install_repo_venv
install_emulator

echo "cloud install complete"
