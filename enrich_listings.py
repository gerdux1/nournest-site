#!/usr/bin/env python3
"""
One-shot geocoder: extracts UK postcodes from listings.json addresses
and adds lat/lng via free postcodes.io API. Writes back to listings.json.

Run once after BOOM scrape. Safe to re-run — only fetches missing entries.
"""

import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "listings.json"

UK_POSTCODE = re.compile(
    r"\b([A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2})(?=[^A-Z0-9]|UK|$)",
    re.IGNORECASE,
)

# Area centroids for listings whose addresses have no postcode at all.
# Keep this list tiny — only entries you've manually verified.
AREA_FALLBACK = {
    "Hammersmith": (51.4927, -0.2339),
    "Kings Cross": (51.5308, -0.1238),
}


def extract_postcode(address):
    m = UK_POSTCODE.search(address)
    if not m:
        return None
    pc = m.group(1).upper().strip()
    if " " not in pc:
        pc = pc[:-3] + " " + pc[-3:]
    return pc


def geocode(postcode):
    url = f"https://api.postcodes.io/postcodes/{urllib.request.quote(postcode)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
            if data.get("status") == 200:
                res = data["result"]
                return res["latitude"], res["longitude"]
    except Exception as e:
        print(f"  ✗ {postcode}: {e}")
    return None, None


def outcode_centroid(outcode):
    """Fallback for postcodes not in postcodes.io — use outcode centroid."""
    url = f"https://api.postcodes.io/outcodes/{urllib.request.quote(outcode)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
            if data.get("status") == 200:
                res = data["result"]
                return res["latitude"], res["longitude"]
    except Exception as e:
        print(f"  ✗ outcode {outcode}: {e}")
    return None, None


def main():
    data = json.loads(DATA.read_text())
    listings = data["listings"]
    updated = 0
    skipped = 0
    failed = 0
    for item in listings:
        if item.get("lat") and item.get("lng"):
            skipped += 1
            continue
        pc = extract_postcode(item["address"])
        if not pc:
            area_match = AREA_FALLBACK.get(item.get("area", "").strip())
            if area_match:
                item["lat"], item["lng"] = area_match
                updated += 1
                print(f"  ⚑ {item['nickname']}: area centroid {item['area']} → {area_match[0]:.4f}, {area_match[1]:.4f}")
                continue
            print(f"  ✗ {item['nickname']}: no postcode in '{item['address']}'")
            failed += 1
            continue
        lat, lng = geocode(pc)
        if lat is None:
            outcode = pc.split()[0]
            print(f"  ↻ {item['nickname']} full postcode failed; trying outcode {outcode}")
            lat, lng = outcode_centroid(outcode)
        if lat is None:
            print(f"  ✗ {item['nickname']}: postcode '{pc}' not found")
            failed += 1
            continue
        item["lat"] = lat
        item["lng"] = lng
        updated += 1
        print(f"  ✓ {item['nickname']}: {pc} → {lat:.4f}, {lng:.4f}")
        time.sleep(0.05)  # gentle on the API
    DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone. Updated: {updated}, already had coords: {skipped}, failed: {failed}")


if __name__ == "__main__":
    main()
