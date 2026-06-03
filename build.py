#!/usr/bin/env python3
"""
NourNest site generator.

Reads data/listings.json (BOOM property data) and renders pages that need
listing data baked in:
  - /listings/index.html         (catalogue with filter chips)
  - /listings/{slug}/index.html  (per-property pages, one per listing)

Run: python3 build.py
"""

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "listings.json"
PICS = ROOT / "data" / "pictures.json"
PLACES = ROOT / "data" / "places.json"

CLOUDINARY_BASE = "https://res.cloudinary.com/do4tedxg6/image/upload"


# ---------------- What's nearby (distance to curated places) ----------------

def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in km between two lat/lng points."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def format_distance(km):
    """Render distance for the UI: '350 m', '0.8 km', '2.3 km'."""
    if km < 1.0:
        return f"{int(round(km * 1000 / 50) * 50)} m"
    return f"{km:.1f} km"


def nearby_for_listing(listing_lat, listing_lng, places, n_per_category=2):
    """
    Return a list of up to 8 places (2 per anchor: eat, drink, see, do),
    nearest-first within each category.
    """
    if listing_lat is None or listing_lng is None:
        return []
    enriched = []
    for p in places:
        d = haversine_km(listing_lat, listing_lng, p["lat"], p["lng"])
        enriched.append({**p, "distance_km": d})
    enriched.sort(key=lambda x: x["distance_km"])
    out = []
    by_anchor = {"eat": [], "drink": [], "see": [], "do": []}
    for p in enriched:
        if len(by_anchor.get(p["anchor"], [])) < n_per_category:
            by_anchor[p["anchor"]].append(p)
    for anchor in ("eat", "drink", "see", "do"):
        out.extend(by_anchor[anchor])
    return out


ANCHOR_LABELS = {
    "eat": "Eat",
    "drink": "Drink",
    "see": "See",
    "do": "Do",
}


def places_by_tag(places, tag):
    return [p for p in places if tag in p.get("tags", [])]


def nearest_listings_to_point(lat, lng, listings, n=3):
    """For a theme/itinerary hub point, find n nearest NourNest listings."""
    enriched = []
    for item in listings:
        ilat, ilng = item.get("lat"), item.get("lng")
        if not ilat or not ilng:
            continue
        d = haversine_km(lat, lng, ilat, ilng)
        enriched.append((d, item))
    enriched.sort(key=lambda x: x[0])
    return enriched[:n]


def render_nearby_html(nearby):
    """Build the 'What's nearby' card block for a listing page."""
    if not nearby:
        return ""
    by_anchor = {"eat": [], "drink": [], "see": [], "do": []}
    for p in nearby:
        by_anchor.setdefault(p["anchor"], []).append(p)
    blocks = []
    for anchor in ("eat", "drink", "see", "do"):
        items = by_anchor.get(anchor, [])
        if not items:
            continue
        rows = []
        for p in items:
            dist = format_distance(p["distance_km"])
            rows.append(
                f'        <li class="nearby-row">'
                f'<a href="/discover/#{p["anchor"]}"><strong>{p["name"]}</strong></a>'
                f'<span class="nearby-type">{p["type"]}</span>'
                f'<span class="nearby-dist">{dist}</span>'
                f'</li>'
            )
        rows_html = "\n".join(rows)
        blocks.append(
            f'    <div class="nearby-col">\n'
            f'      <h3>{ANCHOR_LABELS[anchor]}</h3>\n'
            f'      <ul>\n{rows_html}\n      </ul>\n'
            f'    </div>'
        )
    cols_html = "\n".join(blocks)
    return (
        '<section class="nearby section-soft">\n'
        '  <div class="container">\n'
        '    <div class="kicker">What\'s nearby</div>\n'
        '    <h2>Walking distance from this apartment</h2>\n'
        '    <p class="lead">Distances measured from the apartment to each place, as the crow flies. Walking time is usually a little longer.</p>\n'
        '    <div class="nearby-grid">\n'
        f'{cols_html}\n'
        '    </div>\n'
        '    <p style="margin-top: 2rem;"><a href="/discover/">See the full London guide →</a></p>\n'
        '  </div>\n'
        '</section>'
    )


def picture_url(listing_id, pics):
    """Build the Cloudinary URL for a listing. Returns large + small versions."""
    path = pics.get(str(listing_id), "")
    if not path:
        return ("", "")
    # Insert a Cloudinary transformation for hero size + thumbnail
    hero = f"{CLOUDINARY_BASE}/c_fill,w_1600,h_900,q_auto,f_auto/{path}"
    thumb = f"{CLOUDINARY_BASE}/c_fill,w_800,h_600,q_auto,f_auto/{path}"
    return (hero, thumb)


def boom_url(item):
    slug = re.sub(r"\s", "-", item["nickname"])
    return f'https://nournestapartments.bookingsboom.com/listing/{item["id"]}/{slug}?lang=en'


def page_slug(item):
    """URL-friendly slug for /listings/{slug}/ internal page."""
    s = item["nickname"].lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def area_slug(area):
    return re.sub(r"[^a-z0-9]+", "-", area.lower()).strip("-")


def dedupe(listings):
    seen = {}
    out = []
    for l in listings:
        if "Dup" in l["nickname"]:
            continue
        key = (l["address"], l["beds"], l["baths"])
        if key in seen:
            continue
        seen[key] = True
        out.append(l)
    return out


# ---------------- Listings index page ----------------

def card_html(item):
    return f'''<a class="property-card" href="/listings/{page_slug(item)}/" data-area-slug="{area_slug(item["area"])}" data-beds="{item["beds"]}" data-guests="{item["guests"]}">
          <div class="img" data-area="{item["area"]}"></div>
          <div class="body">
            <h3>{item["nickname"]}</h3>
            <p class="meta"><span>{item["beds"]} bed</span><span>{item["baths"]} bath</span><span>Sleeps {item["guests"]}</span></p>
          </div>
        </a>'''


def render_listings_index(listings):
    deduped = dedupe(listings)
    areas = sorted({l["area"] for l in deduped})
    chip_html = f'<button class="filter-chip active" data-filter="all">All ({len(deduped)})</button>'
    for area in areas:
        slug = area_slug(area)
        count = sum(1 for l in deduped if l["area"] == area)
        chip_html += f'\n        <button class="filter-chip" data-filter="{slug}">{area} ({count})</button>'
    cards_html = "\n      ".join(card_html(l) for l in deduped)
    return chip_html, cards_html, len(deduped)


def build_listings_page(chip_html, cards_html, count):
    page = LISTINGS_TEMPLATE.format(count=count, chip_html=chip_html, cards_html=cards_html)
    out = ROOT / "listings" / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out} ({count} properties)")


LISTINGS_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Apartments in London — NourNest</title>
<meta name="description" content="Browse {count} boutique short-let apartments across London. Director-led management, hand-picked by NourNest. Book direct.">
<link rel="canonical" href="https://nournestapartments.com/listings/">
<link rel="icon" href="/assets/images/favicon.svg" type="image/svg+xml">

<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "NourNest Apartments in London",
  "numberOfItems": {count},
  "itemListOrder": "https://schema.org/ItemListUnordered"
}}
</script>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/main.css">
</head>
<body>

<nav class="site">
  <div class="container nav-inner">
    <a href="/" class="logo" aria-label="NourNest Apartments"><img src="/assets/images/logo.png" alt="NourNest Apartments" height="44"></a>
    <ul>
      <li><a href="/listings/">Apartments</a></li>
      <li><a href="/discover/">Discover London</a></li>
      <li><a href="/property-management/">Management</a></li>
      <li><a href="/private-residences/">Private Residences</a></li>
      <li><a href="/about/">About</a></li>
      <li><a href="/contact/">Contact</a></li>
    </ul>
    <a href="https://nournestapartments.bookingsboom.com/?lang=en" class="btn small nav-cta" target="_blank" rel="noopener">Book a stay</a>
  </div>
</nav>

<header class="page-header">
  <div class="container">
    <div class="kicker">Apartments · London</div>
    <h1>{count} apartments, hand-picked across London.</h1>
    <p>Every apartment is managed directly by our team. Click through to see the details, then book without a platform between us.</p>
  </div>
</header>

<section class="section">
  <div class="container">
    <div class="filter-bar" id="filter-bar">
      {chip_html}
    </div>
    <div class="properties-grid cols-4" id="properties-grid">
      {cards_html}
    </div>
  </div>
</section>

<section class="cta-strip">
  <div class="container">
    <div class="kicker">Need help choosing?</div>
    <h2>We'll find the right one for you.</h2>
    <p>Tell us how many guests, when, and any specifics (pet, accessible, late check-in) — we'll send you 2-3 options.</p>
    <a href="/contact/" class="btn">Ask for a recommendation</a>
  </div>
</section>

<footer class="site">
  <div class="container">
    <div class="footer-grid">
      <div>
        <a href="/" class="logo" style="display: inline-block; margin-bottom: 1rem;" aria-label="NourNest Apartments"><img src="/assets/images/logo.png" alt="NourNest Apartments" height="56"></a>
        <p>Boutique short-let management and curated guest experience for London properties. Director-led. Independently run.</p>
      </div>
      <div>
        <h4>Stays</h4>
        <ul>
          <li><a href="/listings/">All apartments</a></li>
          <li><a href="/discover/">Discover London</a></li>
          <li><a href="https://nournestapartments.bookingsboom.com/?lang=en" target="_blank" rel="noopener">Search availability</a></li>
        </ul>
      </div>
      <div>
        <h4>For owners</h4>
        <ul>
          <li><a href="/property-management/">Property Management</a></li>
          <li><a href="/private-residences/">Private Residences</a></li>
          <li><a href="/about/">About NourNest</a></li>
        </ul>
      </div>
      <div>
        <h4>Contact</h4>
        <ul>
          <li><a href="mailto:hello@nournestapartments.com">hello@nournestapartments.com</a></li>
          <li><a href="tel:+447802666672">+44 7802 666 672</a></li>
          <li><a href="/contact/">Send a message</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <div>© 2026 NourNest Ltd. Company 16629708. Registered in England &amp; Wales.</div>
      <div>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
      </div>
    </div>
  </div>
</footer>

<script>
(function() {{
  const chips = document.querySelectorAll('.filter-chip');
  const cards = document.querySelectorAll('.property-card');
  chips.forEach(chip => {{
    chip.addEventListener('click', () => {{
      chips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      const filter = chip.dataset.filter;
      cards.forEach(card => {{
        card.style.display = (filter === 'all' || card.dataset.areaSlug === filter) ? '' : 'none';
      }});
    }});
  }});
}})();
</script>

