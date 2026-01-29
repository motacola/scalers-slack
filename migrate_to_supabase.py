import json
import os

from dotenv import load_dotenv
from supabase import Client, create_client

# Load environment variables from .env file
load_dotenv()

# Get credentials
SUPABASE_URL = "https://hmehmfuxzqejfmbyumyc.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_KEY:
    print("❌ Error: SUPABASE_ANON_KEY or SUPABASE_SERVICE_ROLE_KEY not found in .env file")
    print("\n📝 To fix this:")
    print("1. Go to: https://supabase.com/dashboard/project/hmehmfuxzqejfmbyumyc/settings/api")
    print("2. Copy your 'service_role' key (secret key, recommended for migrations)")
    print("3. Add to your .env file:")
    print("   SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...")
    exit(1)

def main():
    print("🚀 Starting migration to Supabase...")
    
    # Initialize Supabase client
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✓ Connected to Supabase")
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return

    # 1. Create the table using raw SQL
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
    
    print("📦 Creating projects table...")
    try:
        supabase.rpc("exec_sql", {"query": create_table_sql}).execute()
        print("✓ Table created/verified")
    except Exception as e:
        # Table might already exist or we might need to use a different approach
        # Let's try using the postgrest API instead
        print(f"⚠️  Note: {e}")
        print("   Proceeding with data insertion (table may already exist)...")

    # 2. Load config.json
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        projects = config.get("projects", [])
        print(f"✓ Found {len(projects)} projects in config.json")
    except Exception as e:
        print(f"❌ Error loading config.json: {e}")
        return

    # 3. Insert each project using the Supabase client
    success_count = 0
    error_count = 0
    
    for p in projects:
        project_data = {
            "name": p.get("name", ""),
            "slack_channel_id": p.get("slack_channel_id", ""),
            "notion_page_url": p.get("notion_page_url", ""),
            "notion_audit_page_id": p.get("notion_audit_page_id", ""),
            "notion_last_synced_page_id": p.get("notion_last_synced_page_id", "")
        }
        
        try:
            # Use upsert to insert or update if exists
            supabase.table('projects').upsert(
                project_data,
                on_conflict='name'
            ).execute()
            
            print(f"✓ Synced: {project_data['name']}")
            success_count += 1
        except Exception as e:
            print(f"✗ Error syncing {project_data['name']}: {e}")
            error_count += 1

    print("\n✅ Migration complete!")
    print(f"   ✓ Success: {success_count}")
    if error_count > 0:
        print(f"   ✗ Errors: {error_count}")

if __name__ == "__main__":
    main()
