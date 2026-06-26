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


# ── LISTING PAGES — get slugs ──────────────────────────────────────────────────

def scrape_slugs():
    slugs = []
    seen = set()
    for page in range(1, 6):
        url = LISTING_BASE if page == 1 else f"{LISTING_BASE}?page={page}"
        print(f"  Listing page {page}: {url}")
        html = get(url, delay=2)
        found = re.findall(r'href="(/es_ES/partners/[a-z0-9][a-z0-9\-]*-\d+)"', html)
        for s in found:
            if s not in seen:
                seen.add(s)
                slugs.append(s)
    print(f"  Found {len(slugs)} partner slugs")
    return slugs


# ── INDIVIDUAL PARTNER PAGE ────────────────────────────────────────────────────

def parse_int(text):
    cleaned = re.sub(r'[^\d]', '', text)
    return int(cleaned) if cleaned else 0


def scrape_partner(slug, idx):
    url = f"{BASE}{slug}?country_id=67"
    html = get(url, delay=1.5)
    if not html:
        return None

    # ── Name ──────────────────────────────────────────────────────────────────
    m = re.search(r'<h1[^>]*>\s*([^<]+?)\s*</h1>', html)
    name = m.group(1).strip() if m else slug.split("/")[-1].replace("-", " ").title()

    # ── Grade ─────────────────────────────────────────────────────────────────
    grade = "Ready"
    grade_m = re.search(r'(?:partner.grade|grade)["\s]+([Gold|Silver|Ready]+)', html, re.IGNORECASE)
    if not grade_m:
        grade_m = re.search(r'<[^>]+class="[^"]*(?:badge|grade)[^"]*"[^>]*>([^<]*(?:Gold|Silver|Ready)[^<]*)<', html, re.IGNORECASE)
    if grade_m:
        g = grade_m.group(1).strip()
        if "Gold" in g:
            grade = "Gold"
        elif "Silver" in g:
            grade = "Silver"
    # Fallback: look for plain text
    if grade == "Ready":
        if re.search(r'\bGold\b', html):
            grade = "Gold"
        elif re.search(r'\bSilver\b', html):
            grade = "Silver"

    # ── Stats — try multiple patterns ─────────────────────────────────────────
    def find_stat(patterns):
        for pat in patterns:
            m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
            if m:
                return parse_int(m.group(1))
        return 0

    refs = find_stat([
        r'(\d[\d,.]*)\s*(?:referencias|references)',
        r'(?:referencias|references)[^\d]*(\d[\d,.]*)',
        r'"num_references"\s*:\s*(\d+)',
    ])
    retention = find_stat([
        r'(\d+)\s*%\s*(?:retenci[oó]n|retention)',
        r'(?:retenci[oó]n|retention)[^\d]*(\d+)\s*%',
        r'"retention"\s*:\s*(\d+)',
    ])
    avg_users = find_stat([
        r'(\d[\d,.]*)\s*(?:usuarios promedio|avg\.?\s*users?|average users?)',
        r'(?:usuarios promedio|avg\.?\s*users?)[^\d]*(\d[\d,.]*)',
        r'"avg_users"\s*:\s*(\d+)',
    ])
    large_users = find_stat([
        r'(\d[\d,.]*)\s*(?:usuarios grandes?|large users?)',
        r'(?:usuarios grandes?|large users?)[^\d]*(\d[\d,.]*)',
        r'"large_users"\s*:\s*(\d+)',
    ])
    experts = find_stat([
        r'(\d[\d,.]*)\s*(?:expertos certificados?|certified experts?)',
        r'(?:expertos certificados?|certified experts?)[^\d]*(\d[\d,.]*)',
        r'"certified_experts"\s*:\s*(\d+)',
    ])

    # ── Sectors (partner own tags) ────────────────────────────────────────────
    # These are the partner's industry sectors, not client sectors
    sector_raw = re.findall(r'text-bg-(?:primary|info|warning|success|danger)">([^<]+)</span>', html)
    sectors = [[s.strip(), None] for s in dict.fromkeys(sector_raw) if s.strip()]

    # ── Client reference names (skip first 2 = partner logo images) ───────────
    name_matches = re.findall(r'alt="([^"]+)"\s+loading="lazy"', html)
    raw_names = name_matches[2:] if len(name_matches) > 2 else []
    ref_names = [n.strip() for n in raw_names if n.strip()]

    # Client sectors (text-bg-secondary badges = reference sector tags)
    ref_sector_matches = re.findall(r'text-bg-secondary">([^<]+)</span>', html)

    refs_list = []
    for i, rn in enumerate(ref_names):
        s = ref_sector_matches[i].strip() if i < len(ref_sector_matches) else ""
        refs_list.append({"n": rn, "s": s})

    # Always use actual extracted count to stay in sync with refs_list
    if refs_list:
        refs = len(refs_list)

    # ── Numeric ID (rid) ──────────────────────────────────────────────────────
    rid_m = re.search(r'-(\d+)$', slug)
    rid = rid_m.group(1) if rid_m else ""

    return {
        "id": idx,
        "rid": rid,
        "name": name,
        "grade": grade,
        "retention": retention,
        "refs": refs,
        "avgUsers": avg_users,
        "largeUsers": large_users,
        "experts": experts,
        "sectors": sectors,
        "url": f"{BASE}{slug}",
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
        r'90 partners · [^·]+ · fuente',
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

    print("\n[1/3] Scraping listing pages for slugs...")
    slugs = scrape_slugs()

    print(f"\n[2/3] Scraping {len(slugs)} partner pages...")
    partners = []
    for i, slug in enumerate(slugs):
        print(f"  [{i+1}/{len(slugs)}] {slug}")
        p = scrape_partner(slug, i + 1)
        if p:
            partners.append(p)

    print(f"\n[3/3] Building HTML...")
    partners_js, partners_sorted = build_partners_js(partners)
    refs_js = build_refs_js(partners_sorted)
    build_html(partners_js, refs_js, partners_sorted)

    print("\n=== Done ===")
