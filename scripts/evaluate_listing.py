#!/usr/bin/env python3
"""Evaluate a Rightmove listing against the london-scorer scorecard.

Usage:
    python scripts/evaluate_listing.py https://www.rightmove.co.uk/properties/123456789
    python scripts/evaluate_listing.py 123456789
    python scripts/evaluate_listing.py "1 Example Road, Harpenden AL5"
"""

import asyncio
import json
import math
import re
import sys
import urllib.request
import websockets
import pandas as pd

SCORECARD_CSV = "out/zone-scorecard.csv"
CDP_URL = "http://localhost:9222"
WS_TIMEOUT = 12

# Known schools near target zones (Outstanding/Good)
SCHOOLS = {
    "AL5": {"name": "Crabtree Infants", "postcode": "AL55PU", "ofsted": "Outstanding"},
    "AL1": {"name": "Bernards Heath Infant", "postcode": "AL13PR", "ofsted": "Outstanding"},
    "AL3": {"name": "Garden Fields JMI", "postcode": "AL34SG", "ofsted": "Good"},
    "AL4": {"name": "Wheatfields Infants", "postcode": "AL48TD", "ofsted": "Outstanding"},
    "NW7": {"name": "St Paul's CE Primary", "postcode": "NW72BT", "ofsted": "Outstanding"},
    "WD7": {"name": "Hertsmere Jewish Primary", "postcode": "WD78HE", "ofsted": "Outstanding"},
    "AL8": {"name": "Commonswood Primary", "postcode": "AL87QH", "ofsted": "Good"},
    "AL9": {"name": "Brookmans Park School", "postcode": "AL97QE", "ofsted": "Good"},
}

# Known stations
STATIONS = {
    "AL5": "Harpenden Station",
    "AL1": "St Albans City Station",
    "AL3": "St Albans City Station",
    "AL4": "St Albans Abbey Station",
    "NW7": "Mill Hill Broadway Station",
    "WD7": "Radlett Station",
    "AL8": "Welwyn Garden City Station",
    "AL9": "Brookmans Park Station",
    "EN4": "New Barnet Station",
    "EN5": "New Barnet Station",
    "N14": "Southgate Station",
    "N3":  "Finchley Central Station",
}


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def geocode_postcode(pc):
    """Get lat/lon for a UK postcode."""
    pc_clean = pc.replace(" ", "")
    try:
        r = json.loads(urllib.request.urlopen(
            f"https://api.postcodes.io/postcodes/{pc_clean}", timeout=10).read())
        res = r.get("result", {})
        return res.get("latitude"), res.get("longitude")
    except Exception:
        return None, None


def get_zone_data(outcode):
    """Look up zone from scorecard CSV."""
    try:
        df = pd.read_csv(SCORECARD_CSV)
        row = df[df["district"] == outcode]
        if row.empty:
            return None
        return row.iloc[0].to_dict()
    except Exception:
        return None


