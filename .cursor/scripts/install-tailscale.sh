#!/usr/bin/env bash
set -euo pipefail

TAILSCALE_VERSION="${TAILSCALE_VERSION:-1.102.3}"
INSTALL_DIR="${TAILSCALE_INSTALL_DIR:-${HOME}/.local/bin}"

if command -v tailscale >/dev/null 2>&1 && command -v tailscaled >/dev/null 2>&1; then
  echo "Tailscale client is already installed."
  exit 0
fi

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Tailscale Cloud Agent installation requires Linux." >&2
  exit 2
fi

case "$(uname -m)" in
  x86_64) archive_arch="amd64" ;;
  aarch64|arm64) archive_arch="arm64" ;;
  *)
    echo "Unsupported Tailscale architecture: $(uname -m)" >&2
    exit 2
    ;;
esac

archive_name="tailscale_${TAILSCALE_VERSION}_${archive_arch}.tgz"
package_url="https://pkgs.tailscale.com/stable/${archive_name}"
checksum_url="${package_url}.sha256"
release_api="https://api.github.com/repos/tailscale/tailscale/releases/tags/v${TAILSCALE_VERSION}"
work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT
archive="${work_dir}/${archive_name}"

download_package() {
  curl --retry 3 --retry-delay 2 --fail --silent --show-error \
    --location "${package_url}" --output "${archive}" &&
    curl --retry 3 --retry-delay 2 --fail --silent --show-error \
      --location "${checksum_url}" --output "${archive}.sha256"
}

download_github_asset() {
  local asset_url checksum_asset_url release_json
  release_json="${work_dir}/release.json"
  curl --retry 3 --retry-delay 2 --fail --silent --show-error \
    --location "${release_api}" --output "${release_json}" || return 1
  asset_url="$(
    python3 -c '
import json
import sys

name = sys.argv[1]
release = json.load(open(sys.argv[2]))
for asset in release.get("assets", []):
    if asset.get("name") == name:
        print(asset["browser_download_url"])
        break
' "${archive_name}" "${release_json}"
  )"
  checksum_asset_url="$(
    python3 -c '
import json
import sys

name = sys.argv[1]
release = json.load(open(sys.argv[2]))
for asset in release.get("assets", []):
    if asset.get("name") == name:
        print(asset["browser_download_url"])
        break
' "${archive_name}.sha256" "${release_json}"
  )"
  [[ -n "${asset_url}" && -n "${checksum_asset_url}" ]] || return 1
  curl --retry 3 --retry-delay 2 --fail --silent --show-error \
    --location "${asset_url}" --output "${archive}" &&
    curl --retry 3 --retry-delay 2 --fail --silent --show-error \
      --location "${checksum_asset_url}" --output "${archive}.sha256"
  return 0
}

if download_package; then
  echo "Downloaded Tailscale from the official package endpoint."
elif download_github_asset; then
  echo "Downloaded an official GitHub release asset after the package endpoint failed."
else
  echo "Unable to download Tailscale ${TAILSCALE_VERSION}." >&2
  echo "The official package endpoint failed and this GitHub release has no Linux binary asset." >&2
  exit 1
fi

expected="$(tr -d '[:space:]' < "${archive}.sha256")"
if command -v sha256sum >/dev/null 2>&1; then
  actual="$(sha256sum "${archive}" | awk '{print $1}')"
else
  actual="$(shasum -a 256 "${archive}" | awk '{print $1}')"
fi
if [[ "${actual}" != "${expected}" ]]; then
  echo "Tailscale package checksum verification failed." >&2
  exit 1
fi

tar -xzf "${archive}" -C "${work_dir}"
binary_dir="${work_dir}/tailscale_${TAILSCALE_VERSION}_${archive_arch}"
[[ -x "${binary_dir}/tailscale" && -x "${binary_dir}/tailscaled" ]] || {
  echo "Tailscale archive did not contain the expected binaries." >&2
  exit 1
}

install -d "${INSTALL_DIR}"
install -m 0755 "${binary_dir}/tailscale" "${INSTALL_DIR}/tailscale"
install -m 0755 "${binary_dir}/tailscaled" "${INSTALL_DIR}/tailscaled"
"${INSTALL_DIR}/tailscale" version
