#!/usr/bin/env python3
"""Generate the listings.myredeal.com static site from listings.json.

Usage:  python3 build.py
Reads:  listings.json   (array of listing objects; null = unknown, omit it)
Writes: index.html, contact.html, <slug>.html (one per listing)

Listing fields:
  slug, address, city, state, zip, price (int),
  beds, baths (int or null), sqft (int or null), sqft_approx (bool),
  type ("Single-family" | "Multi-family"), agent (str or null), note (str or null),
  agent_phone (str or null), agent_email (str or null),
  description (str or null — listing remarks, rendered verbatim when present)

Per-listing agent contact (agent_phone / agent_email) overrides the site-wide
defaults (EMAIL / PHONE_DISPLAY) on that listing's detail page.
"""
import html
import json
import os
import re
import urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
EMAIL = "tc@myredeal.com"
PHONE_DISPLAY = "+1 (474) 733-3257"
PHONE_TEL = "+14747333257"
OFFICE = "8100 Marty Street, Overland Park, KS 66204"
FINE_PRINT = ("Listing data compiled from public sources, October 2026. "
              "Availability, price, and details subject to change \u2014 "
              "contact the listing agent to confirm.")

# Tasteful gradient placeholders (never fake photos). Picked by hash of slug.
# ROA brand family: Powersuit Blue depths with Legacy Green accents.
GRADIENTS = [
    "linear-gradient(135deg,#0B1E44 0%,#10295A 55%,#1A9175 160%)",
    "linear-gradient(135deg,#10295A 0%,#1E3F7E 60%,#2E5AA0 130%)",
    "linear-gradient(135deg,#0B1E44 0%,#14406B 70%,#1A9175 165%)",
    "linear-gradient(135deg,#10295A 0%,#1A5C6B 160%)",
    "linear-gradient(135deg,#14305E 0%,#1E3F7E 55%,#1A9175 160%)",
]


def esc(s):
    return html.escape(str(s), quote=True)


def fmt_price(n):
    return "${:,}".format(n)


def full_address(lst):
    return f"{lst['address']}, {lst['city']}, {lst['state']} {lst['zip']}"


def specs_line(lst):
    """Compact '4 bd · 2 ba · 1,730 sqft' line; omits unknowns."""
    parts = []
    if lst.get("beds"):
        parts.append(f"{lst['beds']} bd")
    if lst.get("baths"):
        parts.append(f"{lst['baths']} ba")
    if lst.get("sqft"):
        sq = f"{lst['sqft']:,} sqft"
        if lst.get("sqft_approx"):
            sq = "~" + sq
        parts.append(sq)
    return " \u00b7 ".join(parts) if parts else lst["type"]


def gradient_for(slug):
    return GRADIENTS[abs(hash(slug)) % len(GRADIENTS)]


def agent_contact(lst):
    """Per-listing agent contact, falling back to the site-wide defaults.

    Returns (name, email, phone_display, phone_tel). Listings may carry
    optional agent_phone / agent_email fields; anything missing falls back
    to EMAIL / PHONE_DISPLAY / PHONE_TEL.
    """
    name = lst.get("agent") or "the listing agent"
    email = (lst.get("agent_email") or "").strip() or EMAIL
    raw_phone = (lst.get("agent_phone") or "").strip()
    if raw_phone:
        digits = re.sub(r"\D", "", raw_phone)
        if len(digits) == 10:
            phone_tel = "+1" + digits
            phone_display = f"+1 ({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
        elif len(digits) == 11 and digits.startswith("1"):
            phone_tel = "+" + digits
            phone_display = f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:11]}"
        else:
            phone_tel = digits
            phone_display = raw_phone
    else:
        phone_tel, phone_display = PHONE_TEL, PHONE_DISPLAY
    return name, email, phone_display, phone_tel


def header():
    return f"""<header class="site-header">
  <div class="header-inner">
    <a class="brand-link" href="/"><img class="brand-logo" src="/assets/roa-logo-white-on-blue.png" alt="Realty of America"></a>
    <nav class="site-nav">
      <a href="/">All listings</a>
      <a href="/contact">Contact</a>
    </nav>
  </div>
</header>"""


def footer():
    return f"""<footer class="site-footer">
  <div class="footer-inner">
    <img class="footer-logo" src="/assets/roa-logo-green-triangle.png" alt="Realty of America">
    <div class="footer-grid">
      <div>
        <h3>MyReDeal Listings</h3>
        <p>Every active Realty of America listing across the Kansas City metro &mdash; one page.</p>
      </div>
      <div>
        <h3>Contact</h3>
        <p><a href="mailto:{EMAIL}">{EMAIL}</a><br>
        <a href="tel:{PHONE_TEL}">{PHONE_DISPLAY}</a><br>
        {esc(OFFICE)}</p>
      </div>
      <div>
        <h3>Browse</h3>
        <p><a href="/">All listings</a><br><a href="/contact">Contact us</a></p>
      </div>
    </div>
    <div class="fine-print">{esc(FINE_PRINT)}</div>
  </div>
</footer>"""


