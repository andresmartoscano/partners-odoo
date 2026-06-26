"""
Odoo.com Spain Partner Directory Scraper
Generates index.html from template.html with live data from odoo.com.
Run: python scraper.py
"""
import requests
import json
import re
import time
import os
import sys
import html as ihtml

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
BASE = "https://www.odoo.com"
LISTING_BASE = f"{BASE}/es_ES/partners/country/spain-67"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ── HTTP ──────────────────────────────────────────────────────────────────────

def get(url, retries=3, delay=1.5):
    for attempt in range(retries):
        try:
            time.sleep(delay)
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.text
        except Exception as e:
            if attempt == retries - 1:
                print(f"  ERROR fetching {url}: {e}", file=sys.stderr)
                return ""
            time.sleep(2 ** attempt)
    return ""


# ── LISTING PAGES — partner cards with all stats ────────────────────────────────

def parse_int(text):
    cleaned = re.sub(r'[^\d]', '', text)
    return int(cleaned) if cleaned else 0


def parse_cards(html):
    """Parse every partner card on a listing page.

    The listing page renders one card per partner, each wrapped in an anchor
    with aria-label="Ir al distribuidor" pointing at the detail page. The card
    already carries every numeric stat we need (grade, retention %, average and
    largest project size, reference count and certified-expert count), so we
    read them here and only visit the detail page for the client list + sectors.
    """
    cards = []
    anchors = list(re.finditer(
        r'aria-label="Ir al distribuidor"\s+href="(/es_ES/partners/[^"?#]+)', html))
    starts = [m.start() for m in anchors] + [len(html)]
    for i, m in enumerate(anchors):
        block = html[m.start():starts[i + 1]]
        slug = m.group(1)

        nm = re.search(r'<h5[^>]*>\s*<span>([^<]+)</span>', block)
        name = ihtml.unescape(nm.group(1)).strip() if nm else \
            slug.split("/")[-1].replace("-", " ").title()

        # Grade badge classes: bg_gold / bg_silver / (none → Ready)
        if "bg_gold" in block:
            grade = "Gold"
        elif "bg_silver" in block:
            grade = "Silver"
        else:
            grade = "Ready"

        rt = re.search(r'<small><span>(\d+)</span>\s*%', block)
        retention = int(rt.group(1)) if rt else 0
        avg = re.search(r'Proyecto medio:.*?(\d[\d.]*)\s*usuarios', block, re.DOTALL)
        avg_users = parse_int(avg.group(1)) if avg else 0
        lg = re.search(r'Proyecto m[^:]*grande:.*?(\d[\d.+]*)\s*usuarios', block, re.DOTALL)
        large_users = parse_int(lg.group(1)) if lg else 0
        rf = re.search(r'(\d[\d.,]*)\s*Referencias', block)
        refs = parse_int(rf.group(1)) if rf else 0
        ex = re.search(r'(\d[\d.,]*)\s*con certificaci', block)
        experts = parse_int(ex.group(1)) if ex else 0

        rid_m = re.search(r'-(\d+)$', slug)
        cards.append({
            "slug": slug,
            "rid": rid_m.group(1) if rid_m else "",
            "name": name,
            "grade": grade,
            "retention": retention,
            "refs": refs,
            "avgUsers": avg_users,
            "largeUsers": large_users,
            "experts": experts,
            "url": f"{BASE}{slug}",
        })
    return cards


def scrape_listing():
    """Paginate the Spain partner directory and return all partner cards."""
    cards = []
    seen = set()
    MAX_PAGES = 20  # safety cap; Spain has ~5 pages of 20
    for page in range(1, MAX_PAGES + 1):
        url = LISTING_BASE if page == 1 else f"{LISTING_BASE}?page={page}"
        print(f"  Listing page {page}: {url}")
        html = get(url, delay=2)
        page_cards = parse_cards(html)
        if not page_cards:
            break  # no more partners
        new = 0
        for c in page_cards:
            if c["slug"] not in seen:
                seen.add(c["slug"])
                cards.append(c)
                new += 1
        if new == 0:
            break  # pagination wrapped around / repeated last page
    print(f"  Found {len(cards)} partner cards")
    return cards


# ── INDIVIDUAL PARTNER PAGE — client references + sectors ───────────────────────

