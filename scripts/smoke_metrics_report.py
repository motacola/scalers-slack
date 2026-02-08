#!/usr/bin/env python3
"""Summarize browser no-API smoke metrics history."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    interpolated = ordered[lower] + (ordered[upper] - ordered[lower]) * weight
    return int(round(interpolated))


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _load_metrics(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except Exception:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def _filter_metrics(
    metrics: list[dict[str, Any]],
    limit: int | None = None,
    since_hours: float | None = None,
    now_epoch: float | None = None,
) -> list[dict[str, Any]]:
    filtered = list(metrics)
    if since_hours and since_hours > 0:
        reference_epoch = now_epoch if now_epoch is not None else datetime.now(timezone.utc).timestamp()
        min_ts = reference_epoch - (since_hours * 3600.0)
        filtered = [item for item in filtered if _to_float(item.get("ts_epoch"), -1.0) >= min_ts]
    if limit and limit > 0 and len(filtered) > limit:
        filtered = filtered[-limit:]
    return filtered


def _detect_last_regression(events_by_check: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    regressions: list[dict[str, Any]] = []

    for check_name, events in events_by_check.items():
        ordered_events = sorted(events, key=lambda item: _to_float(item.get("ts_epoch"), 0.0))
        for idx in range(1, len(ordered_events)):
            current = ordered_events[idx]
            prior = ordered_events[:idx]
            prior_elapsed = [_to_int(event.get("elapsed_ms"), 0) for event in prior]
            prior_latency_samples = [value for value in prior_elapsed if value > 0]
            prior_failures = sum(1 for event in prior if not bool(event.get("ok")))
            prior_failure_rate = (prior_failures / len(prior)) if prior else 0.0

            current_elapsed = _to_int(current.get("elapsed_ms"), 0)
            current_ok = bool(current.get("ok"))
            ts_epoch = _to_float(current.get("ts_epoch"), 0.0)

            if not current_ok and prior_failure_rate <= 0.2:
                regressions.append(
                    {
                        "check_name": check_name,
                        "kind": "new_failure",
                        "ts_epoch": ts_epoch,
                        "ts_utc": datetime.fromtimestamp(ts_epoch, tz=timezone.utc).isoformat() if ts_epoch else "",
                        "observed_ms": current_elapsed,
                        "baseline_p95_ms": _percentile(prior_latency_samples, 95) if prior_latency_samples else 0,
                        "detail": str(current.get("detail") or ""),
                    }
                )

            if current_elapsed <= 0 or len(prior_latency_samples) < 5:
                continue
            baseline_p95 = _percentile(prior_latency_samples, 95)
            if baseline_p95 < 200:
                continue
            threshold = max(int(baseline_p95 * 1.25), baseline_p95 + 500)
            if current_elapsed > threshold:
                regressions.append(
                    {
                        "check_name": check_name,
                        "kind": "latency_spike",
                        "ts_epoch": ts_epoch,
                        "ts_utc": datetime.fromtimestamp(ts_epoch, tz=timezone.utc).isoformat() if ts_epoch else "",
                        "observed_ms": current_elapsed,
                        "baseline_p95_ms": baseline_p95,
                        "threshold_ms": threshold,
                        "detail": str(current.get("detail") or ""),
                    }
                )

    if not regressions:
        return None
    return max(regressions, key=lambda item: _to_float(item.get("ts_epoch"), 0.0))


def build_summary(
    metrics: list[dict[str, Any]],
    source_path: str,
    limit: int | None,
    since_hours: float | None,
) -> dict[str, Any]:
    runs = len(metrics)
    failures = sum(1 for metric in metrics if not bool(metric.get("ok")))
    elapsed_samples = [_to_int(metric.get("elapsed_ms"), 0) for metric in metrics]

    check_samples: dict[str, list[int]] = {}
    check_failures: dict[str, int] = {}
    check_latest: dict[str, dict[str, Any]] = {}
    check_events: dict[str, list[dict[str, Any]]] = {}

    for metric in metrics:
        ts_epoch = _to_float(metric.get("ts_epoch"), 0.0)
        checks = metric.get("checks", [])
        if not isinstance(checks, list):
            continue
        for raw_check in checks:
            if not isinstance(raw_check, dict):
                continue
            name = str(raw_check.get("name") or "unknown")
            ok = bool(raw_check.get("ok"))
            elapsed = _to_int(raw_check.get("elapsed_ms"), 0)
            detail = str(raw_check.get("detail") or "")

            check_samples.setdefault(name, []).append(elapsed)
            check_failures[name] = check_failures.get(name, 0) + (0 if ok else 1)
            check_events.setdefault(name, []).append(
                {"ts_epoch": ts_epoch, "ok": ok, "elapsed_ms": elapsed, "detail": detail}
            )

            previous = check_latest.get(name)
            if previous is None or ts_epoch >= _to_float(previous.get("ts_epoch"), 0.0):
                check_latest[name] = {
                    "ts_epoch": ts_epoch,
                    "ok": ok,
                    "elapsed_ms": elapsed,
                    "detail": detail,
                }

    check_rows: list[dict[str, Any]] = []
    for name, samples in check_samples.items():
        latest = check_latest.get(name, {})
        run_count = len(samples)
        failure_count = check_failures.get(name, 0)
        check_rows.append(
            {
                "name": name,
                "runs": run_count,
                "failures": failure_count,
                "failure_rate_pct": round((failure_count / run_count) * 100.0, 2) if run_count else 0.0,
                "p50_ms": _percentile(samples, 50),
                "p95_ms": _percentile(samples, 95),
                "latest_ms": _to_int(latest.get("elapsed_ms"), 0),
                "latest_ok": bool(latest.get("ok")),
                "latest_detail": str(latest.get("detail") or ""),
                "latest_ts_epoch": _to_float(latest.get("ts_epoch"), 0.0),
            }
        )

    check_rows.sort(key=lambda row: (-row["p95_ms"], row["name"]))
    last_regression = _detect_last_regression(check_events)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_path": source_path,
        "filters": {"limit": limit, "since_hours": since_hours},
        "overall": {
            "runs": runs,
            "failures": failures,
            "failure_rate_pct": round((failures / runs) * 100.0, 2) if runs else 0.0,
            "elapsed_ms": {
                "min": min(elapsed_samples) if elapsed_samples else 0,
                "max": max(elapsed_samples) if elapsed_samples else 0,
                "p50": _percentile(elapsed_samples, 50),
                "p95": _percentile(elapsed_samples, 95),
            },
        },
        "checks": check_rows,
        "last_regression": last_regression,
    }


def _render_text(summary: dict[str, Any]) -> str:
    overall = summary.get("overall", {})
    elapsed = overall.get("elapsed_ms", {})
    lines: list[str] = []
    lines.append(f"Smoke Metrics Report: {summary.get('source_path')}")
    lines.append(
        "Overall: "
        f"runs={overall.get('runs', 0)} "
        f"failures={overall.get('failures', 0)} "
        f"failure_rate={overall.get('failure_rate_pct', 0.0)}% "
        f"p50={elapsed.get('p50', 0)}ms "
        f"p95={elapsed.get('p95', 0)}ms"
    )

    lines.append("")
    lines.append("Per-check metrics:")
    checks = summary.get("checks", [])
    if not checks:
        lines.append("- No check data found.")
    else:
        for check in checks:
            lines.append(
                "- "
                f"{check.get('name')}: runs={check.get('runs')} "
                f"fail_rate={check.get('failure_rate_pct')}% "
                f"p50={check.get('p50_ms')}ms "
                f"p95={check.get('p95_ms')}ms "
                f"latest={check.get('latest_ms')}ms "
                f"latest_ok={check.get('latest_ok')}"
            )

    lines.append("")
    regression = summary.get("last_regression")
    if isinstance(regression, dict):
        lines.append(
            "Last regression: "
            f"check={regression.get('check_name')} "
            f"kind={regression.get('kind')} "
            f"observed={regression.get('observed_ms')}ms "
            f"baseline_p95={regression.get('baseline_p95_ms')}ms "
            f"at={regression.get('ts_utc')}"
        )
    else:
        lines.append("Last regression: none detected")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize browser no-API smoke metrics history.")
    parser.add_argument(
        "--metrics-path",
        default="output/smoke/browser_no_api_metrics.jsonl",
        help="Path to metrics JSONL produced by browser_no_api_smoke.py",
    )
    parser.add_argument("--limit", type=int, default=200, help="Only analyze the most recent N runs")
    parser.add_argument("--since-hours", type=float, help="Only include runs newer than N hours")
    parser.add_argument("--json", action="store_true", help="Print summary as JSON")
    args = parser.parse_args()

    metrics_path = Path(args.metrics_path)
    raw_metrics = _load_metrics(metrics_path)
    filtered = _filter_metrics(raw_metrics, limit=args.limit, since_hours=args.since_hours)
    summary = build_summary(filtered, str(metrics_path), args.limit, args.since_hours)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(_render_text(summary))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
