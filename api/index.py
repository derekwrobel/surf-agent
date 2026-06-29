import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify
import json, urllib.request, urllib.parse, zoneinfo, hashlib, math as _math
from datetime import datetime, timedelta
from cache import cache_get, cache_set, cache_available

app = Flask(__name__)

# ---------------------------------------------------------------------------
# NOAA buoy database — nearest 2 selected dynamically per request
# ---------------------------------------------------------------------------
ALL_BUOYS = [
    {"id":"46258","name":"Mission Bay West",          "lat":32.749,"lng":-117.369,"note":"OB/Mission Beach"},
    {"id":"46254","name":"Scripps Nearshore",         "lat":32.868,"lng":-117.267,"note":"La Jolla nearshore"},
    {"id":"46266","name":"Del Mar Nearshore",         "lat":32.957,"lng":-117.279,"note":"Del Mar/Torrey Pines"},
    {"id":"46274","name":"Leucadia Nearshore",        "lat":33.080,"lng":-117.353,"note":"Encinitas/Leucadia"},
    {"id":"46224","name":"Oceanside Offshore",        "lat":33.177,"lng":-117.469,"note":"Carlsbad/Oceanside"},
    {"id":"46232","name":"Point Loma South",          "lat":32.517,"lng":-117.425,"note":"S SD offshore"},
    {"id":"46235","name":"Imperial Beach Nearshore",  "lat":32.494,"lng":-117.422,"note":"IB/Coronado"},
    {"id":"46086","name":"San Clemente Island",       "lat":32.491,"lng":-118.046,"note":"S/SW swell approach SD"},
    {"id":"46025","name":"Santa Monica Basin",        "lat":33.749,"lng":-119.053,"note":"NW swell approach SoCal"},
    {"id":"46285","name":"Capistrano Beach Nearshore","lat":33.428,"lng":-117.666,"note":"Dana Point/OC"},
    {"id":"46253","name":"San Pedro South",           "lat":33.518,"lng":-118.186,"note":"OC offshore"},
    {"id":"46222","name":"San Pedro",                 "lat":33.618,"lng":-118.317,"note":"Long Beach/San Pedro"},
    {"id":"46221","name":"Santa Monica Bay",          "lat":33.860,"lng":-118.641,"note":"LA/Santa Monica"},
    {"id":"46069","name":"S Santa Barbara Basin",    "lat":34.259,"lng":-120.671,"note":"Ventura/SB offshore"},
    {"id":"46054","name":"West Santa Barbara",        "lat":34.274,"lng":-120.459,"note":"Santa Barbara"},
    {"id":"46011","name":"Santa Maria",               "lat":34.956,"lng":-120.998,"note":"Central Coast/SLO"},
    {"id":"46215","name":"Morro Bay Offshore",        "lat":35.204,"lng":-120.859,"note":"Morro Bay/Pismo"},
    {"id":"46028","name":"Cape San Martin",           "lat":35.741,"lng":-121.903,"note":"Big Sur"},
    {"id":"46042","name":"Monterey",                  "lat":36.785,"lng":-122.469,"note":"Monterey Bay"},
    {"id":"46013","name":"Bodega Bay",                "lat":38.241,"lng":-123.301,"note":"Bodega Bay"},
    {"id":"46026","name":"San Francisco",             "lat":37.750,"lng":-122.838,"note":"SF/Ocean Beach"},
    {"id":"46236","name":"Point Reyes",               "lat":37.907,"lng":-123.470,"note":"Point Reyes NorCal"},
    {"id":"46014","name":"Point Arena",               "lat":39.235,"lng":-123.974,"note":"Mendocino"},
    {"id":"46022","name":"Eel River",                 "lat":40.716,"lng":-124.540,"note":"Eureka/NorCal"},
    {"id":"46027","name":"St. George",                "lat":41.849,"lng":-124.381,"note":"Crescent City/OR border"},
    {"id":"46015","name":"Port Orford",               "lat":42.754,"lng":-124.839,"note":"S Oregon"},
    {"id":"46229","name":"Umpqua Offshore",           "lat":43.772,"lng":-124.549,"note":"Coos Bay/Central OR"},
    {"id":"46050","name":"Stonewall Bank",            "lat":44.679,"lng":-124.535,"note":"Newport/Central OR"},
    {"id":"46089","name":"Tillamook",                 "lat":45.928,"lng":-125.815,"note":"N Oregon/Tillamook"},
    {"id":"46029","name":"Columbia River Bar",        "lat":46.148,"lng":-124.508,"note":"Columbia River/Seaside"},
    {"id":"46041","name":"Cape Elizabeth",            "lat":47.353,"lng":-124.731,"note":"WA coast/Westport"},
    {"id":"46087","name":"Neah Bay",                  "lat":48.494,"lng":-124.726,"note":"NW Washington"},
    {"id":"41009","name":"Canaveral 20NM",            "lat":28.508,"lng":-80.185, "note":"Cape Canaveral/Space Coast"},
    {"id":"41010","name":"Canaveral 120NM",           "lat":28.906,"lng":-78.471, "note":"E Florida offshore"},
    {"id":"41112","name":"NE Florida Nearshore",      "lat":30.709,"lng":-81.292, "note":"Jacksonville/NE FL"},
    {"id":"41047","name":"NE Bahamas",                "lat":27.513,"lng":-71.490, "note":"Deep water E Florida"},
    {"id":"41013","name":"Frying Pan Shoals",         "lat":33.436,"lng":-77.743, "note":"Wilmington NC"},
    {"id":"41025","name":"Diamond Shoals",            "lat":35.010,"lng":-75.402, "note":"Cape Hatteras/OBX"},
    {"id":"41001","name":"East Hatteras",             "lat":34.676,"lng":-72.698, "note":"Offshore Hatteras"},
    {"id":"44014","name":"Virginia Beach Offshore",   "lat":36.611,"lng":-74.836, "note":"Virginia Beach"},
    {"id":"44009","name":"Delaware Bay",              "lat":38.461,"lng":-74.703, "note":"Cape May NJ"},
    {"id":"44091","name":"New Jersey Nearshore",      "lat":39.772,"lng":-73.769, "note":"NJ coast"},
    {"id":"44065","name":"NY Bight",                  "lat":40.369,"lng":-73.703, "note":"NY/Rockaway"},
    {"id":"44025","name":"NY Harbor Offshore",        "lat":40.258,"lng":-73.175, "note":"NJ/NY Harbor"},
    {"id":"44017","name":"Montauk",                   "lat":40.694,"lng":-72.048, "note":"Long Island/Montauk"},
    {"id":"44008","name":"Nantucket",                 "lat":40.504,"lng":-69.248, "note":"Nantucket/Cape Cod"},
    {"id":"44018","name":"SE Cape Cod",               "lat":41.255,"lng":-69.305, "note":"SE Cape Cod"},
    {"id":"44013","name":"Boston",                    "lat":42.346,"lng":-70.651, "note":"Boston/MA Coast"},
    {"id":"44007","name":"Portland",                  "lat":43.525,"lng":-70.141, "note":"Maine coast"},
    {"id":"44027","name":"Jonesport",                 "lat":44.279,"lng":-67.307, "note":"Downeast Maine"},
]

