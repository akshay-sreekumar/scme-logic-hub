import uuid
import time
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("🚨 Starting incremental crowd simulation for Gate A!")
print("We will add 10 users every 10 seconds. The Logic Hub should catch the trend.\n")

# Start loop
current_users = 0
generated_users = []

for iteration in range(5): # 5 loops of 10 users = 50 total (100% capacity)
    print(f"--- Adding 10 more users (Total: {current_users + 10} / 50 capacity) ---")
    
    new_users = []
    for _ in range(10):
        new_user = {
            "user_id": str(uuid.uuid4()),
            "latitude": 10.005, # Center of Gate A
            "longitude": 76.005,
        }
        new_users.append(new_user)
        generated_users.append(new_user)
        
    current_users += 10
    
    # Insert new users
    supabase.table("live_locations").insert(new_users).execute()
    
    print("✅ Inserted. Sleeping for 12 seconds to let Logic Hub calculate the new trend...")
    time.sleep(12) # Wait slightly longer than the Logic Hub 10s loop

print("\n🚀 Simulation complete! Deleting dummy users to clean up DB...")
for user in generated_users:
    try:
        supabase.table("live_locations").delete().eq("user_id", user["user_id"]).execute()
    except Exception as e:
         pass 

print("✅ Cleanup complete.")
