#!/usr/bin/env python3
"""Search Rightmove for rental listings via Chrome CDP (localhost:9222).

Uses Input.insertText to type into Rightmove's React search, clicks the first
autocomplete suggestion, navigates to filtered results, and extracts listings.
"""

import asyncio
import json
import sys
import urllib.request
import websockets

ZONES = [
    {"name": "Harpenden", "outcode": "AL5"},
    {"name": "Radlett", "outcode": "WD7"},
    {"name": "St Albans", "outcode": "AL1"},
    {"name": "Mill Hill, London", "outcode": "NW7"},
    {"name": "Welwyn Garden City", "outcode": "AL8"},
    {"name": "Brookmans Park", "outcode": "AL9"},
]

WS_TIMEOUT = 8


async def send(ws, msg_id_ref, method, params=None):
    msg_id_ref[0] += 1
    mid = msg_id_ref[0]
    msg = {"id": mid, "method": method}
    if params:
        msg["params"] = params
    await ws.send(json.dumps(msg))
    deadline = asyncio.get_event_loop().time() + WS_TIMEOUT
    while asyncio.get_event_loop().time() < deadline:
        try:
            r = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if r.get("id") == mid:
                return r
        except asyncio.TimeoutError:
            return {}
    return {}


async def search_zone(ws, mid, zone_name):
    """Search Rightmove for 4+ bed rentals with garden in a zone."""
    print(f"  {zone_name}: navigating...", file=sys.stderr, flush=True)

    # Go to rent search page
    await send(ws, mid, "Page.navigate", {"url": "https://www.rightmove.co.uk/property-to-rent.html"})
    await asyncio.sleep(3)

    # Focus input and type
    await send(ws, mid, "Runtime.evaluate", {"expression": "document.getElementById('ta_searchInput')?.focus()"})
    await asyncio.sleep(0.3)
    await send(ws, mid, "Input.insertText", {"text": zone_name})
    await asyncio.sleep(2)

    # Click first suggestion
    await send(ws, mid, "Runtime.evaluate", {"expression": """
        var items = document.querySelectorAll('li');
        for (var i = 0; i < items.length; i++) {
            if (items[i].offsetHeight > 0 && items[i].textContent.trim().length < 100 &&
                items[i].textContent.toLowerCase().includes(arguments && arguments[0] || '')) {
                items[i].click();
                break;
            }
        }
    """})
    # Actually click the first visible LI that looks like a suggestion
    await send(ws, mid, "Runtime.evaluate", {"expression": f"""
        var items = document.querySelectorAll('li');
        var clicked = false;
        for (var i = 0; i < items.length; i++) {{
            var li = items[i];
            if (li.offsetHeight > 0 && li.textContent.includes('{zone_name.split(",")[0]}') && li.textContent.length < 100) {{
                li.click();
                clicked = true;
                break;
            }}
        }}
        clicked ? 'clicked' : 'no match';
    """})
    await asyncio.sleep(1)

    # Click search button
    await send(ws, mid, "Runtime.evaluate", {"expression": """
        var btn = document.querySelector('button[class*="ta_propertyToRentControls__cta"]');
        if (btn) btn.click();
    """})
    await asyncio.sleep(5)

    # Check if we're on a results page
    r = await send(ws, mid, "Runtime.evaluate", {"expression": "location.href", "returnByValue": True})
    url = r.get("result", {}).get("result", {}).get("value", "")

    if "search" not in url and "find" not in url:
        print(f"  {zone_name}: not on results page ({url})", file=sys.stderr, flush=True)
        return []

    # Now add filters via URL manipulation
    # Add minBedrooms=4, maxPrice=4000, propertyTypes=houses, mustHave=garden
    if "?" in url:
        filtered_url = url + "&minBedrooms=4&maxPrice=4000&propertyTypes=detached%2Csemi-detached%2Cterraced%2Cbungalow&mustHave=garden&includeLetAgreed=false"
    else:
        filtered_url = url + "?minBedrooms=4&maxPrice=4000&propertyTypes=detached%2Csemi-detached%2Cterraced%2Cbungalow&mustHave=garden&includeLetAgreed=false"

    await send(ws, mid, "Page.navigate", {"url": filtered_url})
    await asyncio.sleep(5)

    # Extract listings
    r = await send(ws, mid, "Runtime.evaluate", {"expression": """
        var cards = document.querySelectorAll('.l-searchResult, [id^="property-"], [class*="propertyCard"]');
        var results = [];
        var seen = new Set();
        // Also try finding via property links
        if (cards.length === 0) {
            var links = document.querySelectorAll('a[href*="/properties/"]');
            links.forEach(function(link) {
                var href = link.href;
                if (seen.has(href)) return;
                seen.add(href);
                var card = link.closest('[class*="Card"], [class*="Result"], article') || link.parentElement.parentElement;
                var text = card ? card.textContent.replace(/\\s+/g, ' ').trim() : '';
                // Extract price (£X,XXX pcm pattern)
                var priceMatch = text.match(/£[\\d,]+\\s*(?:pcm|pm|per month)/i);
                var price = priceMatch ? priceMatch[0] : '';
                // Extract bedrooms
                var bedMatch = text.match(/(\\d+)\\s*bed/i);
                var beds = bedMatch ? bedMatch[1] + ' bed' : '';
                results.push({
                    url: href.split('?')[0],
                    price: price,
                    address: text.substring(0, 120),
                    beds: beds,
                });
            });
        } else {
            cards.forEach(function(card, i) {
                if (i >= 8) return;
                var link = card.querySelector('a[href*="/properties/"]');
                if (!link || seen.has(link.href)) return;
                seen.add(link.href);
                var price = card.querySelector('[class*="price"], [class*="Price"]');
                var addr = card.querySelector('address, [class*="address"], [class*="Address"]');
                var text = card.textContent.replace(/\\s+/g, ' ').trim();
                var bedMatch = text.match(/(\\d+)\\s*bed/i);
                results.push({
                    url: link.href.split('?')[0],
                    price: price ? price.textContent.trim() : '',
                    address: addr ? addr.textContent.trim() : text.substring(0, 120),
                    beds: bedMatch ? bedMatch[1] + ' bed' : '',
                });
            });
        }
        JSON.stringify(results.slice(0, 6));
    """, "returnByValue": True})

    raw = r.get("result", {}).get("result", {}).get("value", "[]")
    try:
        listings = json.loads(raw)
    except json.JSONDecodeError:
        listings = []

    print(f"  {zone_name}: {len(listings)} listings found", file=sys.stderr, flush=True)
    return listings


async def main():
    targets = json.loads(urllib.request.urlopen("http://localhost:9222/json").read())
    ws_url = [t for t in targets if t["type"] == "page"][0]["webSocketDebuggerUrl"]
    mid = [0]

    all_results = {}

    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        await send(ws, mid, "Page.enable")
        await send(ws, mid, "Runtime.enable")

        for zone in ZONES:
            try:
                listings = await search_zone(ws, mid, zone["name"])
                all_results[zone["name"]] = {
                    "outcode": zone["outcode"],
                    "listings": listings,
                }
            except Exception as e:
                print(f"  {zone['name']}: ERROR {e}", file=sys.stderr, flush=True)
                all_results[zone["name"]] = {"outcode": zone["outcode"], "listings": []}
            await asyncio.sleep(2)

    with open("out/listings.json", "w") as f:
        json.dump(all_results, f, indent=2)

    total = sum(len(v["listings"]) for v in all_results.values())
    print(f"\nTotal: {total} listings across {len(ZONES)} zones", file=sys.stderr, flush=True)
    print(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
