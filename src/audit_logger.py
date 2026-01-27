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

        self.ensure_initialized()

    def ensure_initialized(self) -> None:
        if not self.enabled:
            return

        if self.storage_dir:
            os.makedirs(self.storage_dir, exist_ok=True)

        if self._db_initialized:
            return

        try:
            self._init_db()
        except sqlite3.Error:
            self._db_initialized = False

    def _init_db(self) -> None:
        directory = os.path.dirname(self.sqlite_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_registry (
                    run_id TEXT PRIMARY KEY,
                    project TEXT,
                    created_at TEXT NOT NULL,
                    status TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    real_name TEXT,
                    display_name TEXT,
                    updated_at TEXT NOT NULL
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

    def has_run_id(self, run_id: str) -> bool:
        if not self.enabled:
            return False

        if self._db_initialized:
            try:
                with sqlite3.connect(self.sqlite_path) as connection:
                    row = connection.execute(
                        "SELECT 1 FROM run_registry WHERE run_id = ? LIMIT 1", (run_id,)
                    ).fetchone()
                return row is not None
            except sqlite3.Error:
                self._db_initialized = False

        return self._run_id_in_jsonl(run_id)

    def record_run_id(self, run_id: str, project: str, status: str = "completed", details: dict | None = None) -> None:
        if not self.enabled:
            return

        payload = {"run_id": run_id, "project": project, "status": status}
        if details:
            payload.update(details)

        if self._db_initialized:
            try:
                with sqlite3.connect(self.sqlite_path) as connection:
                    connection.execute(
                        "INSERT OR IGNORE INTO run_registry (run_id, project, created_at, status) VALUES (?, ?, ?, ?)",
                        (run_id, project, _utc_now_iso(), status),
                    )
                    connection.commit()
            except sqlite3.Error:
                self._db_initialized = False

        self.log(action="run_registry", status=status, details=payload)

    def _write_jsonl(self, record: dict) -> None:
        directory = os.path.dirname(self.jsonl_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.jsonl_path, "a") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _run_id_in_jsonl(self, run_id: str) -> bool:
        if not os.path.exists(self.jsonl_path):
            return False

        try:
            with open(self.jsonl_path, "r") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("action") != "run_registry":
                        continue
                    details = record.get("details", {})
                    if isinstance(details, dict) and details.get("run_id") == run_id:
                        return True
        except OSError:
            return False

        return False
    def get_user_name(self, user_id: str) -> str | None:
        if not self.enabled or not self._db_initialized:
            return None
        try:
            with sqlite3.connect(self.sqlite_path) as connection:
                row = connection.execute(
                    "SELECT real_name, display_name FROM users WHERE user_id = ? LIMIT 1", (user_id,)
                ).fetchone()
            if row:
                return row[0] or row[1]
        except sqlite3.Error:
            self._db_initialized = False
        return None

    def set_user_name(self, user_id: str, real_name: str, display_name: str) -> None:
        if not self.enabled or not self._db_initialized:
            return
        try:
            with sqlite3.connect(self.sqlite_path) as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO users (user_id, real_name, display_name, updated_at) VALUES (?, ?, ?, ?)",
                    (user_id, real_name, display_name, _utc_now_iso()),
                )
                connection.commit()
        except sqlite3.Error:
            self._db_initialized = False
