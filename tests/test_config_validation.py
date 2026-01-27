import unittest

from src.config_validation import validate_config


class ConfigValidationTests(unittest.TestCase):
    def test_duplicate_project_names(self):
        config = {
            "settings": {"features": {}, "audit": {}},
            "projects": [
                {"name": "dup", "slack_channel_id": "C012345678"},
                {"name": "dup", "slack_channel_id": "C012345679"},
            ],
        }
        errors = validate_config(config)
        self.assertTrue(any("project.name must be unique" in err for err in errors))

    def test_missing_notion_ids_when_enabled(self):
        config = {
            "settings": {
                "features": {"enable_notion_audit_note": True, "enable_notion_last_synced": True},
                "audit": {"notion_last_synced_property": "Last Synced"},
            },
            "projects": [
                {"name": "demo", "slack_channel_id": "C012345678"},
            ],
        }
        errors = validate_config(config)
        self.assertTrue(any("missing notion_audit_page_id" in err for err in errors))
        self.assertTrue(any("missing notion_last_synced_page_id" in err for err in errors))

    def test_disable_notion_checks(self):
        config = {
            "settings": {
                "features": {"enable_notion_audit_note": False, "enable_notion_last_synced": False},
                "audit": {},
            },
            "projects": [
                {"name": "demo", "slack_channel_id": "C012345678"},
            ],
        }
        errors = validate_config(config)
        self.assertFalse(any("notion" in err for err in errors))

    def test_notion_page_url_validation(self):
        config = {
            "settings": {
                "features": {"enable_notion_audit_note": False, "enable_notion_last_synced": False},
                "audit": {},
            },
            "projects": [
                {
                    "name": "demo",
                    "slack_channel_id": "C012345678",
                    "notion_page_url": "https://www.notion.so/Example-Page-0123456789abcdef0123456789abcdef",
                },
                {
                    "name": "bad",
                    "slack_channel_id": "C012345679",
                    "notion_page_url": "https://www.notion.so/Example-Page-invalid",
                },
            ],
        }
        errors = validate_config(config)
        self.assertTrue(any("project 'bad' has invalid notion_page_url" in err for err in errors))
        self.assertFalse(any("project 'demo' has invalid notion_page_url" in err for err in errors))


if __name__ == "__main__":
    unittest.main()
