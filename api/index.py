from flask import Flask, request, jsonify
import json, os, urllib.request, urllib.parse, zoneinfo
from datetime import datetime, timedelta

app = Flask(__name__)

SPOTS = [
  # San Diego
  {"key":"sunset_cliffs", "name":"Sunset Cliffs",       "lat":32.7215,"lng":-117.2568,"note":"Reef W/SW swell"},
  {"key":"ob_pier",       "name":"OB Pier",              "lat":32.7528,"lng":-117.2553,"note":"Home base"},
  {"key":"ob_jetty",      "name":"OB Jetty",             "lat":32.7566,"lng":-117.2531,"note":"N jetty hollow peaks"},
  {"key":"avalanche",     "name":"Avalanche",            "lat":32.7544,"lng":-117.2534,"note":"SW/W swell 197-307deg"},
  {"key":"mission",       "name":"Mission Beach",        "lat":32.7662,"lng":-117.2525,"note":"Beach break"},
  {"key":"pb_dr",         "name":"PB Dr.",               "lat":32.7795,"lng":-117.2510,"note":"Beach break"},
  {"key":"crystal",       "name":"Crystal Pier",         "lat":32.7882,"lng":-117.2527,"note":"PB pier break"},
  {"key":"tourm",         "name":"Tourmaline",           "lat":32.7972,"lng":-117.2597,"note":"Longboard friendly"},
  {"key":"lj_shores",     "name":"La Jolla Shores",      "lat":32.8572,"lng":-117.2567,"note":"Protected south wind"},
  {"key":"blacks",        "name":"Blacks Beach",         "lat":32.8789,"lng":-117.2519,"note":"Uncrowded hike in"},
  {"key":"scripps",       "name":"Scripps Pier",         "lat":32.8664,"lng":-117.2541,"note":"N La Jolla"},
  {"key":"delmar_15",     "name":"Del Mar 15th St",      "lat":32.9561,"lng":-117.2719,"note":"Town beach break"},
  {"key":"delmar_river",  "name":"Del Mar Rivermouth",   "lat":32.9609,"lng":-117.2739,"note":"Shifting sandbars"},
  {"key":"delmar_29",     "name":"Del Mar 29th St",      "lat":32.9680,"lng":-117.2724,"note":"N Del Mar peaks"},
  {"key":"cardiff",       "name":"Cardiff",              "lat":33.0136,"lng":-117.2820,"note":"Reef long rides"},
  {"key":"swamis",        "name":"Swami's",              "lat":33.0367,"lng":-117.2921,"note":"Reef best W swell"},
  {"key":"grandview",     "name":"Grandview",            "lat":33.0574,"lng":-117.2940,"note":"Reef consistent"},
  # Orange County
  {"key":"trestles",      "name":"Trestles",             "lat":33.3828,"lng":-117.5897,"note":"World class"},
  {"key":"lowers",        "name":"Lowers",               "lat":33.3789,"lng":-117.5878,"note":"CT contest site"},
  {"key":"san_onofre",    "name":"San Onofre",           "lat":33.3697,"lng":-117.5636,"note":"Longboard mecca"},
  {"key":"doheny",        "name":"Doheny",               "lat":33.4611,"lng":-117.6731,"note":"Beginner friendly"},
  {"key":"salt_creek",    "name":"Salt Creek",           "lat":33.4867,"lng":-117.7103,"note":"Powerful beach break"},
  {"key":"brooks_street", "name":"Brooks Street",        "lat":33.5422,"lng":-117.7853,"note":"Laguna reef"},
  {"key":"thalia",        "name":"Thalia Street",        "lat":33.5328,"lng":-117.7814,"note":"Laguna consistent"},
  {"key":"huntington",    "name":"Huntington Beach",     "lat":33.6553,"lng":-118.0005,"note":"Surf City USA"},
  {"key":"newps_pier",    "name":"Newport Pier",         "lat":33.6033,"lng":-117.9322,"note":"Classic beach break"},
  {"key":"the_wedge",     "name":"The Wedge",            "lat":33.5936,"lng":-117.8819,"note":"Bodysurf shore break"},
  # Los Angeles
  {"key":"malibu",        "name":"Malibu First Point",   "lat":34.0361,"lng":-118.6789,"note":"Iconic longboard wave"},
  {"key":"zuma",          "name":"Zuma Beach",           "lat":34.0155,"lng":-118.8228,"note":"Beach break consistent"},
  {"key":"el_porto",      "name":"El Porto",             "lat":33.9022,"lng":-118.4286,"note":"Manhattan Beach powerful"},
  {"key":"manhattan_pier","name":"Manhattan Pier",       "lat":33.8869,"lng":-118.4153,"note":"Beach break"},
  {"key":"hermosa",       "name":"Hermosa Beach",        "lat":33.8622,"lng":-118.4003,"note":"Beach break"},
  {"key":"venice",        "name":"Venice Beach",         "lat":33.9850,"lng":-118.4695,"note":"Beach break"},
  {"key":"topanga",       "name":"Topanga",              "lat":34.0428,"lng":-118.5981,"note":"Beach break consistent"},
  {"key":"county_line",   "name":"County Line",          "lat":34.0561,"lng":-118.9178,"note":"Ventura LA border"},
  # Ventura / Santa Barbara
  {"key":"rincon",        "name":"Rincon",               "lat":34.3733,"lng":-119.4756,"note":"Queen of the Coast"},
  {"key":"c_street",      "name":"C Street",             "lat":34.2731,"lng":-119.3103,"note":"Long point break"},
  {"key":"emma_wood",     "name":"Emma Wood",            "lat":34.2947,"lng":-119.3311,"note":"Beach break consistent"},
  {"key":"ventura_pier",  "name":"Ventura Pier",         "lat":34.2697,"lng":-119.2978,"note":"Beach break"},
  {"key":"hammonds",      "name":"Hammonds",             "lat":34.4047,"lng":-119.6481,"note":"Reef right point"},
  {"key":"leadbetter",    "name":"Leadbetter",           "lat":34.4072,"lng":-119.6969,"note":"SB longboard"},
  {"key":"campus_pt",     "name":"Campus Point",         "lat":34.4103,"lng":-119.8444,"note":"UCSB reef right"},
  # Central Coast
  {"key":"pismo",         "name":"Pismo Beach",          "lat":35.1428,"lng":-120.6411,"note":"Beach break"},
  {"key":"shell_beach",   "name":"Shell Beach",          "lat":35.1642,"lng":-120.6742,"note":"Reef consistent"},
  {"key":"morro_rock",    "name":"Morro Rock",           "lat":35.3697,"lng":-120.8753,"note":"Beach break"},
  {"key":"cayucos",       "name":"Cayucos Pier",         "lat":35.4428,"lng":-120.9108,"note":"Beach break mellow"},
  # Monterey Bay
  {"key":"steamer_lane",  "name":"Steamer Lane",         "lat":36.9514,"lng":-122.0264,"note":"Santa Cruz iconic reef"},
  {"key":"pleasure_pt",   "name":"Pleasure Point",       "lat":36.9619,"lng":-121.9731,"note":"Santa Cruz reef right"},
  {"key":"cowell",        "name":"Cowell's",             "lat":36.9522,"lng":-122.0267,"note":"Beginner mellow"},
  {"key":"mavericks",     "name":"Mavericks",            "lat":37.4958,"lng":-122.5008,"note":"Big wave experts only"},
  {"key":"capitola",      "name":"Capitola",             "lat":36.9753,"lng":-121.9533,"note":"Beach break mellow"},
  {"key":"pacifica",      "name":"Pacifica",             "lat":37.6108,"lng":-122.4897,"note":"Beach break windy"},
  # San Francisco
  {"key":"ocean_beach_sf","name":"Ocean Beach SF",       "lat":37.7594,"lng":-122.5107,"note":"Powerful experts"},
  {"key":"kelly_cove",    "name":"Kelly's Cove",         "lat":37.7700,"lng":-122.5117,"note":"SF sheltered corner"},
  {"key":"linda_mar",     "name":"Linda Mar",            "lat":37.5961,"lng":-122.4997,"note":"Pacifica beginner"},
  {"key":"fort_point",    "name":"Fort Point",           "lat":37.8108,"lng":-122.4775,"note":"Under GG bridge"},
  # North Coast CA
  {"key":"bolinas",       "name":"Bolinas",              "lat":37.9083,"lng":-122.7167,"note":"Mellow remote"},
  {"key":"salmon_creek",  "name":"Salmon Creek",         "lat":38.3522,"lng":-123.0736,"note":"Sonoma beach break"},
  {"key":"goat_rock",     "name":"Goat Rock",            "lat":38.4508,"lng":-123.1303,"note":"Sonoma river mouth"},
  {"key":"fort_bragg",    "name":"Fort Bragg",           "lat":39.4458,"lng":-123.8119,"note":"Beach break cold"},
  # Oregon
  {"key":"brookings",     "name":"Brookings",            "lat":42.0528,"lng":-124.2831,"note":"Beach break consistent"},
  {"key":"gold_beach",    "name":"Gold Beach",           "lat":42.4039,"lng":-124.4228,"note":"Beach break"},
  {"key":"bandon",        "name":"Bandon",               "lat":43.1178,"lng":-124.4097,"note":"Beach break remote"},
  {"key":"florence",      "name":"Florence",             "lat":43.9825,"lng":-124.1050,"note":"Beach break"},
  {"key":"newport_or",    "name":"Newport OR",           "lat":44.6364,"lng":-124.0531,"note":"Agate Beach consistent"},
  {"key":"lincoln_city",  "name":"Lincoln City",         "lat":44.9578,"lng":-124.0136,"note":"Beach break consistent"},
  {"key":"neskowin",      "name":"Neskowin",             "lat":45.1025,"lng":-123.9817,"note":"Beach break mellow"},
  {"key":"oswald_west",   "name":"Oswald West",          "lat":45.7481,"lng":-123.9583,"note":"Short Sands sheltered"},
  {"key":"cannon_beach",  "name":"Cannon Beach",         "lat":45.8892,"lng":-123.9617,"note":"Scenic beach break"},
  {"key":"seaside",       "name":"Seaside",              "lat":45.9933,"lng":-123.9233,"note":"Most consistent OR"},
  {"key":"pacific_city",  "name":"Pacific City",         "lat":45.2078,"lng":-123.9608,"note":"Dory fleet beach break"},
  # Washington
  {"key":"westport",      "name":"Westport",             "lat":46.9008,"lng":-124.1050,"note":"Most consistent WA"},
  {"key":"south_jetty_wa","name":"South Jetty WA",       "lat":46.9069,"lng":-124.1097,"note":"Powerful jetty break"},
  {"key":"long_beach_wa", "name":"Long Beach WA",        "lat":46.3522,"lng":-124.0525,"note":"Beach break exposed"},
  {"key":"moclips",       "name":"Moclips",              "lat":47.2394,"lng":-124.2119,"note":"Beach break remote"},
  {"key":"la_push",       "name":"La Push",              "lat":47.9108,"lng":-124.6356,"note":"Remote tribal land"},
  {"key":"shi_shi",       "name":"Shi Shi Beach",        "lat":48.2733,"lng":-124.6869,"note":"Remote hike in"},
  # Florida
  {"key":"sebastian_inlet","name":"Sebastian Inlet",     "lat":27.8594,"lng":-80.4508,"note":"Best FL break inlet"},
  {"key":"cocoa_beach",   "name":"Cocoa Beach",          "lat":28.3200,"lng":-80.6078,"note":"Consistent beginner"},
  {"key":"new_smyrna",    "name":"New Smyrna Beach",     "lat":29.0258,"lng":-80.9272,"note":"Sharky fun waves"},
  {"key":"ponce_inlet",   "name":"Ponce Inlet",          "lat":29.0811,"lng":-80.9297,"note":"Inlet break"},
  {"key":"flagler",       "name":"Flagler Beach",        "lat":29.4728,"lng":-81.1283,"note":"Pier break consistent"},
  {"key":"jax_beach",     "name":"Jacksonville Beach",   "lat":30.2936,"lng":-81.3967,"note":"Beach break"},
  # Mid Atlantic
  {"key":"cape_hatteras", "name":"Cape Hatteras",        "lat":35.2306,"lng":-75.5283,"note":"Powerful storm swell"},
  {"key":"rodanthe",      "name":"Rodanthe",             "lat":35.5925,"lng":-75.4658,"note":"OBX consistent"},
  {"key":"wrightsville",  "name":"Wrightsville Beach",   "lat":34.2083,"lng":-77.7969,"note":"Beach break consistent"},
  {"key":"va_beach",      "name":"Virginia Beach",       "lat":36.8519,"lng":-75.9780,"note":"Beach break consistent"},
  {"key":"ocean_city_md", "name":"Ocean City MD",        "lat":38.3365,"lng":-75.0849,"note":"Beach break storm swell"},
  {"key":"manasquan",     "name":"Manasquan Inlet",      "lat":40.1019,"lng":-74.0431,"note":"Best NJ break inlet"},
  {"key":"belmar",        "name":"Belmar",               "lat":40.1753,"lng":-74.0233,"note":"Beach break consistent"},
  {"key":"asbury_park",   "name":"Asbury Park",          "lat":40.2203,"lng":-74.0128,"note":"Beach break"},
  {"key":"ditch_plains",  "name":"Ditch Plains",         "lat":41.0311,"lng":-71.9367,"note":"Best NY break reef"},
  {"key":"montauk",       "name":"Montauk",              "lat":41.0428,"lng":-71.9547,"note":"Multiple breaks"},
  {"key":"long_beach_ny", "name":"Long Beach NY",        "lat":40.5883,"lng":-73.6586,"note":"Beach break consistent"},
  {"key":"rockaway",      "name":"Rockaway Beach",       "lat":40.5828,"lng":-73.8158,"note":"NYC surf beach break"},
  # New England
  {"key":"ruggles",       "name":"Ruggles",              "lat":41.4614,"lng":-71.4619,"note":"RI reef localized"},
  {"key":"narragansett",  "name":"Narragansett",         "lat":41.4511,"lng":-71.4567,"note":"RI consistent beach break"},
  {"key":"first_beach",   "name":"First Beach Newport",  "lat":41.4878,"lng":-71.3083,"note":"RI beach break"},
  {"key":"nahant",        "name":"Nahant",               "lat":42.4256,"lng":-70.9233,"note":"MA reef exposed"},
  {"key":"good_harbor",   "name":"Good Harbor",          "lat":42.6228,"lng":-70.6564,"note":"MA beach break"},
  {"key":"ogunquit",      "name":"Ogunquit",             "lat":43.2494,"lng":-70.5983,"note":"ME beach break mellow"},
  {"key":"york_beach",    "name":"York Beach",           "lat":43.1728,"lng":-70.6114,"note":"ME beach break"},
]
SPOT_BY_KEY = {s["key"]: s for s in SPOTS}

