#!/usr/bin/env python3
"""Genç Android başlatıcı (launcher) simgelerini üretir.

Web simgeleriyle aynı gradyan ve konum iğnesi işaretini kullanır (tools/brand.py).
Android yoğunluk klasörlerine yazar:

- mipmap-<yoğunluk>/ic_launcher.png        : yuvarlatılmış kare (klasik)
- mipmap-<yoğunluk>/ic_launcher_round.png  : daire (yuvarlak simge)
- drawable-<yoğunluk>/ic_launcher_foreground.png : uyarlanabilir simge ön katmanı
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brand  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "android", "app", "src", "main", "res")

# Android yoğunluk başına (mipmap, ön katman) piksel boyutları.
DENSITIES = {
    "mdpi": (48, 108),
    "hdpi": (72, 162),
    "xhdpi": (96, 216),
    "xxhdpi": (144, 324),
    "xxxhdpi": (192, 432),
}


def save(img, *parts):
    path = os.path.join(RES, *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    print("yazıldı:", os.path.relpath(path, ROOT), img.size)


def main():
    for dens, (mip, fg) in DENSITIES.items():
        save(brand.draw_ticket(brand.rounded(brand.gloss(brand.gradient(mip))), border=True),
             "mipmap-" + dens, "ic_launcher.png")
        save(brand.draw_ticket(brand.circle(brand.gloss(brand.gradient(mip)))),
             "mipmap-" + dens, "ic_launcher_round.png")
        # Uyarlanabilir simge: sistem maskeler, bu yüzden tam kare gradyan.
        # İğne, güvenli alana (karenin %66'sı) sığması için küçültülür.
        save(brand.draw_ticket(brand.gloss(brand.gradient(fg)), scale=0.6),
             "drawable-" + dens, "ic_launcher_foreground.png")


if __name__ == "__main__":
    main()
