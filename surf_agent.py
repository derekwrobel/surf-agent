#!/usr/bin/env python3
"""
SD Surf Agent
Cross-references three data sources for a reliable dawn patrol recommendation:
  1. Open-Meteo  — hourly wave/wind forecast per spot (free, no key)
  2. NOAA Buoys  — real-time measured swell offshore (free, no key)
  3. NOAA Tides  — tide predictions for La Jolla station (free, no key)

Usage:
    python surf_agent.py                    # check default spots
    python surf_agent.py --all              # check all spots
    python surf_agent.py --spots ob_pier avalanche lj_shores swamis
    python surf_agent.py --date 2           # days ahead (default: 1 = tomorrow)
    python surf_agent.py --list             # show all spot keys

Requires:
    pip install anthropic requests
    ANTHROPIC_API_KEY environment variable set
"""

import os
import sys
import argparse
import requests
from datetime import datetime, timedelta
import anthropic

# ---------------------------------------------------------------------------
# Spot definitions
# ---------------------------------------------------------------------------
ZONES = {
    "OB / Point Loma": [
        {"key": "sunset_cliffs", "name": "Sunset Cliffs",    "lat": 32.7215, "lng": -117.2568, "note": "Reef · W/SW swell"},
        {"key": "ob_pier",       "name": "OB Pier",          "lat": 32.7528, "lng": -117.2553, "note": "Home base"},
        {"key": "avalanche",     "name": "Avalanche",        "lat": 32.7510, "lng": -117.2560, "note": "SW/W swell 197-307°"},
    ],
    "Mission / PB": [
        {"key": "mission",  "name": "Mission Beach", "lat": 32.7662, "lng": -117.2525, "note": "Beach break"},
        {"key": "pb_dr",    "name": "PB Dr.",        "lat": 32.7795, "lng": -117.2510, "note": "Beach break"},
        {"key": "crystal",  "name": "Crystal Pier",  "lat": 32.7882, "lng": -117.2527, "note": "PB pier break"},
        {"key": "tourm",    "name": "Tourmaline",    "lat": 32.7972, "lng": -117.2597, "note": "Longboard friendly"},
    ],
    "La Jolla": [
        {"key": "lj_shores", "name": "La Jolla Shores", "lat": 32.8572, "lng": -117.2567, "note": "Protected south wind"},
        {"key": "blacks",    "name": "Blacks Beach",    "lat": 32.8789, "lng": -117.2519, "note": "Uncrowded · hike in"},
        {"key": "scripps",   "name": "Scripps Pier",   "lat": 32.8664, "lng": -117.2541, "note": "N La Jolla"},
    ],
    "Del Mar": [
        {"key": "delmar_15",    "name": "Del Mar 15th St",    "lat": 32.9561, "lng": -117.2719, "note": "Town beach break"},
        {"key": "delmar_river", "name": "Del Mar Rivermouth", "lat": 32.9609, "lng": -117.2739, "note": "Shifting sandbars"},
        {"key": "delmar_29",    "name": "Del Mar 29th St",    "lat": 32.9680, "lng": -117.2724, "note": "N Del Mar peaks"},
    ],
    "Encinitas": [
        {"key": "cardiff",   "name": "Cardiff",   "lat": 33.0136, "lng": -117.2820, "note": "Reef · long rides"},
        {"key": "swamis",    "name": "Swami's",   "lat": 33.0367, "lng": -117.2921, "note": "Reef · best W swell"},
        {"key": "grandview", "name": "Grandview", "lat": 33.0574, "lng": -117.2940, "note": "Reef · consistent"},
    ],
}

DEFAULT_KEYS = {"ob_pier", "avalanche", "tourm", "lj_shores"}
ALL_SPOTS    = [s for spots in ZONES.values() for s in spots]
SPOT_BY_KEY  = {s["key"]: s for s in ALL_SPOTS}

# ---------------------------------------------------------------------------
# NOAA station config
# ---------------------------------------------------------------------------
# Tide station: La Jolla (9410230)
NOAA_TIDE_STATION = "9410230"

# Buoys — listed closest-to-farthest from SD
NOAA_BUOYS = [
    {"id": "46224", "name": "Offshore Encinitas",    "note": "~10mi offshore, closest to SD spots"},
    {"id": "46025", "name": "Santa Monica Basin",    "note": "tracks approaching NW groundswell"},
    {"id": "46086", "name": "San Clemente Island",   "note": "catches S/SW swell from Mexico"},
]

