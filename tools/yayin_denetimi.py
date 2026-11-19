#!/usr/bin/env python3
"""Yayın denetimi — yayına çıkan verinin üç güvencesini bağımsız sınar.

Yayın yükü (data/cities/*.json + data/index.json) üretildikten sonra çalışır ve
uygulamanın gerçekten okuyacağı dosyaları denetler. `tekrar_denetimi.py` kaynak
veriyi sınar; bu betik ise yayına giden kopyayı sınar. İkisi ayrı yerlerde
bozulabileceği için ayrı tutulur.

Denetlenenler:
  1. Tekrar yok     : aynı il + gün + benzer başlık + benzer mekan iki kez yok.
  2. Sayı doğru     : index.json'daki her il sayısı kendi dosyasındaki kayıt
                      sayısıyla birebir aynı; toplam da dosyaların toplamı.
  3. En ucuz doğru  : cheapest_source gerçekten en düşük fiyatlı kaynak;
                      price_by_source ile price alanı çelişmiyor.

Kullanım:
    python3 tools/yayin_denetimi.py
    python3 tools/yayin_denetimi.py --sessiz   # yalnızca hata varsa yazar
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CITY_DIR = ROOT / "data" / "cities"
INDEX = ROOT / "data" / "index.json"


def _modul():
    spec = importlib.util.spec_from_file_location(
        "collect_tickets", ROOT / "tools" / "collect_tickets.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _kayitlar():
    """İl dosyalarını ve dizini okur; okunamayan dosya hata sayılır."""
    if not INDEX.exists():
        raise SystemExit("dizin yok: data/index.json (önce build_payload.py)")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    iller = {}
    for kayit in index.get("cities") or []:
        yol = CITY_DIR / f"{kayit.get('slug','')}.json"
        if not yol.exists():
            raise SystemExit(f"il dosyası yok: {yol}")
        iller[kayit.get("city", "")] = json.loads(yol.read_text(encoding="utf-8"))
    return index, iller


def tekrar_sinamasi(m, iller) -> list[str]:
    """Aynı etkinliğin iki kez yayınlanıp yayınlanmadığını sınar.

    Ölçüt, birleştirme kuralının aynısıdır (`_ayni_etkinlik`). Daha gevşek bir
    ölçüt kullanmak yanlış alarm üretiyordu: aynı salonda aynı gün yapılan
    "Tabak Boyama" ve "Ayna Boyama" atölyeleri benzer başlıklı ama farklı
    etkinlikler (fiyatları da farklı). Ölçüt birleştirmeyle aynı olunca
    "kalan tekrar" gerçekten birleştiricinin kaçırdığı kayıt demektir.
    """
    sorunlar = []
    for il, govde in iller.items():
        # Birleştirme başlıktan il adını çıkarır (il zaten eşleşmiş sayılır).
        # Aynısı yapılmazsa "MEDUSA ... ANTALYA" ile "CARETTA ... ANTALYA"
        # gibi farklı atölyeler benzer görünüp yanlış alarm üretiyor.
        il_tok = set(m.norm(il).split())
        gunler: dict[str, list[dict]] = {}
        for ev in govde.get("events") or []:
            gunler.setdefault(ev.get("date") or "", []).append(ev)
        for gun, kayitlar in gunler.items():
            if not gun or len(kayitlar) < 2:
                continue
            for i, a in enumerate(kayitlar):
                for b in kayitlar[i + 1:]:
                    if not m._ayni_etkinlik(
                        m._tokens(a.get("title", "")) - il_tok, m._tokens(a.get("venue", "")),
                        m._venue_key(a.get("venue", "")), a.get("venue", ""),
                        m._tokens(b.get("title", "")) - il_tok, m._tokens(b.get("venue", "")),
                        m._venue_key(b.get("venue", "")), b.get("venue", ""),
                    ):
                        continue
                    # Fiyatı farklı olan kayıtlar ayrı etkinliktir; birleştirme
                    # de onları ayırır (en ucuzu seçmek yanlış olurdu).
                    if a.get("price") != b.get("price"):
                        continue
                    sorunlar.append(
                        f"{il} {gun}: “{a.get('title','')[:40]}” ≈ "
                        f"“{b.get('title','')[:40]}”")
    return sorunlar


def sayi_sinamasi(index, iller) -> list[str]:
    """Dizin sayıları il dosyalarındaki gerçek kayıtlarla uyuşuyor mu?"""
    sorunlar = []
    toplam = 0
    for kayit in index.get("cities") or []:
        il = kayit.get("city", "")
        gercek = len((iller.get(il) or {}).get("events") or [])
        toplam += gercek
        if kayit.get("count") != gercek:
            sorunlar.append(
                f"{il}: dizin {kayit.get('count')} diyor, dosyada {gercek} kayıt var")
    if index.get("total") != toplam:
        sorunlar.append(
            f"dizin toplamı {index.get('total')}, dosyaların toplamı {toplam}")
    # Geçmiş kayıtlar yayına hiç girmemeli: bilet alınamaz, listede görünmez.
    from datetime import date
    bugun = date.today().isoformat()
    gecmis = [
        f"{il}: {ev.get('id')} ({ev.get('date')})"
        for il, govde in iller.items()
        for ev in (govde.get("events") or [])
        if (ev.get("date") or "") < bugun
    ]
    sorunlar.extend(f"geçmiş kayıt yayında: {s}" for s in gecmis[:5])
    if len(gecmis) > 5:
        sorunlar.append(f"… ve {len(gecmis) - 5} geçmiş kayıt daha")
    return sorunlar


def fiyat_sinamasi(iller) -> list[str]:
    """En ucuz kaynak gerçekten en düşük fiyatlı olan mı?"""
    sorunlar = []
    for il, govde in iller.items():
        for ev in govde.get("events") or []:
            fiyatlar = ev.get("price_by_source") or {}
            secilen = ev.get("cheapest_source")
            if not fiyatlar or secilen is None:
                continue
            en_dusuk = min(fiyatlar.values())
            if abs(fiyatlar.get(secilen, -1) - en_dusuk) > 0.01:
                sorunlar.append(
                    f"{il}: {ev.get('id')} cheapest_source={secilen} "
                    f"({fiyatlar.get(secilen)}), en düşük {en_dusuk}")
            fiyat = ev.get("price")
            if fiyat is not None and abs(fiyat - en_dusuk) > 0.01:
                sorunlar.append(
                    f"{il}: {ev.get('id')} price={fiyat}, düşük kaynak fiyatı {en_dusuk}")
    return sorunlar


def kimlik_sinamasi(iller) -> list[str]:
    """Aynı kimlik iki kez geçiyor mu? (arayüz kimliği anahtar olarak kullanır)"""
    sayac: Counter[str] = Counter()
    for govde in iller.values():
        for ev in govde.get("events") or []:
            sayac[ev.get("id") or ""] += 1
    return [f"kimlik {kim} {adet} kez geçiyor" for kim, adet in sayac.items() if adet > 1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessiz", action="store_true", help="yalnızca hata varsa yaz")
    args = ap.parse_args()

    index, iller = _kayitlar()
    m = _modul()

    bolumler = [
        ("Tekrar", tekrar_sinamasi(m, iller)),
        ("Sayı", sayi_sinamasi(index, iller)),
        ("En ucuz", fiyat_sinamasi(iller)),
        ("Kimlik", kimlik_sinamasi(iller)),
    ]

    toplam = sum(len(s) for _, s in bolumler)
    if not args.sessiz or toplam:
        for ad, sorunlar in bolumler:
            if sorunlar:
                print(f"✗ {ad}: {len(sorunlar)} sorun")
                for s in sorunlar[:5]:
                    print(f"    {s}")
            else:
                print(f"✓ {ad}: temiz")

    if toplam:
        print(f"✗ yayın denetimi başarısız: {toplam} sorun")
        return 1
    print(f"✓ yayın denetimi geçti: {len(iller)} il, {index.get('total')} etkinlik")
    return 0


if __name__ == "__main__":
    sys.exit(main())
