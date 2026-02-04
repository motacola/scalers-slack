import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser(description="Create Playwright storage state for Slack + Notion.")
    parser.add_argument("--output", default="config/browser_storage_state.json", help="Storage state output path")
    parser.add_argument("--headless", action="store_true", help="Run browser headless (not recommended)")
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=900,
        help="Max seconds to wait for manual login before saving storage state",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=5,
        help="Seconds between auth checks",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context()
        page = context.new_page()

        print("Opening Slack. Please log in if needed, then leave the tab open.")
        page.goto("https://app.slack.com/client", wait_until="domcontentloaded")

        deadline = time.time() + args.wait_seconds
        while time.time() < deadline:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                result = page.evaluate(
                    """
                    async () => {
                        try {
                            const res = await fetch('https://slack.com/api/auth.test', { credentials: 'include' });
                            const data = await res.json();
                            return { ok: Boolean(data && data.ok), data };
                        } catch (e) {
                            return { ok: false, error: String(e) };
                        }
                    }
                    """
                )
            except Exception:
                time.sleep(args.poll_seconds)
                continue

            if result.get("ok"):
                print("Slack auth confirmed.")
                break
            time.sleep(args.poll_seconds)
        else:
            print("Slack auth not confirmed before timeout.")

        print("Opening Notion. Please log in if needed, then leave the tab open.")
        page.goto("https://www.notion.so", wait_until="domcontentloaded")

        deadline = time.time() + args.wait_seconds
        while time.time() < deadline:
            cookies = context.cookies("https://www.notion.so")
            if any(cookie.get("name") == "token_v2" for cookie in cookies):
                print("Notion auth confirmed.")
                break
            time.sleep(args.poll_seconds)
        else:
            print("Notion auth not confirmed before timeout.")

        context.storage_state(path=str(output_path))
        browser.close()

    print(f"Storage state saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