# ---------------------------------------------------------------------------
# Data source 1: Open-Meteo — per-spot hourly forecast
# ---------------------------------------------------------------------------
def fetch_openmeteo(spot: dict, target_date: datetime) -> str:
    params = {
        "latitude":  spot["lat"],
        "longitude": spot["lng"],
        "hourly": ",".join([
            "wave_height", "wave_period", "wave_direction",
            "swell_wave_height", "swell_wave_period", "swell_wave_direction",
            "wind_speed_10m", "wind_direction_10m",
        ]),
        "wind_speed_unit": "mph",
        "timezone":     "America/Los_Angeles",
        "forecast_days": max(2, (target_date.date() - datetime.now().date()).days + 1),
    }
    resp = requests.get("https://marine-api.open-meteo.com/v1/marine", params=params, timeout=10)
    resp.raise_for_status()
    hourly = resp.json()["hourly"]
    date_str = target_date.strftime("%Y-%m-%d")

    lines = []
    for i, t in enumerate(hourly["time"]):
        if not t.startswith(date_str):
            continue
        hour = int(t[11:13])
        if 5 <= hour <= 8:
            wh   = hourly["wave_height"][i]           or 0
            wp   = hourly["wave_period"][i]           or 0
            wd   = hourly["wave_direction"][i]        or 0
            swh  = hourly["swell_wave_height"][i]     or 0
            swp  = hourly["swell_wave_period"][i]     or 0
            swd  = hourly["swell_wave_direction"][i]  or 0
            ws   = hourly["wind_speed_10m"][i]        or 0
            wdir = hourly["wind_direction_10m"][i]    or 0
            lines.append(
                f"  {t[11:16]}: wave {wh:.1f}m/{wp:.0f}s/{wd:.0f}° | "
                f"swell {swh:.1f}m {swp:.0f}s from {swd:.0f}° | "
                f"wind {ws:.0f}mph from {wdir:.0f}°"
            )

    if not lines:
        return f"{spot['name']}: no dawn data"
    return f"{spot['name']} ({spot['note']}):\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Data source 2: NOAA Buoys — real-time measured swell
# ---------------------------------------------------------------------------
def fetch_buoys() -> str:
    """
    Pulls the last 5 observations from each buoy via NDBC realtime2 txt files.
    Fields: YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP DEWP VIS PTDY TIDE
    We care about: WVHT (wave height m), DPD (dominant period s), MWD (mean wave direction °)
    """
    results = []
    for buoy in NOAA_BUOYS:
        url = f"https://www.ndbc.noaa.gov/data/realtime2/{buoy['id']}.txt"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            lines = resp.text.strip().splitlines()

            # Line 0 = header, line 1 = units, lines 2+ = data (newest first)
            header = lines[0].lstrip("#").split()
            data_lines = [l for l in lines[2:] if not l.startswith("#")][:5]

            readings = []
            for row in data_lines:
                cols = row.split()
                if len(cols) < len(header):
                    continue
                row_dict = dict(zip(header, cols))
                wvht = row_dict.get("WVHT", "MM")
                dpd  = row_dict.get("DPD",  "MM")
                mwd  = row_dict.get("MWD",  "MM")
                wspd = row_dict.get("WSPD", "MM")
                wdir = row_dict.get("WDIR", "MM")
                yr   = row_dict.get("YY",   "??")
                mo   = row_dict.get("MM",   "??")
                dy   = row_dict.get("DD",   "??")
                hh   = row_dict.get("hh",   "??")
                mm_t = row_dict.get("mm",   "??")

                # Skip rows with missing wave data
                if wvht == "MM" or dpd == "MM":
                    continue

                wvht_ft = float(wvht) * 3.28084
                readings.append(
                    f"  {mo}/{dy} {hh}:{mm_t}Z — "
                    f"{wvht_ft:.1f}ft @ {dpd}s from {mwd}° | wind {wspd}mph/{wdir}°"
                )

            if readings:
                results.append(
                    f"Buoy {buoy['id']} ({buoy['name']}) — {buoy['note']}:\n"
                    + "\n".join(readings[:3])  # last 3 obs
                )
            else:
                results.append(f"Buoy {buoy['id']} ({buoy['name']}): no recent wave data")

        except Exception as e:
            results.append(f"Buoy {buoy['id']} ({buoy['name']}): error — {e}")

    return "\n\n".join(results)


