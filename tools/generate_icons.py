#!/usr/bin/env python3
"""Genç PWA ikonlarını üretir (icons/ klasörüne PNG yazar).

İkon: koyu zemin üzerine krem "G" monogramı (bkz. tools/brand.py). Bu, yeni
kelime markası logosunun kare sürümüdür (bkz. tools/assets/logo_source.png).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brand  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")


def save(img, name):
    img.save(os.path.join(OUT, name))
    print("yazıldı:", name, img.size)


def main():
    os.makedirs(OUT, exist_ok=True)
    for size in (192, 512):
        save(brand.draw_monogram(brand.rounded(brand.flat(size, brand.ICON_BG))), f"icon-{size}.png")
    save(brand.draw_monogram(brand.flat(512, brand.ICON_BG), scale=0.9), "maskable-512.png")
    save(brand.draw_monogram(brand.rounded(brand.flat(180, brand.ICON_BG))), "apple-touch-icon.png")
    save(brand.draw_monogram(brand.flat(32, brand.ICON_BG)), "favicon-32.png")


if __name__ == "__main__":
    main()
