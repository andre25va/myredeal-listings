#!/usr/bin/env python3
"""Add a listing to the listings.myredeal.com template site.

Template intake: give it a Redfin link + agent info and it fetches the
listing, parses the facts, appends to listings.json, and rebuilds the site.

Usage:
  python3 add_listing.py --redfin-url <url> --agent-name "Jane Doe" \\
      --agent-phone "+1 (913) 555-0100" --agent-email jane@example.com

  # Redfin fetch failed / blocked? Pass the fields manually instead:
  python3 add_listing.py --address "1011 Tam Oshanter Dr, Kansas City, MO 64110" \\
      --price 320000 --beds 3 --baths 2 --sqft 1500 --type Single-family \\
      --agent-name "Jane Doe"

  # Preview what would be added, without writing anything:
  python3 add_listing.py --redfin-url <url> --agent-name "Jane Doe" --dry-run

Manual flags (--address, --price, --beds, --baths, --sqft, --type) also act as
overrides on top of a --redfin-url parse. Unknown fields are left empty —
nothing is ever invented. Adding a listing whose address is already present
is refused unless --force is passed.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(ROOT, "listings.json")
SITE_URL = "https://listings.myredeal.com"

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


# ---------------------------------------------------------------- fetch/parse

def fetch_redfin(url):
    """Fetch a Redfin page server-side. Raises on network/HTTP failure."""
    req = urllib.request.Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _clean(s):
    return " ".join(str(s).split()) if s else ""


def to_int(v):
    """Best-effort int from messy input ('$320,000', 320000, '1,730 sqft')."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    digits = re.sub(r"[^\d]", "", str(v))
    return int(digits) if digits else None


def parse_redfin(page):
    """Best-effort parse of a Redfin listing page. Never invents values.

    Returns a dict with any of: street, city, state, zip, price, beds,
    baths, sqft, type, description. Missing fields are simply absent.
    """
    data = {}

    # 1) JSON-LD structured data — the most reliable source on Redfin.
    for m in re.finditer(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            page, re.S | re.I):
        try:
            blob = json.loads(m.group(1).strip())
        except Exception:
            continue
        items = blob if isinstance(blob, list) else [blob]
        for item in items:
            if not isinstance(item, dict):
                continue
            t = item.get("@type", "")
            types = t if isinstance(t, list) else [t]
            if not any("Residence" in x or x in ("Product", "House",
                                                "SingleFamilyResidence",
                                                "RealEstateListing")
                       for x in types):
                continue
            addr = item.get("address", {})
            if isinstance(addr, dict):
                if addr.get("streetAddress"):
                    data.setdefault("street", _clean(addr["streetAddress"]))
                if addr.get("addressLocality"):
                    data.setdefault("city", _clean(addr["addressLocality"]))
                if addr.get("addressRegion"):
                    data.setdefault("state", _clean(addr["addressRegion"]))
                if addr.get("postalCode"):
                    data.setdefault("zip", _clean(str(addr["postalCode"]))[:10])
            offers = item.get("offers", {})
            if isinstance(offers, dict):
                price = to_int(offers.get("price") or offers.get("lowPrice"))
                if price and price > 1000:
                    data.setdefault("price", price)
            desc = _clean(item.get("description"))
            if desc and not data.get("description"):
                data["description"] = desc

    # 2) Open-graph / meta tags.
    def meta(prop):
        m = re.search(
            r'<meta[^>]+property=["\']' + re.escape(prop) +
            r'["\'][^>]+content=["\']([^"\']+)["\']', page, re.I)
        return _clean(m.group(1)) if m else ""

    og_desc = meta("og:description")
    if og_desc and not data.get("description"):
        # og:description on Redfin is usually a fact summary, not remarks —
        # keep it only if it reads like a real description.
        if len(og_desc) > 120:
            data["description"] = og_desc

    # 3) Regex fallbacks over the raw HTML.
    if "price" not in data:
        for pat in (r'"price"\s*:\s*"?\$?([\d,]{4,})"?',
                    r'data-rf-test-id="abp-price"[^>]*>\s*\$([\d,]+)'):
            m = re.search(pat, page)
            price = to_int(m.group(1)) if m else None
            if price and price > 1000:
                data["price"] = price
                break
    if "beds" not in data:
        for pat in (r'"beds?"\s*:\s*(\d{1,2})',
                    r'(\d{1,2})\s*beds?\b'):
            m = re.search(pat, page, re.I)
            beds = to_int(m.group(1)) if m else None
            if beds is not None and 0 < beds <= 30:
                data["beds"] = beds
                break
    if "baths" not in data:
        for pat in (r'"baths?"\s*:\s*(\d{1,2}(?:\.\d)?)',
                    r'(\d{1,2}(?:\.\d)?)\s*baths?\b'):
            m = re.search(pat, page, re.I)
            if m:
                try:
                    baths = float(m.group(1))
                except ValueError:
                    continue
                if 0 < baths <= 30:
                    data["baths"] = int(baths) if baths.is_integer() else baths
                    break
    if "sqft" not in data:
        for pat in (r'"(?:sqFt|squareFeet|livingArea)"\s*:\s*"?([\d,]{3,})"?',
                    r'([\d,]{3,})\s*sq\.?\s*ft\.?\b'):
            m = re.search(pat, page, re.I)
            sqft = to_int(m.group(1)) if m else None
            if sqft and 100 <= sqft <= 100000:
                data["sqft"] = sqft
                break

    # Sanity-filter anything that slipped through.
    if data.get("zip") and not re.fullmatch(r"\d{5}(-\d{4})?", data["zip"] or ""):
        data.pop("zip", None)
    return data


