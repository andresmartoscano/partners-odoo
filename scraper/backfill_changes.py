"""Reconstruye scraper/changes.json desde el historial git de index.html.

Recorre todos los commits que tocan index.html (en orden cronológico), extrae
REFS de cada snapshot y diffea pares consecutivos con partner_changes. La fecha
de cada cambio es la fecha del commit donde aparece por primera vez (orientativa).

Ejecutar desde cualquier sitio: python scraper/backfill_changes.py
Es idempotente: mergea con el changes.json existente (dedupe incluido).
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import partner_changes as pc

REPO_DIR = os.path.join(pc.SCRIPT_DIR, "..")


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=REPO_DIR, capture_output=True, check=True
    ).stdout.decode("utf-8", errors="replace")


def main():
    log = git("log", "--reverse", "--format=%H %cI", "--", "index.html")
    commits = [line.split(" ", 1) for line in log.strip().splitlines() if " " in line]
    print(f"{len(commits)} commits de index.html en el historial")

    prev_refs = None
    meta = {}
    all_new = []
    snapshots = 0
    for sha, iso_date in commits:
        html = git("show", f"{sha}:index.html")
        refs = pc.extract_refs(html)
        if refs is None or len(refs) < pc.MIN_PARTNERS_FOR_DIFF:
            continue  # snapshot roto o sin datos embebidos
        snapshots += 1
        meta.update(pc.extract_partner_meta(html))  # el más nuevo pisa al viejo
        date_str = iso_date[:10]
        if prev_refs is not None:
            found = pc.diff_snapshots(prev_refs, refs, meta, date_str)
            if found:
                print(f"  {sha[:7]} {date_str}: {len(found)} cambio(s)")
                for c in found:
                    print(f"    {c['n']}: {c['f']} -> {c['t']}")
            all_new.extend(found)
        prev_refs = refs

    print(f"{snapshots} snapshots válidos diffeados, {len(all_new)} cambios detectados")
    existing = pc.load_changes()
    added = pc.append_changes(existing, all_new)
    pc.save_changes(existing)
    print(f"changes.json: {added} nuevos, {len(existing)} en total")


if __name__ == "__main__":
    main()
