#!/usr/bin/env python3
"""Genç - mevcut etkinlik verisini detay alanlarıyla zenginleştirir.

`data/tickets.json` içindeki etkinliklerin benzersiz satıcı sayfalarını çeker,
açıklama / kadro / süre / tür / yaş sınırı / kurallar / organizatör bilgisini
toplar ve aynı URL'yi paylaşan tüm seanslara yazar. Böylece uygulamadaki detay
ekranı (Detay, Biletler, Kadro, Yorumlar, Etkinlik Kuralları) gerçek içerikle
dolar.

Kullanım:
    python3 tools/enrich_events.py            # eksik alanları tamamla
    python3 tools/enrich_events.py --force    # hepsini yeniden çek
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
from pathlib import Path

from collect_tickets import fetch, ld_blocks, walk, detail_extras

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "tickets.json"


def event_node(html_text: str, title: str) -> dict:
    """Sayfadaki JSON-LD Event düğümünü (başlığa en yakın) bulur."""
    best = {}
    for block in ld_blocks(html_text):
        for node in walk(block):
            if node.get("@type") != "Event":
                continue
            if not best or (node.get("description") or "") > (best.get("description") or ""):
                best = node
    return best


def enrich_one(url: str, title: str) -> dict:
    html_text = fetch(url)
    return detail_extras(html_text, event_node(html_text, title))


def needs(e: dict, force: bool) -> bool:
    if force:
        return True
    return not (e.get("description") or e.get("cast") or e.get("rules"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="tüm alanları yeniden çek")
    args = ap.parse_args()

    data = json.loads(DATA.read_text(encoding="utf-8"))
    events = data["events"]

    # URL -> o URL'yi paylaşan etkinliklerden biri (başlık için)
    urls: dict[str, str] = {}
    for e in events:
        url = e.get("url") or e.get("ref")
        if url and needs(e, args.force) and url not in urls:
            urls[url] = e.get("title", "")
    print(f"Zenginleştirilecek benzersiz sayfa: {len(urls)}")

    results: dict[str, dict] = {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {}
        for url, title in urls.items():
            time.sleep(0.15)
            futures[pool.submit(enrich_one, url, title)] = url
        for fut in concurrent.futures.as_completed(futures):
            url = futures[fut]
            try:
                results[url] = fut.result()
            except Exception as exc:  # ağ hatalarında mevcut veri korunur
                print(f"  ! alınamadı: {url} ({exc})")
            done += 1
            if done % 25 == 0:
                print(f"    ...{done}/{len(urls)}")

    filled = 0
    for e in events:
        url = e.get("url") or e.get("ref")
        ex = results.get(url)
        if not ex:
            continue
        for key in ("description", "cast", "runtime", "genres", "genre_label", "age", "rules", "organizer"):
            if ex.get(key) or not e.get(key):
                e[key] = ex.get(key)
        filled += 1

    data["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    withdesc = sum(1 for e in events if e.get("description"))
    withcast = sum(1 for e in events if e.get("cast"))
    withrules = sum(1 for e in events if e.get("rules"))
    print(f"✓ {filled} etkinlik güncellendi")
    print(f"  açıklama: {withdesc} · kadro: {withcast} · kurallar: {withrules}")


if __name__ == "__main__":
    main()
