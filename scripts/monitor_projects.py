import sys
import time
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.browser_automation import BrowserAutomationConfig, BrowserSession, SlackBrowserClient
from src.config_loader import load_config


def monitor_projects(projects):
    # Load config
    try:
        app_config = load_config("config.json")
        settings = app_config.get("settings", {})
        browser_settings = settings.get("browser_automation", {})
    except Exception:
        browser_settings = {}

    config = BrowserAutomationConfig(
        enabled=True,
        storage_state_path="browser_storage_state.json",
        headless=True,
        slack_workspace_id=browser_settings.get("slack_workspace_id", ""),
    )
    
    session = BrowserSession(config)
    
    try:
        session.start()
        slack_client = SlackBrowserClient(session, config)
        
        print(f"\n--- Monitoring Updates for {len(projects)} Projects ---")
        
        for project in projects:
            print(f"\n>> Checking: {project}...")
            try:
                # Search for recent mentions of the project name
                # "after:yesterday" ensures we get very recent context
                query = f"\"{project}\" after:yesterday"
                results = slack_client.search_messages_paginated(query, count=5, max_pages=1)
                
                if not results:
                     # Try without quotes if strict match failed
                    query = f"{project} after:yesterday"
                    results = slack_client.search_messages_paginated(query, count=3, max_pages=1)

                if results:
                    print(f"   Found {len(results)} recent updates:")
                    for msg in results:
                        text = msg.get("text", "") or " ".join([b.get("type", "") for b in msg.get("blocks", [])])
                         # Basic cleaning
                        text = text.replace("\n", " ")[:150]
                        user = msg.get("user", "unknown")
                        ts = float(msg.get("ts", 0))
                        time_str = time.strftime('%H:%M', time.localtime(ts))
                        print(f"    - [{time_str}] {user}: {text}...")
                else:
                    print("   No recent updates found.")
                    
            except Exception as e:
                print(f"   Error searching for {project}: {e}")

    except Exception as e:
        print(f"Fatal Error: {e}")

    finally:
        session.close()

if __name__ == "__main__":
    # List derived from user's request
    projects_to_check = [
        "Pro Sewer",
        "Magnify",
        "Parker & Co",
        "Sunshine",
        "EDS",
        "Clear Choice Painting",
        "Kinty Jones",
        "WP checks"
    ]
    monitor_projects(projects_to_check)
