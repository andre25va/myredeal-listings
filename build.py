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
  description (str or null — listing remarks, rendered verbatim when present),
  features (list[str] — property feature bullets),
  photos (list[str] — local /assets/photos/<slug>/N.jpg paths),
  mls (str or null), year_built (int or null), lot_size (str or null),
  status (str — defaults to "For Sale")

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


def hero_photo(lst):
    photos = lst.get("photos") or []
    return photos[0] if photos else None


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


def initials(name):
    parts = [p for p in re.split(r"\s+", name.strip()) if p and p[0].isalpha()]
    return "".join(p[0].upper() for p in parts[:2]) or "ROA"


def header(call_tel=None, call_display=None):
    call_btn = ""
    if call_tel:
        label = esc(call_display or "Call")
        call_btn = (f'<a class="header-call" href="tel:{esc(call_tel)}">{label}</a>')
    return f"""<header class="site-header">
  <div class="header-inner">
    <a class="brand-link" href="/"><img class="brand-logo" src="/assets/roa-logo-white-on-blue.png" alt="Realty of America"></a>
    <nav class="site-nav">
      <a href="/">All listings</a>
      <a href="/contact">Contact</a>
    </nav>
    {call_btn}
  </div>
</header>"""


def footer(lst=None):
    if lst:
        courtesy = (f"Listing courtesy of {lst['agent']}, Realty of America."
                    if lst.get("agent") else "Listing courtesy of Realty of America.")
        mls_line = (f"<p>MLS# {esc(lst['mls'])} &middot; Heartland MLS</p>"
                    if lst.get("mls") else "")
        addr_line = f"<p>{esc(full_address(lst))}</p>"
    else:
        courtesy = "Every active Realty of America listing across the Kansas City metro &mdash; one page."
        mls_line = ""
        addr_line = ""
    return f"""<footer class="site-footer">
  <div class="footer-inner">
    <img class="footer-logo" src="/assets/roa-logo-green-triangle.png" alt="Realty of America">
    {addr_line}
    <p>{courtesy}</p>
    {mls_line}
    <p>Information deemed reliable but not guaranteed.</p>
    <p>Equal Housing Opportunity. We support fair housing and equal opportunity in housing.</p>
    <div class="fine-print">{esc(FINE_PRINT)}</div>
  </div>
</footer>"""


