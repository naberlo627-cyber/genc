#!/usr/bin/env python3
"""Salon fotoğraflarını toplar ve data/venue_photos.json üretir.

Kaynak sırası:
1. Passo mekan görseli (`venue_image`, toplayıcıdan gelir) — uzak URL.
2. Wikimedia Commons araması — ücretsiz lisanslı gerçek fotoğraf, img/venue-*.jpg
   olarak indirilir ve img/VENUE_CREDITS.md içine kaynak/lisans yazılır.

Hiçbiri yoksa salon için fotoğraf üretilmez; uygulama etkinlik görseline ya da
renk geçişine düşer. Bu adım isteğe bağlıdır, uygulama fotoğrafsız da çalışır.
"""
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "img")
UA = "GencApp/1.3 (egitim amacli demo; iletisim: openhands@all-hands.dev)"
W, H = 800, 500

# Salon adı -> Commons arama terimi (genel arama iyi sonuç vermediğinde).
TERMS = {
    "Ahmed Adnan Saygun Sanat Merkezi": "Ahmed Adnan Saygun Arts Center",
    "Elhamra Sahnesi": "Elhamra Theater İzmir",
    "Bornova KSM Bozkurt Kuruç Sahnesi": "Bornova Kültür ve Sanat Merkezi",
    "Bornova KSM Necdet Aydin Sahnesi": "Bornova Kültür ve Sanat Merkezi",
    "İzmir Tepekule Kongre ve Sergi Merkezi Anadolu Salonu": "Tepekule İzmir",
    "Bostanlı Suat Taşer Salonu": "Suat Taşer İzmir",
    "Bostanlı Suat Taşer Tiyatrosu - İzmir": "Suat Taşer İzmir",
}
BAD = re.compile(r"logo|map|plan|harita|svg|\.pdf|\.ogg|\.webm|icon|poster", re.I)


def slug(name):
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^a-z0-9]+", "-", name.translate(tr).lower()).strip("-")


def commons_search(term, n=8):
    url = ("https://commons.wikimedia.org/w/api.php?action=query&generator=search"
           "&gsrsearch=" + urllib.parse.quote(term) + f"&gsrnamespace=6&gsrlimit={n}"
           "&prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=1000&format=json")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        pages = json.load(r).get("query", {}).get("pages", {})
    out = []
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        title = p.get("title", "")
        if not info.get("thumburl") or BAD.search(title):
            continue
        meta = info.get("extmetadata", {})
        out.append({
            "url": info.get("thumburl") or info.get("url"),
            "title": title.replace("File:", ""),
            "license": (meta.get("LicenseShortName", {}).get("value") or "").strip(),
            "creator": re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value") or "").strip(),
            "page": info.get("descriptionurl") or "",
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


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def load_events():
    path = os.path.join(ROOT, "data", "tickets.json")
    if not os.path.exists(path):
        print("data/tickets.json yok; önce collect_tickets.py çalıştırın", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["events"]


def main():
    from PIL import Image  # noqa: F401
    os.makedirs(OUT, exist_ok=True)
    venues = {}
    for e in load_events():
        v = (e.get("venue") or "").strip()
        if not v:
            continue
        rec = venues.setdefault(v, {"venue_image": "", "district": e.get("district", "")})
        if e.get("venue_image") and not rec["venue_image"]:
            rec["venue_image"] = e["venue_image"]

    photos, credits = {}, []
    for name, rec in sorted(venues.items()):
        target = os.path.join(OUT, "venue-" + slug(name) + ".jpg")
        # Passo mekan görselleri kararsız (arada 500) olabildiği için yerel indirilir.
        if rec["venue_image"].startswith("http"):
            try:
                crop_fill(download(rec["venue_image"])).save(
                    target, "JPEG", quality=80, optimize=True, progressive=True)
                photos[name] = os.path.relpath(target, ROOT)
                credits.append((name, os.path.basename(target),
                                {"title": "Passo mekan görseli", "creator": "Passo",
                                 "license": "Satıcı sağladı", "page": rec["venue_image"]}))
                print(f"OK  {name[:40]:40s} -> {os.path.basename(target)} (Passo, yerel)")
                continue
            except Exception as exc:
                print(f"  Passo görseli indirilemedi ({name}): {exc}", file=sys.stderr)
        term = TERMS.get(name, name.replace(" - İzmir", ""))
        done = False
        try:
            for c in commons_search(term):
                try:
                    img = crop_fill(download(c["url"]))
                    img.save(target, "JPEG", quality=80, optimize=True, progressive=True)
                    photos[name] = os.path.relpath(target, ROOT)
                    credits.append((name, os.path.basename(target), c))
                    print(f"OK  {name[:40]:40s} -> {os.path.basename(target)}")
                    done = True
                    break
                except Exception:
                    continue
        except Exception as exc:
            print(f"  arama hatası ({name}): {exc}", file=sys.stderr)
        if not done:
            print(f"--  {name[:40]:40s} -> fotoğraf yok (yedek kullanılacak)")

    with open(os.path.join(ROOT, "data", "venue_photos.json"), "w", encoding="utf-8") as fh:
        json.dump({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "photos": photos},
                  fh, ensure_ascii=False, indent=1)

    if credits:
        target = os.path.join(OUT, "VENUE_CREDITS.md")
        lines = ["# Salon fotoğrafları - kaynak ve lisans", "",
                 "Wikimedia Commons üzerinden bulunmuş ücretsiz lisanslı fotoğraflar.", "",
                 "| Salon | Dosya | Eser | Fotoğrafçı | Lisans | Kaynak |",
                 "|---|---|---|---|---|---|"]
        for name, fname, c in credits:
            lines.append(f"| {name} | {fname} | {c['title'].replace('|','/')} | "
                         f"{c['creator'].replace('|','/') or '-'} | {c['license'].replace('|','/')} | {c['page']} |")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print("OK  lisans bilgileri -> img/VENUE_CREDITS.md")

    print(f"✓ {len(photos)}/{len(venues)} salon için fotoğraf -> data/venue_photos.json")


if __name__ == "__main__":
    main()
