import json
import os
import sqlite3
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class AuditLogger:
    def __init__(self, enabled: bool, storage_dir: str, sqlite_path: str, jsonl_path: str):
        self.enabled = enabled
        self.storage_dir = storage_dir
        self.sqlite_path = sqlite_path
        self.jsonl_path = jsonl_path
        self._db_initialized = False

        if not self.enabled:
            return

        if self.storage_dir:
            os.makedirs(self.storage_dir, exist_ok=True)

        try:
            self._init_db()
        except sqlite3.Error:
            self._db_initialized = False

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    error TEXT
                )
                """
            )
            connection.commit()
        self._db_initialized = True

    def log(self, action: str, status: str, details: dict | None = None, error: str | None = None) -> None:
        if not self.enabled:
            return

        record = {
            "timestamp": _utc_now_iso(),
            "action": action,
            "status": status,
            "details": details or {},
            "error": error,
        }

        if self._db_initialized:
            try:
                with sqlite3.connect(self.sqlite_path) as connection:
                    connection.execute(
                        "INSERT INTO audit_log (timestamp, action, status, details, error) VALUES (?, ?, ?, ?, ?)",
                        (
                            record["timestamp"],
                            record["action"],
                            record["status"],
                            json.dumps(record["details"], ensure_ascii=True),
                            record["error"],
                        ),
                    )
                    connection.commit()
                return
            except sqlite3.Error:
                self._db_initialized = False

        self._write_jsonl(record)

    def log_review(self, action: str, details: dict | None = None, error: str | None = None) -> None:
        self.log(action=action, status="review", details=details, error=error)

    def log_failure(self, action: str, details: dict | None = None, error: str | None = None) -> None:
        self.log(action=action, status="failed", details=details, error=error)

    def _write_jsonl(self, record: dict) -> None:
        os.makedirs(os.path.dirname(self.jsonl_path), exist_ok=True)
        with open(self.jsonl_path, "a") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
