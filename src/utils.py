from datetime import datetime, timezone
import hashlib


def iso_to_unix_ts(iso_value: str) -> str:
    dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    return str(dt.replace(tzinfo=dt.tzinfo or timezone.utc).timestamp())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_run_id(project: str, since: str | None, query: str | None, run_date: str) -> str:
    payload = "|".join([project or "", since or "", query or "", run_date or ""])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
