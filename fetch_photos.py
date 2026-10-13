#!/usr/bin/env python3
"""Download listing photos and merge rich data into listings.json.

Reads:  listings.json, listing_data.json  (from the data-gathering agent)
Writes: assets/photos/<slug>/<n>.jpg, updated listings.json

Photo fields added per listing: photos[], description, features[], mls,
year_built, lot_size. Andre's own listings get his public contact info.
"""
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
PHOTO_DIR = os.path.join(ROOT, "assets", "photos")
MAX_PHOTOS = 10

# Andre's public listing contact (matches his other marketing).
ANDRE_PHONE = "(312) 998-9898"
ANDRE_EMAIL = "info@andrevargasteam.com"

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def download(url, dest):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
        f.write(r.read())


def main():
    with open(os.path.join(ROOT, "listings.json"), encoding="utf-8") as f:
        listings = json.load(f)
    data_path = os.path.join(ROOT, "listing_data.json")
    if not os.path.exists(data_path):
        print("listing_data.json not found — nothing to merge.")
        return
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    for lst in listings:
        slug = lst["slug"]
        d = data.get(slug) or {}

        # Andre's own listings carry his public contact info.
        if (lst.get("agent") or "").strip().startswith("Andre Vargas"):
            lst.setdefault("agent_phone", ANDRE_PHONE)
            lst.setdefault("agent_email", ANDRE_EMAIL)

        for key in ("description", "features", "mls", "year_built", "lot_size"):
            if d.get(key):
                lst[key] = d[key]

        photos = (d.get("photos") or [])[:MAX_PHOTOS]
        saved = []
        if photos:
            dest_dir = os.path.join(PHOTO_DIR, slug)
            os.makedirs(dest_dir, exist_ok=True)
            for i, url in enumerate(photos, 1):
                dest = os.path.join(dest_dir, f"{i}.jpg")
                try:
                    download(url, dest)
                    saved.append(f"/assets/photos/{slug}/{i}.jpg")
                    print(f"  {slug}: photo {i} ok")
                except Exception as e:
                    print(f"  {slug}: photo {i} FAILED ({e})")
        lst["photos"] = saved

    with open(os.path.join(ROOT, "listings.json"), "w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2, ensure_ascii=False)
    total = sum(len(l.get("photos", [])) for l in listings)
    print(f"Merged. {total} photos across {len(listings)} listings.")


if __name__ == "__main__":
    main()
