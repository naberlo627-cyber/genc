#!/usr/bin/env python3
"""Genç - kaynak verisindeki gürültüyü temizler ve metni düzenli hâle getirir.

Kaynak sitelerin (Biletinial, Passo, Biletino) ham metinlerinde bozuk biçimleme
bulunur: yüzlerce karakterlik tire/ayraç satırları, art arda boşluklar, satır
sonu karışıklıkları ve görünmez karakterler. Bunlar uygulamada hem okunaksız
görünür hem de dar ekranda yatay kaydırmaya yol açar.

Bu adım `data/tickets.json` içindeki metin alanlarını yerinde düzenler:
  * açıklama, kurallar, adres, mekan, başlık, organizatör, kadro adları
  * görünmez/denetim karakterleri ve art arda boşluklar sadeleşir
  * aynı ayracın uzun tekrarları (------, ====, ____, ....) kısalır
  * üçten fazla ardışık boş satır ikiye iner

Tekrar çalıştırılabilir (idempotent) ve kayıpsızdır: yalnızca biçimlendirme
düzeltilir, anlamlı metin korunur.

Kullanım: python3 tools/clean_events.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TICKETS = ROOT / "data" / "tickets.json"

# Görünmez ve denetim karakterleri (zero-width, BOM, C0/C1 denetimleri).
_INVISIBLE = re.compile("[\u3164\u200b-\u200f\u2060\ufeff\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]")
# Aynı noktalama karakterinin uzun tekrarı: ------, =====, ____, ...., ****
_RUN = re.compile(r"([\-=_*~.#•·])\1{3,}")
# Boşluğa benzeyen tüm karakterler (NBSP, ince boşluk, sekme...).
_SPACEY = re.compile("[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000\t]")
# Satır içi art arda boşluklar.
_INLINE_SPACES = re.compile("[ ]{2,}")
# Üçten fazla ardışık yeni satır.
_BLANK_LINES = re.compile(r"\n{3,}")


def clean_text(s: str) -> str:
    """Tek bir metin alanını düzenler; boşsa boş döner."""
    if not s:
        return s
    t = str(s)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _INVISIBLE.sub("", t)
    t = _SPACEY.sub(" ", t)
    t = _RUN.sub(lambda m: m.group(1) * 2, t)   # "------" -> "--"
    t = "\n".join(_INLINE_SPACES.sub(" ", ln).strip() for ln in t.split("\n"))
    t = _BLANK_LINES.sub("\n\n", t)
    return t.strip()


def clean_short(s: str) -> str:
    """Tek satırlık alanlar (başlık, mekan, adres): yeni satır ve fazla boşluk yok."""
    if not s:
        return s
    return _INLINE_SPACES.sub(" ", clean_text(s).replace("\n", " ")).strip()


def clean_event(e: dict) -> None:
    for key in ("title", "venue", "address", "organizer", "genre_label", "age"):
        if e.get(key):
            e[key] = clean_short(e[key])
    if e.get("description"):
        e["description"] = clean_text(e["description"])
    if isinstance(e.get("rules"), list):
        e["rules"] = [clean_text(r) for r in e["rules"] if clean_text(r)]
    if isinstance(e.get("cast"), list):
        for c in e["cast"]:
            if isinstance(c, dict):
                if c.get("name"):
                    c["name"] = clean_short(c["name"])
                if c.get("role"):
                    c["role"] = clean_short(c["role"])


def main() -> None:
    data = json.loads(TICKETS.read_text(encoding="utf-8"))
    events = data.get("events") or []
    for e in events:
        clean_event(e)
    TICKETS.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {len(events)} etkinliğin metni temizlendi")


if __name__ == "__main__":
    main()
