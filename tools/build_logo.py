#!/usr/bin/env python3
"""Yeni "genç" logosunu kaynak görselden vektörleştirir ve ikon maskelerini üretir.

Kaynak: tools/assets/logo_source.png (kullanıcının hazırladığı kelime markası;
koyu zemin üzerine krem "genç" ve aksan renkli "ç"). Bu betik:

1. Kaynak görselden glif maskelerini (krem harfler, aksan harfi) çıkarır.
2. potrace ile SVG yollarına dönüştürür.
3. tools/assets/logo_paths.json : Genc.html #logo / #gmono ve paylaşım kartının
   kullandığı yol verisi.
4. tools/assets/wordmark_main_mask.png / wordmark_accent_mask.png : ikon
   üreticilerinin bastığı yüksek çözünürlüklü kelime markası maskeleri.
5. tools/assets/gmono_mask.png : "G" monogramı maskesi (küçük boyutlar için).

potrace yoksa betik mevcut logo_paths.json'dan maskeleri yeniden üretir.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "tools", "assets")
SRC = os.path.join(ASSETS, "logo_source.png")
PATHS = os.path.join(ASSETS, "logo_paths.json")
MASK_MONO = os.path.join(ASSETS, "gmono_mask.png")
MASK_WM_MAIN = os.path.join(ASSETS, "wordmark_main_mask.png")
MASK_WM_ACCENT = os.path.join(ASSETS, "wordmark_accent_mask.png")

# Kaynak görselde glif bölgesi (build_logo.py'nin ölçtüğü sabit kırpma).
CROP = (263, 232, 1144, 548)          # x0, y0, x1, y1
CREAM_MIN = (120, 120, 110)
RED_DOMINANCE = 55

MASK_CANVAS = 1024
MONO_WIDTH = 595                      # monogram tuval içinde ~%58
WORDMARK_WIDTH = 2048                 # yüksek çözünürlüklü kelime markası maskesi


def _masks():
    im = Image.open(SRC).convert("RGB")
    a = np.asarray(im).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    cream = (r > CREAM_MIN[0]) & (g > CREAM_MIN[1]) & (b > CREAM_MIN[2]) \
        & (np.abs(r - g) < 45) & (r - b < 70)
    red = (r - g > RED_DOMINANCE) & (r - b > RED_DOMINANCE) & (r > 90)
    x0, y0, x1, y1 = CROP
    return cream[y0:y1, x0:x1], red[y0:y1, x0:x1]


def _pbm(mask, path):
    Image.fromarray((~mask).astype(np.uint8) * 255).convert("1").save(path)


def _trace(pbm, out):
    subprocess.run(
        ["potrace", "-s", "--turdsize", "6", "--alphamax", "1.0",
         "--opttolerance", "0.2", "-o", out, pbm],
        check=True,
    )
    return " ".join(re.findall(r'<path d="([^"]+)"', open(out).read(), re.S)).strip()


def _vectorize():
    cream, red = _masks()
    gmask = cream.copy()
    gmask[:, 260:] = False           # G, kaynak görselde sütun 0-249'da
    ys, xs = np.where(gmask)
    g_crop = gmask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

    tmp = os.path.join(ASSETS, "_tmp")
    os.makedirs(tmp, exist_ok=True)
    try:
        _pbm(cream, os.path.join(tmp, "main.pbm"))
        _pbm(red, os.path.join(tmp, "accent.pbm"))
        _pbm(g_crop, os.path.join(tmp, "mono.pbm"))
        return {
            "viewBox": "0 0 %d %d" % (cream.shape[1], cream.shape[0]),
            "monoViewBox": "0 0 %d %d" % (g_crop.shape[1], g_crop.shape[0]),
            "main": _trace(os.path.join(tmp, "main.pbm"), os.path.join(tmp, "main.svg")),
            "accent": _trace(os.path.join(tmp, "accent.pbm"), os.path.join(tmp, "accent.svg")),
            "mono": _trace(os.path.join(tmp, "mono.pbm"), os.path.join(tmp, "mono.svg")),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _render(path_data, viewbox, out_width):
    """Yolu verilen genişlikte beyaz-üstü-siyah PNG maskesine çizer."""
    import cairosvg
    vb = viewbox.split()
    w, h = float(vb[2]), float(vb[3])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s">'
        '<g transform="translate(0,%s) scale(0.1,-0.1)" fill="#ffffff">'
        '<path d="%s"/></g></svg>' % (w, h, h, path_data)
    )
    raw = os.path.join(ASSETS, "_render_raw.png")
    cairosvg.svg2png(bytestring=svg.encode(), write_to=raw,
                     output_width=out_width, background_color="black")
    img = Image.open(raw).convert("L")
    os.remove(raw)
    return img


def _center_on(mask, canvas, width):
    scale = width / mask.width
    mask = mask.resize((max(1, round(mask.width * scale)),
                        max(1, round(mask.height * scale))), Image.LANCZOS)
    out = Image.new("L", (canvas, canvas), 0)
    out.paste(mask, ((canvas - mask.width) // 2, (canvas - mask.height) // 2))
    return out


def _masks_from_paths(data):
    mono = _render(data["mono"], data["monoViewBox"], MONO_WIDTH * 4)
    _center_on(mono, MASK_CANVAS, MONO_WIDTH).save(MASK_MONO)

    _render(data["main"], data["viewBox"], WORDMARK_WIDTH).save(MASK_WM_MAIN)
    _render(data["accent"], data["viewBox"], WORDMARK_WIDTH).save(MASK_WM_ACCENT)


def main():
    if shutil.which("potrace") and os.path.exists(SRC):
        data = _vectorize()
        json.dump(data, open(PATHS, "w"), indent=1)
        print("yollar üretildi:", PATHS)
    else:
        data = json.load(open(PATHS))
        print("potrace yok ya da kaynak eksik; mevcut logo_paths.json kullanılıyor")
    _masks_from_paths(data)
    print("maskeler üretildi:", MASK_MONO, MASK_WM_MAIN, MASK_WM_ACCENT)


if __name__ == "__main__":
    sys.exit(main())