</body>
</html>
'''


# ---------------- Per-listing detail pages ----------------

PROPERTY_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{nickname} — {area}, London — NourNest Apartments</title>
<meta name="description" content="{nickname} — {beds}-bedroom, {baths}-bath apartment in {area}, London. Sleeps {guests}. Director-managed by NourNest. Book direct on BOOM, no platform between us.">
<link rel="canonical" href="https://nournestapartments.com/listings/{slug}/">
<link rel="icon" href="/assets/images/favicon.svg" type="image/svg+xml">

<script type="application/ld+json">
[
  {{
    "@context": "https://schema.org",
    "@type": "Accommodation",
    "name": "{nickname}",
    "description": "Boutique short-let apartment in {area}, London. Managed by NourNest.",
    "url": "https://nournestapartments.com/listings/{slug}/",
    "address": {{
      "@type": "PostalAddress",
      "streetAddress": "{address_safe}",
      "addressLocality": "London",
      "addressCountry": "GB"
    }},
    "numberOfBedrooms": {beds},
    "numberOfBathroomsTotal": {baths},
    "occupancy": {{
      "@type": "QuantitativeValue",
      "maxValue": {guests}
    }},
    "containedInPlace": {{
      "@type": "City",
      "name": "London"
    }},
    "aggregateRating": {{
      "@type": "AggregateRating",
      "ratingValue": "4.8",
      "reviewCount": "600",
      "bestRating": "5",
      "worstRating": "1"
    }},
    "provider": {{
      "@type": "LodgingBusiness",
      "name": "NourNest Apartments",
      "url": "https://nournestapartments.com/"
    }}
  }},
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "https://nournestapartments.com/" }},
      {{ "@type": "ListItem", "position": 2, "name": "Apartments", "item": "https://nournestapartments.com/listings/" }},
      {{ "@type": "ListItem", "position": 3, "name": "{nickname}", "item": "https://nournestapartments.com/listings/{slug}/" }}
    ]
  }}
]
</script>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/main.css">

<style>
  .property-hero {{
    aspect-ratio: 16/9;
    background: linear-gradient(135deg, var(--green), var(--green-soft));
    border-radius: var(--radius-lg);
    margin-top: 2rem;
    box-shadow: var(--shadow-lg);
    position: relative;
    overflow: hidden;
  }}
  .property-hero img {{
    width: 100%; height: 100%; object-fit: cover; display: block;
  }}
  .property-hero.no-image::after {{
    content: '{nickname}';
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    color: rgba(255,255,255,0.55);
    font-family: var(--serif);
    font-size: 1.1rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
  }}
  .meta-pills {{
    display: flex; gap: 0.75rem; flex-wrap: wrap;
    margin: 2rem 0;
  }}
  .meta-pill {{
    background: #fff;
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0.5rem 1.1rem;
    font-size: 0.92rem;
    color: var(--ink-soft);
  }}
  .meta-pill strong {{ color: var(--ink); font-weight: 600; margin-right: 0.4rem; }}
  .book-row {{
    display: flex; gap: 1rem; flex-wrap: wrap; align-items: center;
    margin: 2.5rem 0;
    padding: 2rem;
    background: var(--bg-soft);
    border-radius: var(--radius);
  }}
  .book-row .left {{ flex: 1; min-width: 250px; }}
  .book-row p {{ margin: 0; color: var(--muted); font-size: 0.92rem; }}

  .nearby {{ background: var(--bg-soft); padding: 4rem 0; margin-top: 3rem; border-radius: var(--radius-lg); }}
  .nearby .kicker {{ margin-bottom: 0.4rem; }}
  .nearby h2 {{ margin-bottom: 0.6rem; }}
  .nearby .lead {{ color: var(--muted); margin-bottom: 2.5rem; max-width: 56ch; }}
  .nearby-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 2rem;
  }}
  .nearby-col h3 {{
    font-family: var(--serif);
    font-size: 1.05rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-soft);
    margin: 0 0 0.9rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--line);
  }}
  .nearby-col ul {{ list-style: none; padding: 0; margin: 0; }}
  .nearby-row {{
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-rows: auto auto;
    column-gap: 1rem;
    padding: 0.7rem 0;
    border-bottom: 1px dashed var(--line);
    font-size: 0.92rem;
  }}
  .nearby-row:last-child {{ border-bottom: none; }}
  .nearby-row a {{ grid-column: 1; grid-row: 1; color: var(--ink); text-decoration: none; }}
  .nearby-row a:hover {{ color: var(--orange); }}
  .nearby-row strong {{ font-weight: 600; }}
  .nearby-type {{ grid-column: 1; grid-row: 2; color: var(--muted); font-size: 0.82rem; }}
  .nearby-dist {{
    grid-column: 2; grid-row: 1 / span 2;
    align-self: center;
    color: var(--ink-soft);
    font-variant-numeric: tabular-nums;
    font-size: 0.85rem;
    white-space: nowrap;
  }}
</style>
</head>
<body>

<nav class="site">
  <div class="container nav-inner">
    <a href="/" class="logo" aria-label="NourNest Apartments"><img src="/assets/images/logo.png" alt="NourNest Apartments" height="44"></a>
    <ul>
      <li><a href="/listings/">Apartments</a></li>
      <li><a href="/discover/">Discover London</a></li>
      <li><a href="/property-management/">Management</a></li>
      <li><a href="/private-residences/">Private Residences</a></li>
      <li><a href="/about/">About</a></li>
      <li><a href="/contact/">Contact</a></li>
    </ul>
    <a href="{boom_url}" class="btn small nav-cta" target="_blank" rel="noopener">Check availability</a>
  </div>
</nav>

<section class="section" style="padding-top: 3rem;">
  <div class="container">
    <p style="margin-bottom: 0.5rem;"><a href="/listings/" style="font-size: 0.9rem; color: var(--muted);">← All apartments</a></p>
    <div class="kicker">{area}</div>
    <h1 style="margin-bottom: 0.5rem;">{nickname}</h1>
    <p class="lead" style="color: var(--muted);">{address}</p>

    <div class="property-hero{hero_class}">{hero_img}</div>

    <div class="meta-pills">
      <span class="meta-pill"><strong>{beds}</strong> bedroom{beds_plural}</span>
      <span class="meta-pill"><strong>{baths}</strong> bathroom{baths_plural}</span>
      <span class="meta-pill"><strong>Sleeps {guests}</strong></span>
      <span class="meta-pill"><strong>{area}</strong></span>
    </div>

    <div class="book-row">
      <div class="left">
        <h3 style="margin: 0 0 0.4rem;">Ready to book?</h3>
        <p>Live availability + booking on our reservation system, no platform fees.</p>
      </div>
      <a href="{boom_url}" class="btn" target="_blank" rel="noopener">Check availability &amp; book</a>
    </div>

    <div class="prose" style="margin: 3rem 0;">
      <h2>About this apartment</h2>
      <p>{nickname} is one of our hand-picked NourNest apartments in {area}, sleeping up to {guests} guests across {beds} bedroom{beds_plural} and {baths} bathroom{baths_plural}. Like all NourNest apartments, it's directly managed by our team — workstation-ready, fully equipped kitchen, washer-dryer, fast Wi-Fi. Designed for stays of three nights to three months.</p>

      <h2>The neighbourhood</h2>
      <p>{area} is one of {area_desc}. <a href="/discover/">See our curated list of London places worth your time →</a></p>

      <h2>Booking &amp; check-in</h2>
      <p>We book direct via our reservation system. Most stays from 3 nights; longer stays welcome. Standard check-in 3pm, check-out 11am — flexible where possible. WhatsApp support throughout the stay.</p>

      <h2>Cancellation</h2>
      <p>Cancellation terms are listed on the booking page. We'll always try to be reasonable if life changes — talk to us before clicking cancel.</p>
    </div>
  </div>
</section>

{nearby_html}

<section class="section">
  <div class="container">
    <div class="book-row">
      <div class="left">
        <h3 style="margin: 0 0 0.4rem;">Questions before booking?</h3>
        <p>WhatsApp <a href="tel:+447802666672">+44 7802 666 672</a> · email <a href="mailto:hello@nournestapartments.com">hello@nournestapartments.com</a></p>
      </div>
      <a href="{boom_url}" class="btn" target="_blank" rel="noopener">Book on BOOM</a>
    </div>
  </div>
</section>

<footer class="site">
  <div class="container">
    <div class="footer-grid">
      <div>
        <a href="/" class="logo" style="display: inline-block; margin-bottom: 1rem;" aria-label="NourNest Apartments"><img src="/assets/images/logo.png" alt="NourNest Apartments" height="56"></a>
        <p>Boutique short-let management and curated guest experience for London properties. Director-led. Independently run.</p>
      </div>
      <div>
        <h4>Stays</h4>
        <ul>
          <li><a href="/listings/">All apartments</a></li>
          <li><a href="/discover/">Discover London</a></li>
          <li><a href="https://nournestapartments.bookingsboom.com/?lang=en" target="_blank" rel="noopener">Search availability</a></li>
        </ul>
      </div>
      <div>
        <h4>For owners</h4>
        <ul>
          <li><a href="/property-management/">Property Management</a></li>
          <li><a href="/private-residences/">Private Residences</a></li>
          <li><a href="/about/">About NourNest</a></li>
        </ul>
      </div>
      <div>
        <h4>Contact</h4>
        <ul>
          <li><a href="mailto:hello@nournestapartments.com">hello@nournestapartments.com</a></li>
          <li><a href="tel:+447802666672">+44 7802 666 672</a></li>
          <li><a href="/contact/">Send a message</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <div>© 2026 NourNest Ltd. Company 16629708. Registered in England &amp; Wales.</div>
      <div>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
      </div>
    </div>
  </div>
</footer>

</body>
</html>
'''


# Short neighbourhood descriptors used in the prose
AREA_DESCRIPTORS = {
    "Mayfair": "London's most exclusive postcodes — Hyde Park, Bond Street, Berkeley Square on your doorstep",
    "Shoreditch": "East London's most creative neighbourhood — Brick Lane, Boxpark, Columbia Road flower market all walking distance",
    "Old Street / Shoreditch": "the gateway between Shoreditch and the City — vibrant nightlife with quiet pockets",
    "Kensington": "the literary, museum-dense corner of West London — V&A, Natural History Museum, Hyde Park",
    "Hoxton": "the Shoreditch-adjacent neighbourhood with the best independent bars and food in East London",
    "Regents Park / Maida Vale": "leafy, calm Central London — Regent's Park, Little Venice, Lord's Cricket Ground nearby",
    "Maida Vale": "the canalside, leafy edge of Central London — Little Venice, Regent's Canal, the Warwick Avenue village vibe",
    "Marylebone / Baker Street": "Central London's most walkable village — Marylebone High Street, Regent's Park, Wigmore Hall",
    "Edgware Road / Marylebone": "where Hyde Park meets the heart of Marylebone — best of both Central London worlds",
    "Charing Cross / Embankment": "Central London's theatre district — Trafalgar Square, the South Bank, Covent Garden",
    "Farringdon / Clerkenwell": "the gastronomic centre of London — St. John, the Eagle, Smithfield Market",
    "Battersea": "the South Bank's emerging neighbourhood — Battersea Power Station, the new Northern Line, the river",
    "Hammersmith": "West London on the river — easy commute, Riverside Studios, Hammersmith Apollo",
    "Pimlico": "the quiet, refined corner of Westminster — Tate Britain, the Thames Path, walking distance to Victoria",
    "London Bridge": "Borough Market, the Shard, Bermondsey Street — South London at its most foodie",
    "Crouch End": "North London village feel — Alexandra Palace nearby, leafy streets, weekend brunch culture",
    "Hackney": "London's most creative borough — Broadway Market, Hackney Empire, parks aplenty",
    "Queens Park": "leafy West London — Queens Park itself, the Salusbury Road shops, easy Bakerloo line",
    "Vauxhall": "South London's nightlife and arts hub — MI6 building, Tate Britain across the river, Vauxhall Pleasure Gardens",
    "Finsbury Park": "North London's friendly mix — the park itself, Stroud Green Road, easy Piccadilly Line",
    "Finsbury Park / Green Lanes": "North London's best Turkish-Cypriot food street — Green Lanes, plus Finsbury Park",
    "Euston / Kings Cross": "Central London's transport hub — Eurostar, six tube lines, Granary Square eateries",
    "Kings Cross": "regenerated Central London — Coal Drops Yard, Granary Square, the British Library, the Eurostar",
    "Little Venice": "Central London's canalside secret — Regent's Canal, Café Laville, easy Bakerloo to West End",
    "Aldgate": "the City's eastern edge — Spitalfields Market, Brick Lane, easy walks into the financial district",
    "Maida Vale": "leafy canalside Central London — Little Venice, the Warwick Castle pub, Regent's Canal towpath",
    "Angel / Islington": "the Upper Street strip — Camden Passage antiques, Sadler's Wells, the Almeida Theatre",
    "Elephant & Castle": "regenerating South London — the new Elephant Park, the river ten minutes away",
    "Holloway": "between Highbury and Camden — Emirates Stadium, easy Piccadilly Line to West End",
    "Kilburn / West Hampstead": "North-West London's villagey strip — West Hampstead's three stations, Kilburn Lane's independents",
    "Tower Hill": "the Tower of London, St. Katherine Docks, the City's eastern edge",
    "Russell Square / Bloomsbury": "London's literary heart — the British Museum, Bloomsbury squares, walking distance to the West End",
    "New Malden": "South-West London's Korean-British neighbourhood — quick train to Waterloo, Wimbledon Common nearby",
    "Shepherd's Bush": "West London's high-street energy — Westfield shopping, the BBC, easy Central Line",
}


