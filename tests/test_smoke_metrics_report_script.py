from __future__ import annotations

import json
import sys

import scripts.smoke_metrics_report as report


def _metric(ts_epoch: float, ok: bool, elapsed_ms: int, checks: list[dict]) -> dict:
    return {
        "ts_epoch": ts_epoch,
        "ok": ok,
        "elapsed_ms": elapsed_ms,
        "checks": checks,
    }


def _check(name: str, ok: bool, elapsed_ms: int, detail: str = "") -> dict:
    return {"name": name, "ok": ok, "elapsed_ms": elapsed_ms, "detail": detail}


def test_build_summary_computes_overall_and_check_percentiles():
    metrics = [
        _metric(1000, True, 1000, [_check("Slack history", True, 500)]),
        _metric(1010, True, 2000, [_check("Slack history", True, 700)]),
        _metric(1020, False, 3000, [_check("Slack history", False, 900)]),
        _metric(1030, True, 4000, [_check("Slack history", True, 1100)]),
    ]

    summary = report.build_summary(metrics, "output/smoke/browser_no_api_metrics.jsonl", limit=200, since_hours=None)

    assert summary["overall"]["runs"] == 4
    assert summary["overall"]["failures"] == 1
    assert summary["overall"]["failure_rate_pct"] == 25.0
    assert summary["overall"]["elapsed_ms"]["p50"] == 2500
    assert summary["overall"]["elapsed_ms"]["p95"] == 3850

    check_row = summary["checks"][0]
    assert check_row["name"] == "Slack history"
    assert check_row["runs"] == 4
    assert check_row["failures"] == 1
    assert check_row["failure_rate_pct"] == 25.0
    assert check_row["p50_ms"] == 800
    assert check_row["p95_ms"] == 1070


def test_build_summary_detects_latency_spike_regression():
    metrics = [
        _metric(2000, True, 1500, [_check("Slack history", True, 1000)]),
        _metric(2010, True, 1500, [_check("Slack history", True, 1050)]),
        _metric(2020, True, 1500, [_check("Slack history", True, 1100)]),
        _metric(2030, True, 1500, [_check("Slack history", True, 1000)]),
        _metric(2040, True, 1500, [_check("Slack history", True, 1200)]),
        _metric(2050, True, 2600, [_check("Slack history", True, 2500)]),
    ]

    summary = report.build_summary(metrics, "metrics.jsonl", limit=200, since_hours=None)
    regression = summary["last_regression"]

    assert regression is not None
    assert regression["kind"] == "latency_spike"
    assert regression["check_name"] == "Slack history"
    assert regression["observed_ms"] == 2500
    assert regression["baseline_p95_ms"] > 0


def test_build_summary_detects_new_failure_regression():
    metrics = [
        _metric(3000, True, 1000, [_check("Slack auth", True, 300)]),
        _metric(3010, True, 1000, [_check("Slack auth", True, 320)]),
        _metric(3020, True, 1000, [_check("Slack auth", True, 280)]),
        _metric(3030, False, 1000, [_check("Slack auth", False, 350, "not_authed")]),
    ]

    summary = report.build_summary(metrics, "metrics.jsonl", limit=200, since_hours=None)
    regression = summary["last_regression"]

    assert regression is not None
    assert regression["kind"] == "new_failure"
    assert regression["check_name"] == "Slack auth"
    assert regression["detail"] == "not_authed"


def test_filter_metrics_applies_since_and_limit():
    metrics = [
        _metric(1000, True, 1000, []),
        _metric(2000, True, 1000, []),
        _metric(3000, True, 1000, []),
        _metric(4000, True, 1000, []),
    ]

    filtered = report._filter_metrics(metrics, limit=2, since_hours=1, now_epoch=5000)

    assert [item["ts_epoch"] for item in filtered] == [3000, 4000]


def test_main_json_output_from_file(tmp_path, monkeypatch, capsys):
    metrics_path = tmp_path / "browser_no_api_metrics.jsonl"
    rows = [
        _metric(5000, True, 1000, [_check("Slack auth", True, 200)]),
        _metric(5010, True, 1200, [_check("Slack auth", True, 220)]),
    ]
    metrics_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["smoke_metrics_report.py", "--metrics-path", str(metrics_path), "--json", "--limit", "10"],
    )

    exit_code = report.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["source_path"] == str(metrics_path)
    assert payload["overall"]["runs"] == 2
    assert len(payload["checks"]) == 1
    assert payload["checks"][0]["name"] == "Slack auth"
