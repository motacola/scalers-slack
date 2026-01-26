import unittest

from src.slack_client import SlackClient


class StubSlackClient(SlackClient):
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.token = "test"
        self.base_url = "https://example.com"

    def _request(self, method, path, params=None, json_body=None):
        self.requests.append({"method": method, "path": path, "params": params, "json_body": json_body})
        if not self.responses:
            raise AssertionError("No more stub responses available")
        return self.responses.pop(0)


class SlackClientPaginationTests(unittest.TestCase):
    def test_fetch_channel_history_paginated(self):
        responses = [
            {"ok": True, "messages": [{"ts": "1"}], "response_metadata": {"next_cursor": "abc"}},
            {"ok": True, "messages": [{"ts": "2"}], "response_metadata": {"next_cursor": ""}},
        ]
        client = StubSlackClient(responses)

        messages = client.fetch_channel_history_paginated("C123", max_pages=5)

        self.assertEqual([message["ts"] for message in messages], ["1", "2"])
        self.assertEqual(len(client.requests), 2)
        self.assertIn("cursor", client.requests[1]["params"])

    def test_search_messages_paginated(self):
        responses = [
            {
                "ok": True,
                "messages": {"matches": [{"ts": "1"}], "paging": {"page": 1, "pages": 2}},
            },
            {
                "ok": True,
                "messages": {"matches": [{"ts": "2"}], "paging": {"page": 2, "pages": 2}},
            },
        ]
        client = StubSlackClient(responses)

        matches = client.search_messages_paginated("test", count=2, max_pages=5)

        self.assertEqual([match["ts"] for match in matches], ["1", "2"])
        self.assertEqual(len(client.requests), 2)

    def test_search_messages_respects_max_pages(self):
        responses = [
            {
                "ok": True,
                "messages": {"matches": [{"ts": "1"}], "paging": {"page": 1, "pages": 3}},
            },
            {
                "ok": True,
                "messages": {"matches": [{"ts": "2"}], "paging": {"page": 2, "pages": 3}},
            },
        ]
        client = StubSlackClient(responses)

        matches = client.search_messages_paginated("test", count=2, max_pages=1)

        self.assertEqual([match["ts"] for match in matches], ["1"])
        self.assertEqual(len(client.requests), 1)


if __name__ == "__main__":
    unittest.main()
