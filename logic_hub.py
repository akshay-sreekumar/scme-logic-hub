import os
import time
import math
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env file.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Settings
DATA_WINDOW_SECONDS = 30 
LOOP_INTERVAL = 10 
DENSITY_ALERT_THRESHOLD = 85 
HISTORY_SIZE = 12 
PREDICT_AHEAD_MINUTES = 5 
PREDICT_AHEAD_TICKS = (PREDICT_AHEAD_MINUTES * 60) / LOOP_INTERVAL
DEFAULT_MAX_CAPACITY = 500 # Fallback capacity for the entire event

# Global State
EVENT_CONFIG = None
EVENT_HISTORY = []

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points in meters."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def fetch_latest_config():
    """Fetches event center and radius from Supabase."""
    global EVENT_CONFIG
    try:
        response = supabase.table("event_config").select("*").limit(1).execute()
        if response.data and len(response.data) > 0:
            EVENT_CONFIG = response.data[0]
            print(f"📍 Event Sync: Center({EVENT_CONFIG['latitude']}, {EVENT_CONFIG['longitude']}) Radius({EVENT_CONFIG['radius']}m)")
            return True
        else:
            print("⚠️ Event Config table is empty. Please set a location in Admin Dash.")
            return False
    except Exception as e:
        print(f"❌ Error fetching config: {e}")
    return False

def run_logic_hub():
    print("🧠 Smart Crowd Management Logic Hub (Single Zone Mode) Started...")
    
    # Wait for first config fetch
    while not fetch_latest_config():
        print("⏳ Waiting for initial event configuration...")
        time.sleep(5)
    
    global EVENT_HISTORY
    config_fetch_counter = 0

    while True:
        try:
            # Refresh config every 3 cycles (30s)
            config_fetch_counter += 1
            if config_fetch_counter >= 3:
                fetch_latest_config()
                config_fetch_counter = 0

            if not EVENT_CONFIG:
                time.sleep(LOOP_INTERVAL)
                continue

            current_time = datetime.now().strftime('%H:%M:%S')
            
            # 1. Fetch GPS locations
            time_threshold = (datetime.now(timezone.utc) - timedelta(seconds=DATA_WINDOW_SECONDS)).isoformat()
            response = supabase.table("live_locations").select("user_id, latitude, longitude").gte("timestamp", time_threshold).execute()
            
            active_users = {loc['user_id']: loc for loc in response.data if loc.get('user_id')}
            
            # 2. Count users inside the Event Zone
            count_inside = 0
            event_lat = EVENT_CONFIG['latitude']
            event_lng = EVENT_CONFIG['longitude']
            event_radius = EVENT_CONFIG['radius']
            
            for user_id, loc in active_users.items():
                u_lat, u_lng = loc['latitude'], loc['longitude']
                dist = haversine(u_lat, u_lng, event_lat, event_lng)
                if dist <= event_radius:
                    count_inside += 1

            # 3. Density and Prediction
            # Assume a max capacity for the event or use a field from config if exists
            max_cap = EVENT_CONFIG.get('max_capacity', DEFAULT_MAX_CAPACITY)
            density = min(100, int((count_inside / max_cap) * 100))
            
            EVENT_HISTORY.append(density)
            if len(EVENT_HISTORY) > HISTORY_SIZE: EVENT_HISTORY.pop(0)

            predicted_density = density
            if len(EVENT_HISTORY) >= 3:
                y = EVENT_HISTORY
                x = list(range(len(y)))
                mx, my = sum(x)/len(x), sum(y)/len(y)
                num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
                den = sum((xi - mx)**2 for xi in x)
                slope = num / den if den != 0 else 0
                predicted_density = max(0, min(100, int(density + (slope * PREDICT_AHEAD_TICKS))))

            icon = "🟢" if density < 50 else ("🟠" if density < 85 else "🔴")
            print(f"[{current_time}] {icon} EVENT ZONE: {count_inside}/{max_cap} ({density}%) | Pred in 5m: {predicted_density}%")

            # 4. Sync to DB
            supabase.table("density").upsert({
                "zone_id": "main_event",
                "zone_name": "Event Area",
                "density_score": density,
                "updated_at": "now()"
            }).execute()

            # 5. Trigger Alerts
            if density > DENSITY_ALERT_THRESHOLD:
                supabase.table("alerts").insert({
                    "type": "CROWD_SURGE",
                    "priority": "HIGH",
                    "confidence": 1.0,
                    "instruction": f"CRITICAL: Event Area is saturated ({density}%).",
                    "latitude": event_lat,
                    "longitude": event_lng
                }).execute()
            elif predicted_density > DENSITY_ALERT_THRESHOLD:
                supabase.table("alerts").insert({
                    "type": "PREDICTIVE_WARNING",
                    "priority": "MEDIUM",
                    "confidence": 0.8,
                    "instruction": f"PREDICTION: Event Area will saturate in 5 mins.",
                    "latitude": event_lat,
                    "longitude": event_lng
                }).execute()

        except Exception as e:
            print(f"❌ Loop Error: {e}")
        
        time.sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    run_logic_hub()