def scrape_partner(card, idx):
    """Visit a partner's detail page to collect its client references and the
    partner's own industry sector(s). Numeric stats already came from the card."""
    slug = card["slug"]
    url = f"{BASE}{slug}?country_id=67"
    html = get(url, delay=1.5)
    if not html:
        # Detail fetch failed — keep the card stats, just no client list.
        return {**{k: card[k] for k in
                   ("rid", "name", "grade", "retention", "refs",
                    "avgUsers", "largeUsers", "experts", "url")},
                "id": idx, "sectors": [], "refs_list": []}

    # ── Client reference names + sectors ──────────────────────────────────────
    # Each client reference is rendered as a card containing an anchor
    #   <a href="/es_ES/customers/<slug>-<id>"><span>CLIENT NAME</span></a>
    # optionally followed (within the same card) by a sector badge
    #   <span class="badge ms-1 text-bg-secondary">SECTOR</span>
    #
    # The customer anchor is present for every reference, so we key off it and
    # bound each reference's sector lookup to the slice before the next anchor.
    refs_list = []
    anchors = list(re.finditer(r'<a\s+href="/es_ES/customers/[^"]+"\s*>(.*?)</a>', html, re.DOTALL))
    for j, a in enumerate(anchors):
        cname = re.sub(r'<[^>]+>', '', a.group(1))      # strip any nested tags
        cname = ihtml.unescape(cname).strip()
        if not cname:
            continue
        start = a.end()
        end = anchors[j + 1].start() if j + 1 < len(anchors) else len(html)
        # Client sector badges carry the ms-1 modifier; the partner's own sector
        # badge does not, so this regex won't pick it up by mistake.
        s_m = re.search(r'ms-1 text-bg-secondary">([^<]+)</span>', html[start:end])
        s = ihtml.unescape(s_m.group(1)).strip() if s_m else ""
        refs_list.append({"n": cname, "s": s})

    # ── Partner's own industry sector(s) ──────────────────────────────────────
    # Rendered as <span class="badge text-bg-secondary">SECTOR</span> (no ms-1),
    # before the client references list begins.
    head = html[:anchors[0].start()] if anchors else html
    sector_raw = re.findall(r'<span class="badge text-bg-secondary">([^<]+)</span>', head)
    sectors = [[ihtml.unescape(s).strip(), None] for s in dict.fromkeys(sector_raw) if s.strip()]

    # Prefer the actual client count from the detail page; fall back to the
    # card's reference count if no client anchors were found.
    refs = len(refs_list) if refs_list else card["refs"]

    return {
        "id": idx,
        "rid": card["rid"],
        "name": card["name"],
        "grade": card["grade"],
        "retention": card["retention"],
        "refs": refs,
        "avgUsers": card["avgUsers"],
        "largeUsers": card["largeUsers"],
        "experts": card["experts"],
        "sectors": sectors,
        "url": card["url"],
        "refs_list": refs_list,
    }


# ── BUILD JS DATA ──────────────────────────────────────────────────────────────

def build_partners_js(partners):
    # Sort: Gold first, then Silver, then Ready; within each grade by refs desc
    grade_order = {"Gold": 0, "Silver": 1, "Ready": 2}
    sorted_p = sorted(partners, key=lambda p: (grade_order.get(p["grade"], 3), -p["refs"]))

    lines = ["const PARTNERS = ["]
    for i, p in enumerate(sorted_p):
        p["id"] = i + 1  # re-number after sort
        sectors_js = json.dumps(p["sectors"], ensure_ascii=False)
        url_js = f'"{p["url"]}"' if p["url"] else "null"
        comma = "," if i < len(sorted_p) - 1 else ""
        lines.append(
            f'  {{ id:{p["id"]}, rid:"{p["rid"]}", name:{json.dumps(p["name"], ensure_ascii=False)}, '
            f'grade:"{p["grade"]}", retention:{p["retention"]}, refs:{p["refs"]}, '
            f'avgUsers:{p["avgUsers"]}, largeUsers:{p["largeUsers"]}, experts:{p["experts"]}, '
            f'sectors:{sectors_js}, url:{url_js} }}{comma}'
        )
    lines.append("];")
    return "\n".join(lines), sorted_p


def build_refs_js(partners):
    refs_obj = {}
    for p in partners:
        if p["refs_list"] and p["rid"]:
            refs_obj[p["rid"]] = [{"n": r["n"], "s": r["s"]} for r in p["refs_list"]]
    return "const REFS=" + json.dumps(refs_obj, ensure_ascii=False, separators=(",", ":")) + ";"


# ── GENERATE HTML ──────────────────────────────────────────────────────────────

def build_html(partners_js, refs_js, partners):
    template_path = os.path.join(SCRIPT_DIR, "template.html")
    out_path = os.path.join(SCRIPT_DIR, "..", "index.html")

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    gold = sum(1 for p in partners if p["grade"] == "Gold")
    silver = sum(1 for p in partners if p["grade"] == "Silver")
    ready = sum(1 for p in partners if p["grade"] == "Ready")
    total = len(partners)

    from datetime import date
    month_es = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    today = date.today()
    date_str = f"{month_es[today.month-1]} {today.year}"

    html = template.replace("__PARTNERS_DATA__", partners_js)
    html = html.replace("__REFS_DATA__", refs_js)
    html = re.sub(
        r'\d+\s*partners\s*·[^·]+·\s*fuente',
        f'{total} partners · {date_str} · fuente',
        html
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Generated index.html ({os.path.getsize(out_path)//1024} KB)")
    print(f"  {gold} Gold / {silver} Silver / {ready} Ready — {total} total")


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Odoo Spain Partners Scraper ===")

    print("\n[1/3] Scraping listing pages for partner cards...")
    cards = scrape_listing()

    if len(cards) < 10:
        print(f"ERROR: Only {len(cards)} partner cards found — aborting to avoid overwriting with bad data.", file=sys.stderr)
        sys.exit(1)

    print(f"\n[2/3] Scraping {len(cards)} partner detail pages...")
    partners = []
    for i, card in enumerate(cards):
        print(f"  [{i+1}/{len(cards)}] {card['name']}")
        p = scrape_partner(card, i + 1)
        if p:
            partners.append(p)

    if len(partners) < 10:
        print(f"ERROR: Only {len(partners)} partners scraped — aborting to avoid overwriting with bad data.", file=sys.stderr)
        sys.exit(1)

    print(f"\n[3/3] Building HTML...")
    partners_js, partners_sorted = build_partners_js(partners)
    refs_js = build_refs_js(partners_sorted)
    build_html(partners_js, refs_js, partners_sorted)

    print("\n=== Done ===")
