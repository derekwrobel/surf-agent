from flask import Flask, request, jsonify
import json, os, urllib.request, urllib.parse, zoneinfo, hashlib
from datetime import datetime, timedelta
from cache import cache_get, cache_set, cache_available

app = Flask(__name__)

NOAA_TIDE_STATIONS = {
  "default":     "9410230",  # La Jolla CA
  "socal":       "9410230",  # La Jolla CA
  "norcal":      "9414290",  # San Francisco CA
  "oregon":      "9437540",  # Charleston OR
  "washington":  "9441102",  # West Point WA
  "florida":     "8721604",  # Trident Pier FL
  "mid_atlantic":"8638610",  # Sewells Point VA
  "new_england": "8443970",  # Boston MA
  "new_york":    "8516945",  # Kings Point NY
}

NOAA_BUOYS = [
  {"id":"46224","name":"Offshore Encinitas",  "note":"~10mi offshore SD"},
  {"id":"46025","name":"Santa Monica Basin",  "note":"NW groundswell approach"},
  {"id":"46086","name":"San Clemente Island", "note":"S/SW swell from Mexico"},
]

SYSTEM_PROMPT = """You are an expert surf forecast AI agent. Cross-reference all three data sources for an accurate ranked recommendation.

DATA SOURCES:
- Open-Meteo: hourly model forecast per spot (wave height/period/direction, wind)
- NOAA Buoys: real measured offshore swell (ground truth — weight this over model when different)
- NOAA Tides: tide predictions for the nearest tide station

GENERAL SURF KNOWLEDGE:
- Wave period: >12s = quality groundswell; 8-12s = moderate; <8s = wind swell/choppy
- Wind: offshore = glassy; onshore = blown out; side-offshore = ok; side-onshore = choppy
- Good height: 0.5-2m (1.5-6ft). Under 0.3m = flat. Over 3m = big/solid day
- Rising tide generally improves beach breaks; dropping tide can improve reef/point breaks
- Low tide exposes reefs more — can be hollow but also more dangerous

SAN DIEGO SPECIFIC:
- South wind (160-200deg) -> La Jolla Shores protected; OB/PB beach breaks get choppy
- Extreme low tide (<= -1.2ft) -> skip Avalanche south side, use OB pier north sandbar
- Avalanche + OB Jetty: both north of OB pier. Avalanche is the small jetty, OB Jetty is the main north jetty
- Avalanche optimal swell: 197-307deg (SSW/SW/W). NW swell misses it
- Sunset Cliffs: reef, needs solid W/SW groundswell, very tide-sensitive, experts only
- Blacks Beach: exposed to all swells, uncrowded, steep hike required
- Windansea: localized crew, reef break, best on W/NW swell
- Swami's: right point reef, best W swell, crowded locals
- Cardiff Reef: long rides W/NW swell, kelp possible
- Trestles/Lowers: world class rivermouth pointbreak, works on most swells, always crowded
- Mavericks: big wave venue only, experts/tow-in only

EAST COAST SPECIFIC:
- East Coast needs hurricane swell (summer/fall) or nor'easters (fall/winter) for quality waves
- Outer Banks NC: most exposed EC spot, excellent on NE/E swell from nor'easters
- Sebastian Inlet FL: best Florida break, N jetty focuses swell into hollow peaks
- Ruggles RI: handles biggest hurricane surf on EC, experts only
- Manasquan NJ: inlet focuses swell, powerful and hollow
- Rockaway NY: best when low pressure systems or tropical storms track offshore

PACIFIC NORTHWEST SPECIFIC:
- Oregon/WA: massive powerful beach breaks, often closeouts, consistent wind swell
- Cold water (48-54F), thick wetsuits required
- Seaside OR: most consistent OR break, powerful left, localized

Always recommend — never say stay home.

Output format:
[RIGHT NOW / DAWN PATROL - context]
Conditions: [1-sentence cross-referenced summary — note if buoy confirms or contradicts model]

RANKED SPOTS
1. [Name] [1-5 stars]  [height ft] | [period]s | [dir]deg swell | wind [speed]mph [dir]deg | tide [ft]
   [One sentence reason]
2-N. [same format]

SKIP (flat/blown out):
- [Name]: [reason]

Notes: [tide warnings, crowd notes, buoy vs model gaps. 2-3 sentences]

Stars: 5=pumping 4=good 3=decent 2=marginal 1=barely surfable. Convert m to ft (x3.28)."""


