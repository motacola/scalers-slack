import sys
import time
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.browser_automation import BrowserAutomationConfig, BrowserSession, SlackBrowserClient
from src.config_loader import load_config


def check_my_tasks(user_id="U0A6MGN9S77"):  # Christopher Belgrave's ID
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
        
        print(f"\n--- Searching Tasks for Christopher Belgrave ({user_id}) ---")
        
        # Search for mentions of the user
        queries = [
            f"<@{user_id}>",
            "Christopher Belgrave",
            "Chris task",
            "Chris copy",
            "from:Lisa Appleby to:Christopher Belgrave"
        ]
        
        seen_ts = set()
        
        for query in queries:
            print(f"\n>> Searching: '{query}' (recent)...")
            try:
                # Search messages
                results = slack_client.search_messages_paginated(query, count=5, max_pages=1)
                
                if results:
                    for msg in results:
                        ts = msg.get("ts")
                        if ts in seen_ts:
                            continue
                        seen_ts.add(ts)
                        
                        text = msg.get("text", "") or " ".join([b.get("type", "") for b in (msg.get("blocks") or [])])
                        text = text.replace("\n", " ").strip()
                        user = msg.get("user", "unknown")
                         
                        # Convert TS to readable
                        try:
                            time_obj = time.localtime(float(ts))
                            time_str = time.strftime("%Y-%m-%d %H:%M", time_obj)
                        except (TypeError, ValueError):
                            time_str = str(ts)
                            
                        print(f"   [{time_str}] {user}: {text[:300]}...")
                        print(f"      Link: {msg.get('permalink')}")
                else:
                    print("   No results found.")
            except Exception as e:
                print(f"   Error: {e}")

    except Exception as e:
        print(f"Fatal Error: {e}")

    finally:
        session.close()

if __name__ == "__main__":
    check_my_tasks()
