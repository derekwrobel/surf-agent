from flask import Flask, request, jsonify
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
import zoneinfo


app = Flask(__name__)

SPOTS = [
    {"key": "sunset_cliffs",  "name": "Sunset Cliffs",       "lat": 32.7215, "lng": -117.2568, "zone": "OB / Point Loma",  "note": "Reef - W/SW swell"},
    {"key": "ob_pier",        "name": "OB Pier",              "lat": 32.7528, "lng": -117.2553, "zone": "OB / Point Loma",  "note": "Home base"},
    {"key": "avalanche",      "name": "Avalanche",            "lat": 32.7510, "lng": -117.2560, "zone": "OB / Point Loma",  "note": "SW/W swell 197-307deg"},
    {"key": "mission",        "name": "Mission Beach",        "lat": 32.7662, "lng": -117.2525, "zone": "Mission / PB",     "note": "Beach break"},
    {"key": "pb_dr",          "name": "PB Dr.",               "lat": 32.7795, "lng": -117.2510, "zone": "Mission / PB",     "note": "Beach break"},
    {"key": "crystal",        "name": "Crystal Pier",         "lat": 32.7882, "lng": -117.2527, "zone": "Mission / PB",     "note": "PB pier break"},
    {"key": "tourm",          "name": "Tourmaline",           "lat": 32.7972, "lng": -117.2597, "zone": "Mission / PB",     "note": "Longboard friendly"},
    {"key": "lj_shores",      "name": "La Jolla Shores",      "lat": 32.8572, "lng": -117.2567, "zone": "La Jolla",         "note": "Protected south wind"},
    {"key": "blacks",         "name": "Blacks Beach",         "lat": 32.8789, "lng": -117.2519, "zone": "La Jolla",         "note": "Uncrowded - hike in"},
    {"key": "scripps",        "name": "Scripps Pier",         "lat": 32.8664, "lng": -117.2541, "zone": "La Jolla",         "note": "N La Jolla"},
    {"key": "delmar_15",      "name": "Del Mar 15th St",      "lat": 32.9561, "lng": -117.2719, "zone": "Del Mar",          "note": "Town beach break"},
    {"key": "delmar_river",   "name": "Del Mar Rivermouth",   "lat": 32.9609, "lng": -117.2739, "zone": "Del Mar",          "note": "Shifting sandbars"},
    {"key": "delmar_29",      "name": "Del Mar 29th St",      "lat": 32.9680, "lng": -117.2724, "zone": "Del Mar",          "note": "N Del Mar peaks"},
    {"key": "cardiff",        "name": "Cardiff",              "lat": 33.0136, "lng": -117.2820, "zone": "Encinitas",        "note": "Reef - long rides"},
    {"key": "swamis",         "name": "Swami's",              "lat": 33.0367, "lng": -117.2921, "zone": "Encinitas",        "note": "Reef - best W swell"},
    {"key": "grandview",      "name": "Grandview",            "lat": 33.0574, "lng": -117.2940, "zone": "Encinitas",        "note": "Reef - consistent"},
]
SPOT_BY_KEY = {s["key"]: s for s in SPOTS}

NOAA_TIDE_STATION = "9410230"
NOAA_BUOYS = [
    {"id": "46224", "name": "Offshore Encinitas",  "note": "~10mi offshore, closest to SD"},
    {"id": "46025", "name": "Santa Monica Basin",  "note": "tracks approaching NW groundswell"},
    {"id": "46086", "name": "San Clemente Island", "note": "catches S/SW swell from Mexico"},
]