NOAA_TIDE_STATIONS = {
  "default":    "9410230",  # La Jolla
  "california": "9410230",
  "oregon":     "9437540",  # Charleston OR
  "washington": "9441102",  # West Point WA
  "florida":    "8721604",  # Trident Pier FL
  "mid_atlantic":"8638610", # Sewells Point VA
  "new_england": "8443970", # Boston MA
}

NOAA_BUOYS = [
  {"id":"46224","name":"Offshore Encinitas",  "note":"~10mi offshore SD"},
  {"id":"46025","name":"Santa Monica Basin",  "note":"NW groundswell approach"},
  {"id":"46086","name":"San Clemente Island", "note":"S/SW swell from Mexico"},
]

SYSTEM_PROMPT = """You are an expert surf forecast AI agent. You will receive wave data for one or more surf spots and must give an accurate ranked recommendation.

You will receive three data sources:
- Open-Meteo: hourly model forecast per spot (wave height/period/direction, wind)
- NOAA Buoys: real measured offshore swell (ground truth)
- NOAA Tides: tide predictions

Cross-reference all three. When buoy and model differ, weight buoy more heavily for current conditions.

GENERAL KNOWLEDGE:
- Wave period: >12s = quality groundswell; 8-12s = moderate; <8s = wind swell/choppy
- Wind: offshore = glassy; onshore = blown out
- Good height: 0.5-2m (1.5-6ft). Under 0.3m = flat. Over 3m = big day
- Rising tide generally improves beach breaks; dropping tide can improve reef/point breaks

SAN DIEGO LOCAL KNOWLEDGE:
- South wind (160-200deg) -> La Jolla Shores protected; OB/PB beach breaks get choppy
- Extreme low tide (<= -1.2ft) -> skip Avalanche south side, OB pier north sandbar is the move
- Avalanche and OB Jetty are both north of OB pier; Avalanche is the small jetty, OB Jetty is the main north jetty
- Avalanche optimal swell: 197-307deg (SSW/SW/W)
- OB Jetty: picks up similar swell to Avalanche, can be hollower on the right sandbar
- Sunset Cliffs: reef, needs solid W/SW groundswell, very tide-sensitive
- Blacks Beach: exposed, uncrowded, hike required
- Swami's: reef, best W swell, crowded with locals
- Cardiff: long rides W/NW swell, kelp possible
- Grandview: consistent reef, less crowded than Swami's

Never say stay home - always rank and recommend.

Output format:

RIGHT NOW / DAWN PATROL - [context]
Conditions: [1-sentence cross-referenced summary]

RANKED SPOTS
1. [Name] [1-5 stars]  [height ft] | [period]s | [dir]deg swell | wind [speed]mph [dir]deg | tide [ft]
   [One sentence reason]
2. ...

SKIP:
- [Name]: [reason]

Notes: [2-3 sentences on tides, crowds, anything notable]

Stars: 5=pumping 4=good 3=decent 2=marginal 1=barely surfable. Convert m to ft (x3.28)."""


