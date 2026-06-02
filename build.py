#!/usr/bin/env python3
"""
NourNest site generator.

Reads data/listings.json (BOOM property data) and renders pages that need
listing data baked in (currently: listings/index.html).

Run: python3 build.py
"""

import json
import re
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "listings.json"


def boom_url(item):
    slug = re.sub(r"\s", "-", item["nickname"])
    return f'https://nournestapartments.bookingsboom.com/listing/{item["id"]}/{slug}?lang=en'


def area_slug(area):
    return re.sub(r"[^a-z0-9]+", "-", area.lower()).strip("-")


def card_html(item):
    return dedent(f'''
        <a class="property-card" href="{boom_url(item)}" target="_blank" rel="noopener" data-area-slug="{area_slug(item["area"])}" data-beds="{item["beds"]}" data-guests="{item["guests"]}">
          <div class="img" data-area="{item["area"]}"></div>
          <div class="body">
            <h3>{item["nickname"]}</h3>
            <p class="meta"><span>{item["beds"]} bed</span><span>{item["baths"]} bath</span><span>Sleeps {item["guests"]}</span></p>
          </div>
        </a>''').strip()


def render_listings(listings):
    # Group + sort: dedup the "- Dup" entries by preferring the original
    seen_addresses = {}
    deduped = []
    for l in listings:
        key = (l["address"], l["beds"], l["baths"])
        if "Dup" in l["nickname"]:
            continue
        if key in seen_addresses:
            continue
        seen_addresses[key] = True
        deduped.append(l)

    # Unique areas for filter chips
    areas = sorted({l["area"] for l in deduped})
    chip_html = '<button class="filter-chip active" data-filter="all">All ({})</button>'.format(len(deduped))
    for area in areas:
        slug = area_slug(area)
        count = sum(1 for l in deduped if l["area"] == area)
        chip_html += f'\n        <button class="filter-chip" data-filter="{slug}">{area} ({count})</button>'

    cards_html = "\n      ".join(card_html(l) for l in deduped)

    return chip_html, cards_html, len(deduped)


def build_listings_page(chip_html, cards_html, count):
    template = LISTINGS_TEMPLATE.format(
        count=count,
        chip_html=chip_html,
        cards_html=cards_html,
    )
    out = ROOT / "listings" / "index.html"
    out.write_text(template, encoding="utf-8")
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
    <a href="/" class="logo">Nour<span>Nest</span></a>
    <ul>
      <li><a href="/listings/">Apartments</a></li>
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
    <p>Every apartment is managed directly by our team. Click through to see availability and book without a platform between us.</p>
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
        <a href="/" class="logo" style="display: inline-block; margin-bottom: 1rem;">Nour<span>Nest</span></a>
        <p>Boutique short-let management and curated guest experience for London properties. Director-led. Independently run.</p>
      </div>
      <div>
        <h4>Stays</h4>
        <ul>
          <li><a href="/listings/">All apartments</a></li>
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


def main():
    data = json.loads(DATA.read_text())
    listings = data["listings"]
    chip_html, cards_html, count = render_listings(listings)
    build_listings_page(chip_html, cards_html, count)


if __name__ == "__main__":
    main()
