import unittest
from unittest import mock

import requests

from src.slack_client import SlackClient
from src.notion_client import NotionClient


class FakeResponse:
    def __init__(self, status_code, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


class RetryTests(unittest.TestCase):
    def test_slack_retries_on_429(self):
        responses = [
            FakeResponse(429, {"ok": False, "error": "ratelimited"}, headers={"Retry-After": "0"}),
            FakeResponse(200, {"ok": True}),
        ]

        def fake_request(*args, **kwargs):
            return responses.pop(0)

        with mock.patch("requests.request", side_effect=fake_request) as req_mock, mock.patch("time.sleep"):
            client = SlackClient(
                token="x",
                retry_config={"max_attempts": 2, "backoff_base": 0, "backoff_max": 0, "jitter": 0},
            )
            data = client._request("GET", "test")

        self.assertEqual(data.get("ok"), True)
        self.assertEqual(req_mock.call_count, 2)

    def test_notion_retries_on_429(self):
        responses = [
            FakeResponse(429, {"object": "error"}, headers={"Retry-After": "0"}),
            FakeResponse(200, {"object": "page"}),
        ]

        def fake_request(*args, **kwargs):
            return responses.pop(0)

        with mock.patch("requests.request", side_effect=fake_request) as req_mock, mock.patch("time.sleep"):
            client = NotionClient(
                token="x",
                retry_config={"max_attempts": 2, "backoff_base": 0, "backoff_max": 0, "jitter": 0},
            )
            data = client._request("GET", "pages/abc", idempotent=True)

        self.assertEqual(data.get("object"), "page")
        self.assertEqual(req_mock.call_count, 2)

    def test_notion_network_error_no_retry_for_non_idempotent(self):
        def fake_request(*args, **kwargs):
            raise requests.exceptions.ConnectionError("boom")

        with mock.patch("requests.request", side_effect=fake_request):
            client = NotionClient(
                token="x",
                retry_config={"max_attempts": 2, "retry_non_idempotent": False},
            )
            with self.assertRaises(RuntimeError):
                client._request("PATCH", "blocks/abc/children", json_body={}, idempotent=False)


if __name__ == "__main__":
    unittest.main()