# ---------------------------------------------------------------------------
# Data source 3: NOAA Tides — tide predictions for target day
# ---------------------------------------------------------------------------
def fetch_tides(target_date: datetime) -> str:
    """
    Fetches hourly tide predictions from NOAA CO-OPS for La Jolla station.
    Also fetches hi/lo events for the day.
    """
    date_str = target_date.strftime("%Y%m%d")

    # Hourly predictions 4am–9am
    hourly_params = {
        "begin_date":  date_str,
        "end_date":    date_str,
        "station":     NOAA_TIDE_STATION,
        "product":     "predictions",
        "datum":       "MLLW",
        "time_zone":   "lst_ldt",
        "interval":    "h",
        "units":       "english",
        "application": "surf_agent",
        "format":      "json",
    }
    # Hi/lo events
    hilo_params  = {**hourly_params, "interval": "hilo"}

    try:
        hourly_resp = requests.get(
            "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter",
            params=hourly_params, timeout=10
        )
        hourly_resp.raise_for_status()
        hourly_data = hourly_resp.json().get("predictions", [])

        hilo_resp = requests.get(
            "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter",
            params=hilo_params, timeout=10
        )
        hilo_resp.raise_for_status()
        hilo_data = hilo_resp.json().get("predictions", [])

    except Exception as e:
        return f"NOAA Tides: error — {e}"

    # Dawn window hourly (5am–8am)
    dawn_lines = []
    for p in hourly_data:
        t = p.get("t", "")
        v = float(p.get("v", 0))
        hour = int(t[11:13]) if len(t) >= 13 else -1
        if 5 <= hour <= 8:
            dawn_lines.append(f"  {t[11:16]}: {v:+.2f} ft")

    # All hi/lo events for the day
    hilo_lines = []
    for p in hilo_data:
        t    = p.get("t", "")
        v    = float(p.get("v", 0))
        kind = "HIGH" if p.get("type") == "H" else "LOW "
        hilo_lines.append(f"  {kind} {t[11:16]}: {v:+.2f} ft")

    # Flag extreme low tide
    lows = [float(p["v"]) for p in hilo_data if p.get("type") == "L"]
    warning = ""
    if any(l <= -1.2 for l in lows):
        worst = min(lows)
        warning = f"\n  ⚠️  EXTREME LOW TIDE ({worst:+.2f} ft) — skip Avalanche south side, use OB pier north sandbar"

    lines = [f"NOAA Tides — La Jolla station ({NOAA_TIDE_STATION}), {target_date.strftime('%A %b')} {target_date.day}:"]
    if hilo_lines:
        lines.append("  Hi/Lo events:")
        lines.extend(hilo_lines)
    if dawn_lines:
        lines.append("  Dawn patrol window (5–8 AM):")
        lines.extend(dawn_lines)
    if warning:
        lines.append(warning)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude recommendation
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a surf forecast AI agent for an experienced San Diego surfer who surfs ~90% of days and does dawn patrol (5:30–7 AM window).

