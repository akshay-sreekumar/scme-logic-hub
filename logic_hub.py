import os
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env file
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env file.")
    print("Please create a .env file based on .env.example")
    exit(1)

# Initialize Supabase Admin Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Define physical zones for the event
# In a real app, these bounds would come from a database or config.
ZONES = {
    "zone_1": {
        "name": "Gate A",
        "lat_min": 10.000,
        "lat_max": 10.010,
        "lng_min": 76.000,
        "lng_max": 76.010,
        "max_capacity": 50, # Used to compute density percentage
        "center_lat": 10.005,
        "center_lng": 76.005
    },
    "zone_2": {
        "name": "Main Stage",
        "lat_min": 10.011,
        "lat_max": 10.020,
        "lng_min": 76.000,
        "lng_max": 76.010,
        "max_capacity": 200,
        "center_lat": 10.0155,
        "center_lng": 76.005
    }
}

# Settings
DATA_WINDOW_SECONDS = 30 # A user is considered "active" in a zone if seen within 30s
LOOP_INTERVAL = 10 # Run the loop every 10 seconds
DENSITY_ALERT_THRESHOLD = 85 # Trigger alert if density > 85%

def run_logic_hub():
    print("🧠 Smart Crowd Management Logic Hub Started...")
    print(f"Monitoring {len(ZONES)} zones every {LOOP_INTERVAL} seconds.\n")
    
    while True:
        try:
            current_time = datetime.now().strftime('%H:%M:%S')
            print(f"--- Processing Cycle: {current_time} ---")
            
            # 1. Fetch recently active GPS locations
            time_threshold = (datetime.now(timezone.utc) - timedelta(seconds=DATA_WINDOW_SECONDS)).isoformat()
            
            # Get all location data logged in the last X seconds
            response = supabase.table("live_locations").select("user_id, latitude, longitude").gte("timestamp", time_threshold).execute()
            
            # We filter by dictionary to keep only the latest ping per user_id
            active_users = {}
            for loc in response.data:
                active_users[loc['user_id']] = loc
                
            print(f"📡 Active GPS users in the last {DATA_WINDOW_SECONDS}s: {len(active_users)}")

            # 2. Assign Users to Zones
            zone_counts = {zone_id: 0 for zone_id in ZONES.keys()}
            
            for user_id, loc in active_users.items():
                lat = loc['latitude']
                lng = loc['longitude']
                
                for zone_id, bounds in ZONES.items():
                    if bounds['lat_min'] <= lat <= bounds['lat_max'] and bounds['lng_min'] <= lng <= bounds['lng_max']:
                        zone_counts[zone_id] += 1
                        break # User belongs to one zone

            # 3. Fetch Camera Counts
            # WARNING: As of now, the `camera_stats` table does not exist in the DB schema provided. 
            # We are mocking the camera count. Later, you can query your camera table here.
            camera_counts = {
                "zone_1": 0, 
                "zone_2": 0
            }

            # 4. Fusion & Update
            for zone_id, bounds in ZONES.items():
                gps_count = zone_counts[zone_id]
                cam_count = camera_counts.get(zone_id, 0)
                
                # Logic: Total = Max(Camera, GPS) (Data Fusion!)
                total_people = max(gps_count, cam_count)
                
                # Calculate percentage
                density_percentage = int((total_people / bounds['max_capacity']) * 100)
                density_percentage = min(100, density_percentage) # Cap at 100%
                
                status_icon = "🟢" if density_percentage < 50 else ("🟠" if density_percentage < 85 else "🔴")
                print(f"{status_icon} [{bounds['name']}] GPS: {gps_count} | Cam: {cam_count} => Total: {total_people} ({density_percentage}% capacity)")
                
                # Upsert into `density` table
                supabase.table("density").upsert({
                    "zone_id": zone_id,
                    "zone_name": bounds['name'],
                    "density_score": density_percentage,
                    "updated_at": "now()"
                }).execute()
                
                # 5. Alert Trigger Engine
                if density_percentage > DENSITY_ALERT_THRESHOLD:
                    print(f"   ⚠️ HIGH DENSITY ALERT Triggered for {bounds['name']}!")
                    
                    # Insert into alerts table
                    supabase.table("alerts").insert({
                        "type": "CROWD_SURGE",
                        "priority": "HIGH",
                        "confidence": 1.0,
                        "instruction": f"Disperse crowd in {bounds['name']}. Reached {density_percentage}% capacity.",
                        "latitude": bounds['center_lat'],
                        "longitude": bounds['center_lng']
                        # "camera_id": null (since it's a zone-wide structural alert, not from a specific camera)
                    }).execute()

        except Exception as e:
            print(f"❌ Error during processing cycle: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)
            continue
            
        print("-" * 40)
        time.sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    run_logic_hub()
