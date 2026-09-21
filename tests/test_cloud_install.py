import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = (ROOT / ".cursor" / "cloud" / "install.sh").read_text(encoding="utf-8")


class CloudInstallTests(unittest.TestCase):
    def test_apt_update_only_when_packages_missing(self):
        update_at = INSTALL.index("sudo apt-get update")
        self.assertIn("package_installed", INSTALL)
        self.assertLess(INSTALL.index("install_apt_packages"), update_at)
        self.assertNotIn("deb.debian.org", INSTALL)

    def test_tailscale_uses_static_tarball(self):
        self.assertIn("pkgs.tailscale.com/stable/tailscale_latest_", INSTALL)
        self.assertNotIn("tailscale-archive-keyring.gpg", INSTALL)
        self.assertNotIn("apt-get install -y tailscale", INSTALL)

    def test_install_stays_noninteractive_and_terminates(self):
        self.assertIn("DEBIAN_FRONTEND=noninteractive", INSTALL)
        self.assertIn('echo "cloud install complete"', INSTALL)
        self.assertNotIn("pnpm run dev", INSTALL)
        self.assertNotIn("tailscale up", INSTALL)


if __name__ == "__main__":
    unittest.main()