def fetch_url(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "surf-agent/1.0"})
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

    if not lines: return f"{spot['name']}: no data"
    return f"{spot['name']} ({spot['note']}):\n" + "\n".join(lines)


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


def get_tide_station(spot_keys):
    # Pick best tide station based on spot geography
    for key in spot_keys:
        spot = SPOT_BY_KEY.get(key)
        if not spot: continue
        lat = spot["lat"]
        if lat < 35: return NOAA_TIDE_STATIONS["california"]
        if lat < 42.5: return NOAA_TIDE_STATIONS["oregon"]
        if lat < 49: return NOAA_TIDE_STATIONS["washington"]
        if lat < 36: return NOAA_TIDE_STATIONS["florida"]
        if lat < 41: return NOAA_TIDE_STATIONS["mid_atlantic"]
        return NOAA_TIDE_STATIONS["new_england"]
    return NOAA_TIDE_STATIONS["default"]


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
        warning=f"\n  EXTREME LOW TIDE ({min(lows):+.2f}ft) - skip Avalanche south side, use OB pier north sandbar"

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
        "model": "claude-sonnet-4-6", "max_tokens": 1200,
        "system": SYSTEM_PROMPT,
        "messages": [{"role":"user","content":(
            f"Rank ONLY these spots for {mode_str}: {spot_names}. Do not include any other spots.\n\n"
            f"SOURCE 1 - Open-Meteo forecast:\n{openmeteo_block}\n\n"
            f"SOURCE 2 - NOAA Buoy readings:\n{buoy_block}\n\n"
            f"SOURCE 3 - NOAA Tides:\n{tide_block}"
        )}]
    }).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload, headers={
        "Content-Type":"application/json","x-api-key":api_key,"anthropic-version":"2023-06-01",
    })
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())["content"][0]["text"]


