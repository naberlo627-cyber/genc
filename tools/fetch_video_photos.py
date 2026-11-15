#!/usr/bin/env python3
"""Kısa videolar akışı için gerçek fotoğraflar indirir (Wikimedia Commons).

Her video etkinliği için anahtar sözcükle Commons'ta arama yapar, dikey
(portre), renkli ve yeterince parlak bir görsel seçer, kart oranına
(720x1280) kırpar ve img/vid-<id>.jpg olarak kaydeder. Kaynak ve lisans
bilgisi img/VID-CREDITS.json + img/VID-CREDITS.md'ye yazılır.
"""
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "img")
UA = "GencApp/1.5 (egitim amacli demo; iletisim: openhands@all-hands.dev)"
W, H = 720, 1280

# Video etkinliği id -> Commons arama sözcüğü.
QUERIES = {
    "celik": "cinema interior movie theater",
    "minik": "children playing colorful activity",
    "sessiz": "cinema theater seats red screen",
    "gulmece": "stand up comedy microphone stage",
    "yaz": "theater stage performance night",
    "kardelen": "live concert stage lights singer",
    "kaz": "mountain forest fog landscape",
    "caz": "jazz festival stage",
    "tango": "tango dancers couple dancing",
    "efes": "ancient ruins temple turkey",
    "kugu": "ballet dancer stage performance",
}


def search(term, limit=14):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": "filetype:bitmap " + term, "gsrnamespace": "6",
        "gsrlimit": str(limit), "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": str(W * 2),
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = json.load(urllib.request.urlopen(req, timeout=25))
    return list(data.get("query", {}).get("pages", {}).values())


def candidates(pages):
    """Kart oranına göre sıralı aday görseller döndürür (dikeyler önce)."""
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        w, h = ii.get("width", 0), ii.get("height", 0)
        mime = ii.get("mime", "")
        if mime not in ("image/jpeg", "image/png") or min(w, h) < 700:
            continue
        ratio = w / h
        # Dikey görseller öne; sonra kart oranına yakınlık; sonra çözünürlük.
        score = (0 if h > w else 100) + abs(ratio - W / H) - min(w, h) / 100000.0
        out.append((score, ii, p))
    out.sort(key=lambda t: t[0])
    return [(ii, p) for _, ii, p in out]


def crop_cover(img, w, h):
    """object-fit: cover mantığıyla ortadan kırpar."""
    sw, sh = img.size
    scale = max(w / sw, h / sh)
    nw, nh = round(sw * scale), round(sh * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def _samples(img):
    small = img.convert("RGB").resize((48, 48))
    data = small.tobytes()
    return [data[i:i + 3] for i in range(0, len(data), 3)]


def colorful(img, need=12.0):
    """Görselin yeterince renkli olduğunu (siyah-beyaz olmadığını) söyler."""
    px = _samples(img)
    sat = sum(max(p) - min(p) for p in px)
    return sat / len(px) >= need


def brightness(img):
    """Görselin ortalama parlaklığı (0-255); çok karanlık kareleri eler."""
    px = _samples(img)
    return sum(sum(p) for p in px) / (3 * len(px))


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60).read()


def license_of(ii):
    meta = ii.get("extmetadata", {}) or {}
    def g(k):
        v = meta.get(k, {}).get("value", "")
        return re.sub(r"<[^>]+>", "", str(v)).strip()
    return g("LicenseShortName"), g("Artist"), g("Credit")


def load_credits():
    path = os.path.join(OUT, "VID-CREDITS.json")
    if os.path.exists(path):
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_credits(credits):
    with io.open(os.path.join(OUT, "VID-CREDITS.json"), "w", encoding="utf-8") as fh:
        json.dump(credits, fh, ensure_ascii=False, indent=2, sort_keys=True)
    lines = ["# Video fotoğrafları — kaynak ve lisans", ""]
    for eid in sorted(credits):
        lines.append("- `vid-%s.jpg` — %s" % (eid, credits[eid]))
    with io.open(os.path.join(OUT, "VID-CREDITS.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    os.makedirs(OUT, exist_ok=True)
    credits = load_credits()
    ok = 0
    for eid, term in QUERIES.items():
        dest = os.path.join(OUT, "vid-%s.jpg" % eid)
        if os.path.exists(dest) and eid in credits:
            print("zaten var:", os.path.basename(dest)); ok += 1; continue
        try:
            best = None
            for ii, page in candidates(search(term)):
                try:
                    raw = fetch(ii.get("thumburl") or ii["url"])
                    img = Image.open(io.BytesIO(raw)).convert("RGB")
                except Exception:
                    continue
                if not colorful(img) or brightness(img) < 45:
                    continue
                best = (img, ii, page)
                break
            if not best:
                print("atlandı (uygun görsel yok):", eid, term)
                continue
            img, ii, page = best
            crop_cover(img, W, H).save(dest, "JPEG", quality=82, optimize=True)
            lic, artist, _ = license_of(ii)
            title = page.get("title", "").replace("File:", "")
            credits[eid] = "%s — %s — %s" % (title, artist or "?", lic or "?")
            print("yazıldı:", os.path.basename(dest), ii.get("width"), "x", ii.get("height"), "->", (W, H))
            ok += 1
        except Exception as exc:  # tek tek denemelerde devam et
            print("hata:", eid, exc)
    save_credits(credits)
    print("\n%d/%d fotoğraf indirildi" % (ok, len(QUERIES)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