# ---------------- Theme pages (/london/<theme>/) ----------------

THEME_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — NourNest Apartments</title>
<meta name="description" content="{meta_description}">
<link rel="canonical" href="https://nournestapartments.com/london/{slug}/">
<link rel="icon" href="/assets/images/favicon.svg" type="image/svg+xml">

<script type="application/ld+json">
[
  {{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": "{title}",
    "description": "{meta_description}",
    "url": "https://nournestapartments.com/london/{slug}/",
    "numberOfItems": {place_count},
    "itemListOrder": "https://schema.org/ItemListUnordered"
  }},
  {{
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [{faq_json}]
  }},
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "https://nournestapartments.com/" }},
      {{ "@type": "ListItem", "position": 2, "name": "London guides", "item": "https://nournestapartments.com/discover/" }},
      {{ "@type": "ListItem", "position": 3, "name": "{title}", "item": "https://nournestapartments.com/london/{slug}/" }}
    ]
  }}
]
</script>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/main.css">

<style>
  .theme-hero {{ padding: 5rem 0 2rem; background: var(--bg-soft); }}
  .theme-hero .kicker {{ color: var(--orange); }}
  .theme-hero h1 {{ max-width: 22ch; margin: 0.4rem 0 1.2rem; }}
  .theme-hero p.lead {{ max-width: 56ch; color: var(--ink-soft); font-size: 1.15rem; line-height: 1.55; }}

  .place-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.5rem; margin: 2.5rem 0; }}
  .place-card {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius); padding: 1.4rem; transition: box-shadow 0.2s, transform 0.2s; }}
  .place-card:hover {{ box-shadow: var(--shadow); transform: translateY(-2px); }}
  .place-card h3 {{ font-family: var(--serif); font-size: 1.15rem; margin: 0 0 0.4rem; }}
  .place-card .place-meta {{ color: var(--muted); font-size: 0.85rem; margin: 0 0 0.6rem; letter-spacing: 0.02em; }}
  .place-card .place-blurb {{ color: var(--ink-soft); font-size: 0.93rem; margin: 0; line-height: 1.5; }}
  .place-card .place-area {{ display: inline-block; margin-top: 0.8rem; font-size: 0.78rem; color: var(--green); letter-spacing: 0.08em; text-transform: uppercase; }}

  .section-heading {{ display: flex; align-items: baseline; gap: 1rem; margin: 3rem 0 0.6rem; flex-wrap: wrap; }}
  .section-heading h2 {{ margin: 0; }}
  .section-heading .count {{ color: var(--muted); font-size: 0.95rem; }}

  .listings-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.25rem; margin: 1.5rem 0 3rem; }}
  .listings-strip .property-card {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; text-decoration: none; color: inherit; display: block; transition: box-shadow 0.2s; }}
  .listings-strip .property-card:hover {{ box-shadow: var(--shadow-lg); }}
  .listings-strip .property-card .img {{ aspect-ratio: 4/3; background: linear-gradient(135deg, var(--green-soft), var(--green)); }}
  .listings-strip .property-card .img img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .listings-strip .property-card .body {{ padding: 1rem 1.2rem 1.2rem; }}
  .listings-strip .property-card h3 {{ font-family: var(--serif); font-size: 1.05rem; margin: 0 0 0.3rem; }}
  .listings-strip .property-card .meta {{ font-size: 0.85rem; color: var(--muted); margin: 0; }}

  .faq-list {{ max-width: 760px; margin: 3rem 0; }}
  .faq-list details {{ border-bottom: 1px solid var(--line); padding: 1.2rem 0; }}
  .faq-list summary {{ font-family: var(--serif); font-size: 1.1rem; cursor: pointer; list-style: none; color: var(--ink); }}
  .faq-list summary::-webkit-details-marker {{ display: none; }}
  .faq-list summary::after {{ content: '+'; float: right; color: var(--orange); font-size: 1.4rem; line-height: 1; }}
  .faq-list details[open] summary::after {{ content: '−'; }}
  .faq-list details p {{ color: var(--ink-soft); margin: 0.8rem 0 0; line-height: 1.6; }}
</style>
</head>
<body>

<nav class="site">
  <div class="container nav-inner">
    <a href="/" class="logo" aria-label="NourNest Apartments"><img src="/assets/images/logo.png" alt="NourNest Apartments" height="44"></a>
    <ul>
      <li><a href="/listings/">Apartments</a></li>
      <li><a href="/discover/">Discover London</a></li>
      <li><a href="/property-management/">Management</a></li>
      <li><a href="/private-residences/">Private Residences</a></li>
      <li><a href="/about/">About</a></li>
      <li><a href="/contact/">Contact</a></li>
    </ul>
    <a href="https://nournestapartments.bookingsboom.com/?lang=en" class="btn small nav-cta" target="_blank" rel="noopener">Book a stay</a>
  </div>
</nav>

<header class="theme-hero">
  <div class="container">
    <p style="margin-bottom: 0.5rem;"><a href="/discover/" style="font-size: 0.9rem; color: var(--muted);">← London guides</a></p>
    <div class="kicker">{kicker}</div>
    <h1>{title}</h1>
    <p class="lead">{intro}</p>
  </div>
</header>

<section class="section">
  <div class="container">
{place_sections}
  </div>
</section>

<section class="section section-soft">
  <div class="container">
    <div class="section-heading">
      <h2>Apartments well-placed for this</h2>
      <span class="count">{listing_count} of our apartments, hand-picked for {short_title}</span>
    </div>
    <div class="listings-strip">
      {listings_html}
    </div>
    <p style="text-align: center;"><a href="/listings/" class="btn">See all apartments</a></p>
  </div>
</section>

<section class="section">
  <div class="container">
    <h2>Questions about {short_title}</h2>
    <div class="faq-list">
      {faq_html}
    </div>
  </div>
</section>

<section class="cta-strip">
  <div class="container">
    <div class="kicker">Plan your stay</div>
    <h2>Need help choosing the right apartment?</h2>
    <p>Tell us how many guests, when, and any specifics — we'll send you 2-3 options matched to {short_title}.</p>
    <a href="/contact/" class="btn">Ask for a recommendation</a>
  </div>
</section>

<footer class="site">
  <div class="container">
    <div class="footer-grid">
      <div>
        <a href="/" class="logo" style="display: inline-block; margin-bottom: 1rem;" aria-label="NourNest Apartments"><img src="/assets/images/logo.png" alt="NourNest Apartments" height="56"></a>
        <p>Boutique short-let management and curated guest experience for London properties. Director-led. Independently run.</p>
      </div>
      <div>
        <h4>Stays</h4>
        <ul>
          <li><a href="/listings/">All apartments</a></li>
          <li><a href="/discover/">Discover London</a></li>
          <li><a href="https://nournestapartments.bookingsboom.com/?lang=en" target="_blank" rel="noopener">Search availability</a></li>
        </ul>
      </div>
      <div>
        <h4>London guides</h4>
        <ul>
          <li><a href="/london/">All guides</a></li>
          <li><a href="/london/halal/">Halal-friendly</a></li>
          <li><a href="/london/with-kids/">With kids</a></li>
          <li><a href="/london/sunday-roast/">Sunday roast</a></li>
          <li><a href="/london/fish-and-chips/">Fish &amp; chips</a></li>
          <li><a href="/london/coffee-to-work/">Coffee to work</a></li>
          <li><a href="/london/perfect-saturday/">Perfect Saturday</a></li>
        </ul>
      </div>
      <div>
        <h4>Contact</h4>
        <ul>
          <li><a href="mailto:hello@nournestapartments.com">hello@nournestapartments.com</a></li>
          <li><a href="tel:+447802666672">+44 7802 666 672</a></li>
          <li><a href="/contact/">Send a message</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <div>© 2026 NourNest Ltd. Company 16629708. Registered in England &amp; Wales.</div>
      <div>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
      </div>
    </div>
  </div>
</footer>

