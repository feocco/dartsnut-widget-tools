import json
import tempfile
import unittest
from pathlib import Path

from tools.dartsnut.cli import parse_args
from tools.dartsnut.manifest import ManifestError, load_manifest
from tools.dartsnut.pages import PageConflictError, upsert_widget_page


class ManifestTests(unittest.TestCase):
    def make_app(self, root: Path) -> Path:
        app = root / "sample_widget_128_128"
        app.mkdir()
        (app / "conf.json").write_text(
            json.dumps(
                {
                    "id": app.name,
                    "type": "widget",
                    "name": "Sample",
                    "version": "1.0.0",
                    "size": [128, 128],
                    "fields": [],
                    "preview": [],
                }
            ),
            encoding="utf-8",
        )
        (app / "main.py").write_text("print('ok')\n", encoding="utf-8")
        (app / "pyproject.toml").write_text(
            """
[project]
name = "sample-widget-128-128"
version = "1.0.0"
dependencies = ["pydartsnut==1.2.1"]

[tool.dartsnut]
include = ["conf.json", "main.py", "pyproject.toml"]
""".strip(),
            encoding="utf-8",
        )
        return app

    def test_manifest_lists_only_declared_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(Path(tmp))
            (app / ".env.local").write_text("SECRET=value\n", encoding="utf-8")
            manifest = load_manifest(app)

        self.assertEqual(
            [str(file.relative_path) for file in manifest.files],
            ["conf.json", "main.py", "pyproject.toml"],
        )

    def test_manifest_rejects_forbidden_declared_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(Path(tmp))
            (app / ".env").write_text("SECRET=value\n", encoding="utf-8")
            project = app / "pyproject.toml"
            project.write_text(
                project.read_text(encoding="utf-8").replace(
                    '"pyproject.toml"]',
                    '"pyproject.toml", ".env"]',
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ManifestError, "forbidden"):
                load_manifest(app)

    def test_manifest_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(Path(tmp))
            (app / "linked.py").symlink_to(app / "main.py")
            project = app / "pyproject.toml"
            project.write_text(
                project.read_text(encoding="utf-8").replace(
                    '"pyproject.toml"]',
                    '"pyproject.toml", "linked.py"]',
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ManifestError, "forbidden"):
                load_manifest(app)

    def test_host_is_required(self):
        with self.assertRaises(SystemExit):
            parse_args(["plan", "--app", "widgets/sample"])


class PageTests(unittest.TestCase):
    def test_title_collision_is_rejected(self):
        config = {
            "pages": [
                {
                    "uuid": "foreign",
                    "title": "Sample",
                    "widgets": [{"id": "other"}],
                }
            ]
        }

        with self.assertRaisesRegex(PageConflictError, "already owned"):
            upsert_widget_page(config, "sample_widget", "Sample")


if __name__ == "__main__":
    unittest.main()