SYSTEM_PROMPT = """You are a surf forecast AI agent for an experienced San Diego surfer who surfs ~90% of days and does dawn patrol (5:30-7 AM window).

You will receive three data sources - cross-reference them for a reliable picture:
- Open-Meteo: hourly model forecast per spot (wave height/period/direction, wind)
- NOAA Buoys: real measured swell offshore right now (ground truth for what's in the water)
- NOAA Tides: tide heights and hi/lo events for La Jolla

When buoy data and model data differ, weight the buoy more heavily for current conditions; use the model for timing/trend.

LOCAL KNOWLEDGE:
- South wind (160-200 degrees) -> La Jolla Shores is protected; OB/PB beach breaks get choppy
- Extreme low tide (<= -1.2 ft) -> skip Avalanche south side, use OB pier north sandbar peaks
- Avalanche optimal swell: 197-307 degrees (SSW/SW/W) - north/NW swell misses it
- Sunset Cliffs: reef, needs solid W/SW groundswell, very tide-sensitive
- Blacks Beach: exposed to all swells, uncrowded, hike down required
- Del Mar Rivermouth: best with S/SW swell, shifting sandbars
- Swami's: reef, best W swell, can be crowded with locals
- Cardiff Reef: long rides on W/NW swell, kelp can be an issue
- Grandview: consistent reef, less crowded than Swami's
- Wind: offshore = easterly (~90 degrees); onshore = westerly (~270 degrees); dawn often glassy in summer
- Wave period: >12s = quality groundswell; 8-12s = moderate; <8s = wind swell/choppy
- Good dawn height: 0.5-2m (1.5-6ft). Under 0.3m = flat. Over 3m = big day

Never say stay home - always rank and recommend.

Output format:

DAWN PATROL - [Day, Month Date]
Conditions: [1-sentence cross-referenced swell/wind summary]

RANKED SPOTS
1. [Spot name] [1-5 stars]  [height ft] | [period]s | [swell dir]deg | wind [speed]mph [dir]deg | tide [ft]
   [One sentence: why it's #1 today]
2. [Spot name] ...
   [One sentence]
(all checked spots, best to worst)

SKIP (flat or blown out):
- [Spot name]: [one-word reason]

Notes: [Tide warnings, crowd notes, buoy vs model discrepancies. 2-3 sentences max.]

Star ratings: 5=pumping, 4=good, 3=decent, 2=marginal, 1=barely surfable.
Convert wave height to feet (1m = 3.28ft). Be direct and specific."""


def fetch_url(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "surf-agent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def fetch_openmeteo(spot, target_date):
    params = urllib.parse.urlencode({
        "latitude": spot["lat"],
        "longitude": spot["lng"],
        "hourly": "wave_height,wave_period,wave_direction,swell_wave_height,swell_wave_period,swell_wave_direction,wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "mph",
        "timezone": "America/Los_Angeles",
        "forecast_days": 2,
    })
    data = json.loads(fetch_url(f"https://marine-api.open-meteo.com/v1/marine?{params}"))
    hourly = data["hourly"]
    date_str = target_date.strftime("%Y-%m-%d")
    lines = []
    for i, t in enumerate(hourly["time"]):
        if not t.startswith(date_str):
            continue
        hour = int(t[11:13])
        if 5 <= hour <= 8:
            wh  = hourly["wave_height"][i]         or 0
            wp  = hourly["wave_period"][i]          or 0
            wd  = hourly["wave_direction"][i]       or 0
            swh = hourly["swell_wave_height"][i]    or 0
            swp = hourly["swell_wave_period"][i]    or 0
            swd = hourly["swell_wave_direction"][i] or 0
            ws  = hourly["wind_speed_10m"][i]       or 0
            wdr = hourly["wind_direction_10m"][i]   or 0
            lines.append(
                f"  {t[11:16]}: wave {wh:.1f}m/{wp:.0f}s/{wd:.0f}deg | "
                f"swell {swh:.1f}m {swp:.0f}s from {swd:.0f}deg | "
                f"wind {ws:.0f}mph from {wdr:.0f}deg"
            )
    if not lines:
        return f"{spot['name']}: no dawn data"
    return f"{spot['name']} ({spot['note']}):\n" + "\n".join(lines)


def fetch_buoys():
    results = []
    for buoy in NOAA_BUOYS:
        url = f"https://www.ndbc.noaa.gov/data/realtime2/{buoy['id']}.txt"
        try:
            text = fetch_url(url)
            lines = text.strip().splitlines()
            header = lines[0].lstrip("#").split()
            rows = [l for l in lines[2:] if not l.startswith("#")][:5]
            readings = []
            for row in rows:
                cols = row.split()
                if len(cols) < len(header):
                    continue
                d = dict(zip(header, cols))
                wvht   = d.get("WVHT", "MM")
                dpd    = d.get("DPD",  "MM")
                mwd    = d.get("MWD",  "MM")
                wspd   = d.get("WSPD", "MM")
                wdir_b = d.get("WDIR", "MM")
                mo     = d.get("MM", "?")
                dy     = d.get("DD", "?")
                hh     = d.get("hh", "?")
                mm_t   = d.get("mm", "?")
                if wvht == "MM" or dpd == "MM":
                    continue
                ft = float(wvht) * 3.28084
                readings.append(
                    f"  {mo}/{dy} {hh}:{mm_t}Z - "
                    f"{ft:.1f}ft @ {dpd}s from {mwd}deg | wind {wspd}mph/{wdir_b}deg"
                )
            if readings:
                results.append(
                    f"Buoy {buoy['id']} ({buoy['name']}) - {buoy['note']}:\n"
                    + "\n".join(readings[:3])
                )
            else:
                results.append(f"Buoy {buoy['id']} ({buoy['name']}): no recent wave data")
        except Exception as e:
            results.append(f"Buoy {buoy['id']} ({buoy['name']}): error - {e}")
    return "\n\n".join(results)


def fetch_tides(target_date):
    date_str = target_date.strftime("%Y%m%d")
    base = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

    def get(interval):
        p = urllib.parse.urlencode({
            "begin_date": date_str, "end_date": date_str,
            "station": NOAA_TIDE_STATION, "product": "predictions",
            "datum": "MLLW", "time_zone": "lst_ldt",
            "interval": interval, "units": "english",
            "application": "surf_agent", "format": "json",
        })
        return json.loads(fetch_url(f"{base}?{p}")).get("predictions", [])

    try:
        hourly = get("h")
        hilo   = get("hilo")
    except Exception as e:
        return f"NOAA Tides: error - {e}"

    dawn_lines = []
    for p in hourly:
        t    = p.get("t", "")
        v    = float(p.get("v", 0))
        hour = int(t[11:13]) if len(t) >= 13 else -1
        if 5 <= hour <= 8:
            dawn_lines.append(f"  {t[11:16]}: {v:+.2f} ft")

    hilo_lines = []
    lows = []
    for p in hilo:
        t    = p.get("t", "")
        v    = float(p.get("v", 0))
        kind = "HIGH" if p.get("type") == "H" else "LOW "
        hilo_lines.append(f"  {kind} {t[11:16]}: {v:+.2f} ft")
        if p.get("type") == "L":
            lows.append(v)

    warning = ""
    if any(l <= -1.2 for l in lows):
        warning = f"\n  EXTREME LOW TIDE ({min(lows):+.2f} ft) - skip Avalanche south side, use OB pier north sandbar"

    out = [f"NOAA Tides - La Jolla ({NOAA_TIDE_STATION}), {target_date.strftime('%A %b')} {target_date.day}:"]
    if hilo_lines:
        out.append("  Hi/Lo events:")
        out.extend(hilo_lines)
    if dawn_lines:
        out.append("  Dawn window (5-8 AM):")
        out.extend(dawn_lines)
    if warning:
        out.append(warning)
    return "\n".join(out)


def call_claude(openmeteo_block, buoy_block, tide_block, target_date, spot_names):
    api_key    = os.environ.get("ANTHROPIC_API_KEY", "")
    date_label = f"{target_date.strftime('%A, %B')} {target_date.day}"
    payload = json.dumps({
        "model":      "claude-sonnet-4-6",
        "max_tokens": 1200,
        "system":     SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": (
                f"Rank ONLY these spots for dawn patrol on {date_label}: {spot_names}. Do not include any other spots.\n\n"
                f"SOURCE 1 - Open-Meteo forecast (model):\n{openmeteo_block}\n\n"
                f"SOURCE 2 - NOAA Buoy readings (measured):\n{buoy_block}\n\n"
                f"SOURCE 3 - NOAA Tide predictions:\n{tide_block}"
            )
        }]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
        }
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())["content"][0]["text"]