async def scrape_rightmove(listing_id):
    """Scrape a Rightmove listing page via CDP."""
    targets = json.loads(urllib.request.urlopen(f"{CDP_URL}/json").read())
    ws_url = [t for t in targets if t["type"] == "page"][0]["webSocketDebuggerUrl"]

    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        mid = [0]
        async def s(method, params=None):
            mid[0] += 1
            msg = {"id": mid[0], "method": method}
            if params: msg["params"] = params
            await ws.send(json.dumps(msg))
            dl = asyncio.get_event_loop().time() + WS_TIMEOUT
            while asyncio.get_event_loop().time() < dl:
                try:
                    r = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
                    if r.get("id") == mid[0]: return r
                except asyncio.TimeoutError: return {}
            return {}

        await s("Page.enable")
        await s("Runtime.enable")

        url = f"https://www.rightmove.co.uk/properties/{listing_id}"
        await s("Page.navigate", {"url": url})
        await asyncio.sleep(5)

        r = await s("Runtime.evaluate", {"expression": """
            (function() {
                var d = {};

                // Address — use itemprop or h1 (most reliable on Rightmove)
                var addr = document.querySelector('[itemprop="streetAddress"]');
                d.address = addr ? addr.textContent.trim() : '';
                if (!d.address) {
                    var h1 = document.querySelector('h1');
                    if (h1) d.address = h1.textContent.trim();
                }

                // Parse title for structured data: "4 bedroom detached house for rent in ..."
                var title = document.title || '';
                var titleMatch = title.match(/(\d+)\s*bedroom\s+([\w\s-]+?)\s+for\s+rent/i);
                if (titleMatch) {
                    d.beds = titleMatch[1];
                    d.type = titleMatch[2].trim();
                }

                // Price from meta description or page
                var meta = document.querySelector('meta[name="description"]');
                var metaContent = meta ? meta.content : '';
                var text = document.body.innerText;

                var priceMatch = text.match(/£([\d,]+)\s*(?:pcm|per calendar month)/i);
                d.price = priceMatch ? '£' + priceMatch[1] + ' pcm' : '';

                // Fallback beds/type from body text if not from title
                if (!d.beds) {
                    var bedsMatch = text.match(/(\d+)\s*(?:bed|bedroom)/i);
                    d.beds = bedsMatch ? bedsMatch[1] : '';
                }
                if (!d.type) {
                    var typeMatch = text.match(/(Detached|Semi-Detached|Semi Detached|Terraced|End.of.Terrace|Bungalow|Flat|Maisonette)/i);
                    d.type = typeMatch ? typeMatch[1] : '';
                }

                var bathMatch = text.match(/(\d+)\s*(?:bath|bathroom)/i);
                d.baths = bathMatch ? bathMatch[1] : '';

                // Garden
                d.garden = /garden/i.test(text) ? 'Yes' : 'No';

                // EPC sqm if present
                var sqmMatch = text.match(/(\d+)\s*(?:sq\.?\s*m|m²|sqm)/i);
                d.sqm = sqmMatch ? sqmMatch[1] : '';

                // Postcode from address
                var pcMatch = d.address.match(/([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})/i);
                d.postcode = pcMatch ? pcMatch[1].trim() : '';
                if (!d.postcode) {
                    var ocMatch = d.address.match(/([A-Z]{1,2}\d[A-Z\d]?)(?:\s|$|,)/i);
                    d.outcode = ocMatch ? ocMatch[1].trim() : '';
                }

                // Key features
                var features = [];
                document.querySelectorAll('[class*="feature" i] li, [class*="keyFeature" i] li, [class*="Key"] li').forEach(function(li) {
                    features.push(li.textContent.trim());
                });
                d.features = features.slice(0, 10).join(' | ');

                // Agent — from "MARKETED BY" section
                var agentEls = document.querySelectorAll('[class*="agent" i], [class*="marketed" i]');
                var agentText = '';
                agentEls.forEach(function(el) {
                    var t = el.textContent.trim();
                    if (t.length > 5 && t.length < 100 && !agentText) agentText = t;
                });
                d.agent = agentText.replace(/MARKETED BY\s*/i, '').substring(0, 60);

                var agentPhone = document.querySelector('a[href^="tel:"]');
                d.agent_phone = agentPhone ? agentPhone.textContent.trim() : '';

                return JSON.stringify(d);
            })()
        """, "returnByValue": True})

        raw = r.get("result", {}).get("result", {}).get("value", "{}")
        return json.loads(raw)


def format_distance(meters):
    if meters < 1000:
        return f"{int(meters)}m"
    return f"{meters/1000:.1f}km"


def evaluate(listing_data):
    """Combine listing data with zone scorecard data."""
    # Get postcode / outcode
    postcode = listing_data.get("postcode", "")
    outcode = listing_data.get("outcode", "")
    if postcode and not outcode:
        outcode = postcode.split()[0] if " " in postcode else postcode[:3]
    if not outcode:
        # Try to extract from address
        addr = listing_data.get("address", "")
        m = re.search(r'\b([A-Z]{1,2}\d[A-Z\d]?)\s*\d[A-Z]{2}\b', addr, re.I)
        if m:
            outcode = m.group(1).upper()
            postcode = m.group(0).upper()
        else:
            m = re.search(r'\b([A-Z]{1,2}\d[A-Z\d]?)\b', addr, re.I)
            if m:
                outcode = m.group(1).upper()

    # Geocode
    lat, lon = None, None
    if postcode:
        lat, lon = geocode_postcode(postcode)
    if lat is None and outcode:
        try:
            r = json.loads(urllib.request.urlopen(
                f"https://api.postcodes.io/outcodes/{outcode}", timeout=10).read())
            res = r.get("result", {})
            lat, lon = res.get("latitude"), res.get("longitude")
        except Exception:
            pass

    # Zone data from scorecard
    zone = get_zone_data(outcode) if outcode else None

    # Distance to nearest station
    station_dist = None
    station_name = STATIONS.get(outcode)
    if station_name and lat and lon:
        slat, slon = geocode_postcode(station_name.replace(" ", "+").split("+")[0] + " station")
        # Use known station postcodes instead
        station_pcs = {
            "Harpenden Station": "AL54SP",
            "St Albans City Station": "AL15HE",
            "Mill Hill Broadway Station": "NW72JU",
            "Radlett Station": "WD77AP",
            "Welwyn Garden City Station": "AL86HA",
            "Brookmans Park Station": "AL97SS",
        }
        spc = station_pcs.get(station_name)
        if spc:
            slat, slon = geocode_postcode(spc)
            if slat:
                station_dist = haversine_m(lat, lon, slat, slon)

    # Distance to nearest good school
    school_dist = None
    school_info = SCHOOLS.get(outcode)
    if school_info and lat and lon:
        schlat, schlon = geocode_postcode(school_info["postcode"])
        if schlat:
            school_dist = haversine_m(lat, lon, schlat, schlon)

    # Crabtree catchment check (only for AL5)
    in_crabtree = None
    crabtree_dist = None
    if outcode == "AL5" and lat and lon:
        clat, clon = geocode_postcode("AL55PU")
        if clat:
            crabtree_dist = haversine_m(lat, lon, clat, clon)
            in_crabtree = crabtree_dist < 1500  # conservative catchment

    return {
        "listing": listing_data,
        "outcode": outcode,
        "postcode": postcode,
        "lat": lat,
        "lon": lon,
        "zone": zone,
        "station_name": station_name,
        "station_dist": station_dist,
        "school_info": school_info,
        "school_dist": school_dist,
        "in_crabtree": in_crabtree,
        "crabtree_dist": crabtree_dist,
    }