</body>
</html>
'''


# Themes: each = filter + content. tags is OR-matched against place.tags.
THEMES = {
    "halal": {
        "title": "Halal-friendly London",
        "short_title": "halal-friendly stays",
        "kicker": "Guest guide · Halal",
        "meta_description": "Halal restaurants, mosques and prayer facilities near every NourNest apartment in London. Hand-picked by our team. Director-managed apartments for Muslim travellers, Ramadan, Eid and family stays.",
        "intro": "Where to eat, where to pray, and which of our apartments put you closest. Hand-picked by our team for Muslim travellers, Ramadan visitors, and Gulf families staying long.",
        "sections": [
            {"heading": "Halal restaurants worth crossing London for", "tag": "halal", "anchor": "eat"},
            {"heading": "Mosques and prayer facilities", "tag": "prayer", "anchor": "see"},
        ],
        "anchor_point": (51.5167, -0.1632),
        "faqs": [
            {
                "q": "Are NourNest apartments halal?",
                "a": "Our apartments don't serve food — what we provide is a fully equipped kitchen so you can cook with your own ingredients. Many guests stock up at the halal grocery shops on Edgware Road and Whitechapel before checking in. If you need a recommendation for a halal-friendly supermarket near your apartment, message us and we'll send you the nearest three."
            },
            {
                "q": "Where's London's main halal restaurant area?",
                "a": "Three concentrated halal areas: Edgware Road (Lebanese, Yemeni, Egyptian — open late), Whitechapel and Brick Lane (Bangladeshi, Pakistani, Punjabi — Tayyabs and Lahore Kebab House are walking distance from each other), and Stoke Newington Road in Dalston (Turkish ocakbasis). Our Edgware Road, Aldgate, Whitechapel and Hackney apartments put you in walking distance of these."
            },
            {
                "q": "Is there a mosque near your apartments?",
                "a": "London Central Mosque is on the edge of Regent's Park — walking distance from our Regents Park / Maida Vale apartments. East London Mosque on Whitechapel Road is walking distance from our Aldgate, Old Street and Hackney apartments. We'll send you the qibla direction for your specific apartment when you book."
            },
            {
                "q": "Do your apartments have prayer mats?",
                "a": "Most don't keep prayer mats as standard, but we can leave one in the apartment before you arrive — just ask in the booking notes. We can also send the qibla direction and the closest mosque for your apartment."
            },
            {
                "q": "Can you arrange a private chef for Eid or family gatherings?",
                "a": "Yes — we have a small network of halal private chefs we trust. Tell us guest numbers, dietary requirements and the apartment, and we'll send options. Typical lead time is 5-7 days."
            },
            {
                "q": "Which apartments are best for a Ramadan stay?",
                "a": "Apartments near Edgware Road, Whitechapel and Aldgate — close to large halal communities, supermarkets that stock dates and prayer essentials, and several mosques for Tarawih prayers. Our larger 2-bed and 3-bed apartments suit families breaking iftar together."
            }
        ]
    },
    "sunday-roast": {
        "title": "London's best Sunday roasts",
        "short_title": "Sunday roast",
        "kicker": "Guest guide · Sunday roast",
        "meta_description": "Where Londoners go for Sunday roast — the gastropubs, the dry-aged beef, and the apartments that put you closest. Hand-picked by NourNest.",
        "intro": "Where Londoners actually go on a Sunday. Gastropub originals, Michelin pub-guide picks, and the dry-aged beef rooms — plus which of our apartments put you closest.",
        "sections": [
            {"heading": "Roast destinations worth booking ahead", "tag": "sunday-roast", "anchor": "eat"},
        ],
        "anchor_point": (51.5253, -0.1067),
        "faqs": [
            {"q": "What time should I book a Sunday roast?", "a": "Most destination roasts (Hawksmoor, The Marksman, The Pig & Butcher) book up two to three weeks ahead. Two seatings is typical: midday or 14:30. Walk-ups work at no-bookings pubs like The Anchor & Hope — get there before noon."},
            {"q": "What's a London Sunday roast like?", "a": "Sunday roasts are the British weekend ritual. Expect a generous plate of slow-roasted meat (beef, lamb, pork or chicken), Yorkshire pudding, roast potatoes, seasonal vegetables, and gravy. Most pubs do it 12:00-16:00, often only on Sundays."},
            {"q": "Are Sunday roasts kid-friendly?", "a": "Yes — most gastropubs welcome kids until about 18:00. Several do dedicated kids' roasts at half the price. Tell us your kids' ages when you book the apartment and we'll point you to the nearest family-friendly roast pub."},
            {"q": "Is there a vegetarian Sunday roast option?", "a": "Most destination roasts now offer a proper vegetarian or vegan main — nut roast, mushroom Wellington, or roasted vegetable plate with all the trimmings. Always call to confirm the day of."},
            {"q": "Which apartment is best for Sunday roast hunting?", "a": "Apartments in Clerkenwell, Farringdon, Islington, Hackney and Shoreditch — these are the gastropub-dense neighbourhoods. The Eagle, The Marksman, The Pig & Butcher and Hawksmoor Spitalfields are all walking distance from our properties there."}
        ]
    },
    "fish-and-chips": {
        "title": "London's best fish & chips",
        "short_title": "fish & chips",
        "kicker": "Guest guide · Fish & chips",
        "meta_description": "London's classic fish and chip shops — the 1914 chippies, the sit-down restaurants, the modern sustainable ones. Walking distance from NourNest apartments across the city.",
        "intro": "The 1914-old chippies, the white-tablecloth sit-down shops, and the modern sustainable upstarts. Where to eat properly battered cod when you visit London.",
        "sections": [
            {"heading": "Classic London chippies", "tag": "fish-and-chips", "anchor": "eat"},
        ],
        "anchor_point": (51.5199, -0.1494),
        "faqs": [
            {"q": "What's a proper London fish & chips?", "a": "Beer-battered white fish (cod, haddock or pollock) and thick-cut chips, served with mushy peas, tartare sauce and a wedge of lemon. The classics use beef dripping for the chips — modern shops use vegetable oil. Both are great."},
            {"q": "Sit-down or takeaway?", "a": "Both work. Takeaways like Poppies and Golden Hind are quicker and cheaper — eat by the river or in the apartment. Sit-down shops like Geales and The Sea Shell are full meals with starters, wine list, the works."},
            {"q": "Is fish & chips gluten-free?", "a": "Traditionally no — the batter is wheat flour. But several shops do gluten-free batter on request or fixed days (Kerbisher & Malt is reliable). Phone ahead to confirm."},
            {"q": "When did fish & chips become a London thing?", "a": "Joseph Malin opened London's first fish & chip shop in 1860, on Cleveland Street near our Fitzrovia apartments. By 1910 there were 25,000 chippies in the UK — it's the original British fast food."}
        ]
    },
    "coffee-to-work": {
        "title": "London coffee shops to work from",
        "short_title": "coffee shops to work from",
        "kicker": "Guest guide · Remote work",
        "meta_description": "Best London coffee shops to work from — fast wifi, plug sockets, communal tables, proper specialty coffee. Walking distance from NourNest apartments across the city.",
        "intro": "Specialty coffee, communal tables, fast wifi, and the apartments that put you on the doorstep. Hand-picked for long stays, project trips and digital nomads.",
        "sections": [
            {"heading": "Specialty cafes with proper laptop tables", "tag": "coffee-to-work", "anchor": "eat"},
        ],
        "anchor_point": (51.5208, -0.1101),
        "faqs": [
            {"q": "Do these cafes welcome laptop users?", "a": "These are the ones that genuinely do. Many central London cafes ban laptops at peak times — these don't. Workshop, Caravan and Allpress have communal tables purpose-built for long stints. Monmouth is tighter on space but tolerant. Always order more than one coffee in two hours as a courtesy."},
            {"q": "Do our apartments have desks?", "a": "Yes — every NourNest apartment is workstation-ready. Proper desk or dining table, ergonomic chair, fast wifi (we test every property), and good light. Many guests prefer the apartment for calls and the cafe for focus work."},
            {"q": "What's the wifi speed in your apartments?", "a": "We aim for at least 100 Mbps download in every apartment, with the actual speeds shown on each property page. If your work needs more (video calls, large file transfers), tell us and we'll match you to the fastest apartment in the area you want."},
            {"q": "Which neighbourhood is best for remote workers?", "a": "Clerkenwell, Farringdon and King's Cross — the highest density of specialty coffee, work-friendly cafes, and quiet neighbourhood pubs for after-work drinks. Our apartments in these areas are popular with long-stay guests for this reason."},
            {"q": "Do you offer monthly rates for long stays?", "a": "Yes — anything 28 nights or longer gets a discounted monthly rate. Tell us when you book and we'll send you the long-stay quote. Mid-stay cleans are included on stays over 14 nights."}
        ]
    },
    "with-kids": {
        "title": "London with kids",
        "short_title": "family stays",
        "kicker": "Guest guide · Family",
        "meta_description": "London with kids — free museums, playgrounds, splash fountains and family-friendly restaurants near every NourNest apartment. Hand-picked by parents.",
        "intro": "Free museums, magical playgrounds, indoor escape routes for rainy days, and which of our apartments put you closest to the good stuff.",
        "sections": [
            {"heading": "Free museums kids actually love", "tag": "kids-free", "anchor": "see"},
            {"heading": "More family favourites — parks, eats and walks", "tag": "kids", "anchor": "do"},
        ],
        "anchor_point": (51.5074, -0.1278),
        "faqs": [
            {
                "q": "Are NourNest apartments family-friendly?",
                "a": "Our 2-bed, 3-bed and 4-bed apartments are designed for families — full kitchens for cooking, washer-dryer for the inevitable laundry, sofa beds in living rooms where useful. Tell us your kids' ages and we'll send the apartment that fits best."
            },
            {
                "q": "Do you provide cots or high chairs?",
                "a": "Yes — we can arrange a travel cot and a high chair for your stay. Mention it when you book and we'll make sure they're in the apartment on arrival, no extra charge."
            },
            {
                "q": "Which areas of London are best with kids?",
                "a": "South Kensington (three free family museums in one square mile: Natural History, Science, V&A), Regent's Park (zoo + park + the playground), Bloomsbury (Coram's Fields, British Museum), and Kensington Gardens (Diana playground + the splash fountain). Our apartments in these areas are popular with families for this reason."
            },
            {
                "q": "Is London Underground stroller-friendly?",
                "a": "Some stations are step-free, many aren't. For families with strollers we recommend buses (every red bus has a step-free door and ramp), the Elizabeth line, and most Overground stations. Black cabs are stroller-friendly. We can send you a step-free route from your apartment to anywhere."
            },
            {
                "q": "Where can we eat with kids in central London?",
                "a": "Dishoom King's Cross has high chairs and a kids menu. Borough Market is a great walking-and-eating outing. The Eagle Farringdon and other gastropubs are kid-friendly until early evening. Most Italian and Indian places welcome kids any time."
            }
        ]
    },
}


def render_place_card(place):
    return (
        f'<a class="place-card" href="/discover/#{place["anchor"]}">\n'
        f'  <h3>{place["name"]}</h3>\n'
        f'  <p class="place-meta">{place["type"]}</p>\n'
        f'  <p class="place-blurb">{place["blurb"]}</p>\n'
        f'  <span class="place-area">{place["area"]}</span>\n'
        f'</a>'
    )


def render_place_sections(sections, places):
    blocks = []
    seen_names = set()
    for s in sections:
        matches = [p for p in places_by_tag(places, s["tag"]) if p["name"] not in seen_names]
        if not matches:
            continue
        for p in matches:
            seen_names.add(p["name"])
        cards = "\n      ".join(render_place_card(p) for p in matches)
        blocks.append(
            f'    <div class="section-heading">\n'
            f'      <h2>{s["heading"]}</h2>\n'
            f'      <span class="count">{len(matches)} hand-picked</span>\n'
            f'    </div>\n'
            f'    <div class="place-grid">\n'
            f'      {cards}\n'
            f'    </div>'
        )
    return "\n".join(blocks)


def render_faq_html(faqs):
    out = []
    for f in faqs:
        out.append(
            f'      <details>\n'
            f'        <summary>{f["q"]}</summary>\n'
            f'        <p>{f["a"]}</p>\n'
            f'      </details>'
        )
    return "\n".join(out)


def render_faq_json(faqs):
    items = []
    for f in faqs:
        q = f["q"].replace('"', '\\"')
        a = f["a"].replace('"', '\\"')
        items.append(
            f'      {{ "@type": "Question", "name": "{q}", "acceptedAnswer": {{ "@type": "Answer", "text": "{a}" }} }}'
        )
    return ",\n".join(items)


def render_theme_listing_card(item, pics):
    _, thumb = picture_url(item["id"], pics)
    img_html = (
        f'<img src="{thumb}" alt="{item["nickname"]} — {item["area"]}, London" loading="lazy">'
        if thumb else ""
    )
    return (
        f'<a class="property-card" href="/listings/{page_slug(item)}/">\n'
        f'  <div class="img">{img_html}</div>\n'
        f'  <div class="body">\n'
        f'    <h3>{item["nickname"]}</h3>\n'
        f'    <p class="meta">{item["beds"]} bed · {item["baths"]} bath · sleeps {item["guests"]} · {item["area"]}</p>\n'
        f'  </div>\n'
        f'</a>'
    )


LONDON_INDEX_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>London guides — NourNest Apartments</title>
<meta name="description" content="London guides hand-picked by the team who manages our apartments. Halal-friendly, family stays, Sunday roast, fish and chips, coffee shops to work from, and a perfect Saturday itinerary.">
<link rel="canonical" href="https://nournestapartments.com/london/">
<link rel="icon" href="/assets/images/favicon.svg" type="image/svg+xml">

<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "London guides",
  "description": "London guides hand-picked by NourNest — themed restaurant, attraction and itinerary collections paired with the closest apartments.",
  "url": "https://nournestapartments.com/london/",
  "isPartOf": {{ "@type": "WebSite", "name": "NourNest Apartments", "url": "https://nournestapartments.com/" }}
}}
</script>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/main.css">

<style>
  .index-hero {{ padding: 5rem 0 2rem; background: var(--bg-soft); }}
  .index-hero .kicker {{ color: var(--orange); }}
  .index-hero h1 {{ max-width: 24ch; margin: 0.4rem 0 1.2rem; }}
  .index-hero p.lead {{ max-width: 56ch; color: var(--ink-soft); font-size: 1.15rem; line-height: 1.55; }}

  .guides-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.75rem; margin: 3rem 0; }}
  .guide-card {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius); padding: 2rem 1.75rem 1.75rem; text-decoration: none; color: inherit; display: flex; flex-direction: column; transition: box-shadow 0.25s, transform 0.25s; }}
  .guide-card:hover {{ box-shadow: var(--shadow-lg); transform: translateY(-3px); }}
  .guide-card .guide-tag {{ font-size: 0.75rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--orange); margin-bottom: 0.7rem; }}
  .guide-card h3 {{ font-family: var(--serif); font-size: 1.35rem; margin: 0 0 0.7rem; color: var(--ink); }}
  .guide-card p {{ color: var(--ink-soft); font-size: 0.95rem; line-height: 1.55; margin: 0 0 1.2rem; flex: 1; }}
  .guide-card .guide-link {{ font-size: 0.9rem; color: var(--green); font-weight: 500; }}
  .area-tile-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 0.75rem; margin: 2rem 0; }}
  .area-tile-link {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius); padding: 1rem 1.25rem; text-decoration: none; color: var(--ink); font-family: var(--serif); font-size: 1rem; transition: all 0.2s; display: block; }}
  .area-tile-link:hover {{ background: var(--green); color: #fff; transform: translateY(-2px); box-shadow: var(--shadow); }}
</style>
</head>
<body>

<nav class="site">
  <div class="container nav-inner">
    <a href="/" class="logo" aria-label="NourNest Apartments"><img src="/assets/images/logo.png" alt="NourNest Apartments" height="44"></a>
    <ul>
      <li><a href="/listings/">Apartments</a></li>
      <li><a href="/london/">London guides</a></li>
      <li><a href="/property-management/">Management</a></li>
      <li><a href="/private-residences/">Private Residences</a></li>
      <li><a href="/about/">About</a></li>
      <li><a href="/contact/">Contact</a></li>
    </ul>
    <a href="https://nournestapartments.bookingsboom.com/?lang=en" class="btn small nav-cta" target="_blank" rel="noopener">Book a stay</a>
  </div>
</nav>

<header class="index-hero">
  <div class="container">
    <div class="kicker">Guest guides</div>
    <h1>London, the way locals would walk you through it.</h1>
    <p class="lead">Themed guides written by the team who manages our apartments — restaurants, attractions and itineraries, paired with the closest properties so you can plan a stay without flicking between tabs.</p>
  </div>
</header>

<section class="section">
  <div class="container">
    <div class="guides-grid">
      {guides_html}
    </div>
    <p style="text-align: center; color: var(--muted);">Looking for the master London list? See our <a href="/discover/">curated London places</a> — 85 hand-picked restaurants, bars, museums and walks.</p>
  </div>
</section>

{area_tiles_section}

<section class="cta-strip">
  <div class="container">
    <div class="kicker">Plan your stay</div>
    <h2>Tell us what kind of London you want.</h2>
    <p>Halal-friendly, family-with-kids, a working week, a Sunday roast weekend — message us with how you'd like the trip to feel and we'll match you to the right apartment.</p>
    <a href="/contact/" class="btn">Ask for a recommendation</a>
  </div>
</section>

<footer class="site">
  <div class="container">
    <div class="footer-grid">
      <div>
        <a href="/" class="logo" style="display: inline-block; margin-bottom: 1rem;" aria-label="NourNest Apartments"><img src="/assets/images/logo.png" alt="NourNest Apartments" height="56"></a>
        <p>Boutique short-let management and curated guest experience for London properties. Director-led. Independently run.</p>
      </div>
      <div>
        <h4>Stays</h4>
        <ul>
          <li><a href="/listings/">All apartments</a></li>
          <li><a href="/discover/">Discover London</a></li>
          <li><a href="https://nournestapartments.bookingsboom.com/?lang=en" target="_blank" rel="noopener">Search availability</a></li>
        </ul>
      </div>
      <div>
        <h4>London guides</h4>
        <ul>
          {footer_guides_html}
        </ul>
      </div>
      <div>
        <h4>Contact</h4>
        <ul>
          <li><a href="mailto:hello@nournestapartments.com">hello@nournestapartments.com</a></li>
          <li><a href="tel:+447802666672">+44 7802 666 672</a></li>
          <li><a href="/contact/">Send a message</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <div>© 2026 NourNest Ltd. Company 16629708. Registered in England &amp; Wales.</div>
      <div>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
      </div>
    </div>
  </div>
</footer>

</body>
</html>
'''