You will receive three data sources — cross-reference them for a reliable picture:
- Open-Meteo: hourly model forecast per spot (wave height/period/direction, wind)
- NOAA Buoys: real measured swell offshore right now (ground truth for what's actually in the water)
- NOAA Tides: tide heights and hi/lo events for La Jolla

When buoy data and model data differ, weight the buoy more heavily for current conditions and use the model for timing/trend.

LOCAL KNOWLEDGE:
- South wind (160–200°) → La Jolla Shores is protected; OB/PB beach breaks get choppy
- Extreme low tide (≤ −1.2 ft) → skip Avalanche south side, use OB pier north sandbar peaks
- Avalanche optimal swell: 197–307° (SSW/SW/W) — north/NW swell misses it
- Sunset Cliffs: reef, needs solid W/SW groundswell, very tide-sensitive, sharky at dawn
- Blacks Beach: exposed to all swells, uncrowded, hike down required
- Del Mar Rivermouth: best with S/SW swell, shifting sandbars
- Swami's: reef, best W swell, can be crowded with locals
- Cardiff Reef: long rides on W/NW swell, kelp can be an issue
- Grandview: consistent reef, less crowded than Swami's
- Wind: offshore = easterly (~90°); onshore (blown out) = westerly (~270°); dawn is often glassy in summer
- Wave period: >12s = quality groundswell; 8–12s = moderate; <8s = wind swell/choppy
- Good dawn height: 0.5–2m (1.5–6ft). Under 0.3m = flat. Over 3m = big day

The surfer goes almost every day — never say "stay home", always rank and recommend.

Output format:

DAWN PATROL — [Day, Month Date]
Conditions: [1-sentence cross-referenced swell/wind summary — note if buoy confirms or contradicts model]

RANKED SPOTS
1. [Spot name] ★★★★★  [height ft] | [period]s | [swell dir]° | wind [speed]mph [dir]° | tide [ft]
   [One sentence: why it's #1 today]
2. [Spot name] ★★★★☆  ...
   [One sentence]
... (all checked spots, best to worst)

SKIP (flat or blown out):
- [Spot name]: [one-word reason]

Notes: [Tide warnings, crowd notes, buoy vs model discrepancies, anything worth flagging. 2-3 sentences max.]

Use ★ ratings: 5=pumping, 4=good, 3=decent, 2=marginal, 1=barely surfable.
Convert wave height to feet (1m = 3.28ft). Be direct and specific."""


def get_recommendation(openmeteo_block: str, buoy_block: str, tide_block: str, target_date: datetime) -> str:
    client = anthropic.Anthropic()
    date_label = f"{target_date.strftime('%A, %B')} {target_date.day}"

    user_content = f"""Rank all checked spots for dawn patrol on {date_label}.

━━━ SOURCE 1: Open-Meteo forecast (model) ━━━
{openmeteo_block}

━━━ SOURCE 2: NOAA Buoy readings (measured) ━━━
{buoy_block}

━━━ SOURCE 3: NOAA Tide predictions ━━━
{tide_block}
"""
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}]
    )
    return message.content[0].text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="SD Surf Agent — dawn patrol recommender")
    parser.add_argument("--spots", nargs="+", metavar="KEY",
                        help="Spot keys to check (e.g. ob_pier avalanche swamis)")
    parser.add_argument("--all",  action="store_true", help="Check all spots")
    parser.add_argument("--date", type=int, default=1, metavar="DAYS",
                        help="Days ahead to forecast (default: 1 = tomorrow)")
    parser.add_argument("--list", action="store_true", help="List all spot keys and exit")
    args = parser.parse_args()

    if args.list:
        for zone, spots in ZONES.items():
            print(f"\n{zone}:")
            for s in spots:
                marker = " *" if s["key"] in DEFAULT_KEYS else ""
                print(f"  {s['key']:<18} {s['name']}{marker}")
        print("\n* = dawn patrol defaults")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        sys.exit(1)

    # Resolve spot list
    if args.all:
        spots = ALL_SPOTS
    elif args.spots:
        spots = []
        for k in args.spots:
            if k not in SPOT_BY_KEY:
                print(f"Unknown spot key: {k}  (run --list to see all keys)")
                sys.exit(1)
            spots.append(SPOT_BY_KEY[k])
    else:
        spots = [SPOT_BY_KEY[k] for k in DEFAULT_KEYS]

    target_date = datetime.now() + timedelta(days=args.date)
    date_label  = f"{target_date.strftime('%A, %B')} {target_date.day}"

    print(f"\n🌊  SD Surf Agent — {date_label} dawn patrol")
    print(f"    Spots   : {', '.join(s['name'] for s in spots)}")
    print(f"    Sources : Open-Meteo · NOAA Buoys (46224, 46025, 46086) · NOAA Tides (La Jolla)\n")

    # --- Open-Meteo ---
    print("📡  Open-Meteo forecast:")
    openmeteo_parts = []
    for spot in spots:
        print(f"  → {spot['name']}...", end=" ", flush=True)
        try:
            result = fetch_openmeteo(spot, target_date)
            openmeteo_parts.append(result)
            print("✓")
        except Exception as e:
            openmeteo_parts.append(f"{spot['name']}: error — {e}")
            print(f"✗ {e}")
    openmeteo_block = "\n\n".join(openmeteo_parts)

    # --- NOAA Buoys ---
    print("\n🔴  NOAA Buoy readings:")
    for b in NOAA_BUOYS:
        print(f"  → Buoy {b['id']} ({b['name']})...", end=" ", flush=True)
    buoy_block = fetch_buoys()
    print("✓")

    # --- NOAA Tides ---
    print("\n🌊  NOAA Tide predictions:")
    print(f"  → Station {NOAA_TIDE_STATION} (La Jolla)...", end=" ", flush=True)
    tide_block = fetch_tides(target_date)
    print("✓")

    # --- Claude ---
    print("\n🤖  Claude analyzing all sources...")
    try:
        recommendation = get_recommendation(openmeteo_block, buoy_block, tide_block, target_date)
    except Exception as e:
        print(f"  ✗ Claude API error: {e}")
        sys.exit(1)

    print(f"\n{'━' * 55}")
    print(recommendation)
    print(f"{'━' * 55}\n")


if __name__ == "__main__":
    main()