def page(title, body, description=""):
    desc_tag = (f'<meta name="description" content="{esc(description)}">' if description else "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
{desc_tag}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=Figtree:wght@600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/styles.css">
</head>
<body>
{header()}
{body}
{footer()}
</body>
</html>
"""


def city_group(lst):
    return f"{lst['city']}, {lst['state']}"


def build_index(listings):
    cards = []
    for lst in listings:
        agent_html = (f'<div class="card-agent">Listed by <strong>{esc(lst["agent"])}</strong></div>'
                      if lst.get("agent") else "")
        note_html = (f'<div class="card-note">{esc(lst["note"])}</div>'
                     if lst.get("note") else "")
        cards.append(f"""<article class="card" data-city="{esc(city_group(lst))}" data-price="{lst['price']}">
  <div class="card-visual" style="background:{gradient_for(lst['slug'])}">
    <div class="addr">{esc(lst['address'])}<br><span style="font-weight:400;font-size:.85rem;opacity:.9">{esc(lst['city'])}, {esc(lst['state'])} {esc(lst['zip'])}</span></div>
  </div>
  <div class="card-body">
    <div class="card-price">{fmt_price(lst['price'])}</div>
    <div class="card-specs">{esc(specs_line(lst))} &middot; {esc(lst['type'])}</div>
    {agent_html}
    {note_html}
    <a class="card-link" href="/{esc(lst['slug'])}">View details &rarr;</a>
  </div>
</article>""")

    cities = sorted({city_group(l) for l in listings})
    chips = ['<button class="chip active" data-filter="all">All</button>'] + [
        f'<button class="chip" data-filter="{esc(c)}">{esc(c)}</button>' for c in cities
    ]

    body = f"""<section class="hero">
  <h1>Kansas City <span class="accent">Listings</span></h1>
  <p>Every active Realty of America listing across the KC metro &mdash; one page.</p>
  <div class="count">{len(listings)} active listings</div>
</section>
<div class="toolbar">
  <div class="toolbar-card">
    <div class="filter-group">
      <span class="label">City</span>
      {''.join(chips)}
    </div>
    <div class="filter-group">
      <span class="label">Sort</span>
      <select class="chip" id="sort">
        <option value="featured">Featured</option>
        <option value="asc">Price: low to high</option>
        <option value="desc">Price: high to low</option>
      </select>
    </div>
  </div>
</div>
<main class="grid-wrap">
  <div class="grid" id="grid">
    {''.join(cards)}
  </div>
</main>
<script>
(function () {{
  var chips = Array.prototype.slice.call(document.querySelectorAll('.chip[data-filter]'));
  var sortSel = document.getElementById('sort');
  var grid = document.getElementById('grid');
  var cards = Array.prototype.slice.call(grid.querySelectorAll('.card'));
  var original = cards.slice();
  var activeCity = 'all';

  function render() {{
    var visible = cards.filter(function (c) {{
      return activeCity === 'all' || c.dataset.city === activeCity;
    }});
    var mode = sortSel.value;
    if (mode === 'asc') visible.sort(function (a, b) {{ return a.dataset.price - b.dataset.price; }});
    else if (mode === 'desc') visible.sort(function (a, b) {{ return b.dataset.price - a.dataset.price; }});
    else visible.sort(function (a, b) {{ return original.indexOf(a) - original.indexOf(b); }});
    grid.innerHTML = '';
    if (!visible.length) {{
      grid.innerHTML = '<div class="empty-state">No listings match that filter yet.</div>';
    }} else {{
      visible.forEach(function (c) {{ grid.appendChild(c); }});
    }}
  }}

  chips.forEach(function (chip) {{
    chip.addEventListener('click', function () {{
      chips.forEach(function (c) {{ c.classList.remove('active'); }});
      chip.classList.add('active');
      activeCity = chip.dataset.filter;
      render();
    }});
  }});
  sortSel.addEventListener('change', render);
}})();
</script>"""
    return page("Kansas City Listings | MyReDeal Listings", body,
                "Every active Realty of America listing across the Kansas City metro — one page.")


def describe(lst):
    """Honest description built only from known facts. Never invents features."""
    addr = full_address(lst)
    bits = [f"{addr} is listed at {fmt_price(lst['price'])}."]
    facts = []
    if lst.get("beds") and lst.get("baths"):
        facts.append(f"{lst['beds']}-bedroom, {lst['baths']}-bath")
    if lst.get("sqft"):
        sq = f"{lst['sqft']:,} square feet"
        facts.append(("about " if lst.get("sqft_approx") else "") + sq)
    facts.append(lst["type"].lower())
    bits.append("This " + ", ".join(facts) + ".")
    if lst.get("sqft") and not lst.get("sqft_approx"):
        ppsf = lst["price"] / lst["sqft"]
        bits.append(f"That works out to about ${ppsf:,.0f} per square foot.")
    if lst.get("agent"):
        bits.append(f"Listed by {lst['agent']}.")
    if lst.get("note"):
        bits.append(lst["note"][0].upper() + lst["note"][1:] + ".")
    bits.append("Contact the listing agent to confirm availability, price, and details before making plans.")
    return " ".join(bits)


def build_detail(lst):
    rows = []
    if lst.get("beds"):
        rows.append(("Bedrooms", str(lst["beds"])))
    if lst.get("baths"):
        rows.append(("Bathrooms", str(lst["baths"])))
    if lst.get("sqft"):
        sq = f"{lst['sqft']:,} sqft"
        if lst.get("sqft_approx"):
            sq = "About " + sq
        rows.append(("Living area", sq))
    rows.append(("Property type", lst["type"]))
    if lst.get("agent"):
        rows.append(("Listing agent", lst["agent"]))
    rows.append(("Brokerage", "Realty of America"))
    fact_rows = "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in rows)

    note_html = (f'<div class="detail-note">{esc(lst["note"][0].upper() + lst["note"][1:])}.</div>'
                 if lst.get("note") else "")
    remarks_html = (f'<h3 class="remarks-title">Listing remarks</h3>'
                    f'<p class="detail-desc">{esc(lst["description"])}</p>'
                    if lst.get("description") else "")
    agent_name, agent_email, agent_phone_display, agent_phone_tel = agent_contact(lst)
    maps_url = ("https://www.google.com/maps/search/?api=1&query=" +
                urllib.parse.quote_plus(full_address(lst)))
    inquiry_subject = urllib.parse.quote("Inquiry: " + full_address(lst))

    body = f"""<main class="detail-wrap">
  <div class="breadcrumb"><a href="/">&larr; All listings</a></div>
  <div class="detail-hero">
    <div class="detail-visual" style="background:{gradient_for(lst['slug'])}">
      <div class="addr">
        <h1>{esc(lst['address'])}</h1>
        <div class="sub">{esc(lst['city'])}, {esc(lst['state'])} {esc(lst['zip'])}</div>
      </div>
    </div>
    <div class="detail-body">
      <div class="detail-price">{fmt_price(lst['price'])}</div>
      {note_html}
      <table class="facts">
        {fact_rows}
      </table>
      <p class="detail-desc">{esc(describe(lst))}</p>
      {remarks_html}
      <div class="cta-row">
        <a class="btn btn-primary" href="{maps_url}" target="_blank" rel="noopener">Get directions</a>
        <a class="btn btn-cta" href="/contact">Contact about this home</a>
      </div>
      <div class="agent-card">
        <h2>Interested in <span class="accent">{esc(lst['address'])}</span>?</h2>
        <p>Reach out and {esc(agent_name)} will get back to you about {esc(full_address(lst))}.</p>
        <div class="cta-row">
          <a class="btn btn-cta" href="mailto:{esc(agent_email)}?subject={inquiry_subject}">Email {esc(agent_name)}</a>
          <a class="btn btn-outline" style="border-color:#fff;color:#fff" href="tel:{esc(agent_phone_tel)}">{esc(agent_phone_display)}</a>
        </div>
      </div>
    </div>
  </div>
</main>"""
    return page(f"{lst['address']} — {fmt_price(lst['price'])} | MyReDeal Listings", body,
                f"{full_address(lst)} listed at {fmt_price(lst['price'])}. {specs_line(lst)}.")


def build_contact():
    body = f"""<main>
  <div class="contact-card">
    <h1>Contact us</h1>
    <p>Questions about any listing? Want to schedule a showing? Get in touch.</p>
    <p><strong>Email:</strong> <a href="mailto:{EMAIL}">{EMAIL}</a></p>
    <p><strong>Phone:</strong> <a href="tel:{PHONE_TEL}">{PHONE_DISPLAY}</a></p>
    <p><strong>Office:</strong> {esc(OFFICE)}</p>
    <p style="margin-top:18px"><a class="btn btn-primary" href="/">Browse all listings</a></p>
  </div>
</main>"""
    return page("Contact | MyReDeal Listings", body, "Contact MyReDeal Listings about any Kansas City area listing.")


def main():
    with open(os.path.join(ROOT, "listings.json"), encoding="utf-8") as f:
        listings = json.load(f)

    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_index(listings))
    with open(os.path.join(ROOT, "contact.html"), "w", encoding="utf-8") as f:
        f.write(build_contact())
    for lst in listings:
        path = os.path.join(ROOT, lst["slug"] + ".html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(build_detail(lst))
    print(f"Built index.html, contact.html, and {len(listings)} listing pages.")


if __name__ == "__main__":
    main()
