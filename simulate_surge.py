import uuid
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("🚨 Simulating a massive crowd surge at Gate A...")
print("Gate A capacity is 50. We are sending 45 active users (>85%)...")

# Generate 45 dummy users
dummy_data = []
for _ in range(45):
    dummy_data.append({
        "user_id": str(uuid.uuid4()),
        "latitude": 10.005, # Center of Gate A
        "longitude": 76.005,
    })

# Bulk insert into live_locations
supabase.table("live_locations").insert(dummy_data).execute()

print("✅ Inserted 45 dummy GPS pings at Gate A.")
print("👀 Switch open your terminal where Logic Hub is running. It should detect the surge within 10 seconds and insert an Alert!")