# ---------------------------------------------------------------------------
# NOAA tide station database — nearest selected dynamically per request
# ---------------------------------------------------------------------------
ALL_TIDE_STATIONS = [
    {"id":"9410230","name":"La Jolla CA",           "lat":32.867,"lng":-117.257},
    {"id":"9410660","name":"Los Angeles CA",         "lat":33.720,"lng":-118.272},
    {"id":"9411340","name":"Santa Barbara CA",       "lat":34.408,"lng":-119.686},
    {"id":"9412110","name":"Port San Luis CA",       "lat":35.169,"lng":-120.754},
    {"id":"9413450","name":"Monterey CA",            "lat":36.605,"lng":-121.888},
    {"id":"9414290","name":"San Francisco CA",       "lat":37.807,"lng":-122.465},
    {"id":"9415020","name":"Point Reyes CA",         "lat":37.996,"lng":-122.977},
    {"id":"9416841","name":"Arena Cove CA",          "lat":38.914,"lng":-123.709},
    {"id":"9418767","name":"North Spit CA",          "lat":40.767,"lng":-124.217},
    {"id":"9431647","name":"Port Orford OR",         "lat":42.737,"lng":-124.499},
    {"id":"9432780","name":"Charleston OR",          "lat":43.345,"lng":-124.322},
    {"id":"9435380","name":"South Beach OR",         "lat":44.625,"lng":-124.044},
    {"id":"9437540","name":"Garibaldi OR",           "lat":45.554,"lng":-123.919},
    {"id":"9439040","name":"Astoria OR",             "lat":46.207,"lng":-123.769},
    {"id":"9440910","name":"Toke Point WA",          "lat":46.707,"lng":-123.967},
    {"id":"9441102","name":"West Point WA",          "lat":47.661,"lng":-122.435},
    {"id":"9443090","name":"Port Townsend WA",       "lat":48.113,"lng":-122.760},
    {"id":"8723214","name":"Virginia Key FL",        "lat":25.731,"lng":-80.162},
    {"id":"8721604","name":"Trident Pier FL",        "lat":28.416,"lng":-80.593},
    {"id":"8720030","name":"Fernandina Beach FL",    "lat":30.671,"lng":-81.465},
    {"id":"8661070","name":"Springmaid Pier SC",     "lat":33.655,"lng":-78.918},
    {"id":"8658120","name":"Wilmington NC",          "lat":34.227,"lng":-77.953},
    {"id":"8654467","name":"USCG Hatteras NC",       "lat":35.209,"lng":-75.703},
    {"id":"8651370","name":"Duck NC",                "lat":36.183,"lng":-75.747},
    {"id":"8638610","name":"Sewells Point VA",       "lat":36.947,"lng":-76.330},
    {"id":"8557380","name":"Lewes DE",               "lat":38.782,"lng":-75.119},
    {"id":"8534720","name":"Atlantic City NJ",       "lat":39.355,"lng":-74.418},
    {"id":"8516945","name":"Kings Point NY",         "lat":40.810,"lng":-73.765},
    {"id":"8510560","name":"Montauk NY",             "lat":41.048,"lng":-71.960},
    {"id":"8452660","name":"Newport RI",             "lat":41.505,"lng":-71.327},
    {"id":"8447930","name":"Woods Hole MA",          "lat":41.523,"lng":-70.671},
    {"id":"8443970","name":"Boston MA",              "lat":42.355,"lng":-71.052},
    {"id":"8419317","name":"Portland ME",            "lat":43.657,"lng":-70.247},
    {"id":"8410140","name":"Eastport ME",            "lat":44.904,"lng":-66.985},
]