# ------------------------------------------------------------------ CLI bits

def parse_manual_address(address):
    """Split 'street, city, ST zip' into components. Raises ValueError."""
    m = re.match(
        r"^\s*(?P<street>.+?)\s*,\s*(?P<city>.+?)\s*,\s*"
        r"(?P<state>[A-Za-z]{2})\s+(?P<zip>\d{5}(?:-\d{4})?)\s*$", address)
    if not m:
        raise ValueError(
            f'Could not parse --address "{address}". '
            'Use the format: "1011 Tam Oshanter Dr, Kansas City, MO 64110"')
    return {k: v.strip() for k, v in m.groupdict().items()}


def slugify(street):
    slug = re.sub(r"[^a-z0-9]+", "-", street.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug) or "listing"


def unique_slug(base, existing):
    slug, n = base, 2
    while slug in existing:
        slug = f"{base}-{n}"
        n += 1
    return slug


def norm_address(street, zip_code):
    return re.sub(r"[^a-z0-9]", "", (street + (zip_code or "")).lower())


MANUAL_EXAMPLE = (
    '  python3 add_listing.py --address "1011 Tam Oshanter Dr, Kansas City, MO 64110" \\\n'
    '      --price 320000 --beds 3 --baths 2 --sqft 1500 --type Single-family \\\n'
    '      --agent-name "Your Name" --agent-phone "+1 (913) 555-0100" \\\n'
    '      --agent-email you@example.com'
)


def die_parse_failed(reason, url):
    print(f"Could not use the Redfin link ({reason}).\n"
          "Redfin sometimes blocks automated fetches. Re-run with the fields\n"
          "passed manually instead:\n" + MANUAL_EXAMPLE, file=sys.stderr)
    sys.exit(2)