@app.route("/api/forecast", methods=["GET","OPTIONS"])
def get_spots():
    if request.method=="OPTIONS": return _cors(jsonify({}))
    return _cors(jsonify({"spots": SPOTS}))

@app.route("/api/forecast", methods=["POST"])
def get_forecast():
    try:
        body       = request.get_json(force=True) or {}
        keys       = body.get("spots", [])
        now_mode   = body.get("now", False)
        days_ahead = int(body.get("days_ahead", 1))
        target     = datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles")) + timedelta(days=days_ahead)
        spots      = [SPOT_BY_KEY[k] for k in keys if k in SPOT_BY_KEY]
        if not spots: return _cors(jsonify({"error":"No valid spots"})), 400

        openmeteo_parts = []
        for spot in spots:
            try: openmeteo_parts.append(fetch_openmeteo(spot, target, now=now_mode))
            except Exception as e: openmeteo_parts.append(f"{spot['name']}: error - {e}")

        try: buoy_block = fetch_buoys()
        except Exception as e: buoy_block = f"Buoy data unavailable: {e}"

        tide_station = get_tide_station(keys)
        try: tide_block = fetch_tides(target, tide_station)
        except Exception as e: tide_block = f"Tide data unavailable: {e}"

        spot_names = ", ".join(s["name"] for s in spots)
        result = call_claude("\n\n".join(openmeteo_parts), buoy_block, tide_block, target, spot_names, now_mode)
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
