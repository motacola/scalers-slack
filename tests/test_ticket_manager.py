import unittest

from src.ticket_manager import TicketManager


class DummyNotion:
    def append_audit_note(self, page_id: str, text: str) -> str:
        return page_id


class TicketManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = TicketManager(DummyNotion())

    def test_normalize_page_id_from_url(self):
        url = "https://www.notion.so/Example-Page-01234567-89ab-cdef-0123-456789abcdef"
        self.assertEqual(self.manager._normalize_page_id(url), "0123456789abcdef0123456789abcdef")

    def test_normalize_page_id_raw(self):
        raw = "0123456789abcdef0123456789abcdef"
        self.assertEqual(self.manager._normalize_page_id(raw), raw)

    def test_normalize_page_id_invalid(self):
        bad = "https://www.notion.so/Example-Page-invalid"
        self.assertIsNone(self.manager._normalize_page_id(bad))


if __name__ == "__main__":
    unittest.main()
