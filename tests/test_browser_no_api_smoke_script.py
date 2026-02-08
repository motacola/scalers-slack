from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

import scripts.browser_no_api_smoke as smoke


def _base_config() -> dict:
    return {
        "settings": {"browser_automation": {}},
        "projects": [{"slack_channel_id": "C12345678"}],
    }


@pytest.fixture
def smoke_harness(monkeypatch):
    class FakeSession:
        instances: list["FakeSession"] = []

        def __init__(self, _config):
            self.started = False
            self.closed = False
            self.__class__.instances.append(self)

        def start(self) -> None:
            self.started = True

        def close(self) -> None:
            self.closed = True

    class FakeSlackClient:
        instances: list["FakeSlackClient"] = []

        def __init__(self, _session, _config):
            self.fetch_thread_calls = 0
            self._pagination = {}
            self._slack_api_call = lambda *_args, **_kwargs: {"ok": True}
            self.__class__.instances.append(self)

        def auth_test(self) -> dict:
            return {"ok": True, "team_id": "T123456"}

        def list_conversations_paginated(self, limit: int = 20, max_pages: int = 1) -> list[dict]:
            self._pagination = {"method": "conversations_dom", "pages": max_pages, "messages": min(1, limit)}
            return [{"id": "C12345678", "name": "test-channel"}]

        def fetch_channel_history_paginated(self, _channel_id: str, limit: int = 20, max_pages: int = 1) -> list[dict]:
            self._pagination = {"method": "history_dom", "pages": max_pages, "messages": min(2, limit)}
            return [
                {"ts": "1700000000.000001", "thread_ts": "1700000000.000001", "text": "root"},
                {"ts": "1700000000.000002", "thread_ts": "1700000000.000001", "text": "reply"},
            ][:limit]

        def fetch_thread_replies_paginated(
            self,
            _channel_id: str,
            thread_ts: str,
            limit: int = 30,
            max_pages: int = 1,
        ) -> list[dict]:
            self.fetch_thread_calls += 1
            self._pagination = {"method": "thread_dom", "pages": max_pages, "messages": min(1, limit)}
            return [{"ts": "1700000000.000002", "thread_ts": thread_ts, "text": "reply"}]

        def get_pagination_stats(self) -> dict:
            return dict(self._pagination)

    class FakeNotionClient:
        instances: list["FakeNotionClient"] = []

        def __init__(self, _session, _config):
            self.check_calls = 0
            self.last_checked_page = ""
            self.__class__.instances.append(self)

        def check_page_access(self, page_id: str) -> bool:
            self.check_calls += 1
            self.last_checked_page = page_id
            return True

    def fake_browser_config(_settings: dict):
        return SimpleNamespace(
            enabled=False,
            interactive_login_timeout_ms=120000,
            timeout_ms=30000,
            smart_wait_timeout_ms=15000,
            smart_wait_stability_ms=600,
            max_retries=3,
            notion_base_url="https://www.notion.so",
        )

    monkeypatch.setattr(smoke, "BrowserSession", FakeSession)
    monkeypatch.setattr(smoke, "SlackBrowserClient", FakeSlackClient)
    monkeypatch.setattr(smoke, "NotionBrowserClient", FakeNotionClient)
    monkeypatch.setattr(smoke, "_build_browser_config", fake_browser_config)
    monkeypatch.setattr(smoke, "load_config", lambda _path: _base_config())
    return FakeSession, FakeSlackClient, FakeNotionClient


def test_smoke_json_includes_elapsed_fields(smoke_harness, monkeypatch, capsys):
    fake_sessions, _, _ = smoke_harness
    monkeypatch.setattr(
        sys,
        "argv",
        ["browser_no_api_smoke.py", "--json", "--force-dom", "--skip-thread", "--skip-notion", "--no-metrics"],
    )

    exit_code = smoke.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert isinstance(payload["elapsed_ms"], int)
    assert payload["elapsed_ms"] >= 0
    assert payload["checks"]
    assert all(isinstance(item.get("elapsed_ms"), int) for item in payload["checks"])
    assert fake_sessions.instances and fake_sessions.instances[-1].closed is True


def test_smoke_json_writes_metrics_file(smoke_harness, monkeypatch, capsys, tmp_path):
    metrics_path = tmp_path / "smoke_metrics.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "browser_no_api_smoke.py",
            "--json",
            "--force-dom",
            "--skip-thread",
            "--skip-notion",
            "--metrics-path",
            str(metrics_path),
        ],
    )

    exit_code = smoke.main()
    payload = json.loads(capsys.readouterr().out)
    lines = metrics_path.read_text(encoding="utf-8").strip().splitlines()
    metrics_record = json.loads(lines[-1])

    assert exit_code == 0
    assert payload["metrics_path"] == str(metrics_path)
    assert metrics_record["ok"] is True
    assert isinstance(metrics_record["elapsed_ms"], int)
    assert metrics_record["checks"]


def test_smoke_without_notion_page_checks_base_url(smoke_harness, monkeypatch, capsys):
    _, _, fake_notion = smoke_harness
    monkeypatch.setattr(sys, "argv", ["browser_no_api_smoke.py", "--json", "--skip-thread", "--no-metrics"])

    exit_code = smoke.main()
    payload = json.loads(capsys.readouterr().out)
    notion_check = next(item for item in payload["checks"] if item["name"] == "Notion page access")

    assert exit_code == 0
    assert notion_check["detail"] == "base=https://www.notion.so"
    assert fake_notion.instances and fake_notion.instances[-1].check_calls == 1
    assert fake_notion.instances[-1].last_checked_page == "https://www.notion.so"


def test_smoke_force_dom_uses_history_derived_thread_check(smoke_harness, monkeypatch, capsys):
    _, fake_slack, _ = smoke_harness
    monkeypatch.setattr(
        sys,
        "argv",
        ["browser_no_api_smoke.py", "--json", "--force-dom", "--skip-notion", "--no-metrics"],
    )

    exit_code = smoke.main()
    payload = json.loads(capsys.readouterr().out)
    thread_check = next(item for item in payload["checks"] if item["name"] == "Slack thread replies")

    assert exit_code == 0
    assert payload["ok"] is True
    assert "(history-derived)" in thread_check["detail"]
    assert fake_slack.instances and fake_slack.instances[-1].fetch_thread_calls == 0


def test_smoke_force_dom_strict_thread_uses_thread_fetch(smoke_harness, monkeypatch, capsys):
    _, fake_slack, _ = smoke_harness
    monkeypatch.setattr(
        sys,
        "argv",
        ["browser_no_api_smoke.py", "--json", "--force-dom", "--strict-thread", "--skip-notion", "--no-metrics"],
    )

    exit_code = smoke.main()
    payload = json.loads(capsys.readouterr().out)
    thread_check = next(item for item in payload["checks"] if item["name"] == "Slack thread replies")

    assert exit_code == 0
    assert payload["ok"] is True
    assert "(history-derived)" not in thread_check["detail"]
    assert fake_slack.instances and fake_slack.instances[-1].fetch_thread_calls == 1