# ---------------------------------------------------------------------------
# Cron regions — one representative spot per region for hourly pre-compute
# ---------------------------------------------------------------------------
CRON_REGIONS = {
    "sd_ob_pb":      {"name": "San Diego - OB / PB",             "lat": 32.7528, "lng": -117.2553},
    "sd_la_jolla":   {"name": "San Diego - La Jolla",            "lat": 32.8572, "lng": -117.2567},
    "sd_encinitas":  {"name": "San Diego - Encinitas / Cardiff", "lat": 33.0367, "lng": -117.2921},
    "sd_carlsbad":   {"name": "San Diego - Carlsbad / Oceanside","lat": 33.1958, "lng": -117.3800},
    "oc":            {"name": "Orange County",                    "lat": 33.3828, "lng": -117.5897},
    "la":            {"name": "Los Angeles",                      "lat": 34.0361, "lng": -118.6789},
    "ventura_sb":    {"name": "Ventura / Santa Barbara",         "lat": 34.3733, "lng": -119.4756},
    "monterey":      {"name": "Monterey Bay",                    "lat": 36.9514, "lng": -122.0264},
    "sf":            {"name": "San Francisco",                   "lat": 37.7594, "lng": -122.5107},
    "or_central":    {"name": "Central Oregon",                  "lat": 44.6364, "lng": -124.0531},
    "wa_sw":         {"name": "Southwest Washington",            "lat": 46.9008, "lng": -124.1050},
    "fl_space_coast":{"name": "Florida Space Coast",             "lat": 28.3200, "lng": -80.6078},
    "ec_nc":         {"name": "North Carolina",                  "lat": 35.5925, "lng": -75.4658},
    "ec_nj":         {"name": "New Jersey",                      "lat": 40.1019, "lng": -74.0431},
    "ec_ne":         {"name": "New England",                     "lat": 41.4614, "lng": -71.4619},
}

