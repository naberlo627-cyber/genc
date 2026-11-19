#!/usr/bin/env python3
"""Uygulamanın çalışma anında indirdiği il bazlı veri yükünü üretir.

`data/tickets.json` (okunabilir, girintili) kaynak veridir. Buradan üç çıktı:

  data/events.json     tüm etkinlikler tek dosyada (yedek/araçlar için)
  data/cities/*.json   il başına ayrı dosya — uygulama yalnızca seçili ili indirir
  data/index.json      il listesi ve etkinlik sayıları (seçim ekranı için)

Böylece açılışta 25 MB yerine medyan ~40 KB iner. Günlük veri yenilemesi için
uygulamayı yeniden derlemek gerekmez.

Kullanım: python3 tools/build_payload.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "tickets.json"
DST = ROOT / "data" / "events.json"


CITY_DIR = ROOT / "data" / "cities"
INDEX = ROOT / "data" / "index.json"


# İl dosyaları da budanır: detay sayfası için açıklama/kurallar kalır ama
# kısaltılır. `sources` ve `cheapest_source` korunur çünkü detay sayfası
# "En ucuz: X · Y,Z karşılaştırıldı" satırını bunlardan kurar; `price_by_source`
# yalnızca 2+ kaynaklı kayıtlarda tutulur (tek kaynakta bilgi taşımaz).
DROP_FIELDS = ("ref", "provider", "organizer")
ABOUT_LIMIT = 400
RULES_MAX = 4
RULES_CHARS = 250
CAST_MAX = 4


def _trim(ev: dict) -> dict:
    item = {k: v for k, v in ev.items() if k not in DROP_FIELDS}
    about = item.get("description")
    if isinstance(about, str) and len(about) > ABOUT_LIMIT:
        cut = about[:ABOUT_LIMIT]
        stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        item["description"] = (cut[: stop + 1] if stop > ABOUT_LIMIT // 2 else cut).strip()
    rules = item.get("rules")
    if isinstance(rules, list):
        item["rules"] = [str(t)[:RULES_CHARS] for t in rules[:RULES_MAX]]
    cast = item.get("cast")
    if isinstance(cast, list):
        item["cast"] = cast[:CAST_MAX]
    kaynaklar = item.get("sources") or []
    if len(kaynaklar) < 2:
        item.pop("price_by_source", None)
        item.pop("cheapest_source", None)
    else:
        item["sources"] = kaynaklar[:4]
    return item


def _dump(payload) -> str:
    # Girintisiz ve ASCII-dışı karakterleri koruyarak yaz (mobil için küçük kalsın).
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _slug(city: str) -> str:
    table = {"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
             "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"}
    name = "".join(table.get(ch, ch) for ch in city).lower()
    return "".join(ch if ch.isalnum() else "-" for ch in name).strip("-")


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"kaynak veri yok: {SRC}")
    payload = json.loads(SRC.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    if not events:
        raise SystemExit("veri boş: etkinlik yok")

    text = _dump(payload)
    DST.write_text(text, encoding="utf-8")
    print(f"✓ {len(events)} etkinlik → {DST} ({len(text)} bayt)")

    # Uygulama açılışta yalnızca ilin dosyasını indirir: 29 MB yerine ~40 KB.
    CITY_DIR.mkdir(parents=True, exist_ok=True)
    for old in CITY_DIR.glob("*.json"):
        old.unlink()
    by_city: dict[str, list] = {}
    for ev in events:
        by_city.setdefault(ev.get("city") or "", []).append(ev)
    index = []
    for city, items in sorted(by_city.items(), key=lambda kv: -len(kv[1])):
        slug = _slug(city) or "bilinmeyen"
        body = {"city": city, "generated_at": payload.get("generated_at"),
                "events": [_trim(ev) for ev in items]}
        (CITY_DIR / f"{slug}.json").write_text(_dump(body), encoding="utf-8")
        index.append({"city": city, "slug": slug, "count": len(items)})
    # Kaynak dökümü dizine yazılır: uygulama "N satıcı karşılaştırıldı"
    # bilgisini buradan kurar, ayrıca kaynak kaynak sayı gösterir.
    kaynak_sayilari: dict[str, int] = {}
    for ev in events:
        for kaynak in (ev.get("sources") or [ev.get("source", "")]):
            if kaynak:
                kaynak_sayilari[kaynak] = kaynak_sayilari.get(kaynak, 0) + 1
    INDEX.write_text(_dump({
        "generated_at": payload.get("generated_at"),
        "total": len(events),
        "sources": dict(sorted(kaynak_sayilari.items(), key=lambda kv: -kv[1])),
        "cities": index,
    }), encoding="utf-8")
    print(f"✓ {len(index)} il dosyası → {CITY_DIR} · dizin → {INDEX}")


if __name__ == "__main__":
    main()
