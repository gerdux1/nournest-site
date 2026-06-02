# NourNest Apartments — nournestapartments.com

Boutique short-let management website for [NourNest Ltd](https://find-and-update.company-information.service.gov.uk/company/16629708).

## Stack

- **Static HTML / CSS** — no framework, no build step required for most pages
- **Python build script** (`build.py`) — regenerates `/listings/index.html` from `data/listings.json`
- **Cloudflare Pages** — hosting (free tier)
- **GitHub** — source

## Structure

```
.
├── index.html                  Home
├── listings/index.html         Apartment catalogue (generated)
├── about/index.html
├── property-management/        Landlord-facing
├── private-residences/         UHNW stewardship (noindex)
├── contact/
├── privacy/
├── terms/
├── assets/css/main.css         Brand tokens + components
├── data/listings.json          BOOM property data (51 listings)
├── build.py                    Listings page generator
├── _headers, _redirects        Cloudflare Pages config
├── robots.txt, sitemap.xml, llms.txt
```

## Brand

- **Cream** `#FFFBF2` background
- **Navy** `#071E2F` headlines
- **Orange** `#FF7F00` CTA
- **Forest green** `#385B4F` secondary
- **Playfair Display** (serif headlines) + **Inter** (body)
- Voice: warm · composed · considered — quietly premium, UK spelling

## Local preview

```bash
cd ~/nournest-site
python3 -m http.server 4321
# open http://127.0.0.1:4321/
```

Or via Claude Code's launch.json: server name `nournest-static`.

## Updating listings

When BOOM listings change:

1. Re-fetch from BOOM API or update `data/listings.json` manually
2. Run `python3 build.py`
3. Commit + push — Cloudflare Pages auto-deploys

## Bookings

All booking CTAs deep-link to BOOM's hosted booking site at `nournestapartments.bookingsboom.com`. We don't process payments on this site.

## Deploy

Pushes to `main` deploy automatically via Cloudflare Pages integration.
