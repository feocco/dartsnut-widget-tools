import json
import tempfile
import unittest
from pathlib import Path

from scripts.upload_app import (
    build_widget_page,
    iter_app_files,
    load_app_conf,
    remove_widget_page_references,
    upsert_widget_page,
)


class UploadAppTests(unittest.TestCase):
    def test_load_game_conf_requires_128x160_and_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = Path(tmp) / "sample_game"
            game_dir.mkdir()
            (game_dir / "conf.json").write_text(
                json.dumps(
                    {
                        "id": "sample_game",
                        "type": "game",
                        "name": "Sample Game",
                        "author": "Codex",
                        "version": "1.0.0",
                        "description": "Sample game",
                        "size": [128, 160],
                        "fields": [],
                        "preview": ["abc"],
                    }
                ),
                encoding="utf-8",
            )

            conf = load_app_conf(game_dir)

        self.assertEqual(conf["type"], "game")
        self.assertEqual(conf["size"], [128, 160])

    def test_game_conf_rejects_missing_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = Path(tmp) / "sample_game"
            game_dir.mkdir()
            (game_dir / "conf.json").write_text(
                json.dumps(
                    {
                        "id": "sample_game",
                        "type": "game",
                        "name": "Sample Game",
                        "author": "Codex",
                        "version": "1.0.0",
                        "description": "Sample game",
                        "size": [128, 160],
                        "fields": [],
                        "preview": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "preview"):
                load_app_conf(game_dir)

    def test_remove_widget_page_references_does_not_touch_other_pages(self):
        stale = build_widget_page("pixeldarts_chess_128_128", "PixelDarts Chess")
        keep = build_widget_page("codex_status_128_128", "Codex Status")
        config = {"pages": [stale, keep]}

        updated = remove_widget_page_references(config, "pixeldarts_chess_128_128")

        self.assertEqual(updated["pages"], [keep])

    def test_remove_widget_reference_preserves_sibling_widgets(self):
        stale = build_widget_page("pixeldarts_chess_128_128", "PixelDarts Chess")
        stale["widgets"].append(
            {"id": "clock", "position": [0, 0, 10, 10], "fields": {}}
        )

        updated = remove_widget_page_references(
            {"pages": [stale]},
            "pixeldarts_chess_128_128",
        )

        self.assertEqual(updated["pages"][0]["widgets"][0]["id"], "clock")

    def test_game_upload_helpers_do_not_require_widget_page_upsert(self):
        config = {"pages": []}

        updated = upsert_widget_page(config, "codex_status_128_128", "Codex Status")

        self.assertEqual(len(config["pages"]), 0)
        self.assertEqual(len(updated["pages"]), 1)

    def test_iter_app_files_skips_python_cache_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp) / "sample_game"
            cache_dir = app_dir / "__pycache__"
            cache_dir.mkdir(parents=True)
            (app_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (app_dir / "conf.json").write_text("{}", encoding="utf-8")
            (cache_dir / "main.cpython-314.pyc").write_bytes(b"cache")

            files = [rel.as_posix() for _, rel in iter_app_files(app_dir)]

        self.assertEqual(files, ["conf.json", "main.py"])

    def test_iter_app_files_skips_hidden_secrets_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp) / "sample_game"
            app_dir.mkdir()
            (app_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (app_dir / ".env").write_text("SECRET=value\n", encoding="utf-8")
            (app_dir / ".vscode").mkdir()
            (app_dir / ".vscode" / "settings.json").write_text("{}")
            (app_dir / "link.py").symlink_to(app_dir / "main.py")

            files = [rel.as_posix() for _, rel in iter_app_files(app_dir)]

        self.assertEqual(files, ["main.py"])


if __name__ == "__main__":
    unittest.main()
