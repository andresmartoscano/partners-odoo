"""Detección de cambios de partner entre snapshots del dashboard.

Un "cambio de partner" es un cliente que en un snapshot aparece bajo el
partner A y en el siguiente bajo el partner B (desaparece de A y aparece en B
en el mismo diff). Altas y bajas puras no cuentan como cambio.

Usado por scraper.py (diff del snapshot anterior vs el nuevo en cada run) y
por backfill_changes.py (reconstrucción desde el historial git).
"""
import json
import os
import re
import unicodedata

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHANGES_PATH = os.path.join(SCRIPT_DIR, "changes.json")

REFS_RE = re.compile(r'const REFS=(\{.*?\});', re.DOTALL)
PARTNER_LINE_RE = re.compile(
    r'\{ id:\d+, rid:"(\d+)", name:("(?:[^"\\]|\\.)*"), grade:"(\w+)",')

# Un snapshot con menos partners que esto se considera roto y no se diffea
MIN_PARTNERS_FOR_DIFF = 30


def extract_refs(html):
    """Extrae el objeto REFS ({rid: [{n, s}, ...]}) de un index.html. None si no hay."""
    m = REFS_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def extract_partner_meta(html):
    """Extrae {rid: {"name", "grade"}} del bloque PARTNERS de un index.html."""
    meta = {}
    for rid, name_json, grade in PARTNER_LINE_RE.findall(html):
        meta[rid] = {"name": json.loads(name_json), "grade": grade}
    return meta


def norm_client(name):
    """Clave de comparación de un cliente: minúsculas, sin tildes, espacios colapsados."""
    s = unicodedata.normalize("NFD", name or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


def client_map(refs):
    """{clave normalizada: {"n": nombre, "s": sector, "rids": set de rids}}"""
    cmap = {}
    for rid, lst in refs.items():
        for r in lst:
            key = norm_client(r.get("n", ""))
            if not key:
                continue
            entry = cmap.setdefault(key, {"n": r["n"], "s": r.get("s", ""), "rids": set()})
            entry["rids"].add(rid)
            if not entry["s"] and r.get("s"):
                entry["s"] = r["s"]
    return cmap


def diff_snapshots(old_refs, new_refs, meta, date_str):
    """Compara dos snapshots de REFS y devuelve los cambios de partner.

    meta: {rid: {"name", "grade"}} para resolver nombres (unión de ambos
    snapshots, con preferencia por el más nuevo).
    Devuelve [{"d", "n", "s", "fr", "f", "fg", "tr", "t", "tg"}, ...]
    """
    old_map = client_map(old_refs)
    new_map = client_map(new_refs)
    changes = []
    for key, new_e in new_map.items():
        old_e = old_map.get(key)
        if not old_e:
            continue  # alta nueva, no es un cambio de partner
        removed = old_e["rids"] - new_e["rids"]
        added = new_e["rids"] - old_e["rids"]
        if not removed or not added:
            continue
        for fr in sorted(removed):
            for tr in sorted(added):
                f_meta = meta.get(fr, {})
                t_meta = meta.get(tr, {})
                changes.append({
                    "d": date_str,
                    "n": new_e["n"],
                    "s": new_e["s"] or old_e["s"] or "",
                    "fr": fr,
                    "f": f_meta.get("name", "Partner " + fr),
                    "fg": f_meta.get("grade", ""),
                    "tr": tr,
                    "t": t_meta.get("name", "Partner " + tr),
                    "tg": t_meta.get("grade", ""),
                })
    return changes


def load_changes():
    if os.path.exists(CHANGES_PATH):
        with open(CHANGES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_changes(changes):
    changes.sort(key=lambda c: (c["d"], norm_client(c["n"])))
    with open(CHANGES_PATH, "w", encoding="utf-8") as f:
        json.dump(changes, f, ensure_ascii=False, indent=1)
        f.write("\n")


def append_changes(existing, new_changes):
    """Añade a existing los cambios de new_changes que no estén ya (dedupe por
    cliente + origen + destino + fecha). Devuelve cuántos se añadieron."""
    seen = {(norm_client(c["n"]), c["fr"], c["tr"], c["d"]) for c in existing}
    added = 0
    for c in new_changes:
        k = (norm_client(c["n"]), c["fr"], c["tr"], c["d"])
        if k not in seen:
            seen.add(k)
            existing.append(c)
            added += 1
    return added


def build_changes_js(changes):
    return "const CHANGES=" + json.dumps(
        changes, ensure_ascii=False, separators=(",", ":")) + ";"
