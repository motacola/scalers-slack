import sys
import time
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.browser import BrowserAutomationConfig, BrowserSession, SlackBrowserClient
from src.config_loader import load_config


def check_channel_history(channel_id="C085B73T2JE"):
    # Load config
    try:
        app_config = load_config("config/config.json")
        settings = app_config.get("settings", {})
        browser_settings = settings.get("browser_automation", {})
    except Exception:
        browser_settings = {}

    config = BrowserAutomationConfig(
        enabled=True,
        storage_state_path="config/browser_storage_state.json",
        headless=True,
        slack_workspace_id=browser_settings.get("slack_workspace_id", ""),
    )

    session = BrowserSession(config)

    try:
        session.start()
        slack_client = SlackBrowserClient(session, config)

        print(f"\n--- Fetching History for Channel {channel_id} ---")
        try:
            # Fetch last 50 messages
            messages = slack_client.fetch_channel_history_paginated(channel_id, limit=50, max_pages=1)

            if not messages:
                print("No messages found or unable to fetch history.")
            else:
                print(f"Fetched {len(messages)} messages. showing relevant ones...")

                # Sort by time desc (default)
                for msg in messages:
                    ts = float(msg.get("ts", 0))
                    user = msg.get("user", "unknown")
                    text = msg.get("text", "") or " ".join([b.get("type", "") for b in msg.get("blocks", [])])

                    # Convert TS to readable
                    time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

                    # Filter for relevance (optional, but good for noise reduction)
                    # We want everything from Francisco (U088D41PZ44) or Italo (U095BK30FKQ)
                    # or mentions of them.
                    # Or just print everything since yesterday.

                    print(f"[{time_str}] ({user}): {text[:200]}...")
                    if len(text) > 200:
                        print(f"   {text[200:400]}...")
                    print("-" * 20)

        except Exception as e:
            print(f"Error fetching history: {e}")

    except Exception as e:
        print(f"Fatal Error: {e}")

    finally:
        session.close()


if __name__ == "__main__":
    # C085B73T2JE appears to be the channel they use for daily tasks based on previous search results
    check_channel_history("C085B73T2JE")
