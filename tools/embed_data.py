#!/usr/bin/env python3
"""Gerçek bilet verisini Genc.html içine gömer.

`data/tickets.json` içeriğini `var GENC_DATA=...;` satırına yazar. Veri yoksa
GENC_DATA=null bırakılır (uygulama örnek veriyle çalışır). Bu adım APK derleme
öncesi çalıştırılır; böylece gerçek etkinlikler uygulamaya gömülür.

Kullanım: python3 tools/embed_data.py
"""
import json
import re
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


def main() -> None:
    if DATA.exists():
        payload = json.loads(DATA.read_text(encoding="utf-8"))
        n = payload.get("count", 0)
    else:
        payload, n = None, 0
    venues = json.loads(VENUES.read_text(encoding="utf-8")).get("photos", {}) if VENUES.exists() else {}

    html = HTML.read_text(encoding="utf-8")
    html, c1 = _replace(html, "GENC_DATA", _literal(payload))
    html, c2 = _replace(html, "VENUE_PHOTOS", _literal(venues))
    if c1 != 1 or c2 != 1:
        raise SystemExit("GENC_DATA / VENUE_PHOTOS satırı bulunamadı (uygulama güncel mi?)")
    HTML.write_text(html, encoding="utf-8")
    print(f"✓ GENC_DATA gömüldü: {n} gerçek etkinlik · {len(venues)} salon fotoğrafı")


if __name__ == "__main__":
    main()
