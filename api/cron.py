"""
Vercel Cron Job — runs every hour.
Pre-computes forecasts for all regions and stores in Redis cache.
Called at /api/cron by Vercel's scheduler.
"""
from flask import Flask, request, jsonify
import json, os, zoneinfo
from datetime import datetime, timedelta

# Import shared logic from index
import sys
sys.path.insert(0, os.path.dirname(__file__))
from cache import cache_set, cache_available

app = Flask(__name__)

# All regions with their representative spot coordinates
# We use a single representative spot per region for the cron forecast
# (full multi-spot fetch happens on-demand in index.py)
REGIONS = {
    "sd_south":      {"name": "San Diego - South",              "lat": 32.7215, "lng": -117.2568},
    "sd_ob_pb":      {"name": "San Diego - OB / PB",            "lat": 32.7528, "lng": -117.2553},
    "sd_la_jolla":   {"name": "San Diego - La Jolla",           "lat": 32.8572, "lng": -117.2567},
    "sd_del_mar":    {"name": "San Diego - Del Mar / Solana",   "lat": 32.9561, "lng": -117.2719},
    "sd_encinitas":  {"name": "San Diego - Encinitas / Cardiff","lat": 33.0367, "lng": -117.2921},
    "sd_carlsbad":   {"name": "San Diego - Carlsbad / Oceanside","lat": 33.1958, "lng": -117.3800},
    "oc":            {"name": "Orange County",                   "lat": 33.3828, "lng": -117.5897},
    "la":            {"name": "Los Angeles",                     "lat": 34.0361, "lng": -118.6789},
    "ventura_sb":    {"name": "Ventura / Santa Barbara",        "lat": 34.3733, "lng": -119.4756},
    "central_coast": {"name": "Central Coast",                  "lat": 35.3697, "lng": -120.8753},
    "monterey":      {"name": "Monterey Bay",                   "lat": 36.9514, "lng": -122.0264},
    "sf":            {"name": "San Francisco",                  "lat": 37.7594, "lng": -122.5107},
    "norcal":        {"name": "North Coast CA",                 "lat": 38.4508, "lng": -123.1303},
    "or_south":      {"name": "South Oregon",                   "lat": 42.4039, "lng": -124.4228},
    "or_central":    {"name": "Central Oregon",                 "lat": 44.6364, "lng": -124.0531},
    "or_north":      {"name": "North Oregon",                   "lat": 45.9933, "lng": -123.9233},
    "wa_sw":         {"name": "Southwest Washington",           "lat": 46.9008, "lng": -124.1050},
    "wa_olympic":    {"name": "Olympic Peninsula",              "lat": 47.9108, "lng": -124.6356},
    "fl_space_coast":{"name": "East Coast - Florida Space Coast","lat": 28.3200, "lng": -80.6078},
    "fl_ne":         {"name": "East Coast - Northeast Florida", "lat": 30.2936, "lng": -81.3967},
    "ec_nc":         {"name": "East Coast - North Carolina",    "lat": 35.5925, "lng": -75.4658},
    "ec_va_md":      {"name": "East Coast - Virginia/Maryland", "lat": 36.8519, "lng": -75.9780},
    "ec_nj":         {"name": "East Coast - New Jersey",        "lat": 40.1019, "lng": -74.0431},
    "ec_ny":         {"name": "East Coast - New York",          "lat": 41.0311, "lng": -71.9367},
    "ec_ne":         {"name": "East Coast - New England",       "lat": 41.4614, "lng": -71.4619},
}

def make_cache_key(region_key, target_date, window):
    date_str = target_date.strftime("%Y-%m-%d")
    return f"swell:region:{region_key}:{date_str}:{window}"

def get_window(target_date):
    """Determine the forecast window label based on hour."""
    now_pt = datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
    diff_days = (target_date.date() - now_pt.date()).days
    if diff_days == 0:
        hour = now_pt.hour
        if hour < 10: return "dawn"
        if hour < 14: return "morning"
        if hour < 18: return "afternoon"
        return "evening"
    return "dawn"  # For future days always forecast dawn

@app.route("/", methods=["GET", "POST"])
@app.route("/api/cron", methods=["GET", "POST"])
def run_cron():
    # Verify this is called by Vercel's cron (not a random user)
    auth = request.headers.get("Authorization", "")
    cron_secret = os.environ.get("CRON_SECRET", "")
    if cron_secret and auth != f"Bearer {cron_secret}":
        return jsonify({"error": "Unauthorized"}), 401

    if not cache_available():
        return jsonify({"error": "Redis not configured"}), 500

    # Import forecast functions from index.py
    from index import fetch_openmeteo, fetch_buoys, fetch_tides, call_claude, pick_tide_station, NOAA_BUOYS

    now_pt = datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
    # Pre-compute for today (current window) and tomorrow (dawn)
    targets = [
        (now_pt, get_window(now_pt)),
        (now_pt + timedelta(days=1), "dawn"),
    ]

    # Fetch shared data once (buoys + tides are the same for all regions)
    print("Fetching shared NOAA buoy data...")
    try:
        buoy_block = fetch_buoys()
    except Exception as e:
        buoy_block = f"Buoy data unavailable: {e}"

    results = {"cached": [], "failed": [], "skipped": []}

    for target_date, window in targets:
        # Fetch tides for West Coast (La Jolla) and East Coast (VA Beach)
        tide_blocks = {}
        for station_key, station_id in [("west", "9410230"), ("east", "8638610")]:
            try:
                tide_blocks[station_key] = fetch_tides(target_date, station_id)
            except Exception as e:
                tide_blocks[station_key] = f"Tides unavailable: {e}"

        for region_key, region_info in REGIONS.items():
            cache_key = make_cache_key(region_key, target_date, window)

            # Skip if already cached and fresh (< 50 min old)
            existing = cache_available() and False  # always refresh on cron

            spot = {"key": region_key, "lat": region_info["lat"], "lng": region_info["lng"], "name": region_info["name"]}
            is_now = window == "now"

            try:
                print(f"Fetching {region_info['name']} / {window}...")
                om_block = fetch_openmeteo(spot, target_date, now=is_now)

                # Pick appropriate tide block
                tide_block = tide_blocks["east"] if region_info["lng"] > -81 else tide_blocks["west"]

                result = call_claude(
                    om_block, buoy_block, tide_block,
                    target_date, region_info["name"],
                    now_mode=is_now
                )

                cache_set(cache_key, result, ttl_seconds=7200)
                results["cached"].append(cache_key)
                print(f"  ✓ cached {cache_key}")

            except Exception as e:
                results["failed"].append({"key": cache_key, "error": str(e)})
                print(f"  ✗ {region_key}: {e}")

    return jsonify({
        "status": "ok",
        "cached": len(results["cached"]),
        "failed": len(results["failed"]),
        "details": results
    })


if __name__ == "__main__":
    app.run(debug=True)