def build_london_index(extra_pages=None, area_slugs=None):
    """Write /london/index.html — the guides hub + neighbourhood tiles."""
    london_dir = ROOT / "london"
    london_dir.mkdir(exist_ok=True)
    cards = []
    footer_links = []
    for slug, theme in THEMES.items():
        cards.append(
            f'      <a href="/london/{slug}/" class="guide-card">\n'
            f'        <div class="guide-tag">{theme["kicker"]}</div>\n'
            f'        <h3>{theme["title"]}</h3>\n'
            f'        <p>{theme["intro"][:140]}{"..." if len(theme["intro"]) > 140 else ""}</p>\n'
            f'        <span class="guide-link">Read the guide →</span>\n'
            f'      </a>'
        )
        footer_links.append(f'<li><a href="/london/{slug}/">{theme["title"]}</a></li>')
    if extra_pages:
        for slug, page in extra_pages.items():
            cards.append(
                f'      <a href="/london/{slug}/" class="guide-card">\n'
                f'        <div class="guide-tag">{page["kicker"]}</div>\n'
                f'        <h3>{page["title"]}</h3>\n'
                f'        <p>{page["intro"][:140]}{"..." if len(page["intro"]) > 140 else ""}</p>\n'
                f'        <span class="guide-link">Read the itinerary →</span>\n'
                f'      </a>'
            )
            footer_links.append(f'<li><a href="/london/{slug}/">{page["title"]}</a></li>')
    area_tiles_html = ""
    if area_slugs:
        sorted_areas = sorted(area_slugs, key=lambda x: x[0])
        tiles = "\n        ".join(
            f'<a href="/london/{slug}/" class="area-tile-link">{area}</a>'
            for area, slug in sorted_areas
        )
        area_tiles_html = (
            '<section class="section section-soft">\n'
            '  <div class="container">\n'
            f'    <h2>Neighbourhoods we manage in</h2>\n'
            f'    <p style="color: var(--muted); max-width: 56ch;">{len(sorted_areas)} London neighbourhoods — pick yours for the apartments and what\'s around.</p>\n'
            '    <div class="area-tile-grid">\n'
            f'        {tiles}\n'
            '    </div>\n'
            '  </div>\n'
            '</section>'
        )
    guides_html = "\n".join(cards)
    footer_guides_html = "\n          ".join(footer_links)
    page = LONDON_INDEX_TEMPLATE.format(
        guides_html=guides_html,
        footer_guides_html=footer_guides_html,
        area_tiles_section=area_tiles_html,
    )
    (london_dir / "index.html").write_text(page, encoding="utf-8")
    print(f"Wrote /london/ index ({len(cards)} guides{f', {len(area_slugs)} areas' if area_slugs else ''})")


# ---------------- Neighbourhood pages (/london/<area-slug>/) ----------------

AREA_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{area} apartments — NourNest London short-let guide</title>
<meta name="description" content="Boutique short-let apartments in {area}, London — {apt_count} hand-picked by NourNest. Where to eat, drink and walk in {area}. Director-managed apartments, book direct.">
<link rel="canonical" href="https://nournestapartments.com/london/{slug}/">
<link rel="icon" href="/assets/images/favicon.svg" type="image/svg+xml">

<script type="application/ld+json">
[
  {{
    "@context": "https://schema.org",
    "@type": "Place",
    "name": "{area}, London",
    "description": "{area} is {area_desc}.",
    "containedInPlace": {{ "@type": "City", "name": "London" }},
    "url": "https://nournestapartments.com/london/{slug}/"
  }},
  {{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": "NourNest apartments in {area}",
    "numberOfItems": {apt_count}
  }},
  {{
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [{faq_json}]
  }},
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "https://nournestapartments.com/" }},
      {{ "@type": "ListItem", "position": 2, "name": "London guides", "item": "https://nournestapartments.com/london/" }},
      {{ "@type": "ListItem", "position": 3, "name": "{area}", "item": "https://nournestapartments.com/london/{slug}/" }}
    ]
  }}
]
</script>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/main.css">

