# listings.myredeal.com

Static listings site for Realty of America KC-metro listings. Repo root is the
web root — generated HTML/CSS sits at the top level for Vercel static deploy.

## Template usage

This repo is a reusable template: any agent can generate listing pages for
their own market by feeding in a Redfin link plus agent contact info.

1. **Fork or copy this repo** for your own site.
2. **Add a listing** — one command does it all (fetch, parse, append, rebuild):
   ```bash
   python3 add_listing.py --redfin-url "https://www.redfin.com/..." \
       --agent-name "Your Name" \
       --agent-phone "+1 (913) 555-0100" \
       --agent-email you@example.com
   ```
   If Redfin blocks the fetch, pass the fields manually instead:
   ```bash
   python3 add_listing.py --address "1011 Tam Oshanter Dr, Kansas City, MO 64110" \
       --price 320000 --beds 3 --baths 2 --sqft 1500 --type Single-family \
       --agent-name "Your Name" --agent-phone "+1 (913) 555-0100" \
       --agent-email you@example.com
   ```
   Preview without writing anything with `--dry-run`. See all options with
   `python3 add_listing.py --help`. Each listing's page lands at
   `https://<your-domain>/<slug>` (e.g. `/1011-tam-oshanter-dr`).
3. **Push** — commit the updated `listings.json` and regenerated HTML;
   Vercel redeploys automatically.
4. **Point your subdomain** — add your domain (e.g. `listings.yoursite.com`)
   under Project → Settings → Domains in Vercel, then add the DNS record
   Vercel shows at your registrar.

Per-listing `agent_phone` / `agent_email` in `listings.json` override the
site-wide contact on that listing's page; listings without them fall back to
the site defaults.

## Files

- `listings.json` — the source of truth. Edit prices, add/remove listings here.
- `build.py` — generates `index.html`, `contact.html`, and one `<slug>.html`
  per listing from `listings.json`. Unknown fields (`null`) are omitted from
  pages automatically.
- `styles.css` — the whole design system (navy + gold, mobile-responsive).
- `vercel.json` — `{"cleanUrls": true}` so `/5633-harrison-st` serves
  `5633-harrison-st.html`.

## Rebuild

```bash
cd ~/workspace/myredeal-listings
python3 build.py
```

Then commit the regenerated HTML.

## Deploy

1. Push this folder to a new GitHub repo (e.g. `myredeal-listings`).
2. In Vercel: Add New Project → import the repo. No build command needed
   (static output, already generated). Framework preset: Other.
3. Add the custom domain `listings.myredeal.com` under Project → Settings → Domains.
4. Vercel will show the DNS record to add (a CNAME). Add it at the domain's
   registrar — DNS for myredeal.com lives outside Vercel.

## Notes

- Listing "photos" are CSS gradient placeholders with the address overlaid —
  never fake photos, never lorem ipsum.
- Descriptions are generated only from known facts in `listings.json`.
- Data compiled from public sources, October 2026.
