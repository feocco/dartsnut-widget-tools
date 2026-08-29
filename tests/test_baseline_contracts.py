import unittest

from scripts.upload_app import DartsnutClient, upsert_widget_page


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    def send_json(self, payload):
        self.sent.append(payload)

    def recv_json(self):
        return {"req_id": "1", "content": "ok"}


class BaselineUploadContracts(unittest.TestCase):
    def test_client_request_shape(self):
        socket = FakeWebSocket()

        response = DartsnutClient(socket).request("read_json", file_path="conf.json")

        self.assertEqual(
            socket.sent,
            [{"action": "read_json", "req_id": "1", "file_path": "conf.json"}],
        )
        self.assertEqual(response["content"], "ok")

    def test_page_replacement_behavior_is_pinned_before_fix(self):
        existing = {
            "uuid": "configured-page",
            "title": "Configured",
            "duration": "30",
            "combination": "3",
            "enabled": False,
            "widgets": [
                {
                    "id": "codex_status_128_128",
                    "position": [4, 4, 120, 120],
                    "fields": {"ha_url": "configured"},
                },
                {"id": "clock", "position": [0, 0, 20, 20], "fields": {}},
            ],
            "wv": {"layout": "custom"},
            "future": True,
        }

        updated = upsert_widget_page(
            {"pages": [existing]},
            "codex_status_128_128",
            "Configured",
        )

        self.assertEqual(updated["pages"][0]["widgets"][0]["fields"], {})
        self.assertEqual(len(updated["pages"][0]["widgets"]), 1)
        self.assertNotEqual(updated["pages"][0]["uuid"], "configured-page")


if __name__ == "__main__":
    unittest.main()
