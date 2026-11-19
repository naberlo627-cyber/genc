#!/usr/bin/env python3
"""Tekrar denetimi — "aynı etkinlik iki kez listelenmesin" güvencesi.

`collect_tickets.dedupe_and_cheapest` aynı etkinliği birleştirir; bu betik
sonucu bağımsız olarak sınar. Birleştirme eşiğinden biraz gevşek bir ölçüt
kullanır: aynı il + aynı gün + benzer başlık (≥0.75) + benzer mekan (≥0.4)
olan iki ayrı kayıt kaldıysa şüpheli sayılır.

Şüpheli çift varsa çıkış kodu 1 olur ve çiftler yazdırılır; böylece
eşleştirme kurallarındaki bir gerileme sessizce yayına gitmez.

Kullanım:
    python3 tools/tekrar_denetimi.py
    python3 tools/tekrar_denetimi.py --esik 0.6   # daha sıkı başlık eşiği
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TICKETS = ROOT / "data" / "tickets.json"


def _yukle():
    """collect_tickets.py'yi modül olarak yükler (aynı norm/token kuralları)."""
    spec = importlib.util.spec_from_file_location(
        "collect_tickets", ROOT / "tools" / "collect_tickets.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esik", type=float, default=0.75, help="başlık benzerlik eşiği")
    ap.add_argument("--mekan-esik", type=float, default=0.4, help="mekan benzerlik eşiği")
    args = ap.parse_args()

    m = _yukle()
    try:
        veri = json.loads(TICKETS.read_text(encoding="utf-8"))
    except Exception as hata:
        print(f"! tickets.json okunamadı: {hata}", file=sys.stderr)
        return 2

    olaylar = veri.get("events", [])
    gruplar: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for ev in olaylar:
        gruplar[(ev.get("date", ""), m.norm(ev.get("city", "")))].append(ev)

    ciftler = []
    for (_tarih, il), grup in gruplar.items():
        if len(grup) < 2:
            continue
        onbellek = {id(e): (m._tokens(e.get("title", "")), m._tokens(e.get("venue", "")))
                    for e in grup}
        for i, a in enumerate(grup):
            for b in grup[i + 1:]:
                ta, va = onbellek[id(a)]
                tb, vb = onbellek[id(b)]
                if (m._similar(ta, tb) >= args.esik
                        and m._similar(va, vb) >= args.mekan_esik):
                    ciftler.append((il, a, b))

    print(f"Tekrar denetimi: {len(olaylar)} kayıt · {len(gruplar)} il-gün grubu")
    if not ciftler:
        print("  Şüpheli tekrar yok.")
        return 0

    print(f"  ! {len(ciftler)} şüpheli çift:")
    for il, a, b in ciftler[:25]:
        print(f"    {il} {a.get('date')} · {a.get('price')}₺ {a['source']} / "
              f"{b.get('price')}₺ {b['source']}")
        print(f"      A: {a.get('title', '')[:60]} @ {a.get('venue', '')[:40]}")
        print(f"      B: {b.get('title', '')[:60]} @ {b.get('venue', '')[:40]}")
    if len(ciftler) > 25:
        print(f"    ... ve {len(ciftler) - 25} çift daha")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
