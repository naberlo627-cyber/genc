#!/usr/bin/env python3
"""Kaynak sağlık denetimi — "almadığımız etkinlik kalmasın" güvencesi.

Her çalıştırmada üç şeyi ölçer:

  1. Erişim   : kaynak sitesi yanıt veriyor mu (403/429/timeout değil)?
  2. Verim    : son toplamada kaç kayıt geldi, bir önceki çalışmaya göre düştü mü?
  3. Kapsam   : kaynakta olup uygulamada olmayan il var mı?

Sonuç `data/kaynak_durumu.json` dosyasına yazılır. Düşüş eşiğin altına inerse
çıkış kodu 1 olur; CI bu durumda uyarı adımını çalıştırır.

Kullanım:
    python3 tools/kaynak_denetimi.py            # denetle ve raporla
    python3 tools/kaynak_denetimi.py --sessiz   # yalnızca dosyaya yaz
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TICKETS = DATA / "tickets.json"
DURUM = DATA / "kaynak_durumu.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

# Kaynak başına yoklanacak adres ve beklenen en az kayıt sayısı.
# Eşik, sağlıklı bir günde görülen sayının kabaca yarısıdır: kaynak sessizce
# bozulduğunda (HTML değişti, sayfalama kırıldı) bu değerin altına düşer.
KAYNAKLAR = {
    "Biletinial": {"url": "https://biletinial.com/tr-tr", "min": 2000},
    "Passo": {"url": "https://www.passo.com.tr/", "min": 300},
    "Biletino": {"url": "https://biletino.com/tr/", "min": 1500},
    "Biletimgo": {"url": "https://www.biletimgo.com/sehir-etkinlikleri/istanbul", "min": 100},
}

DUSUS_ESIGI = 0.60  # önceki çalışmanın %60'ının altı = şüpheli düşüş


def erisim(url: str) -> dict:
    """Adresi yoklar; durum kodu ve yanıt süresini döndürür."""
    basla = time.time()
    try:
        istek = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,*/*",
            "Accept-Language": "tr-TR,tr;q=0.9",
        })
        with urllib.request.urlopen(istek, timeout=25) as yanit:
            boyut = len(yanit.read(200_000))
            return {"ok": True, "kod": yanit.status,
                    "ms": int((time.time() - basla) * 1000), "boyut": boyut}
    except urllib.error.HTTPError as hata:
        return {"ok": False, "kod": hata.code,
                "ms": int((time.time() - basla) * 1000), "hata": str(hata.reason)}
    except Exception as hata:
        return {"ok": False, "kod": 0,
                "ms": int((time.time() - basla) * 1000), "hata": type(hata).__name__}


def onceki_durum() -> dict:
    try:
        return json.loads(DURUM.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessiz", action="store_true", help="yalnızca dosyaya yaz")
    args = ap.parse_args()

    onceki = onceki_durum()
    onceki_sayilar = {k: v.get("sayi", 0) for k, v in (onceki.get("kaynaklar") or {}).items()}

    # Bu çalıştırmanın kayıt sayıları.
    sayilar: dict[str, int] = {}
    iller: dict[str, set[str]] = {}
    try:
        veri = json.loads(TICKETS.read_text(encoding="utf-8"))
        for ev in veri.get("events", []):
            for kaynak in (ev.get("sources") or [ev.get("source", "")]):
                if not kaynak:
                    continue
                sayilar[kaynak] = sayilar.get(kaynak, 0) + 1
                if ev.get("city"):
                    iller.setdefault(kaynak, set()).add(ev["city"])
    except Exception as hata:
        print(f"! tickets.json okunamadı: {hata}", file=sys.stderr)

    rapor: dict = {
        "denetlendi": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "kaynaklar": {},
        "sorunlar": [],
    }

    for ad, ayar in KAYNAKLAR.items():
        sonuc = erisim(ayar["url"])
        sayi = sayilar.get(ad, 0)
        onceki_sayi = onceki_sayilar.get(ad, 0)

        sorunlar = []
        if not sonuc["ok"]:
            sorunlar.append(f"erişim hatası ({sonuc.get('kod')} {sonuc.get('hata', '')})".strip())
        if sayi < ayar["min"]:
            sorunlar.append(f"kayıt az: {sayi} < {ayar['min']}")
        if onceki_sayi and sayi < onceki_sayi * DUSUS_ESIGI:
            sorunlar.append(f"düşüş: {sayi} (önceki {onceki_sayi})")

        rapor["kaynaklar"][ad] = {
            "erisim": sonuc,
            "sayi": sayi,
            "onceki_sayi": onceki_sayi,
            "il_sayisi": len(iller.get(ad, ())),
            "sorun": sorunlar,
        }
        if sorunlar:
            rapor["sorunlar"].append({"kaynak": ad, "sorun": sorunlar})

    DURUM.parent.mkdir(parents=True, exist_ok=True)
    DURUM.write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")

    if not args.sessiz:
        print("Kaynak denetimi")
        for ad, k in rapor["kaynaklar"].items():
            durum = "TAMAM" if not k["sorun"] else "SORUN"
            print(f"  {ad:12s} {durum:6s} {k['sayi']:>5d} kayıt · "
                  f"{k['il_sayisi']:>2d} il · {k['erisim']['kod']} · {k['erisim']['ms']}ms")
            for s in k["sorun"]:
                print(f"      ! {s}")
        if not rapor["sorunlar"]:
            print("  Tüm kaynaklar sağlıklı.")

    return 1 if rapor["sorunlar"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
