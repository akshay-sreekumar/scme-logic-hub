import os
import time
import math
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env file
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env file.")
    exit(1)

# Initialize Supabase Admin Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Settings
DATA_WINDOW_SECONDS = 30 
LOOP_INTERVAL = 10 
DENSITY_ALERT_THRESHOLD = 85 
HISTORY_SIZE = 12 
PREDICT_AHEAD_MINUTES = 5 
PREDICT_AHEAD_TICKS = (PREDICT_AHEAD_MINUTES * 60) / LOOP_INTERVAL

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points in meters."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def fetch_zones():
    """Fetch active zones from event_config table."""
    try:
        response = supabase.table("event_config").select("*").eq("is_active", True).execute()
        zones = {}
        for row in response.data:
            zone_id = row['id']
            # Fallback for missing columns in current schema
            zones[zone_id] = {
                "name": row.get("name", f"Zone {zone_id[:6]}"),
                "lat": row['latitude'],
                "lng": row['longitude'],
                "radius": row.get("radius", 100), # Default 100m if radius is 0 or missing
                "max_capacity": row.get("max_capacity", 100) # Default 100 people
            }
        return zones
    except Exception as e:
        print(f"❌ Error fetching zones: {e}")
        return {}

def run_logic_hub():
    print("🧠 Smart Crowd Management Logic Hub (Dynamic Mode) Started...")
    
    # State Memory for Prediction
    zone_history = {} # Initialized dynamically
    
    while True:
        try:
            # Refresh zones every cycle to stay dynamic
            ZONES = fetch_zones()
            if not ZONES:
                print("⚠️ No active zones found in event_config. Waiting...")
                time.sleep(LOOP_INTERVAL)
                continue

            # Initialize history for new zones
            for zone_id in ZONES:
                if zone_id not in zone_history:
                    zone_history[zone_id] = []

            current_time = datetime.now().strftime('%H:%M:%S')
            print(f"--- Processing Cycle: {current_time} | Monitoring {len(ZONES)} Zones ---")
            
            # 1. Fetch recently active GPS locations
            time_threshold = (datetime.now(timezone.utc) - timedelta(seconds=DATA_WINDOW_SECONDS)).isoformat()
            response = supabase.table("live_locations").select("user_id, latitude, longitude").gte("timestamp", time_threshold).execute()
            
            active_users = {loc['user_id']: loc for loc in response.data}
            print(f"📡 Active GPS users: {len(active_users)}")

            # 2. Assign Users to Zones using Radius
            zone_counts = {zone_id: 0 for zone_id in ZONES}
            
            for user_id, loc in active_users.items():
                u_lat, u_lng = loc['latitude'], loc['longitude']
                for zone_id, config in ZONES.items():
                    dist = haversine(u_lat, u_lng, config['lat'], config['lng'])
                    if dist <= config['radius']:
                        zone_counts[zone_id] += 1
                        break

            # 3. Update & Predict
            for zone_id, config in ZONES.items():
                total_people = zone_counts[zone_id]
                density_percentage = min(100, int((total_people / config['max_capacity']) * 100))
                
                # Prediction logic
                history = zone_history[zone_id]
                history.append(density_percentage)
                if len(history) > HISTORY_SIZE: history.pop(0)
                
                predicted_density = density_percentage
                if len(history) >= 3:
                    y = history
                    x = list(range(len(y)))
                    mean_x, mean_y = sum(x)/len(x), sum(y)/len(y)
                    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
                    den = sum((xi - mean_x)**2 for xi in x)
                    slope = num / den if den != 0 else 0
                    predicted_density = max(0, min(100, int(density_percentage + (slope * PREDICT_AHEAD_TICKS))))

                # Log Status
                icon = "🟢" if density_percentage < 50 else ("🟠" if density_percentage < 85 else "🔴")
                trend = "↗️" if predicted_density > density_percentage + 5 else ("↘️" if predicted_density < density_percentage - 5 else "➡️")
                print(f"{icon} [{config['name']}] Dist: {config['radius']}m | Count: {total_people} => {density_percentage}% {trend} (Pred: {predicted_density}%)")
                
                # 4. Sync Density Table
                supabase.table("density").upsert({
                    "zone_id": zone_id,
                    "zone_name": config['name'],
                    "density_score": density_percentage,
                    "updated_at": "now()"
                }).execute()
                
                # 5. Alert Trigger Engine
                if density_percentage > DENSITY_ALERT_THRESHOLD:
                    supabase.table("alerts").insert({
                        "type": "CROWD_SURGE",
                        "zone_name": config['name'],
                        "priority": "HIGH",
                        "confidence": 1.0,
                        "instruction": f"Disperse crowd in {config['name']}. Reached {density_percentage}% capacity.",
                        "latitude": config['lat'],
                        "longitude": config['lng']
                    }).execute()
                elif predicted_density > DENSITY_ALERT_THRESHOLD:
                    supabase.table("alerts").insert({
                        "type": "PREDICTIVE_WARNING",
                        "zone_name": config['name'],
                        "priority": "MEDIUM",
                        "confidence": 0.8,
                        "instruction": f"Prepare for surge at {config['name']}. Projected to hit {predicted_density}% capacity.",
                        "latitude": config['lat'],
                        "longitude": config['lng']
                    }).execute()

        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)
            continue
            
        print("-" * 40)
        time.sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    run_logic_hub()