def _sunrise_sunset_utc(lat, lng, d):
    """Return (sunrise_utc, sunset_utc) as hours (float) for a given date and location.
    Uses the NOAA solar calculation algorithm (accurate to within ~1 minute)."""
    import math
    n = d.timetuple().tm_yday
    # Solar declination
    decl = math.radians(23.45 * math.sin(math.radians(360 / 365 * (n - 81))))
    # Hour angle at sunrise/sunset
    cos_ha = -math.tan(math.radians(lat)) * math.tan(decl)
    cos_ha = max(-1.0, min(1.0, cos_ha))  # clamp for polar edge cases
    ha = math.degrees(math.acos(cos_ha))
    # Solar noon in UTC (longitude offset)
    solar_noon_utc = 12.0 - (lng / 15.0)
    sunrise_utc = solar_noon_utc - ha / 15.0
    sunset_utc  = solar_noon_utc + ha / 15.0
    return sunrise_utc, sunset_utc


def _is_daylight(lat, lng, tz_name, buffer_hours=2):
    """Return True if current local time is within surfable daylight hours
    (from buffer_hours before sunrise to buffer_hours after sunset)."""
    now_utc = datetime.utcnow()
    now_local = datetime.now(zoneinfo.ZoneInfo(tz_name))
    d = now_local.date()
    sunrise_utc, sunset_utc = _sunrise_sunset_utc(lat, lng, d)
    now_utc_h = now_utc.hour + now_utc.minute / 60.0
    return (sunrise_utc - buffer_hours) <= now_utc_h <= (sunset_utc + buffer_hours)


