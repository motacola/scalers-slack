import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.browser import BrowserAutomationConfig, BrowserSession, SlackBrowserClient, NotionBrowserClient
from src.config_loader import load_config

logger = logging.getLogger(__name__)

def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    parser = argparse.ArgumentParser(description="Verify and Maintain Browser Sessions")
    parser.add_argument("--config", default="config/config.json", help="Path to config.json")
    parser.add_argument("--slack", action="store_true", help="Check Slack login")
    parser.add_argument("--notion", action="store_true", help="Check Notion login")
    parser.add_argument("--google", action="store_true", help="Check Google login")
    parser.add_argument("--interactive", action="store_true", help="Open browser for manual login if needed")
    parser.add_argument(
        "--refresh-every-hours",
        type=float,
        default=0.0,
        help="Refresh browser storage state every N hours (requires --interactive)",
    )
    args = parser.parse_args()

    config_data = load_config(args.config)
    settings = config_data.get("settings", {}).get("browser_automation", {})

    if args.refresh_every_hours and not args.interactive:
        logger.warning("--refresh-every-hours requires --interactive; refresh loop will be skipped.")
    
    # Force interactive mode and non-headless if requested
    if args.interactive:
        settings["headless"] = False
        settings["interactive_login"] = True

    browser_config = BrowserAutomationConfig(**{
        k: v for k, v in settings.items() 
        if k in BrowserAutomationConfig.__dataclass_fields__
    })

    session = BrowserSession(browser_config)
    try:
        session.start()
        
        if args.slack or (not args.slack and not args.notion and not args.google):
            logger.info("Checking Slack session...")
            slack = SlackBrowserClient(session, browser_config)
            # Try to go to slack home
            page = session.new_page(slack._slack_client_home())
            try:
                slack._wait_until_ready(page)
                logger.info("✅ Slack Session: LOGGED IN")
            except Exception as e:
                logger.warning(f"❌ Slack Session: NOT LOGGED IN ({e})")
            finally:
                page.close()

        if args.notion or (not args.slack and not args.notion and not args.google):
            logger.info("Checking Notion session...")
            notion = NotionBrowserClient(session, browser_config)
            page = session.new_page(browser_config.notion_base_url)
            try:
                notion._wait_until_ready(page)
                logger.info("✅ Notion Session: LOGGED IN")
            except Exception as e:
                logger.warning(f"❌ Notion Session: NOT LOGGED IN ({e})")
            finally:
                page.close()


        if args.google or (not args.slack and not args.notion and not args.google):
            logger.info("Checking Google session...")
            # We assume if we can reach myaccount.google.com and see 'Welcome', we might be logged in. 
            # Or we simply open it for the user to verify.
            page = session.new_page("https://myaccount.google.com/")
            try:
                # Simple heuristic: wait for the page to load. 
                # If redirection to signin happens, user needs to login.
                page.wait_for_load_state("networkidle")
                if "signin" in page.url or " ServiceLogin" in page.content():
                     logger.warning("❌ Google Session: NOT LOGGED IN (Redirected to Sign-in)")
                else:
                     logger.info("✅ Google Session: Likely LOGGED IN (No redirect)")
            except Exception as e:
                logger.warning(f"❌ Google Session: Error ({e})")
            finally:
                if not args.interactive:
                    page.close()

        if args.interactive:
            logger.info("Browser is open for manual interaction. Press Ctrl+C when done.")
            try:
                refresh_interval = max(0.0, args.refresh_every_hours or 0.0) * 3600
                next_refresh = time.time() + refresh_interval if refresh_interval > 0 else None
                while True:
                    if next_refresh and time.time() >= next_refresh:
                        logger.info("Refreshing browser storage state...")
                        if args.slack or (not args.slack and not args.notion and not args.google):
                            try:
                                slack = SlackBrowserClient(session, browser_config)
                                page = session.new_page(slack._slack_client_home())
                                try:
                                    slack._wait_until_ready(page)
                                finally:
                                    page.close()
                            except Exception as exc:
                                logger.warning(f"Slack refresh failed: {exc}")
                        if args.notion or (not args.slack and not args.notion and not args.google):
                            try:
                                notion = NotionBrowserClient(session, browser_config)
                                page = session.new_page(browser_config.notion_base_url)
                                try:
                                    notion._wait_until_ready(page)
                                finally:
                                    page.close()
                            except Exception as exc:
                                logger.warning(f"Notion refresh failed: {exc}")
                        session.save_storage_state()
                        logger.info("Storage state updated.")
                        next_refresh = time.time() + refresh_interval
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Closing...")
        
        session.save_storage_state()
        logger.info("Storage state updated.")

    finally:
        session.close()

if __name__ == "__main__":
    main()
