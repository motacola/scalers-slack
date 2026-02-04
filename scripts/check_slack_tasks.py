import os
import sys
from pathlib import Path
from time import sleep

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.browser_automation import BrowserAutomationConfig, BrowserSession, SlackBrowserClient
from src.config_loader import load_config


def check_details_browser(users):
    # Load config
    try:
        app_config = load_config("config.json")
        settings = app_config.get("settings", {})
        browser_settings = settings.get("browser_automation", {})
        notion_hub_url = settings.get("notion_hub", {}).get("url")
    except Exception:
        browser_settings = {}
        notion_hub_url = "https://www.notion.so/quickerleads/Website-Hosting-Project-Management-Hub-28e1c9f5b34f8088a7bff341be5aec2f"

    config = BrowserAutomationConfig(
        enabled=True,
        storage_state_path="browser_storage_state.json",
        headless=True,
        slack_workspace_id=browser_settings.get("slack_workspace_id", ""),
    )
    
    session = BrowserSession(config)
    
    try:
        session.start()
        
        # --- Slack: Get Full Details ---
        print("\n--- Slack Details ---")
        try:
            slack_client = SlackBrowserClient(session, config)
            # Search for broader context
            queries = ["Francisco task", "Italo task", "tasks tomorrow", "tasks for tomorrow"]
            seen_ts = set()
            
            for query in queries:
                print(f"Searching: '{query}'")
                results = slack_client.search_messages_paginated(query, count=5, max_pages=1)
                for msg in results:
                    ts = msg.get("ts")
                    if ts in seen_ts:
                        continue
                    seen_ts.add(ts)
                    
                    text = msg.get("text", "") or (msg.get("blocks") or [{}])[0].get("text", {}).get("text", "")
                    # Fetch full blocks if possible, but text usually contains markdown
                    # If text is truncated, we might need to fetch the message permalink content? 
                    # Search results usually have full text.
                    
                    print(f"\n[Message TS: {ts}] P: {msg.get('permalink')}")
                    print(f"{'-'*40}")
                    print(text)
                    print(f"{'-'*40}")
                    
        except Exception as e:
            print(f"Slack Error: {e}")

        # --- Notion: Dump Content ---
        print("\n--- Notion Content Dump ---")
        if notion_hub_url:
            print(f"Navigating to {notion_hub_url}")
            page = session.new_page(notion_hub_url)
            
            try:
                page.wait_for_selector("div[role='main']", timeout=30000)
                sleep(5)  # Wait for rendering
            except Exception:
                print("Wait timeout, proceeding with whatever is loaded...")
                
            # Get text content
            text_content = page.evaluate("document.body.innerText")
            
            dump_path = "output/notion_text_dump.txt"
            os.makedirs("output", exist_ok=True)
            with open(dump_path, "w") as f:
                f.write(text_content)
                
            print(f"Notion text content saved to {dump_path} ({len(text_content)} chars)")
            
            # Print extraction of relevant lines
            print("\nScanning Notion dump for keywords...")
            lines = text_content.split('\n')
            for i, line in enumerate(lines):
                lower_line = line.lower()
                if any(u.lower() in lower_line for u in users) or "tomorrow" in lower_line:
                    # Print context (prev/next line)
                    ctx_start = max(0, i-1)
                    ctx_end = min(len(lines), i+2)
                    print(f"\n--- Context near match (line {i}) ---")
                    for j in range(ctx_start, ctx_end):
                        print(f"{j}: {lines[j]}")
                        
        else:
            print("No Notion URL")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_details_browser(["Francisco", "Italo"])