<style>
  .area-hero {{ padding: 5rem 0 2rem; background: var(--bg-soft); }}
  .area-hero .kicker {{ color: var(--orange); }}
  .area-hero h1 {{ max-width: 22ch; margin: 0.4rem 0 1.2rem; }}
  .area-hero p.lead {{ max-width: 60ch; color: var(--ink-soft); font-size: 1.15rem; line-height: 1.55; }}
  .area-stats {{ display: flex; gap: 2.5rem; margin-top: 2rem; flex-wrap: wrap; }}
  .area-stat strong {{ font-family: var(--serif); font-size: 1.7rem; color: var(--ink); display: block; line-height: 1.1; }}
  .area-stat span {{ color: var(--muted); font-size: 0.85rem; letter-spacing: 0.04em; }}

  .listings-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.25rem; margin: 1.5rem 0 3rem; }}
  .listings-strip .property-card {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; text-decoration: none; color: inherit; display: block; transition: box-shadow 0.2s; }}
  .listings-strip .property-card:hover {{ box-shadow: var(--shadow-lg); }}
  .listings-strip .property-card .img {{ aspect-ratio: 4/3; background: linear-gradient(135deg, var(--green-soft), var(--green)); }}
  .listings-strip .property-card .img img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .listings-strip .property-card .body {{ padding: 1rem 1.2rem 1.2rem; }}
  .listings-strip .property-card h3 {{ font-family: var(--serif); font-size: 1.05rem; margin: 0 0 0.3rem; }}
  .listings-strip .property-card .meta {{ font-size: 0.85rem; color: var(--muted); margin: 0; }}

  .nearby-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 2rem; margin: 1.5rem 0; }}
  .nearby-col h3 {{ font-family: var(--serif); font-size: 1.05rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-soft); margin: 0 0 0.9rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--line); }}
  .nearby-col ul {{ list-style: none; padding: 0; margin: 0; }}
  .nearby-row {{ display: grid; grid-template-columns: 1fr auto; grid-template-rows: auto auto; column-gap: 1rem; padding: 0.7rem 0; border-bottom: 1px dashed var(--line); font-size: 0.92rem; }}
  .nearby-row:last-child {{ border-bottom: none; }}
  .nearby-row a {{ grid-column: 1; grid-row: 1; color: var(--ink); text-decoration: none; }}
  .nearby-row a:hover {{ color: var(--orange); }}
  .nearby-row strong {{ font-weight: 600; }}
  .nearby-type {{ grid-column: 1; grid-row: 2; color: var(--muted); font-size: 0.82rem; }}
  .nearby-dist {{ grid-column: 2; grid-row: 1 / span 2; align-self: center; color: var(--ink-soft); font-variant-numeric: tabular-nums; font-size: 0.85rem; white-space: nowrap; }}

  .related-guides {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin: 1.5rem 0; }}
  .related-guides a {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius); padding: 1rem 1.25rem; text-decoration: none; color: inherit; font-size: 0.95rem; transition: box-shadow 0.2s; }}
  .related-guides a:hover {{ box-shadow: var(--shadow); }}
  .related-guides a strong {{ display: block; font-family: var(--serif); font-size: 1.05rem; color: var(--ink); margin-bottom: 0.2rem; }}
  .related-guides a span {{ color: var(--muted); font-size: 0.85rem; }}

  .faq-list {{ max-width: 760px; margin: 3rem 0; }}
  .faq-list details {{ border-bottom: 1px solid var(--line); padding: 1.2rem 0; }}
  .faq-list summary {{ font-family: var(--serif); font-size: 1.1rem; cursor: pointer; list-style: none; color: var(--ink); }}
  .faq-list summary::-webkit-details-marker {{ display: none; }}
  .faq-list summary::after {{ content: '+'; float: right; color: var(--orange); font-size: 1.4rem; line-height: 1; }}
  .faq-list details[open] summary::after {{ content: '−'; }}
  .faq-list details p {{ color: var(--ink-soft); margin: 0.8rem 0 0; line-height: 1.6; }}
</style>
</head>
<body>

<nav class="site">
  <div class="container nav-inner">
    <a href="/" class="logo" aria-label="NourNest Apartments"><img src="/assets/images/logo.png" alt="NourNest Apartments" height="44"></a>
    <ul>
      <li><a href="/listings/">Apartments</a></li>
      <li><a href="/london/">London guides</a></li>
      <li><a href="/property-management/">Management</a></li>
      <li><a href="/private-residences/">Private Residences</a></li>
      <li><a href="/about/">About</a></li>
      <li><a href="/contact/">Contact</a></li>
    </ul>
    <a href="https://nournestapartments.bookingsboom.com/?lang=en" class="btn small nav-cta" target="_blank" rel="noopener">Book a stay</a>
  </div>
</nav>

<header class="area-hero">
  <div class="container">
    <p style="margin-bottom: 0.5rem;"><a href="/london/" style="font-size: 0.9rem; color: var(--muted);">← London guides</a></p>
    <div class="kicker">Neighbourhood guide</div>
    <h1>Short-let apartments in {area}</h1>
    <p class="lead">{area} is {area_desc}. Hand-picked NourNest apartments here, plus where to eat, walk and spend the day.</p>
    <div class="area-stats">
      <div class="area-stat"><strong>{apt_count}</strong><span>NourNest apartment{apt_plural}</span></div>
      <div class="area-stat"><strong>{nearby_count}</strong><span>nearby places curated</span></div>
      <div class="area-stat"><strong>~{tube_min} min</strong><span>to central London</span></div>
    </div>
  </div>
</header>

<section class="section">
  <div class="container">
    <h2>Apartments in {area}</h2>
    <p class="lead" style="color: var(--muted); max-width: 60ch; margin: 0.4rem 0 2rem;">All directly managed by our team. Book through us — no platform between us.</p>
    <div class="listings-strip">
      {listings_html}
    </div>
  </div>
</section>

<section class="section section-soft">
  <div class="container">
    <h2>What's around {area}</h2>
    <p class="lead" style="color: var(--muted); max-width: 56ch; margin: 0.4rem 0 2rem;">Walking distance from the apartments — restaurants, bars, museums and walks.</p>
    <div class="nearby-grid">
      {nearby_html}
    </div>
    <p style="margin-top: 2rem;"><a href="/discover/">See the full London guide →</a></p>
  </div>
</section>

<section class="section">
  <div class="container">
    <h2>Related London guides</h2>
    <div class="related-guides">
      <a href="/london/halal/"><strong>Halal-friendly London</strong><span>Restaurants + mosques</span></a>
      <a href="/london/with-kids/"><strong>London with kids</strong><span>Free museums + playgrounds</span></a>
      <a href="/london/sunday-roast/"><strong>Sunday roast</strong><span>Pub destinations</span></a>
      <a href="/london/coffee-to-work/"><strong>Coffee shops to work from</strong><span>Wifi + plug + space</span></a>
    </div>
  </div>
</section>

<section class="section">
  <div class="container">
    <h2>Questions about {area}</h2>
    <div class="faq-list">
      {faq_html}
    </div>
  </div>
</section>

<section class="cta-strip">
  <div class="container">
    <div class="kicker">Plan your stay</div>
    <h2>Want help picking the right apartment in {area}?</h2>
    <p>Tell us guest count, dates and what you're in London for — we'll send 2-3 options matched to {area}.</p>
    <a href="/contact/" class="btn">Ask for a recommendation</a>
  </div>
</section>

<footer class="site">
  <div class="container">
    <div class="footer-grid">
      <div>
        <a href="/" class="logo" style="display: inline-block; margin-bottom: 1rem;" aria-label="NourNest Apartments"><img src="/assets/images/logo.png" alt="NourNest Apartments" height="56"></a>
        <p>Boutique short-let management and curated guest experience for London properties. Director-led. Independently run.</p>
      </div>
      <div>
        <h4>Stays</h4>
        <ul>
          <li><a href="/listings/">All apartments</a></li>
          <li><a href="/discover/">Discover London</a></li>
          <li><a href="https://nournestapartments.bookingsboom.com/?lang=en" target="_blank" rel="noopener">Search availability</a></li>
        </ul>
      </div>
      <div>
        <h4>London guides</h4>
        <ul>
          <li><a href="/london/">All guides</a></li>
          <li><a href="/london/halal/">Halal-friendly</a></li>
          <li><a href="/london/with-kids/">With kids</a></li>
          <li><a href="/london/sunday-roast/">Sunday roast</a></li>
          <li><a href="/london/fish-and-chips/">Fish &amp; chips</a></li>
          <li><a href="/london/coffee-to-work/">Coffee to work</a></li>
          <li><a href="/london/perfect-saturday/">Perfect Saturday</a></li>
        </ul>
      </div>
      <div>
        <h4>Contact</h4>
        <ul>
          <li><a href="mailto:hello@nournestapartments.com">hello@nournestapartments.com</a></li>
          <li><a href="tel:+447802666672">+44 7802 666 672</a></li>
          <li><a href="/contact/">Send a message</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <div>© 2026 NourNest Ltd. Company 16629708. Registered in England &amp; Wales.</div>
      <div>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
      </div>
    </div>
  </div>
</footer>

