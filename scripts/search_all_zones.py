#!/usr/bin/env python3
"""Expanded Rightmove search — all zones with score >= 50 and crime < 500.

Direct URL with locationIdentifier — no React typeahead bullshit.
"""

import asyncio
import json
import sys
import urllib.request
import websockets

# All zones worth searching — score >= 50, crime < 500
ZONES = [
    # Herts core
    {"name": "Harpenden",           "outcode": "AL5",  "locId": "REGION^597"},
    {"name": "St Albans",           "outcode": "AL1",  "locId": "REGION^1244"},
    {"name": "Radlett",             "outcode": "WD7",  "locId": "REGION^1108"},
    # North London
    {"name": "Mill Hill",           "outcode": "NW7",  "locId": "REGION^70364"},
    {"name": "Pinner",             "outcode": "HA5",  "locId": "REGION^934"},
    {"name": "Finchley",           "outcode": "N3",   "locId": "REGION^61095"},
    {"name": "North Finchley",     "outcode": "N12",  "locId": "REGION^70359"},
    {"name": "Barnet",             "outcode": "EN5",  "locId": "REGION^815"},
    {"name": "Cockfosters",        "outcode": "EN4",  "locId": "REGION^814"},
    {"name": "Hampstead Garden Suburb", "outcode": "NW11", "locId": "REGION^70362"},
    {"name": "Cricklewood",        "outcode": "NW2",  "locId": "REGION^70355"},
    {"name": "Hampstead",          "outcode": "NW3",  "locId": "REGION^70356"},
    {"name": "Edgware",            "outcode": "HA8",  "locId": "REGION^454"},
]

WS_TIMEOUT = 12
CDP_URL = "http://localhost:9222"


async def send(ws, mid, method, params=None):
    mid[0] += 1
    msg = {"id": mid[0], "method": method}
    if params:
        msg["params"] = params
    await ws.send(json.dumps(msg))
    deadline = asyncio.get_event_loop().time() + WS_TIMEOUT
    while asyncio.get_event_loop().time() < deadline:
        try:
            r = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
            if r.get("id") == mid[0]:
                return r
        except asyncio.TimeoutError:
            return {}
    return {}


def build_url(loc_id, min_beds=4, max_price=4000):
    base = "https://www.rightmove.co.uk/property-to-rent/find.html"
    params = [
        f"locationIdentifier={loc_id}",
        f"minBedrooms={min_beds}",
        f"maxPrice={max_price}",
        "propertyTypes=detached%2Csemi-detached%2Cterraced%2Cbungalow",
        "includeLetAgreed=false",
        "dontShow=houseShare%2Cretirement%2Cstudent",
    ]
    return base + "?" + "&".join(params)


EXTRACT_JS = """
(function() {
    var results = [];
    var seen = new Set();
    var links = document.querySelectorAll('a[href*="/properties/"]');
    links.forEach(function(link) {
        var href = link.href;
        if (!href.includes('/properties/')) return;
        var idMatch = href.match(/\\/properties\\/(\\d+)/);
        if (!idMatch) return;
        var pid = idMatch[1];
        if (seen.has(pid)) return;
        seen.add(pid);
        var card = link.closest('[class*="Card"], [class*="Result"], [class*="listing"], article, [data-test*="property"]');
        if (!card) card = link.parentElement.parentElement.parentElement;
        var text = card ? card.textContent.replace(/\\s+/g, ' ').trim() : '';
        var priceMatch = text.match(/£([\\d,]+)\\s*(?:pcm|pm|per calendar month)/i);
        var price = priceMatch ? '£' + priceMatch[1] + ' pcm' : '';
        var bedMatch = text.match(/(\\d+)\\s*bed/i);
        var beds = bedMatch ? bedMatch[1] : '';
        var typeMatch = text.match(/(Detached|Semi-Detached|Semi Detached|Terraced|End.of.Terrace|Bungalow)/i);
        var propType = typeMatch ? typeMatch[1] : '';
        var addrEl = card ? card.querySelector('address, [class*="address" i], h2, [data-test="address"]') : null;
        var address = addrEl ? addrEl.textContent.trim() : '';
        if (!address && text.length > 10) address = text.substring(0, 120);
        var hasGarden = /garden/i.test(text);
        results.push({
            id: pid,
            url: 'https://www.rightmove.co.uk/properties/' + pid,
            price: price, beds: beds, type: propType,
            address: address.substring(0, 150),
            garden: hasGarden
        });
    });
    return JSON.stringify(results.slice(0, 20));
})()
"""


async def search_zone(ws, mid, zone):
    name = zone["name"]
    url = build_url(zone["locId"])
    print(f"  {name}: searching...", file=sys.stderr, flush=True)
    await send(ws, mid, "Page.navigate", {"url": url})
    await asyncio.sleep(5)

    r = await send(ws, mid, "Runtime.evaluate", {
        "expression": "document.title",
        "returnByValue": True
    })
    title = r.get("result", {}).get("result", {}).get("value", "")
    print(f"  {name}: {title[:60]}", file=sys.stderr, flush=True)

    r = await send(ws, mid, "Runtime.evaluate", {
        "expression": EXTRACT_JS,
        "returnByValue": True
    })
    raw = r.get("result", {}).get("result", {}).get("value", "[]")
    try:
        listings = json.loads(raw)
    except json.JSONDecodeError:
        listings = []

    print(f"  {name}: {len(listings)} listings", file=sys.stderr, flush=True)
    return listings


async def main():
    targets = json.loads(urllib.request.urlopen(f"{CDP_URL}/json").read())
    pages = [t for t in targets if t["type"] == "page"]
    ws_url = pages[0]["webSocketDebuggerUrl"]
    mid = [0]

    all_results = {}

    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        await send(ws, mid, "Page.enable")
        await send(ws, mid, "Runtime.enable")

        for zone in ZONES:
            try:
                listings = await search_zone(ws, mid, zone)
                all_results[zone["name"]] = {
                    "outcode": zone["outcode"],
                    "listings": listings,
                }
            except Exception as e:
                print(f"  {zone['name']}: ERROR {e}", file=sys.stderr, flush=True)
                all_results[zone["name"]] = {"outcode": zone["outcode"], "listings": []}
            await asyncio.sleep(2)

    outfile = "out/listings-all-zones.json"
    with open(outfile, "w") as f:
        json.dump(all_results, f, indent=2)

    total = sum(len(v["listings"]) for v in all_results.values())
    print(f"\nTotal: {total} listings across {len(ZONES)} zones", file=sys.stderr)
    print(f"Saved to {outfile}", file=sys.stderr)

    # Print summary
    for zone_name, data in all_results.items():
        oc = data["outcode"]
        listings = data["listings"]
        if not listings:
            continue
        print(f"\n=== {zone_name} ({oc}) — {len(listings)} listings ===")
        for l in listings:
            garden = "🌳" if l.get("garden") else "  "
            print(f"  #{l['id']:>10s}  {l.get('price','?'):>14s}  {l.get('beds','?'):>2s}bed  {l.get('type','?')[:12]:<12s}  {garden}  {l.get('address','')[:60]}")


if __name__ == "__main__":
    asyncio.run(main())