def fetch_url(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent":"surf-agent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def fetch_openmeteo(spot, target_date, now=False):
    params = urllib.parse.urlencode({
        "latitude": spot["lat"], "longitude": spot["lng"],
        "hourly": "wave_height,wave_period,wave_direction,swell_wave_height,swell_wave_period,swell_wave_direction,wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "mph", "timezone": "America/Los_Angeles", "forecast_days": 2,
    })
    data = json.loads(fetch_url(f"https://marine-api.open-meteo.com/v1/marine?{params}"))
    hourly = data["hourly"]

    if now:
        now_pt = datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
        current_hour = now_pt.strftime("%Y-%m-%dT%H:00")
        lines = []; count = 0; collecting = False
        for i, t in enumerate(hourly["time"]):
            if t == current_hour: collecting = True
            if collecting and count < 4:
                wh=hourly["wave_height"][i] or 0; wp=hourly["wave_period"][i] or 0
                wd=hourly["wave_direction"][i] or 0; swh=hourly["swell_wave_height"][i] or 0
                swp=hourly["swell_wave_period"][i] or 0; swd=hourly["swell_wave_direction"][i] or 0
                ws=hourly["wind_speed_10m"][i] or 0; wdr=hourly["wind_direction_10m"][i] or 0
                lines.append(f"  {t[11:16]}: wave {wh:.1f}m/{wp:.0f}s/{wd:.0f}deg | swell {swh:.1f}m {swp:.0f}s from {swd:.0f}deg | wind {ws:.0f}mph from {wdr:.0f}deg")
                count += 1
    else:
        date_str = target_date.strftime("%Y-%m-%d"); lines = []
        for i, t in enumerate(hourly["time"]):
            if not t.startswith(date_str): continue
            hour = int(t[11:13])
            if 5 <= hour <= 8:
                wh=hourly["wave_height"][i] or 0; wp=hourly["wave_period"][i] or 0
                wd=hourly["wave_direction"][i] or 0; swh=hourly["swell_wave_height"][i] or 0
                swp=hourly["swell_wave_period"][i] or 0; swd=hourly["swell_wave_direction"][i] or 0
                ws=hourly["wind_speed_10m"][i] or 0; wdr=hourly["wind_direction_10m"][i] or 0
                lines.append(f"  {t[11:16]}: wave {wh:.1f}m/{wp:.0f}s/{wd:.0f}deg | swell {swh:.1f}m {swp:.0f}s from {swd:.0f}deg | wind {ws:.0f}mph from {wdr:.0f}deg")

    name = spot.get("name") or spot.get("key", "Unknown")
    if not lines: return f"{name}: no data"
    return f"{name}:\n" + "\n".join(lines)


def fetch_buoys():
    results = []
    for buoy in NOAA_BUOYS:
        try:
            text = fetch_url(f"https://www.ndbc.noaa.gov/data/realtime2/{buoy['id']}.txt")
            lines = text.strip().splitlines()
            header = lines[0].lstrip("#").split()
            rows = [l for l in lines[2:] if not l.startswith("#")][:5]
            readings = []
            for row in rows:
                cols = row.split()
                if len(cols) < len(header): continue
                d = dict(zip(header, cols))
                wvht=d.get("WVHT","MM"); dpd=d.get("DPD","MM"); mwd=d.get("MWD","MM")
                wspd=d.get("WSPD","MM"); wdir_b=d.get("WDIR","MM")
                mo=d.get("MM","?"); dy=d.get("DD","?"); hh=d.get("hh","?"); mm_t=d.get("mm","?")
                if wvht=="MM" or dpd=="MM": continue
                ft = float(wvht)*3.28084
                readings.append(f"  {mo}/{dy} {hh}:{mm_t}Z - {ft:.1f}ft @ {dpd}s from {mwd}deg | wind {wspd}mph/{wdir_b}deg")
            if readings:
                results.append(f"Buoy {buoy['id']} ({buoy['name']}) - {buoy['note']}:\n" + "\n".join(readings[:3]))
            else:
                results.append(f"Buoy {buoy['id']}: no recent data")
        except Exception as e:
            results.append(f"Buoy {buoy['id']}: error - {e}")
    return "\n\n".join(results)


def pick_tide_station(spots):
    # Pick based on average latitude of selected spots
    lats = [s["lat"] for s in spots if "lat" in s]
    if not lats: return NOAA_TIDE_STATIONS["default"]
    avg_lat = sum(lats) / len(lats)
    lngs = [s["lng"] for s in spots if "lng" in s]
    avg_lng = sum(lngs) / len(lngs) if lngs else -100

    # East coast (lng > -81)
    if avg_lng > -81:
        if avg_lat < 36: return NOAA_TIDE_STATIONS["florida"]
        if avg_lat < 40: return NOAA_TIDE_STATIONS["mid_atlantic"]
        if avg_lat < 41.5: return NOAA_TIDE_STATIONS["new_york"]
        return NOAA_TIDE_STATIONS["new_england"]
    # West coast
    if avg_lat > 42: return NOAA_TIDE_STATIONS["washington"]
    if avg_lat > 41: return NOAA_TIDE_STATIONS["oregon"]
    if avg_lat > 37: return NOAA_TIDE_STATIONS["norcal"]
    return NOAA_TIDE_STATIONS["socal"]


def fetch_tides(target_date, station):
    date_str = target_date.strftime("%Y%m%d")
    base = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    def get(interval):
        p = urllib.parse.urlencode({
            "begin_date":date_str,"end_date":date_str,"station":station,
            "product":"predictions","datum":"MLLW","time_zone":"lst_ldt",
            "interval":interval,"units":"english","application":"surf_agent","format":"json",
        })
        return json.loads(fetch_url(f"{base}?{p}")).get("predictions",[])
    try:
        hourly=get("h"); hilo=get("hilo")
    except Exception as e:
        return f"Tides: error - {e}"

    dawn_lines=[]; hilo_lines=[]; lows=[]
    for p in hourly:
        t=p.get("t",""); v=float(p.get("v",0)); hour=int(t[11:13]) if len(t)>=13 else -1
        if 5<=hour<=8: dawn_lines.append(f"  {t[11:16]}: {v:+.2f}ft")
    for p in hilo:
        t=p.get("t",""); v=float(p.get("v",0)); kind="HIGH" if p.get("type")=="H" else "LOW "
        hilo_lines.append(f"  {kind} {t[11:16]}: {v:+.2f}ft")
        if p.get("type")=="L": lows.append(v)

    warning=""
    if any(l<=-1.2 for l in lows):
        warning=f"\n  EXTREME LOW TIDE ({min(lows):+.2f}ft) - skip Avalanche south side, OB pier north sandbar"

    out=[f"NOAA Tides (station {station}), {target_date.strftime('%A %b')} {target_date.day}:"]
    if hilo_lines: out.append("  Hi/Lo:"); out.extend(hilo_lines)
    if dawn_lines: out.append("  Dawn (5-8AM):"); out.extend(dawn_lines)
    if warning: out.append(warning)
    return "\n".join(out)


def call_claude(openmeteo_block, buoy_block, tide_block, target_date, spot_names, now_mode=False):
    api_key = os.environ.get("ANTHROPIC_API_KEY","")
    date_label = f"{target_date.strftime('%A, %B')} {target_date.day}"
    mode_str = "RIGHT NOW (next 3 hours)" if now_mode else f"dawn patrol on {date_label}"
    payload = json.dumps({
        "model":"claude-sonnet-4-6","max_tokens":1500,
        "system":SYSTEM_PROMPT,
        "messages":[{"role":"user","content":(
            f"Rank ONLY these spots for {mode_str}: {spot_names}. Do not include any other spots.\n\n"
            f"SOURCE 1 - Open-Meteo forecast:\n{openmeteo_block}\n\n"
            f"SOURCE 2 - NOAA Buoy readings:\n{buoy_block}\n\n"
            f"SOURCE 3 - NOAA Tides:\n{tide_block}"
        )}]
    }).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload, headers={
        "Content-Type":"application/json","x-api-key":api_key,"anthropic-version":"2023-06-01",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["content"][0]["text"]


@app.route("/api/forecast", methods=["GET","OPTIONS"])
def get_spots():
    if request.method=="OPTIONS": return _cors(jsonify({}))
    return _cors(jsonify({"status":"ok"}))

@app.route("/api/forecast", methods=["POST"])
def get_forecast():
    try:
        body       = request.get_json(force=True) or {}
        spots_in   = body.get("spots", [])
        now_mode   = body.get("now", False)
        days_ahead = int(body.get("days_ahead", 1))
        target     = datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles")) + timedelta(days=days_ahead)

        spots = [s for s in spots_in if "lat" in s and "lng" in s]
        if not spots: return _cors(jsonify({"error":"No valid spots with coordinates"})), 400

        # --- Cache check ---
        spot_keys_sorted = sorted(s.get("key","") for s in spots)
        cache_hash = hashlib.md5(",".join(spot_keys_sorted).encode()).hexdigest()[:8]
        window = "now" if now_mode else "dawn"
        date_str = target.strftime("%Y-%m-%d")
        cache_key = f"swell:user:{cache_hash}:{date_str}:{window}"

        if cache_available():
            cached = cache_get(cache_key)
            if cached:
                return _cors(jsonify({"result": cached, "cached": True}))

        # --- Live fetch ---
        openmeteo_parts = []
        for spot in spots:
            try: openmeteo_parts.append(fetch_openmeteo(spot, target, now=now_mode))
            except Exception as e: openmeteo_parts.append(f"{spot.get('key','?')}: error - {e}")

        try: buoy_block = fetch_buoys()
        except Exception as e: buoy_block = f"Buoy data unavailable: {e}"

        tide_station = pick_tide_station(spots)
        try: tide_block = fetch_tides(target, tide_station)
        except Exception as e: tide_block = f"Tide data unavailable: {e}"

        spot_names = ", ".join(s.get("key","?") for s in spots)
        result = call_claude("\n\n".join(openmeteo_parts), buoy_block, tide_block, target, spot_names, now_mode)

        # Store in cache for 90 minutes
        if cache_available():
            cache_set(cache_key, result, ttl_seconds=5400)

        return _cors(jsonify({"result": result, "cached": False}))
    except Exception as e:
        return _cors(jsonify({"error": str(e)})), 500

def _cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

if __name__ == "__main__":
    app.run(debug=True)