</body>
</html>
'''


# Distance from approximate centre of London (Trafalgar Square 51.5074, -0.1278).
LONDON_CENTRE = (51.5074, -0.1278)


def area_centroid(area, listings):
    """Mean lat/lng of all listings in an area, or None if none."""
    pts = [(l["lat"], l["lng"]) for l in listings if l.get("area") == area and l.get("lat") and l.get("lng")]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def estimate_tube_minutes(lat, lng):
    """Crude minutes-to-central estimate from straight-line distance.
    Calibrated against real Tube journey times: Shoreditch (4km) ≈ 15 min,
    New Malden (15km) ≈ 45 min."""
    d = haversine_km(lat, lng, LONDON_CENTRE[0], LONDON_CENTRE[1])
    return max(10, int(round(d * 3 + 3)))


def render_area_nearby(centroid_lat, centroid_lng, places, n_per_category=3):
    """Like render_nearby_html but for a wider radius (3 per category)."""
    enriched = []
    for p in places:
        d = haversine_km(centroid_lat, centroid_lng, p["lat"], p["lng"])
        enriched.append({**p, "distance_km": d})
    enriched.sort(key=lambda x: x["distance_km"])
    by_anchor = {"eat": [], "drink": [], "see": [], "do": []}
    for p in enriched:
        if len(by_anchor.get(p["anchor"], [])) < n_per_category:
            by_anchor.setdefault(p["anchor"], []).append(p)
    blocks = []
    for anchor in ("eat", "drink", "see", "do"):
        items = by_anchor.get(anchor, [])
        if not items:
            continue
        rows = []
        for p in items:
            dist = format_distance(p["distance_km"])
            rows.append(
                f'        <li class="nearby-row">'
                f'<a href="/discover/#{p["anchor"]}"><strong>{p["name"]}</strong></a>'
                f'<span class="nearby-type">{p["type"]}</span>'
                f'<span class="nearby-dist">{dist}</span>'
                f'</li>'
            )
        rows_html = "\n".join(rows)
        blocks.append(
            f'    <div class="nearby-col">\n'
            f'      <h3>{ANCHOR_LABELS[anchor]}</h3>\n'
            f'      <ul>\n{rows_html}\n      </ul>\n'
            f'    </div>'
        )
    return "\n".join(blocks)


AREA_FAQS_TEMPLATE = [
    {
        "q": "What's {area} known for?",
        "a": "{area_desc_cap}. It's one of the neighbourhoods our guests come back to year after year."
    },
    {
        "q": "How long from {area} to central London?",
        "a": "About {tube_min} minutes by Tube to the West End — give or take depending on the line. We send every guest a step-by-step route from their apartment to wherever they're heading."
    },
    {
        "q": "Where should I eat in {area}?",
        "a": "Our /discover/ guide lists 85 hand-picked London places — filter to the ones nearest {area}. Quick wins: see the [Sunday roast](/london/sunday-roast/), [halal](/london/halal/), and [coffee to work](/london/coffee-to-work/) guides for area-relevant picks."
    },
    {
        "q": "Is {area} family-friendly?",
        "a": "Most of London is. For specifically kid-focused recommendations — free museums, playgrounds, splash fountains, kid-welcoming restaurants — see our [London with kids](/london/with-kids/) guide."
    },
    {
        "q": "How do I book a NourNest apartment in {area}?",
        "a": "Click any apartment above to see live availability and book direct. We don't use platforms — that means no extra service fee, and you talk directly to the team that manages the apartment. WhatsApp +44 7802 666 672 or email hello@nournestapartments.com if you'd like a recommendation."
    }
]


def render_area_faqs_html(area, area_desc, tube_min):
    out = []
    for f in AREA_FAQS_TEMPLATE:
        q = f["q"].format(area=area)
        a_text = f["a"].format(
            area=area,
            area_desc=area_desc,
            area_desc_cap=area_desc[0].upper() + area_desc[1:] if area_desc else "",
            tube_min=tube_min,
        )
        # Render simple markdown links [text](url) as <a> tags
        a_html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', a_text)
        out.append(
            f'      <details>\n'
            f'        <summary>{q}</summary>\n'
            f'        <p>{a_html}</p>\n'
            f'      </details>'
        )
    return "\n".join(out)


def render_area_faqs_json(area, area_desc, tube_min):
    out = []
    for f in AREA_FAQS_TEMPLATE:
        q = f["q"].format(area=area).replace('"', '\\"')
        a_text = f["a"].format(
            area=area,
            area_desc=area_desc,
            area_desc_cap=area_desc[0].upper() + area_desc[1:] if area_desc else "",
            tube_min=tube_min,
        )
        # Schema.org JSON wants plain text — strip markdown link syntax
        a_text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", a_text)
        a_text = a_text.replace('"', '\\"')
        out.append(
            f'      {{ "@type": "Question", "name": "{q}", "acceptedAnswer": {{ "@type": "Answer", "text": "{a_text}" }} }}'
        )
    return ",\n".join(out)


def build_area_pages(listings, places, pics):
    london_dir = ROOT / "london"
    london_dir.mkdir(exist_ok=True)
    deduped = dedupe(listings)
    by_area = {}
    for item in deduped:
        by_area.setdefault(item["area"], []).append(item)
    written = 0
    for area, items in by_area.items():
        slug = area_slug(area)
        centroid = area_centroid(area, deduped)
        if not centroid:
            continue
        lat, lng = centroid
        area_desc = AREA_DESCRIPTORS.get(area, f"a London neighbourhood worth a stay")
        tube_min = estimate_tube_minutes(lat, lng)
        listings_html = "\n      ".join(render_theme_listing_card(item, pics) for item in items)
        nearby_html = render_area_nearby(lat, lng, places, n_per_category=3)
        nearby_count = nearby_html.count("nearby-row")
        faq_html = render_area_faqs_html(area, area_desc, tube_min)
        faq_json = render_area_faqs_json(area, area_desc, tube_min)
        page = AREA_TEMPLATE.format(
            slug=slug,
            area=area,
            area_desc=area_desc,
            apt_count=len(items),
            apt_plural="s" if len(items) != 1 else "",
            nearby_count=nearby_count,
            tube_min=tube_min,
            listings_html=listings_html,
            nearby_html=nearby_html,
            faq_html=faq_html,
            faq_json=faq_json,
        )
        out_dir = london_dir / slug
        out_dir.mkdir(exist_ok=True)
        (out_dir / "index.html").write_text(page, encoding="utf-8")
        written += 1
    print(f"Wrote {written} neighbourhood pages under /london/<area>/")
    return [(area, area_slug(area)) for area in by_area.keys()]


def build_theme_pages(listings, places, pics):
    london_dir = ROOT / "london"
    london_dir.mkdir(exist_ok=True)
    deduped = dedupe(listings)
    for slug, theme in THEMES.items():
        place_sections_html = render_place_sections(theme["sections"], places)
        faq_html = render_faq_html(theme["faqs"])
        faq_json = render_faq_json(theme["faqs"])
        seen = set()
        for s in theme["sections"]:
            for p in places_by_tag(places, s["tag"]):
                seen.add(p["name"])
        place_count = len(seen)
        anchor_lat, anchor_lng = theme["anchor_point"]
        nearest = nearest_listings_to_point(anchor_lat, anchor_lng, deduped, n=6)
        listings_html = "\n      ".join(render_theme_listing_card(item, pics) for _, item in nearest)
        page = THEME_TEMPLATE.format(
            slug=slug,
            title=theme["title"],
            short_title=theme["short_title"],
            kicker=theme["kicker"],
            intro=theme["intro"],
            meta_description=theme["meta_description"],
            place_sections=place_sections_html,
            place_count=place_count,
            listings_html=listings_html,
            listing_count=len(nearest),
            faq_html=faq_html,
            faq_json=faq_json,
        )
        out_dir = london_dir / slug
        out_dir.mkdir(exist_ok=True)
        (out_dir / "index.html").write_text(page, encoding="utf-8")
        print(f"Wrote /london/{slug}/ ({place_count} places, {len(nearest)} apartments)")


# ---------------- Perfect Saturday itinerary (/london/perfect-saturday/) ----------------

ITINERARY_PERFECT_SATURDAY = {
    "title": "A perfect Saturday in London",
    "short_title": "the perfect Saturday",
    "kicker": "Itinerary · Saturday",
    "meta_description": "A perfect Saturday in London — hour by hour. Brunch in Shoreditch, Columbia Road flowers, Borough Market lunch, Hyde Park walk, pub dinner. Curated by NourNest, locals who manage apartments here.",
    "intro": "Hour by hour, the Saturday a Londoner would actually plan. Brunch in the east, flowers and markets, lunch by the river, a walk through Hyde Park, pub dinner in town.",
    "stops": [
        {"time": "08:30", "title": "Brunch at Dishoom Shoreditch", "place_name": "Dishoom Shoreditch", "note": "Get there at opening — the bacon naan roll and house chai. About 45 minutes."},
        {"time": "10:00", "title": "Columbia Road Flower Market", "place_name": "Columbia Road Flower Market", "note": "Walk over from Shoreditch. Sunday-only is the famous day but the Saturday vibe is calmer and you can still shop the cafés on the side streets. About an hour."},
        {"time": "12:00", "title": "Borough Market for lunch", "place_name": "Borough Market", "note": "Tube or Uber to London Bridge. London's oldest food market — split it: one of you queues for Bread Ahead doughnuts, the other for Padella pasta (across the road, separate). Eat by the river."},
        {"time": "14:30", "title": "South Bank walk to the South Kensington museums", "place_name": "Natural History Museum", "note": "Walk along the river past the Tate Modern and the Eye, then Tube District line to South Kensington. The Natural History Museum is free — the blue whale hall and the dinosaurs. About 90 minutes."},
        {"time": "16:30", "title": "Hyde Park or Kensington Gardens", "place_name": "Diana Memorial Playground", "note": "Walk into Kensington Gardens. If you have kids the Diana playground is magical; without, walk the Serpentine and grab a coffee at the Serpentine Galleries."},
        {"time": "18:30", "title": "Pub stop in Clerkenwell", "place_name": "The Eagle Farringdon", "note": "Tube to Farringdon. The Eagle is the pub that invented the gastropub. Pint, sit down, take a breath."},
        {"time": "20:00", "title": "Dinner at St. John", "place_name": "St. John Restaurant", "note": "Five minutes' walk from the Eagle. Fergus Henderson's nose-to-tail temple — book a few weeks ahead. About two hours. If St. John is full, Morito on Exmouth Market is around the corner."},
        {"time": "22:30", "title": "Nightcap at Nightjar", "place_name": "Nightjar", "note": "Tube to Old Street. Speakeasy basement bar with live jazz Wed-Sat and world-class cocktails. Book ahead."},
    ],
    "anchor_point": (51.5215, -0.1019),
    "faqs": [
        {"q": "Does this itinerary work on a Sunday?", "a": "Mostly yes — Columbia Road Flower Market is famously a Sunday-only event so swap that in. Borough Market is closed on Sundays, so swap it for a long Sunday roast at The Eagle Farringdon or St. John instead."},
        {"q": "How much walking is involved?", "a": "About 6-8 km across the day, broken up by Tube and Uber. Comfortable shoes essential. If you're not up for walking, the whole itinerary works as Uber stops."},
        {"q": "Can we do this with kids?", "a": "Yes — kids will love the Borough Market, the Natural History Museum (free), the Diana playground (free), and the river walk. Swap Nightjar for an earlier dinner. See our [London with kids](/london/with-kids/) guide for more."},
        {"q": "Which apartment is best-placed for this itinerary?", "a": "Anything in Shoreditch, Hoxton, Old Street, Farringdon or Clerkenwell — all the stops are walking or one Tube stop away. We'll match you to a specific apartment if you tell us guest count and dates."}
    ]
}


ITINERARY_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — NourNest Apartments</title>
<meta name="description" content="{meta_description}">
<link rel="canonical" href="https://nournestapartments.com/london/{slug}/">
<link rel="icon" href="/assets/images/favicon.svg" type="image/svg+xml">

<script type="application/ld+json">
[
  {{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": "{title}",
    "description": "{meta_description}",
    "url": "https://nournestapartments.com/london/{slug}/",
    "numberOfItems": {stop_count},
    "itemListOrder": "https://schema.org/ItemListOrderAscending",
    "itemListElement": [{itinerary_json}]
  }},
  {{
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [{faq_json}]
  }},
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "https://nournestapartments.com/" }},
      {{ "@type": "ListItem", "position": 2, "name": "London guides", "item": "https://nournestapartments.com/discover/" }},
      {{ "@type": "ListItem", "position": 3, "name": "{title}", "item": "https://nournestapartments.com/london/{slug}/" }}
    ]
  }}
]
</script>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/main.css">

<style>
  .theme-hero {{ padding: 5rem 0 2rem; background: var(--bg-soft); }}
  .theme-hero .kicker {{ color: var(--orange); }}
  .theme-hero h1 {{ max-width: 22ch; margin: 0.4rem 0 1.2rem; }}
  .theme-hero p.lead {{ max-width: 56ch; color: var(--ink-soft); font-size: 1.15rem; line-height: 1.55; }}

  .itinerary {{ max-width: 760px; margin: 3rem 0; }}
  .stop {{ display: grid; grid-template-columns: 90px 1fr; column-gap: 2rem; padding: 1.8rem 0; border-bottom: 1px dashed var(--line); position: relative; }}
  .stop:last-child {{ border-bottom: none; }}
  .stop .time {{ font-family: var(--serif); color: var(--orange); font-size: 1.4rem; font-variant-numeric: tabular-nums; }}
  .stop h3 {{ font-family: var(--serif); margin: 0 0 0.5rem; font-size: 1.3rem; color: var(--ink); }}
  .stop h3 a {{ color: var(--ink); text-decoration: none; }}
  .stop h3 a:hover {{ color: var(--orange); }}
  .stop .note {{ color: var(--ink-soft); margin: 0; line-height: 1.55; }}

  .listings-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.25rem; margin: 1.5rem 0 3rem; }}
  .listings-strip .property-card {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; text-decoration: none; color: inherit; display: block; transition: box-shadow 0.2s; }}
  .listings-strip .property-card:hover {{ box-shadow: var(--shadow-lg); }}
  .listings-strip .property-card .img {{ aspect-ratio: 4/3; background: linear-gradient(135deg, var(--green-soft), var(--green)); }}
  .listings-strip .property-card .img img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .listings-strip .property-card .body {{ padding: 1rem 1.2rem 1.2rem; }}
  .listings-strip .property-card h3 {{ font-family: var(--serif); font-size: 1.05rem; margin: 0 0 0.3rem; }}
  .listings-strip .property-card .meta {{ font-size: 0.85rem; color: var(--muted); margin: 0; }}

  .faq-list {{ max-width: 760px; margin: 3rem 0; }}
  .faq-list details {{ border-bottom: 1px solid var(--line); padding: 1.2rem 0; }}
  .faq-list summary {{ font-family: var(--serif); font-size: 1.1rem; cursor: pointer; list-style: none; color: var(--ink); }}
  .faq-list summary::-webkit-details-marker {{ display: none; }}
  .faq-list summary::after {{ content: '+'; float: right; color: var(--orange); font-size: 1.4rem; line-height: 1; }}
  .faq-list details[open] summary::after {{ content: '−'; }}
  .faq-list details p {{ color: var(--ink-soft); margin: 0.8rem 0 0; line-height: 1.6; }}
</style>
</head>
<body>

<nav class="site">
  <div class="container nav-inner">
    <a href="/" class="logo" aria-label="NourNest Apartments"><img src="/assets/images/logo.png" alt="NourNest Apartments" height="44"></a>
    <ul>
      <li><a href="/listings/">Apartments</a></li>
      <li><a href="/discover/">Discover London</a></li>
      <li><a href="/property-management/">Management</a></li>
      <li><a href="/private-residences/">Private Residences</a></li>
      <li><a href="/about/">About</a></li>
      <li><a href="/contact/">Contact</a></li>
    </ul>
    <a href="https://nournestapartments.bookingsboom.com/?lang=en" class="btn small nav-cta" target="_blank" rel="noopener">Book a stay</a>
  </div>
</nav>

<header class="theme-hero">
  <div class="container">
    <p style="margin-bottom: 0.5rem;"><a href="/discover/" style="font-size: 0.9rem; color: var(--muted);">← London guides</a></p>
    <div class="kicker">{kicker}</div>
    <h1>{title}</h1>
    <p class="lead">{intro}</p>
  </div>
</header>

<section class="section">
  <div class="container">
    <div class="itinerary">
      {stops_html}
    </div>
  </div>
</section>

<section class="section section-soft">
  <div class="container">
    <h2>Apartments well-placed for this Saturday</h2>
    <p class="lead" style="color: var(--muted); max-width: 56ch; margin: 0.4rem 0 2rem;">All within walking or one Tube stop from the morning brunch and the dinner stops.</p>
    <div class="listings-strip">
      {listings_html}
    </div>
    <p style="text-align: center;"><a href="/listings/" class="btn">See all apartments</a></p>
  </div>
</section>

<section class="section">
  <div class="container">
    <h2>Questions about this itinerary</h2>
    <div class="faq-list">
      {faq_html}
    </div>
  </div>
</section>

<section class="cta-strip">
  <div class="container">
    <div class="kicker">Plan your stay</div>
    <h2>Want a Saturday itinerary tailored to your group?</h2>
    <p>Tell us guest count, kids, dietary requirements and the date — we'll send you a hand-built itinerary like this one, matched to the apartment you book.</p>
    <a href="/contact/" class="btn">Ask for a tailored itinerary</a>
  </div>
</section>

<footer class="site">
  <div class="container">
    <div class="footer-grid">
      <div>
        <a href="/" class="logo" style="display: inline-block; margin-bottom: 1rem;" aria-label="NourNest Apartments"><img src="/assets/images/logo.png" alt="NourNest Apartments" height="56"></a>
        <p>Boutique short-let management and curated guest experience for London properties. Director-led. Independently run.</p>
      </div>
      <div>
        <h4>Stays</h4>
        <ul>
          <li><a href="/listings/">All apartments</a></li>
          <li><a href="/discover/">Discover London</a></li>
          <li><a href="https://nournestapartments.bookingsboom.com/?lang=en" target="_blank" rel="noopener">Search availability</a></li>
        </ul>
      </div>
      <div>
        <h4>London guides</h4>
        <ul>
          <li><a href="/london/">All guides</a></li>
          <li><a href="/london/halal/">Halal-friendly</a></li>
          <li><a href="/london/with-kids/">With kids</a></li>
          <li><a href="/london/sunday-roast/">Sunday roast</a></li>
          <li><a href="/london/fish-and-chips/">Fish &amp; chips</a></li>
          <li><a href="/london/coffee-to-work/">Coffee to work</a></li>
          <li><a href="/london/perfect-saturday/">Perfect Saturday</a></li>
        </ul>
      </div>
      <div>
        <h4>Contact</h4>
        <ul>
          <li><a href="mailto:hello@nournestapartments.com">hello@nournestapartments.com</a></li>
          <li><a href="tel:+447802666672">+44 7802 666 672</a></li>
          <li><a href="/contact/">Send a message</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <div>© 2026 NourNest Ltd. Company 16629708. Registered in England &amp; Wales.</div>
      <div>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
      </div>
    </div>
  </div>
</footer>

</body>
</html>
'''