def main():
    ap = argparse.ArgumentParser(
        description="Add a listing to the listings.myredeal.com template site.")
    ap.add_argument("--redfin-url", help="Public Redfin listing URL to parse.")
    ap.add_argument("--address",
                    help='Manual street address, format: "1011 Tam Oshanter Dr, Kansas City, MO 64110"')
    ap.add_argument("--city", help="Manual city (overrides parsed value).")
    ap.add_argument("--state", help="Manual 2-letter state (overrides parsed value).")
    ap.add_argument("--zip", dest="zip_code", help="Manual ZIP (overrides parsed value).")
    ap.add_argument("--price", help='Manual price, e.g. 320000 or "$320,000" (overrides parsed value).')
    ap.add_argument("--beds", type=int, help="Manual bedroom count.")
    ap.add_argument("--baths", help="Manual bathroom count, e.g. 2 or 2.5.")
    ap.add_argument("--sqft", type=int, help="Manual living-area square footage.")
    ap.add_argument("--type", default="Single-family",
                    help='Property type, e.g. "Single-family" or "Multi-family".')
    ap.add_argument("--agent-name", help="Listing agent's name.")
    ap.add_argument("--agent-phone", help="Listing agent's phone.")
    ap.add_argument("--agent-email", help="Listing agent's email.")
    ap.add_argument("--note", help="Short note shown on the listing (e.g. 'recent price cut').")
    ap.add_argument("--force", action="store_true",
                    help="Allow adding an address that is already listed.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse and print the listing without writing anything.")
    args = ap.parse_args()

    # 1) Parse Redfin (best effort).
    parsed = {}
    fetch_failed = False
    fail_reason = ""
    if args.redfin_url:
        try:
            parsed = parse_redfin(fetch_redfin(args.redfin_url))
        except Exception as e:  # network error, block, timeout…
            fetch_failed = True
            fail_reason = str(e) or type(e).__name__

    has_manual_core = bool(args.address and args.price)
    if (fetch_failed or not parsed.get("street") or not parsed.get("price")) \
            and not has_manual_core:
        die_parse_failed(
            fail_reason or "the page parsed but no address/price was found",
            args.redfin_url)

    # 2) Manual flags override parsed values (and are the full fallback path).
    data = dict(parsed)
    if args.address:
        data.update(parse_manual_address(args.address))
    for key, val in (("city", args.city), ("state", args.state),
                     ("zip", args.zip_code)):
        if val:
            data[key] = val.strip()
    if args.price:
        price = to_int(args.price)
        if not price or price <= 1000:
            ap.error(f'Could not read a valid --price from "{args.price}".')
        data["price"] = price
    if args.beds is not None:
        data["beds"] = args.beds
    if args.baths is not None:
        try:
            baths = float(args.baths)
        except (TypeError, ValueError):
            ap.error(f'Could not read --baths from "{args.baths}".')
        data["baths"] = int(baths) if baths.is_integer() else baths
    if args.sqft is not None:
        data["sqft"] = args.sqft
    if args.type:
        data["type"] = args.type.strip()

    # 3) Validate the required core.
    missing = [k for k in ("street", "city", "state", "zip", "price")
               if not data.get(k)]
    if missing:
        print("Missing required fields: " + ", ".join(missing) + ".\n"
              "Pass them manually, e.g.:\n" + MANUAL_EXAMPLE, file=sys.stderr)
        sys.exit(2)

    # 4) Load existing data, refuse duplicates unless --force.
    with open(DATA_FILE, encoding="utf-8") as f:
        listings = json.load(f)
    new_key = norm_address(data["street"], data.get("zip"))
    for lst in listings:
        if norm_address(lst.get("address", ""), lst.get("zip")) == new_key:
            if not args.force:
                print(f'"{data["street"]}" is already listed '
                      f'(/{lst["slug"]}). Pass --force to add it again.',
                      file=sys.stderr)
                sys.exit(3)
            break

    # 5) Build the listing record (schema matches listings.json).
    slug = unique_slug(slugify(data["street"]),
                       {l["slug"] for l in listings})
    listing = {
        "address": data["street"],
        "agent": (args.agent_name or "").strip() or None,
        "agent_email": (args.agent_email or "").strip() or None,
        "agent_phone": (args.agent_phone or "").strip() or None,
        "baths": data.get("baths"),
        "beds": data.get("beds"),
        "city": data["city"],
        "description": data.get("description") or None,
        "note": (args.note or "").strip() or None,
        "price": data["price"],
        "slug": slug,
        "sqft": data.get("sqft"),
        "state": data["state"].upper(),
        "type": data.get("type") or "Single-family",
        "zip": data["zip"],
    }
    # Drop nulls so the JSON stays tidy (build.py treats missing == unknown).
    listing = {k: v for k, v in listing.items() if v is not None}

    if args.dry_run:
        print(json.dumps(listing, indent=2, sort_keys=True))
        print(f"\nSlug: {slug}")
        print(f"URL:  {SITE_URL}/{slug}")
        print("Dry run — nothing written.")
        return

    listings.append(listing)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        f.write(json.dumps(listings, sort_keys=True, ensure_ascii=False))

    result = subprocess.run([sys.executable, os.path.join(ROOT, "build.py")],
                            capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        print("build.py failed:\n" + result.stderr, file=sys.stderr)
        sys.exit(4)

    page_path = os.path.join(ROOT, slug + ".html")
    print(f'Added: {data["street"]}, {data["city"]}, {data["state"]} {data["zip"]}')
    print(f"Page:  {page_path}")
    print(f"URL:   {SITE_URL}/{slug}")
    print(result.stdout.strip())


if __name__ == "__main__":
    main()
