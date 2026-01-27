import json
import os

import requests

SUPABASE_TOKEN = os.getenv("SUPABASE_TOKEN", "")
SQL_API_URL = os.getenv("SUPABASE_SQL_API_URL", "")

def run_sql(sql):
    if not SUPABASE_TOKEN or not SQL_API_URL:
        print("Missing SUPABASE_TOKEN or SUPABASE_SQL_API_URL in environment.")
        return None
    headers = {
        "Authorization": f"Bearer {SUPABASE_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"query": sql}
    response = requests.post(SQL_API_URL, headers=headers, json=payload)
    if response.status_code not in [200, 201]:
        print(f"Error running SQL: {response.status_code} {response.text}")
        return None
    return response.json()

def main():
    print("🚀 Starting migration to Supabase...")
    
    # 1. Create the table
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS public.projects (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name TEXT NOT NULL UNIQUE,
        slack_channel_id TEXT,
        notion_page_url TEXT,
        notion_audit_page_id TEXT,
        notion_last_synced_page_id TEXT,
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    );
    """
    print("Creating projects table...")
    run_sql(create_table_sql)

    # 2. Load config.json
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading config.json: {e}")
        return
    
    projects = config.get("projects", [])
    print(f"Found {len(projects)} projects in config.json")

    # 3. Insert each project
    for p in projects:
        name = p.get("name", "").replace("'", "''")
        slack_id = p.get("slack_channel_id", "").replace("'", "''")
        notion_url = p.get("notion_page_url", "").replace("'", "''")
        audit_id = p.get("notion_audit_page_id", "").replace("'", "''")
        last_sync_id = p.get("notion_last_synced_page_id", "").replace("'", "''")
        
        insert_sql = f"""
        INSERT INTO public.projects (name, slack_channel_id, notion_page_url, notion_audit_page_id, notion_last_synced_page_id)
        VALUES ('{name}', '{slack_id}', '{notion_url}', '{audit_id}', '{last_sync_id}')
        ON CONFLICT (name) DO UPDATE SET
            slack_channel_id = EXCLUDED.slack_channel_id,
            notion_page_url = EXCLUDED.notion_page_url,
            notion_audit_page_id = EXCLUDED.notion_audit_page_id,
            notion_last_synced_page_id = EXCLUDED.notion_last_synced_page_id,
            updated_at = now();
        """
        
        print(f"Syncing {name}...")
        run_sql(insert_sql)

    print("✅ Migration complete!")

if __name__ == "__main__":
    main()