def page(title, body, description="", call_tel=None, call_display=None, listing=None):
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
{header(call_tel, call_display)}
{body}
{footer(listing)}
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
        photo = hero_photo(lst)
        if photo:
            visual = (f'<div class="card-visual has-photo" style="background-image:url(\'{esc(photo)}\')">'
                      f'<div class="addr">{esc(lst["address"])}</div></div>')
        else:
            visual = (f'<div class="card-visual" style="background:{gradient_for(lst["slug"])}">'
                      f'<div class="addr">{esc(lst["address"])}<br><span style="font-weight:400;font-size:.85rem;opacity:.9">{esc(lst["city"])}, {esc(lst["state"])} {esc(lst["zip"])}</span></div></div>')
        cards.append(f"""<article class="card" data-city="{esc(city_group(lst))}" data-price="{lst['price']}">
  {visual}
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


def spec_tiles(lst):
    tiles = []
    if lst.get("beds"):
        tiles.append(("Beds", str(lst["beds"]), "Beds"))
    if lst.get("baths"):
        b = lst["baths"]
        b_str = str(int(b)) if float(b) == int(float(b)) else str(b)
        tiles.append((b_str, "Baths", "Baths"))
    if lst.get("sqft"):
        sq = f"{lst['sqft']:,}"
        if lst.get("sqft_approx"):
            sq = "~" + sq
        tiles.append((sq, "Sq Ft", "Square feet"))
    if lst.get("lot_size"):
        tiles.append((lst["lot_size"], "Lot", "Lot size"))
    return "".join(
        f'<div class="spec-tile"><div class="spec-num">{esc(v)}</div><div class="spec-label">{esc(l)}</div></div>'
        for v, l, _ in tiles)


def build_detail(lst):
    photos = lst.get("photos") or []
    n_photos = len(photos)
    status = lst.get("status") or "For Sale"
    agent_name, agent_email, agent_phone_display, agent_phone_tel = agent_contact(lst)
    addr = full_address(lst)
    maps_embed = ("https://www.google.com/maps?q=" + urllib.parse.quote_plus(addr) + "&output=embed")
    inquiry_subject = urllib.parse.quote("Showing request: " + addr)

    # Hero
    hero = hero_photo(lst)
    if hero:
        hero_style = f"background-image:url('{esc(hero)}')"
        hero_cls = "prop-hero has-photo"
    else:
        hero_style = f"background:{gradient_for(lst['slug'])}"
        hero_cls = "prop-hero"
    hero_html = f"""<section class="{hero_cls}" style="{hero_style}">
    <span class="sale-badge">{esc(status)}</span>
    <img class="hero-watermark" src="/assets/roa-logo-white-on-blue.png" alt="Realty of America">
    {'<a class="photos-btn" href="#photos">View all ' + str(n_photos) + ' photos &#8599;</a>' if n_photos > 1 else ''}
  </section>"""

    # Title block
    mls_line = (f'<div class="mls-line">MLS# {esc(lst["mls"])} &middot; Heartland MLS</div>'
                if lst.get("mls") else "")
    title_html = f"""<section class="title-block">
    <div class="eyebrow">{esc(lst['city'])}, {esc(lst['state'])}</div>
    <h1>{esc(lst['address'])}</h1>
    <div class="title-sub">{esc(lst['city'])}, {esc(lst['state'])} {esc(lst['zip'])}</div>
    <div class="detail-price">{fmt_price(lst['price'])}</div>
    {mls_line}
  </section>"""

    # Specs + CTAs
    cta_html = f"""<section class="cta-band">
    <div class="spec-tiles">{spec_tiles(lst)}</div>
    <div class="cta-row">
      <a class="btn btn-primary" href="#showing">Schedule a Showing &#8599;</a>
      <a class="btn btn-outline" href="tel:{esc(agent_phone_tel)}">Call</a>
      <a class="btn btn-outline" href="sms:{esc(agent_phone_tel)}">Text</a>
    </div>
  </section>"""

    # Gallery
    if photos:
        thumbs = "".join(
            f'<button class="thumb" data-full="{esc(p)}" aria-label="Enlarge photo {i+1}">'
            f'<img loading="lazy" src="{esc(p)}" alt="{esc(lst["address"])} photo {i+1}"></button>'
            for i, p in enumerate(photos))
        gallery_html = f"""<section class="section" id="photos">
    <div class="eyebrow">A closer look at home</div>
    <h2>{n_photos} photos &middot; <span class="muted-sm">Select to enlarge</span></h2>
    <div class="gallery">{thumbs}</div>
  </section>
  <div class="lightbox" id="lightbox" hidden>
    <button class="lb-close" aria-label="Close">&times;</button>
    <img id="lb-img" src="" alt="Enlarged listing photo">
  </div>
  <script>
  (function(){{
    var lb=document.getElementById('lightbox'),img=document.getElementById('lb-img');
    document.querySelectorAll('.thumb').forEach(function(t){{
      t.addEventListener('click',function(){{img.src=t.dataset.full;lb.hidden=false;document.body.style.overflow='hidden';}});
    }});
    function close(){{lb.hidden=true;img.src='';document.body.style.overflow='';}}
    lb.addEventListener('click',close);
    document.querySelector('.lb-close').addEventListener('click',close);
    document.addEventListener('keydown',function(e){{if(e.key==='Escape')close();}});
  }})();
  </script>"""
    else:
        gallery_html = ""

    # About
    about_html = ""
    if lst.get("description"):
        tags = []
        if lst.get("type"):
            tags.append(lst["type"])
        if lst.get("year_built"):
            tags.append(f"Built in {lst['year_built']}")
        tag_html = "".join(f'<span class="tag">{esc(t)}</span>' for t in tags)
        paras = "".join(f"<p>{esc(p.strip())}</p>"
                        for p in re.split(r"\n{2,}|\r\n\r\n", lst["description"]) if p.strip())
        about_html = f"""<section class="section about">
    <div class="eyebrow">Space for your everyday</div>
    <h2>About this home</h2>
    {paras}
    <div class="tag-row">{tag_html}</div>
  </section>"""

    # Features
    features_html = ""
    if lst.get("features"):
        items = "".join(f'<li><span class="check">&check;</span> {esc(f)}</li>'
                        for f in lst["features"])
        features_html = f"""<section class="section">
    <div class="eyebrow">The details that matter</div>
    <h2>Property features</h2>
    <ul class="features">{items}</ul>
  </section>"""

    # Map
    map_html = f"""<section class="section">
    <div class="eyebrow">Explore the location</div>
    <h2>Find your way home</h2>
    <div class="map-wrap"><iframe title="Map of {esc(addr)}" src="{esc(maps_embed)}" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe></div>
    <p class="map-addr">{esc(addr)}</p>
  </section>"""

    # Agent card + showing form
    form_id = "showing-form"
    agent_html = f"""<section class="agent-cta" id="showing">
    <div class="eyebrow light">See it for yourself</div>
    <h2>Let&rsquo;s get you<br>through the door.</h2>
    <p class="agent-sub">Request a showing or ask a question.</p>
    <div class="agent-line">
      <span class="avatar">{esc(initials(agent_name))}</span>
      <div>
        <div class="agent-name">{esc(agent_name)}</div>
        <div class="agent-broker">Realty of America</div>
      </div>
    </div>
    <div class="agent-contact">
      <a href="tel:{esc(agent_phone_tel)}">{esc(agent_phone_display)}</a><br>
      <a href="mailto:{esc(agent_email)}">{esc(agent_email)}</a>
    </div>
    <form class="showing-form" id="{form_id}">
      <h3>Schedule a showing</h3>
      <p class="req-note">Fields marked * are required.</p>
      <label>Name *<input required name="name" type="text" autocomplete="name"></label>
      <label>Phone *<input required name="phone" type="tel" autocomplete="tel"></label>
      <label>Email *<input required name="email" type="email" autocomplete="email"></label>
      <label>Message *<textarea required name="message" rows="4">I&rsquo;d like to schedule a showing for {esc(addr)}.</textarea></label>
      <button class="btn btn-primary" type="submit">Request a Showing &#8599;</button>
      <p class="form-note">Submitting opens your email app addressed to {esc(agent_name)} &mdash; no account needed.</p>
    </form>
  </section>
  <script>
  (function(){{
    var f=document.getElementById('{form_id}');
    f.addEventListener('submit',function(e){{
      e.preventDefault();
      var d=new FormData(f);
      var subject=encodeURIComponent('Showing request: {esc(addr)}');
      var body=encodeURIComponent('Name: '+d.get('name')+'\\nPhone: '+d.get('phone')+'\\nEmail: '+d.get('email')+'\\n\\n'+d.get('message'));
      window.location.href='mailto:{esc(agent_email)}?subject='+subject+'&body='+body;
    }});
  }})();
  </script>"""

    body = f"""<main class="detail-wrap rich">
  <div class="breadcrumb"><a href="/">&larr; All listings</a></div>
  {hero_html}
  {title_html}
  {cta_html}
  {gallery_html}
  {about_html}
  {features_html}
  {map_html}
  {agent_html}
</main>"""
    return page(f"{lst['address']} — {fmt_price(lst['price'])} | MyReDeal Listings", body,
                f"{addr} listed at {fmt_price(lst['price'])}. {specs_line(lst)}.",
                call_tel=agent_phone_tel, call_display="Call", listing=lst)


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