def print_card(ev):
    """Print a formatted evaluation card."""
    l = ev["listing"]
    z = ev["zone"]

    print()
    print("=" * 65)
    addr = l.get("address", "Unknown address")
    print(f"📍 {addr}")
    print("-" * 65)

    # Price, beds, type, garden
    parts = []
    if l.get("price"): parts.append(f"💰 {l['price']}")
    if l.get("beds"): parts.append(f"{l['beds']} bed")
    if l.get("type"): parts.append(l["type"])
    if l.get("garden") == "Yes": parts.append("Garden ✅")
    else: parts.append("Garden ❓")
    print(" · ".join(parts))

    if l.get("sqm"):
        print(f"📐 {l['sqm']} sqm (from listing)")

    if l.get("agent"):
        phone = f" — {l['agent_phone']}" if l.get("agent_phone") else ""
        print(f"🏢 {l['agent']}{phone}")

    if l.get("features"):
        print(f"✨ {l['features'][:120]}")

    print()

    # Station
    if ev["station_name"] and ev["station_dist"]:
        walk_min = int(ev["station_dist"] / 80)  # ~80m/min walking
        print(f"🚆 {ev['station_name']}: {format_distance(ev['station_dist'])} ({walk_min}min walk)")

    # School
    if ev["school_info"] and ev["school_dist"]:
        si = ev["school_info"]
        walk_min = int(ev["school_dist"] / 80)
        print(f"🏫 {si['name']} ({si['ofsted']}): {format_distance(ev['school_dist'])} ({walk_min}min walk)")

    # Crabtree specific
    if ev["in_crabtree"] is not None:
        status = "✅ IN catchment" if ev["in_crabtree"] else "⚠️ possibly outside catchment"
        print(f"🏫 Crabtree Infants: {format_distance(ev['crabtree_dist'])} — {status}")

    print()

    # Zone scorecard data
    if z:
        oc = ev["outcode"]
        rank = "#?"
        try:
            df = pd.read_csv(SCORECARD_CSV)
            rank_n = int((df["score"] >= z["score"]).sum())
            rank = f"#{rank_n}"
        except Exception:
            pass

        crime_icon = "✅ low" if z["crime_1mi_count"] < 200 else ("⚠️ medium" if z["crime_1mi_count"] < 500 else "🔴 high")
        print(f"📊 Zone {oc} — Rank {rank} (score {z['score']:.3f})")
        print(f"   🚇 Commute KX: {int(z['commute_am'])}min AM / {int(z['commute_pm'])}min PM")
        print(f"   🏠 Zone median: {z['epc_median_sqm']:.0f}m² · {z['pct_detached']:.0%} detached")
        print(f"   🏫 School quality: {int(z['school_quality'])}")
        print(f"   🔒 Crime (1mi): {int(z['crime_1mi_count'])} {crime_icon}")
    else:
        print(f"📊 Zone {ev['outcode'] or '?'} — not in scorecard")

    print("=" * 65)
    print()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/evaluate_listing.py <rightmove-url-or-id-or-address>")
        sys.exit(1)

    arg = sys.argv[1]

    # Parse input: URL, ID, or address
    listing_id = None
    address = None

    if "rightmove" in arg:
        m = re.search(r'/properties/(\d+)', arg)
        if m:
            listing_id = m.group(1)
    elif arg.isdigit():
        listing_id = arg
    else:
        address = arg

    if listing_id:
        print(f"Scraping Rightmove #{listing_id}...", flush=True)
        listing_data = await scrape_rightmove(listing_id)
    elif address:
        # Manual address — create minimal listing data
        listing_data = {"address": address, "price": "", "beds": "", "type": "", "garden": ""}
        # Try to extract postcode
        m = re.search(r'([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})', address, re.I)
        if m:
            listing_data["postcode"] = m.group(1).upper()
        else:
            m = re.search(r'([A-Z]{1,2}\d[A-Z\d]?)\b', address, re.I)
            if m:
                listing_data["outcode"] = m.group(1).upper()
    else:
        print("Could not parse input. Provide a Rightmove URL, property ID, or address.")
        sys.exit(1)

    ev = evaluate(listing_data)
    print_card(ev)


if __name__ == "__main__":
    asyncio.run(main())
