#!/usr/bin/env python3
"""Fresh Rightmove search via Chrome CDP — direct URL with locationIdentifier.

Bypasses the React typeahead bullshit. Uses known locationIdentifiers and
navigates directly to filtered results pages.
"""

import asyncio
import json
import sys
import urllib.request
import websockets

# locationIdentifier values discovered from Rightmove
ZONES = [
    {"name": "Harpenden",       "outcode": "AL5",  "locId": "REGION^597"},
    {"name": "St Albans",       "outcode": "AL1",  "locId": "REGION^1244"},
    {"name": "Radlett",         "outcode": "WD7",  "locId": "REGION^1108"},
    {"name": "Mill Hill",       "outcode": "NW7",  "locId": "REGION^70364"},
    {"name": "Welwyn Garden City", "outcode": "AL8", "locId": "REGION^1419"},
    {"name": "Brookmans Park",  "outcode": "AL9",  "locId": "REGION^4789"},
    # Extra zones from scorecard top-10
    {"name": "Wheathampstead",  "outcode": "AL4",  "locId": "REGION^1427"},
    {"name": "Sandridge",       "outcode": "AL3",  "locId": "REGION^1177"},
    {"name": "Pinner",          "outcode": "HA5",  "locId": "REGION^934"},
    {"name": "New Barnet",      "outcode": "EN4",  "locId": "REGION^814"},
    {"name": "New Barnet wider","outcode": "EN5",  "locId": "REGION^815"},
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


def build_url(loc_id, min_beds=4, max_price=4000, must_have_garden=True):
    """Build a Rightmove rental search URL with filters."""
    base = "https://www.rightmove.co.uk/property-to-rent/find.html"
    params = [
        f"locationIdentifier={loc_id}",
        f"minBedrooms={min_beds}",
        f"maxPrice={max_price}",
        "propertyTypes=detached%2Csemi-detached%2Cterraced%2Cbungalow",
        "includeLetAgreed=false",
        "dontShow=houseShare%2Cretirement%2Cstudent",
        "furnishTypes=",  # any
    ]
    if must_have_garden:
        params.append("mustHave=garden")
    return base + "?" + "&".join(params)


async def search_zone(ws, mid, zone):
    """Navigate to filtered search and extract listings."""
    name = zone["name"]
    url = build_url(zone["locId"])

    print(f"  {name}: navigating to filtered results...", file=sys.stderr, flush=True)
    await send(ws, mid, "Page.navigate", {"url": url})
    await asyncio.sleep(5)

    # Check we're on results page
    r = await send(ws, mid, "Runtime.evaluate", {
        "expression": "document.title + ' ||| ' + location.href",
        "returnByValue": True
    })
    page_info = r.get("result", {}).get("result", {}).get("value", "")
    print(f"  {name}: {page_info[:100]}", file=sys.stderr, flush=True)

    # Also try without garden filter if no results
    extract_js = """
    (function() {
        var results = [];
        var seen = new Set();

        // Method 1: property links
        var links = document.querySelectorAll('a[href*="/properties/"]');
        links.forEach(function(link) {
            var href = link.href;
            if (!href.includes('/properties/')) return;
            var idMatch = href.match(/\\/properties\\/(\\d+)/);
            if (!idMatch) return;
            var pid = idMatch[1];
            if (seen.has(pid)) return;
            seen.add(pid);

            // Find the containing card
            var card = link.closest('[class*="Card"], [class*="Result"], [class*="listing"], article, [data-test*="property"]');
            if (!card) card = link.parentElement.parentElement.parentElement;
            var text = card ? card.textContent.replace(/\\s+/g, ' ').trim() : '';

            // Price
            var priceMatch = text.match(/£([\\d,]+)\\s*(?:pcm|pm|per calendar month)/i);
            var price = priceMatch ? '£' + priceMatch[1] + ' pcm' : '';

            // Beds
            var bedMatch = text.match(/(\\d+)\\s*bed/i);
            var beds = bedMatch ? bedMatch[1] : '';

            // Type
            var typeMatch = text.match(/(Detached|Semi-Detached|Semi Detached|Terraced|End.of.Terrace|Bungalow)/i);
            var propType = typeMatch ? typeMatch[1] : '';

            // Address — first line-ish
            var addrEl = card ? card.querySelector('address, [class*="address" i], [class*="Address"], h2, [data-test="address"]') : null;
            var address = addrEl ? addrEl.textContent.trim() : '';
            if (!address && text.length > 10) {
                // Try to grab the first meaningful text chunk
                address = text.substring(0, 120);
            }

            // Garden
            var hasGarden = /garden/i.test(text);

            results.push({
                id: pid,
                url: 'https://www.rightmove.co.uk/properties/' + pid,
                price: price,
                beds: beds,
                type: propType,
                address: address.substring(0, 150),
                garden: hasGarden,
                snippet: text.substring(0, 200)
            });
        });

        return JSON.stringify(results.slice(0, 15));
    })()
    """

    r = await send(ws, mid, "Runtime.evaluate", {
        "expression": extract_js,
        "returnByValue": True
    })

    raw = r.get("result", {}).get("result", {}).get("value", "[]")
    try:
        listings = json.loads(raw)
    except json.JSONDecodeError:
        listings = []

    # If no results with garden, try without
    if len(listings) == 0:
        print(f"  {name}: 0 with garden, trying without...", file=sys.stderr, flush=True)
        url_no_garden = build_url(zone["locId"], must_have_garden=False)
        await send(ws, mid, "Page.navigate", {"url": url_no_garden})
        await asyncio.sleep(4)

        r = await send(ws, mid, "Runtime.evaluate", {
            "expression": extract_js,
            "returnByValue": True
        })
        raw = r.get("result", {}).get("result", {}).get("value", "[]")
        try:
            listings = json.loads(raw)
        except json.JSONDecodeError:
            listings = []

    print(f"  {name}: {len(listings)} listings found", file=sys.stderr, flush=True)
    return listings


async def main():
    # Connect to Chrome
    targets = json.loads(urllib.request.urlopen(f"{CDP_URL}/json").read())
    pages = [t for t in targets if t["type"] == "page"]
    if not pages:
        print("No Chrome tabs found!", file=sys.stderr)
        sys.exit(1)

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
                    "locId": zone["locId"],
                    "listings": listings,
                }
            except Exception as e:
                print(f"  {zone['name']}: ERROR {e}", file=sys.stderr, flush=True)
                all_results[zone["name"]] = {
                    "outcode": zone["outcode"],
                    "locId": zone["locId"],
                    "listings": [],
                }
            await asyncio.sleep(2)

    # Save results
    outfile = "out/listings-fresh.json"
    with open(outfile, "w") as f:
        json.dump(all_results, f, indent=2)

    # Summary
    total = sum(len(v["listings"]) for v in all_results.values())
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Total: {total} listings across {len(ZONES)} zones", file=sys.stderr)
    print(f"Saved to {outfile}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    # Print summary table
    for zone_name, data in all_results.items():
        oc = data["outcode"]
        listings = data["listings"]
        if not listings:
            print(f"\n{zone_name} ({oc}): no listings")
            continue
        print(f"\n{'='*60}")
        print(f"{zone_name} ({oc}) — {len(listings)} listings")
        print(f"{'='*60}")
        for l in listings:
            garden = "🌳" if l.get("garden") else "  "
            ptype = l.get("type", "?")[:12]
            print(f"  #{l['id']:>10s}  {l.get('price','?'):>14s}  {l.get('beds','?'):>2s}bed  {ptype:<12s}  {garden}  {l.get('address','')[:60]}")


if __name__ == "__main__":
    asyncio.run(main())
