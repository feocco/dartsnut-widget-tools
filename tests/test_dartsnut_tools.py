import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.dartsnut.cli import Command, execute, parse_args
from tools.dartsnut.manifest import ManifestError, load_manifest
from tools.dartsnut.pages import (
    PageConflictError,
    new_widget_page,
    remove_widget_reference,
    upsert_widget_page,
)


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

    def test_manifest_rejects_undeclared_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(Path(tmp))
            (app / "notes.md").write_text("not for the board\n", encoding="utf-8")

            with self.assertRaisesRegex(ManifestError, "omits files"):
                load_manifest(app)

    def test_host_is_required(self):
        with self.assertRaises(SystemExit):
            parse_args(["plan", "--app", "widgets/sample"])

    def test_repository_manifests_load(self):
        root = Path(__file__).resolve().parents[1]

        widget = load_manifest(root / "widgets" / "codex_status_128_128")
        game = load_manifest(root / "games" / "pixeldarts_chess_128_160")
        game_files = [str(file.relative_path) for file in game.files]

        self.assertEqual(widget.kind, "widget")
        self.assertEqual(game.kind, "game")
        self.assertNotIn("chess/__init__.py", game_files)
        self.assertNotIn("chess_game.py", game_files)
        self.assertNotIn("dartboard.py", game_files)
        self.assertNotIn("game_state.py", game_files)
        self.assertNotIn("openings.py", game_files)
        self.assertIn("match.py", game_files)
        self.assertIn("chess_logic/continuation.py", game_files)
        self.assertIn("minigame/target_round.py", game_files)

    def test_widget_reupload_reloads_when_config_is_unchanged(self):
        requests = []

        class FakeWebSocket:
            def __init__(self, *args):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        class FakeClient:
            def __init__(self, websocket):
                pass

            def request(self, operation, **payload):
                requests.append((operation, payload))
                if operation == "read_json":
                    config = {"pages": [new_widget_page("sample_widget_128_128", "Sample")]}
                    content = base64.b64encode(json.dumps(config).encode("utf-8")).decode("ascii")
                    return {"content": content}
                if operation == "list_apps":
                    return {"apps": [{"name": "sample_widget_128_128"}]}
                return {}

        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(Path(tmp))
            command = Command("upload", "board", 9251, "/ws", 10, app, None, False)
            with (
                patch("tools.dartsnut.cli.SimpleWebSocket", FakeWebSocket),
                patch("tools.dartsnut.cli.DartsnutClient", FakeClient),
            ):
                self.assertEqual(execute(command), 0)

        operations = [operation for operation, _ in requests]
        self.assertEqual(operations.count("send_file"), 3)
        self.assertEqual(operations.count("write_json"), 0)
        self.assertEqual(operations.count("reload_conf"), 1)


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

    def test_cleanup_removes_only_requested_widget(self):
        config = {
            "pages": [
                {
                    "uuid": "shared",
                    "title": "Shared",
                    "widgets": [{"id": "stale"}, {"id": "clock"}],
                }
            ]
        }

        updated = remove_widget_reference(
            config,
            "stale",
            remove_empty_page=True,
        )

        self.assertEqual(updated["pages"][0]["widgets"], [{"id": "clock"}])


if __name__ == "__main__":
    unittest.main()
