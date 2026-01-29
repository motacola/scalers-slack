"""
Helper script to guide you through getting the correct Supabase credentials.

The SQL API requires database-level keys (service_role or anon), not the management API token.

To get your keys:
1. Go to: https://supabase.com/dashboard/project/hmehmfuxzqejfmbyumyc/settings/api
2. Look for "Project API keys" section
3. Copy either the "anon" key (public) or "service_role" key (secret, recommended for migrations)

Then update your .env file with:
SUPABASE_SERVICE_ROLE_KEY=<your service_role key>

OR use the Supabase client library instead of the SQL API for better authentication.
"""

import os
from dotenv import load_dotenv

load_dotenv()

print(__doc__)

# Check current configuration
print("\n📋 Current Configuration:")
print(f"SUPABASE_TOKEN: {os.getenv('SUPABASE_TOKEN', 'NOT SET')[:20]}...")
print(f"SQL API URL: {os.getenv('SUPABASE_SQL_API_URL', 'NOT SET')}")

print("\n💡 Recommendation:")
print("Use the Supabase Python client library instead of direct SQL API calls.")
print("This provides better authentication and error handling.")
