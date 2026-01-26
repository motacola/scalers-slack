import os
import requests


class NotionClient:
    def __init__(self, token: str | None = None, version: str = "2022-06-28"):
        self.token = token or os.getenv("NOTION_API_KEY")
        self.version = version
        self.base_url = "https://api.notion.com/v1"

    def _request(self, method: str, path: str, json_body: dict | None = None) -> dict:
        if not self.token:
            raise RuntimeError("NOTION_API_KEY is not set")

        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": self.version,
            "Content-Type": "application/json",
        }
        response = requests.request(method, url, headers=headers, json=json_body, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"Notion API error: {response.status_code} {response.text}")
        return response.json()

    def append_audit_note(self, page_id: str, text: str) -> str:
        payload = {
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"type": "text", "text": {"content": text}}
                        ]
                    },
                }
            ]
        }
        data = self._request("PATCH", f"blocks/{page_id}/children", json_body=payload)
        results = data.get("results", [])
        if not results:
            raise RuntimeError("Notion did not return a block for the audit note")
        return results[0]["id"]

    def get_block(self, block_id: str) -> dict:
        return self._request("GET", f"blocks/{block_id}")

    def update_page_property(self, page_id: str, property_name: str, date_iso: str) -> None:
        payload = {
            "properties": {
                property_name: {"date": {"start": date_iso}}
            }
        }
        self._request("PATCH", f"pages/{page_id}", json_body=payload)

    def get_page(self, page_id: str) -> dict:
        return self._request("GET", f"pages/{page_id}")
