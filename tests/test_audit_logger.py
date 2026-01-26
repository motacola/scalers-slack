import os
import tempfile
import unittest

from src.audit_logger import AuditLogger


class AuditLoggerRunIdTests(unittest.TestCase):
    def test_run_id_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_path = os.path.join(tmpdir, "audit.db")
            jsonl_path = os.path.join(tmpdir, "audit.jsonl")
            logger = AuditLogger(
                enabled=True,
                storage_dir=tmpdir,
                sqlite_path=sqlite_path,
                jsonl_path=jsonl_path,
            )
            run_id = "run-123"
            self.assertFalse(logger.has_run_id(run_id))
            logger.record_run_id(run_id, "demo", status="notion_written")
            self.assertTrue(logger.has_run_id(run_id))


if __name__ == "__main__":
    unittest.main()