@app.route("/api/forecast", methods=["GET", "OPTIONS"])
def get_spots():
    if request.method == "OPTIONS":
        return _cors(jsonify({}))
    return _cors(jsonify({"spots": SPOTS}))


@app.route("/api/forecast", methods=["POST"])
def get_forecast():
    try:
        body       = request.get_json(force=True) or {}
        keys       = body.get("spots", [s["key"] for s in SPOTS])
        days_ahead = int(body.get("days_ahead", 1))
        target     = target = datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles")) + timedelta(days=days_ahead)
        spots      = [SPOT_BY_KEY[k] for k in keys if k in SPOT_BY_KEY]

        if not spots:
            return _cors(jsonify({"error": "No valid spots"})), 400

        openmeteo_parts = []
        for spot in spots:
            try:
                openmeteo_parts.append(fetch_openmeteo(spot, target))
            except Exception as e:
                openmeteo_parts.append(f"{spot['name']}: error - {e}")

        try:
            buoy_block = fetch_buoys()
        except Exception as e:
            buoy_block = f"Buoy data unavailable: {e}"

        try:
            tide_block = fetch_tides(target)
        except Exception as e:
            tide_block = f"Tide data unavailable: {e}"

        result = call_claude("\n\n".join(openmeteo_parts), buoy_block, tide_block, target)
        return _cors(jsonify({"result": result}))

    except Exception as e:
        return _cors(jsonify({"error": str(e)})), 500


def _cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


if __name__ == "__main__":
    app.run(debug=True)
