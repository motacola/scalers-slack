import json
import os
import tempfile
import unittest

from src.engine import ScalersSlackEngine


class StubAuditLogger:
    def __init__(self):
        self.records = []
        self.run_ids = set()

    def log(self, action, status, details=None, error=None):
        self.records.append({"action": action, "status": status, "details": details, "error": error})

    def log_failure(self, action, details=None, error=None):
        self.log(action, "failed", details=details, error=error)

    def log_review(self, action, details=None, error=None):
        self.log(action, "review", details=details, error=error)

    def has_run_id(self, run_id):
        return run_id in self.run_ids

    def record_run_id(self, run_id, project, status="completed", details=None):
        self.run_ids.add(run_id)
        self.log("run_registry", status, details={"run_id": run_id, "project": project})


class StubThreadExtractor:
    def __init__(self, threads):
        self.threads = threads
        self.called = False

    def fetch_channel_threads(self, channel_id, oldest=None, latest=None, limit=200, max_pages=10):
        self.called = True
        return self.threads

    def search_threads(self, query, channel_id=None, limit=100, max_pages=5):
        self.called = True
        return self.threads


class EngineDryRunTests(unittest.TestCase):
    def test_run_sync_dry_run(self):
        config = {
            "settings": {
                "slack": {"token_env": "SLACK_BOT_TOKEN", "base_url": "https://slack.com/api", "default_channel_id": ""},
                "notion": {"token_env": "NOTION_API_KEY", "version": "2022-06-28"},
                "audit": {"enabled": False},
            },
            "projects": [
                {
                    "name": "demo",
                    "slack_channel_id": "C123",
                    "notion_audit_page_id": "",
                    "notion_last_synced_page_id": "",
                }
            ],
        }

        threads = [
            {
                "thread_ts": "1704067200.000000",
                "channel_id": "C123",
                "message_count": 1,
                "text_preview": "hello",
                "created_at": "2024-01-01T00:00:00+00:00",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w") as handle:
                json.dump(config, handle)

            audit_logger = StubAuditLogger()
            extractor = StubThreadExtractor(threads)

            engine = ScalersSlackEngine(
                config_path=config_path,
                audit_logger=audit_logger,
                thread_extractor=extractor,
            )

            engine.run_sync(project_name="demo", since="2024-01-01T00:00:00Z", dry_run=True)

            self.assertTrue(extractor.called)
            statuses = [record["status"] for record in audit_logger.records]
            self.assertIn("dry_run", statuses)


if __name__ == "__main__":
    unittest.main()
