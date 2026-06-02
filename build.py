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
import re
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "listings.json"
PICS = ROOT / "data" / "pictures.json"

CLOUDINARY_BASE = "https://res.cloudinary.com/do4tedxg6/image/upload"


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


def build_property_pages(listings, pics):
    deduped = dedupe(listings)
    listings_dir = ROOT / "listings"
    listings_dir.mkdir(exist_ok=True)
    count = 0
    no_pic = 0
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
        )
        out_dir = listings_dir / slug
        out_dir.mkdir(exist_ok=True)
        (out_dir / "index.html").write_text(page, encoding="utf-8")
        count += 1
    print(f"Wrote {count} property pages under /listings/ ({count - no_pic} with photos, {no_pic} without)")


# ---------------- Sitemap update ----------------

SITEMAP_HEAD = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://nournestapartments.com/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>
  <url><loc>https://nournestapartments.com/listings/</loc><changefreq>daily</changefreq><priority>0.9</priority></url>
  <url><loc>https://nournestapartments.com/discover/</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
  <url><loc>https://nournestapartments.com/property-management/</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>
  <url><loc>https://nournestapartments.com/about/</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>
  <url><loc>https://nournestapartments.com/contact/</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>
  <url><loc>https://nournestapartments.com/privacy/</loc><changefreq>yearly</changefreq><priority>0.3</priority></url>
  <url><loc>https://nournestapartments.com/terms/</loc><changefreq>yearly</changefreq><priority>0.3</priority></url>
'''

SITEMAP_TAIL = '</urlset>\n'


def build_sitemap(listings):
    deduped = dedupe(listings)
    lines = [SITEMAP_HEAD]
    for item in deduped:
        slug = page_slug(item)
        lines.append(f'  <url><loc>https://nournestapartments.com/listings/{slug}/</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>\n')
    lines.append(SITEMAP_TAIL)
    (ROOT / "sitemap.xml").write_text("".join(lines), encoding="utf-8")
    print(f"Wrote sitemap.xml with {len(deduped)} property pages")


def main():
    data = json.loads(DATA.read_text())
    listings = data["listings"]
    pics = json.loads(PICS.read_text()) if PICS.exists() else {}
    chip_html, cards_html, count = render_listings_index(listings)
    build_listings_page(chip_html, cards_html, count)
    build_property_pages(listings, pics)
    build_sitemap(listings)


if __name__ == "__main__":
    main()
