#!/usr/bin/env python3
"""Uygulamanın çalışma anında indirdiği kompakt veri yükünü üretir.

`data/tickets.json` (okunabilir, girintili) kaynak veridir; `data/events.json`
ise aynı içeriğin ağ için sıkıştırılmış (girintisiz) kopyasıdır. Uygulama
açılışta bu dosyayı çeker; böylece günlük veri yenilemesi için uygulamayı
yeniden derlemek gerekmez.

Kullanım: python3 tools/build_payload.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "tickets.json"
DST = ROOT / "data" / "events.json"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"kaynak veri yok: {SRC}")
    payload = json.loads(SRC.read_text(encoding="utf-8"))
    if not payload.get("events"):
        raise SystemExit("veri boş: etkinlik yok")
    # Girintisiz ve ASCII-dışı karakterleri koruyarak yaz (mobil için küçük kalsın).
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    DST.write_text(text, encoding="utf-8")
    print(f"✓ {len(payload['events'])} etkinlik → {DST} ({len(text)} bayt)")


if __name__ == "__main__":
    main()
