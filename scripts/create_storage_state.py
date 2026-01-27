import argparse
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser(description="Create Playwright storage state for Slack + Notion.")
    parser.add_argument("--output", default="browser_storage_state.json", help="Storage state output path")
    parser.add_argument("--headless", action="store_true", help="Run browser headless (not recommended)")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context()
        page = context.new_page()

        print("Opening Slack. Please log in if needed, then leave the tab open.")
        page.goto("https://app.slack.com/client", wait_until="domcontentloaded")
        input("Press Enter after Slack login is complete...")

        print("Opening Notion. Please log in if needed, then leave the tab open.")
        page.goto("https://www.notion.so", wait_until="domcontentloaded")
        input("Press Enter after Notion login is complete...")

        context.storage_state(path=str(output_path))
        browser.close()

    print(f"Storage state saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