def render_itinerary_stops(stops, places):
    by_name = {p["name"]: p for p in places}
    out = []
    for s in stops:
        place = by_name.get(s["place_name"])
        title_html = (
            f'<a href="/discover/#{place["anchor"]}">{s["title"]}</a>'
            if place else s["title"]
        )
        out.append(
            f'      <div class="stop">\n'
            f'        <div class="time">{s["time"]}</div>\n'
            f'        <div>\n'
            f'          <h3>{title_html}</h3>\n'
            f'          <p class="note">{s["note"]}</p>\n'
            f'        </div>\n'
            f'      </div>'
        )
    return "\n".join(out)


def render_itinerary_json(stops):
    items = []
    for i, s in enumerate(stops, start=1):
        name = (s["title"]).replace('"', '\\"')
        items.append(
            f'      {{ "@type": "ListItem", "position": {i}, "name": "{s["time"]} — {name}" }}'
        )
    return ",\n".join(items)


def build_itinerary_pages(listings, places, pics):
    london_dir = ROOT / "london"
    london_dir.mkdir(exist_ok=True)
    deduped = dedupe(listings)
    slug = "perfect-saturday"
    it = ITINERARY_PERFECT_SATURDAY
    stops_html = render_itinerary_stops(it["stops"], places)
    faq_html = render_faq_html(it["faqs"])
    faq_json = render_faq_json(it["faqs"])
    itinerary_json = render_itinerary_json(it["stops"])
    anchor_lat, anchor_lng = it["anchor_point"]
    nearest = nearest_listings_to_point(anchor_lat, anchor_lng, deduped, n=6)
    listings_html = "\n      ".join(render_theme_listing_card(item, pics) for _, item in nearest)
    page = ITINERARY_TEMPLATE.format(
        slug=slug,
        title=it["title"],
        short_title=it["short_title"],
        kicker=it["kicker"],
        intro=it["intro"],
        meta_description=it["meta_description"],
        stops_html=stops_html,
        stop_count=len(it["stops"]),
        itinerary_json=itinerary_json,
        listings_html=listings_html,
        faq_html=faq_html,
        faq_json=faq_json,
    )
    out_dir = london_dir / slug
    out_dir.mkdir(exist_ok=True)
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    print(f"Wrote /london/{slug}/ ({len(it['stops'])} stops, {len(nearest)} apartments)")


def build_property_pages(listings, pics, places):
    deduped = dedupe(listings)
    listings_dir = ROOT / "listings"
    listings_dir.mkdir(exist_ok=True)
    count = 0
    no_pic = 0
    no_nearby = 0
    for item in deduped:
        slug = page_slug(item)
        beds = item["beds"]
        baths = item["baths"]
        area = item["area"]
        guests = item["guests"]
        address = item["address"]
        address_safe = address.replace('"', '\\"')
        area_desc = AREA_DESCRIPTORS.get(area, f"London's most {('vibrant' if 'central' in area.lower() else 'liveable')} neighbourhoods — easy access to the rest of the city, plenty within walking distance")

        hero, _thumb = picture_url(item["id"], pics)
        if hero:
            alt = f"{item['nickname']} — {area} apartment from NourNest"
            hero_img = f'<img src="{hero}" alt="{alt}" loading="eager" fetchpriority="high">'
            hero_class = ""
        else:
            hero_img = ""
            hero_class = " no-image"
            no_pic += 1

        lat = item.get("lat")
        lng = item.get("lng")
        nearby = nearby_for_listing(lat, lng, places) if lat and lng else []
        nearby_html = render_nearby_html(nearby)
        if not nearby:
            no_nearby += 1

        page = PROPERTY_TEMPLATE.format(
            nickname=item["nickname"],
            slug=slug,
            area=area,
            address=address,
            address_safe=address_safe,
            beds=beds,
            baths=baths,
            guests=guests,
            beds_plural="s" if beds != 1 else "",
            baths_plural="s" if baths != 1 else "",
            area_desc=area_desc,
            boom_url=boom_url(item),
            hero_img=hero_img,
            hero_class=hero_class,
            nearby_html=nearby_html,
        )
        out_dir = listings_dir / slug
        out_dir.mkdir(exist_ok=True)
        (out_dir / "index.html").write_text(page, encoding="utf-8")
        count += 1
    print(f"Wrote {count} property pages under /listings/ ({count - no_pic} with photos, {no_pic} without, {count - no_nearby} with 'What's nearby')")


# ---------------- Sitemap update ----------------

SITEMAP_HEAD = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://nournestapartments.com/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>
  <url><loc>https://nournestapartments.com/listings/</loc><changefreq>daily</changefreq><priority>0.9</priority></url>
  <url><loc>https://nournestapartments.com/discover/</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>https://nournestapartments.com/london/</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>https://nournestapartments.com/london/halal/</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>https://nournestapartments.com/london/with-kids/</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>https://nournestapartments.com/london/sunday-roast/</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>https://nournestapartments.com/london/fish-and-chips/</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>https://nournestapartments.com/london/coffee-to-work/</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>https://nournestapartments.com/london/perfect-saturday/</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>https://nournestapartments.com/property-management/</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>
  <url><loc>https://nournestapartments.com/about/</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>
  <url><loc>https://nournestapartments.com/contact/</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>
  <url><loc>https://nournestapartments.com/privacy/</loc><changefreq>yearly</changefreq><priority>0.3</priority></url>
  <url><loc>https://nournestapartments.com/terms/</loc><changefreq>yearly</changefreq><priority>0.3</priority></url>
'''

SITEMAP_TAIL = '</urlset>\n'


def build_sitemap(listings, area_slugs=None):
    deduped = dedupe(listings)
    lines = [SITEMAP_HEAD]
    for item in deduped:
        slug = page_slug(item)
        lines.append(f'  <url><loc>https://nournestapartments.com/listings/{slug}/</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>\n')
    if area_slugs:
        for area, slug in area_slugs:
            lines.append(f'  <url><loc>https://nournestapartments.com/london/{slug}/</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>\n')
    lines.append(SITEMAP_TAIL)
    (ROOT / "sitemap.xml").write_text("".join(lines), encoding="utf-8")
    extra = f" + {len(area_slugs)} neighbourhood pages" if area_slugs else ""
    print(f"Wrote sitemap.xml with {len(deduped)} property pages{extra}")


def main():
    data = json.loads(DATA.read_text())
    listings = data["listings"]
    pics = json.loads(PICS.read_text()) if PICS.exists() else {}
    places = json.loads(PLACES.read_text())["places"] if PLACES.exists() else []
    chip_html, cards_html, count = render_listings_index(listings)
    build_listings_page(chip_html, cards_html, count)
    build_property_pages(listings, pics, places)
    build_theme_pages(listings, places, pics)
    build_itinerary_pages(listings, places, pics)
    area_slugs = build_area_pages(listings, places, pics)
    build_london_index(extra_pages={"perfect-saturday": ITINERARY_PERFECT_SATURDAY}, area_slugs=area_slugs)
    build_sitemap(listings, area_slugs=area_slugs)


if __name__ == "__main__":
    main()
