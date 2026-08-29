import json
import tempfile
import unittest
from pathlib import Path

from scripts.upload_widget import (
    build_widget_page,
    iter_widget_files,
    load_widget_conf,
    upsert_widget_page,
)


class UploadWidgetTests(unittest.TestCase):
    def test_load_widget_conf_requires_folder_id_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget_dir = Path(tmp) / "sample_widget"
            widget_dir.mkdir()
            (widget_dir / "conf.json").write_text(
                json.dumps(
                    {
                        "id": "different_id",
                        "type": "widget",
                        "name": "Sample",
                        "author": "Codex",
                        "version": "1.0.0",
                        "description": "Sample widget",
                        "size": [128, 128],
                        "fields": [],
                        "preview": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "must match widget folder name"):
                load_widget_conf(widget_dir)

    def test_upsert_widget_page_replaces_matching_page_and_preserves_others(self):
        config = {
            "user": "",
            "date": "",
            "pages": [
                {
                    "uuid": "existing-1",
                    "title": "Existing Page",
                    "duration": "15",
                    "combination": "0",
                    "enabled": False,
                    "widgets": [],
                    "wv": None,
                },
                build_widget_page("codex_status_128_128", "Codex Status"),
            ],
        }

        updated = upsert_widget_page(config, "codex_status_128_128", "Codex Status")

        self.assertEqual(len(updated["pages"]), 2)
        self.assertEqual(updated["pages"][0], config["pages"][0])
        self.assertEqual(updated["pages"][1]["title"], "Codex Status")
        self.assertTrue(updated["pages"][1]["enabled"])
        self.assertEqual(updated["pages"][1]["widgets"][0]["id"], "codex_status_128_128")
        self.assertEqual(updated["pages"][1]["widgets"][0]["position"], [0, 0, 127, 127])

    def test_upsert_widget_page_preserves_configured_fields_and_page_settings(self):
        configured = build_widget_page("codex_status_128_128", "Codex Status")
        configured["duration"] = "45"
        configured["combination"] = "3"
        configured["enabled"] = False
        configured["wv"] = {"custom": True}
        configured["future"] = "kept"
        configured["widgets"][0]["fields"] = {"ha_url": "configured"}
        configured["widgets"].append(
            {"id": "clock", "position": [1, 1, 10, 10], "fields": {}}
        )

        updated = upsert_widget_page(
            {"pages": [configured]},
            "codex_status_128_128",
            "Codex Status",
        )

        self.assertEqual(updated["pages"], [configured])

    def test_iter_widget_files_skips_python_cache_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget_dir = Path(tmp) / "sample_widget"
            cache_dir = widget_dir / "__pycache__"
            cache_dir.mkdir(parents=True)
            (widget_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (widget_dir / "conf.json").write_text("{}", encoding="utf-8")
            (cache_dir / "main.cpython-314.pyc").write_bytes(b"cache")

            files = [rel.as_posix() for _, rel in iter_widget_files(widget_dir)]

        self.assertEqual(files, ["conf.json", "main.py"])


if __name__ == "__main__":
    unittest.main()
