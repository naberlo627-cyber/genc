#!/usr/bin/env python3
"""Birleştirme — yeni toplanan veriyi önceki yayınla birleştirir.

Kaynak siteler zaman zaman kısmi yanıt veriyor: sayfalama erken bitiyor, tek
il dönüyor ya da istekler yarıda kesiliyor. Böyle bir turda toplanan veriyi
olduğu gibi yazmak yayındaki kayıtları siliyordu (9.522 kayıt 439'a düşmüştü).

Bu betik yeni veriyi önceki veriyle birleştirir: aynı kimlikte yeni kayıt
kazanır, yeni turda görünmeyen eski kayıt korunur. Böylece kısmi bir tur
veri kaybı yerine yalnızca daha az güncelleme getirir.

Sona ermiş kayıtlar bir süre sonra düşürülür; aksi hâlde dosya sürekli büyür
ve uygulama hiç gösterilmeyecek etkinlikleri indirir.

Kullanım:
    python3 tools/birlestir.py --onceki refresh/.onceki.json
    python3 tools/birlestir.py --onceki refresh/.onceki.json --gun 7
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TICKETS = ROOT / "data" / "tickets.json"


def _collector():
    spec = importlib.util.spec_from_file_location(
        "collect_tickets", ROOT / "tools" / "collect_tickets.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _oku(yol: Path) -> list[dict]:
    try:
        return json.loads(yol.read_text(encoding="utf-8")).get("events") or []
    except Exception:
        return []


def birlestir(yeni: list[dict], eski: list[dict], gun: int) -> tuple[list[dict], dict]:
    """Yeni + eski kayıtları birleştirir, eskimiş olanları düşürür."""
    esik = (date.today() - timedelta(days=gun)).isoformat()
    # Aynı kimlikte yeni kayıt kazanır: fiyat/tarih değişmiş olabilir.
    havuz: dict[str, dict] = {}
    for ev in eski:
        if ev.get("id"):
            havuz[ev["id"]] = ev
    korunan = 0
    for ev in yeni:
        kim = ev.get("id")
        if not kim:
            continue
        if kim in havuz:
            korunan += 1
        havuz[kim] = ev

    # Eskimiş kayıtlar atılır; tarihi okunamayan kayıt korunur (silme yerine
    # göstermemek daha güvenli).
    birlesik = []
    dusen = 0
    for ev in havuz.values():
        tarih = ev.get("date") or ""
        if tarih and tarih < esik:
            dusen += 1
            continue
        birlesik.append(ev)

    return birlesik, {"onceki": len(eski), "yeni": len(yeni),
                      "korunan": korunan, "eskimis_dusen": dusen}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--onceki", default="", help="önceki turun tickets.json kopyası")
    ap.add_argument("--gun", type=int, default=7,
                    help="bu kadar günden eski kayıtlar düşürülür (0 = düşürme)")
    ap.add_argument("--sessiz", action="store_true")
    args = ap.parse_args()

    if not TICKETS.exists():
        print("! data/tickets.json yok; birleştirme atlandı", file=sys.stderr)
        return 0

    yeni_payload = json.loads(TICKETS.read_text(encoding="utf-8"))
    yeni = yeni_payload.get("events") or []
    eski = _oku(Path(args.onceki)) if args.onceki else []

    if not eski:
        if not args.sessiz:
            print(f"✓ birleştirilecek önceki veri yok; {len(yeni)} kayıt korundu")
        return 0

    birlesik, ozet = birlestir(yeni, eski, args.gun)
    if len(birlesik) < len(yeni):
        print(f"! birleştirme kayıt azalttı ({len(yeni)} → {len(birlesik)}); "
              f"yeni veri olduğu gibi bırakıldı", file=sys.stderr)
        return 0

    # Birleşik havuz yeniden tekilleştirilir: eski ve yeni tur aynı etkinliği
    # farklı kimlikle bulmuş olabilir (kimlik başlıktan türetiliyor).
    m = _collector()
    birlesik = m.dedupe_and_cheapest(birlesik)

    iller = sorted({ev.get("city", "") for ev in birlesik if ev.get("city")})
    payload = {
        "generated_at": yeni_payload.get("generated_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "city": (iller[0] if len(iller) == 1 else ""),
        "cities": iller,
        "count": len(birlesik),
        "sources": yeni_payload.get("sources") or [],
        "events": birlesik,
    }
    tmp = TICKETS.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, TICKETS)

    if not args.sessiz:
        print(f"✓ birleştirildi: önceki {ozet['onceki']} + yeni {ozet['yeni']} "
              f"→ {len(birlesik)} kayıt · {len(iller)} il "
              f"(eskimiş düşen {ozet['eskimis_dusen']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