def _haversine(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = _math.radians(lat2-lat1); dlng = _math.radians(lng2-lng1)
    a = _math.sin(dlat/2)**2 + _math.cos(_math.radians(lat1))*_math.cos(_math.radians(lat2))*_math.sin(dlng/2)**2
    return R * 2 * _math.asin(_math.sqrt(a))

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

SAN DIEGO - OB / POINT LOMA:
- South wind (160-200deg) -> La Jolla Shores protected; OB/PB beach breaks get choppy
- Extreme low tide (<= -1.2ft) -> skip Avalanche south side; use OB pier north sandbar
- Avalanche: SW to W swell (220-280deg) is optimal; pure S or SSW (180-210deg) hits the jetty wrong and closes out; needs W component
- OB Jetty (main north jetty): same window as Avalanche (220-280deg); can be hollower with right sandbar
- OB Pier: W/NW/SW swell; low to mid tide; right peeling into pier is main attraction
- Sunset Cliffs: W swell ideal (270deg), W/NW/SW all work; pure S misses most breaks; low to mid tide; experts only; kelp smooths NW wind chop
- Imperial Beach: SW swell better here than central SD; good S/SW summertime option; medium tides

SAN DIEGO - PB / MISSION:
- Tourmaline/PB/Crystal Pier: W/NW/SW swell; beach breaks and reefs; low to mid tide best
- South wind -> beach breaks get choppy

SAN DIEGO - LA JOLLA:
- Windansea: SW swell ideal (225-250deg); W/NW also works; any tide; localized — respect the crew
- Bird Rock: S/SW swell best (180-240deg); W/NW produces soft peaks at N Bird only; low to mid tide
- Hospitals/Horseshoes: NW/W swell (270-310deg); winter-only; experts only; low tide
- Blacks Beach: any swell with W component; deep canyon attracts all W swell; 2ft to as big as it gets
- La Jolla Shores: W/NW swell best; S wind can blow offshore here (cliff protection); smaller than nearby breaks

SAN DIEGO - DEL MAR / SOLANA:
- Del Mar Rivermouth: best with S/SW; shifting sandbars; good on any direction
- Fletcher Cove/Tide Beach: beach/reef mix; picks up most swells

SAN DIEGO - ENCINITAS / CARDIFF:
- Swami's: W swell ideal (260-280deg); SW also works; pure S/SSW is marginal; right point reef; crowded locals
- Cardiff Reef: WNW swell ideal (280-300deg); W/NW both work; long right point; all tides; kelp possible
- Pipes: W/NW swell; consistent left; low tide best
- Beacons: W swell best; picks up S swell in summer; works on wind swell when long-period is absent
- Grandview: SW swell ideal (225-260deg); consistent reef/beach; less crowded than Swami's
- Seaside Reef: SW swell best; high-performance left; extreme low tide = tubes
- Stone Steps/Moonlight: beach break; picks up most swells; beginner-friendly

SAN DIEGO - CARLSBAD / OCEANSIDE:
- Ponto: jetty sandbars; rights off south jetty on W/NW; lefts off north jetty on S/SW
- Tamarack: beach break; W/NW/SW swell; accessible
- Oceanside Harbor/Jetty: W/NW swell best; hollow peaks near jetty

ORANGE COUNTY / LA:
- Trestles/Lowers: SW swell ideal (225-250deg); works on any swell; world class; always crowded; tide-insensitive
- Trestles/Uppers: W swell best (260-280deg); right point; low tide
- Rincon: WNW swell ideal (285-300deg); classic right point; best Dec-Feb
- Malibu: SW/W swell (230-270deg); right point longboard wave; best S/SW in summer
- Huntington: W/NW/SW swell; beach break; consistent; any tide

CENTRAL / NOR CAL:
- Steamer Lane SC: NW/W swell (280-310deg); world-class reef; winter best
- Pleasure Point SC: W/NW swell; right reef; multiple sections
- Ocean Beach SF: NW/W swell; powerful; experts only
- Mavericks: NW swell (300-320deg) only; big wave; 15ft+ faces; experts/tow-in only

PACIFIC NORTHWEST:
- Seaside OR: SW swell ideal at point (225-250deg); NW also works on beach; most consistent OR; localized
- Westport WA: WSW swell best (240-260deg); beach/jetty; spring/summer best
- Oregon/WA general: powerful beach breaks; cold water (48-54F); thick wetsuits required

EAST COAST:
- Cape Hatteras/OBX: NE/E swell best from nor'easters; S swell also works; most exposed EC spot
- Sebastian Inlet FL: NE swell ideal; N jetty focuses swell into hollow rights
- Manasquan NJ: SSE/SE swell ideal; inlet focuses swell; powerful and hollow; mid rising tide best
- Ruggles RI: SE/E swell; handles biggest hurricane surf on EC; experts only
- East Coast general: needs hurricane swell (summer/fall) or nor'easters (fall/winter) for quality

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


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
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


def pick_nearest_buoys(spots, n=2):
    lats = [s["lat"] for s in spots if "lat" in s]
    lngs = [s["lng"] for s in spots if "lng" in s]
    if not lats: return ALL_BUOYS[:n]
    clat = sum(lats)/len(lats); clng = sum(lngs)/len(lngs)
    return sorted(ALL_BUOYS, key=lambda b: _haversine(clat, clng, b["lat"], b["lng"]))[:n]


def fetch_buoys(spots):
    buoys = pick_nearest_buoys(spots, n=2)
    results = []
    for buoy in buoys:
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
                results.append(f"Buoy {buoy['id']} ({buoy['name']}): no recent wave data")
        except Exception as e:
            results.append(f"Buoy {buoy['id']} ({buoy['name']}): error - {e}")
    return "\n\n".join(results)


def pick_tide_station(spots):
    lats = [s["lat"] for s in spots if "lat" in s]
    lngs = [s["lng"] for s in spots if "lng" in s]
    if not lats: return ALL_TIDE_STATIONS[0]["id"]
    clat = sum(lats)/len(lats); clng = sum(lngs)/len(lngs)
    return min(ALL_TIDE_STATIONS, key=lambda t: _haversine(clat, clng, t["lat"], t["lng"]))["id"]


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
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

        # Cache check
        spot_keys_sorted = sorted(s.get("key","") for s in spots)
        cache_hash = hashlib.md5(",".join(spot_keys_sorted).encode()).hexdigest()[:8]
        window = "now" if now_mode else "dawn"
        date_str = target.strftime("%Y-%m-%d")
        cache_key = f"swell:user:{cache_hash}:{date_str}:{window}"

        if cache_available():
            cached = cache_get(cache_key)
            if cached:
                return _cors(jsonify({"result": cached, "cached": True}))

        # Live fetch
        openmeteo_parts = []
        for spot in spots:
            try: openmeteo_parts.append(fetch_openmeteo(spot, target, now=now_mode))
            except Exception as e: openmeteo_parts.append(f"{spot.get('key','?')}: error - {e}")

        try: buoy_block = fetch_buoys(spots)
        except Exception as e: buoy_block = f"Buoy data unavailable: {e}"

        tide_station = pick_tide_station(spots)
        try: tide_block = fetch_tides(target, tide_station)
        except Exception as e: tide_block = f"Tide data unavailable: {e}"

        spot_names = ", ".join(s.get("key","?") for s in spots)
        result = call_claude("\n\n".join(openmeteo_parts), buoy_block, tide_block, target, spot_names, now_mode)

        if cache_available():
            cache_set(cache_key, result, ttl_seconds=5400)

        return _cors(jsonify({"result": result, "cached": False}))
    except Exception as e:
        return _cors(jsonify({"error": str(e)})), 500


@app.route("/api/cron", methods=["GET","POST"])
@app.route("/api/cron-run", methods=["GET","POST"])
@app.route("/cron", methods=["GET","POST"])
@app.route("/cron-run", methods=["GET","POST"])
def run_cron():
    auth = request.headers.get("Authorization", "")
    cron_secret = os.environ.get("CRON_SECRET", "")
    if cron_secret and auth != f"Bearer {cron_secret}":
        return _cors(jsonify({"error": "Unauthorized"})), 401
    if not cache_available():
        return _cors(jsonify({"error": "Redis not configured"})), 500

    now_pt = datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
    targets = [
        (now_pt + timedelta(days=1), "dawn"),
        (now_pt, "now"),
    ]

    west_spot = [{"lat": 32.7528, "lng": -117.2553}]
    east_spot  = [{"lat": 35.5925, "lng": -75.4658}]
    try: west_buoys = fetch_buoys(west_spot)
    except Exception as e: west_buoys = f"Buoys unavailable: {e}"
    try: east_buoys = fetch_buoys(east_spot)
    except Exception as e: east_buoys = f"Buoys unavailable: {e}"

    results = {"cached": [], "failed": []}

    for target_date, window in targets:
        tide_blocks = {}
        for key, sid in [("west","9410230"),("east","8638610")]:
            try: tide_blocks[key] = fetch_tides(target_date, sid)
            except Exception as e: tide_blocks[key] = f"Tides unavailable: {e}"

        for region_key, region_info in CRON_REGIONS.items():
            date_str = target_date.strftime("%Y-%m-%d")
            cache_key = f"swell:region:{region_key}:{date_str}:{window}"
            is_east = region_info["lng"] > -81
            tz_name = "America/New_York" if is_east else "America/Los_Angeles"
            # Skip if it's dark at this region right now — no point caching
            if not _is_daylight(region_info["lat"], region_info["lng"], tz_name):
                results["cached"].append(f"{cache_key}:skipped-nighttime")
                continue
            spot = {"key": region_key, "lat": region_info["lat"],
                    "lng": region_info["lng"], "name": region_info["name"]}
            try:
                om_block   = fetch_openmeteo(spot, target_date, now=(window=="now"))
                buoy_block = east_buoys if is_east else west_buoys
                tide_block = tide_blocks["east"] if is_east else tide_blocks["west"]
                result = call_claude(om_block, buoy_block, tide_block,
                                     target_date, region_info["name"],
                                     now_mode=(window=="now"))
                cache_set(cache_key, result, ttl_seconds=7200)
                results["cached"].append(cache_key)
            except Exception as e:
                results["failed"].append({"key": cache_key, "error": str(e)})

    return _cors(jsonify({
        "status": "ok",
        "cached": len(results["cached"]),
        "failed": len(results["failed"]),
        "details": results
    }))


def _cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


if __name__ == "__main__":
    app.run(debug=True)
