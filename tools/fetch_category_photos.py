#!/usr/bin/env python3
"""Kategori ızgarası için gerçek fotoğraflar indirir (Openverse API, ücretsiz lisans).

Her kategori için anahtar sözcükle arama yapar, ilk uygun görseli indirir,
kart boyutuna (480x340) kırpar ve img/cat-<slug>.jpg olarak kaydeder.
"""
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "img")
UA = "GencApp/1.3 (egitim amacli demo; iletisim: openhands@all-hands.dev)"
W, H = 480, 340

CATS = {
    "konser": "live music concert stage",
    "sinema": "cinema movie theater screen",
    "tiyatro": "theatre stage performance actors",
    "gezi-turu": "travel tour landscape bus",
    "festival": "street festival crowd celebration",
    "stand-up": "stand up comedy microphone stage",
    "cocuk-etkinlikleri": "children playing kids activity",
    "spor": "football stadium sport match",
    "sergi": "art gallery exhibition paintings",
    "dans": "dance couple dancing stage",
    "opera-ve-bale": "ballet opera stage performance",
    "acik-hava": "hiking nature sunrise outdoors",
}


def slug(name):
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = name.translate(tr).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def get_json(url, tries=4):
    """Openverse zaman zaman 5xx döner; kısa bekleyip yeniden dener."""
    import time
    last = None
    for i in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def search(term, n=6):
    url = ("https://api.openverse.org/v1/images/?q=" + urllib.parse.quote(term)
           + "&page_size=" + str(n) + "&license_type=commercial&mature=false")
    try:
        data = get_json(url)
    except Exception as e:
        print(f"  arama hatası ({term}): {e}", file=sys.stderr)
        return []
    out = []
    for x in data.get("results", []):
        if not x.get("url"):
            continue
        lic = ((x.get("license") or "") + "-" + (x.get("license_version") or "")).lower()
        # "nd" (türev yasak) lisansları atla: kırpma/yeniden boyutlandırma türev sayılır.
        if "nd" in lic.split("-"):
            continue
        out.append({
            "url": x["url"],
            "title": x.get("title") or "",
            "creator": x.get("creator") or "",
            "license": (x.get("license") or "") + (" " + x.get("license_version", "")).strip(),
            "source": x.get("foreign_landing_url") or x.get("url"),
        })
    return out


def crop_fill(raw, w=W, h=H):
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    iw, ih = im.size
    scale = max(w / iw, h / ih)
    im = im.resize((max(1, int(iw * scale + 0.5)), max(1, int(ih * scale + 0.5))), Image.LANCZOS)
    iw, ih = im.size
    left, top = (iw - w) // 2, (ih - h) // 2
    return im.crop((left, top, left + w, top + h))


def terms_for(term):
    """Ana terim ve yedekleri; Openverse bazı sorgularda 403/504 dönebiliyor."""
    extra = {
        "hiking nature sunrise outdoors": ["hiking mountains", "mountain sunrise landscape", "nature trail hike"],
    }
    return [term] + extra.get(term, [])


def read_credits(path):
    """Var olan CREDITS.md satırlarını {dosya: satır} olarak okur."""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("| ") and "cat-" in line:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 2:
                    rows[cells[1]] = line.rstrip("\n")
    return rows


def write_credits(credits):
    """İndirilen fotoğrafların kaynak ve lisans bilgilerini kaydeder (birleştirir)."""
    if not credits:
        return
    target = os.path.join(OUT, "CREDITS.md")
    rows = read_credits(target)
    for name, fname, c in credits:
        title = (c["title"] or "-").replace("|", "/")
        creator = (c["creator"] or "-").replace("|", "/")
        lic = (c["license"] or "-").replace("|", "/")
        rows[fname] = f"| {name} | {fname} | {title} | {creator} | {lic} | {c['source']} |"
    lines = ["# Kategori fotoğrafları - kaynak ve lisans", "",
             "Bu görseller Openverse (openverse.org) üzerinden bulunmuş ücretsiz",
             "lisanslı fotoğraflardır. Uygulama içinde kullanılabilir.", "",
             "| Kategori | Dosya | Eser | Fotoğrafçı | Lisans | Kaynak |",
             "|---|---|---|---|---|---|"]
    lines += [rows[k] for k in sorted(rows)]
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("OK  lisans bilgileri -> img/CREDITS.md")


def main():
    from PIL import Image  # noqa: F401  (varlık kontrolü)
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    credits = []
    for name, term in CATS.items():
        if only and slug(name) not in only:
            continue
        target = os.path.join(OUT, "cat-" + slug(name) + ".jpg")
        done = False
        cands = []
        for t in terms_for(term):
            cands += search(t)
        for c in cands:
            try:
                raw = download(c["url"])
                img = crop_fill(raw)
                img.save(target, "JPEG", quality=78, optimize=True, progressive=True)
                credits.append((name, os.path.basename(target), c))
                print(f"OK  {name:22s} -> {os.path.relpath(target, ROOT)} ({os.path.getsize(target)//1024} KB)")
                done = True
                break
            except Exception as e:
                print(f"  atlandı: {e}", file=sys.stderr)
        if not done:
            print(f"HATA {name}: görsel indirilemedi", file=sys.stderr)
            return 1
    write_credits(credits)
    return 0


if __name__ == "__main__":
    sys.exit(main())
