#!/usr/bin/env python3
"""Gerçek bilet verisini Genc.html içine gömer.

`data/tickets.json` içeriğini `var GENC_DATA=...;` satırına yazar. Veri yoksa
GENC_DATA=null bırakılır (uygulama örnek veriyle çalışır). Bu adım APK derleme
öncesi çalıştırılır; böylece gerçek etkinlikler uygulamaya gömülür.

Kullanım: python3 tools/embed_data.py
"""
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "Genc.html"
DATA = ROOT / "data" / "tickets.json"
VENUES = ROOT / "data" / "venue_photos.json"


def _literal(payload) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Gömülü JSON HTML'i bozmasın: </script> kaçışı.
    return text.replace("</", "<\\/")


def _replace(html: str, name: str, literal: str) -> tuple[str, int]:
    # Yedek dizede ters bölü kaçışları yorumlanmasın diye fonksiyon kullanılır
    # (aksi halde JSON'daki \n gerçek satır sonuna dönüşüp betiği bozar).
    return re.subn(
        rf"var {name}=.*?;\n",
        lambda m: f"var {name}={literal};\n",
        html,
        count=1,
        flags=re.S,
    )


# Gömülü kopya yalnızca çevrimdışı/ilk açılış yedeğidir: uygulama açılışta
# seçili ilin dosyasını ağdan çeker (data/cities/<il>.json). Yedeğe yalnızca
# varsayılan ilin kayıtları, uygulamanın kullandığı alanlarla gömülür; aksi
# halde HTML 9 bin etkinlikle ~20 MB olur ve açılış yavaşlar.
DEFAULT_CITY = "İzmir"
KEEP_FIELDS = ("id", "type", "art", "title", "venue", "city", "image", "venue_image",
               "district", "address", "lat", "lng", "start", "date", "when", "wd",
               "price", "price_label", "currency", "availability", "source", "url",
               # Çevrimdışı yedekte de kaynak karşılaştırması görünsün.
               "sources", "price_by_source", "cheapest_source")


def _slim(payload: dict) -> dict:
    bugun = date.today().isoformat()
    events = [
        {k: ev[k] for k in KEEP_FIELDS if k in ev}
        for ev in payload.get("events", [])
        if ev.get("city") == DEFAULT_CITY and (ev.get("date") or "") >= bugun
    ]
    return {**payload, "city": DEFAULT_CITY, "count": len(events),
            "cities": [DEFAULT_CITY], "events": events}


def main() -> None:
    if DATA.exists():
        payload = json.loads(DATA.read_text(encoding="utf-8"))
        payload = _slim(payload)
        n = payload["count"]
    else:
        payload, n = None, 0
    venues = json.loads(VENUES.read_text(encoding="utf-8")).get("photos", {}) if VENUES.exists() else {}

    html = HTML.read_text(encoding="utf-8")
    html, c1 = _replace(html, "GENC_DATA", _literal(payload))
    html, c2 = _replace(html, "VENUE_PHOTOS", _literal(venues))
    if c1 != 1 or c2 != 1:
        raise SystemExit("GENC_DATA / VENUE_PHOTOS satırı bulunamadı (uygulama güncel mi?)")
    HTML.write_text(html, encoding="utf-8")
    embedded = len(payload["events"]) if payload else 0
    print(f"✓ GENC_DATA gömüldü: {DEFAULT_CITY} için {embedded} etkinlik "
          f"(toplam {n}) · {len(venues)} salon fotoğrafı")


if __name__ == "__main__":
    main()
