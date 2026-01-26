from datetime import datetime, timezone


def iso_to_unix_ts(iso_value: str) -> str:
    dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    return str(dt.replace(tzinfo=dt.tzinfo or timezone.utc).timestamp())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
