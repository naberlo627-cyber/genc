#!/usr/bin/env python3
"""Genç PWA ikonlarını üretir (icons/ klasörüne PNG yazar).

İkon: krem zemin üzerine aksan renkli "G" monogramı (bkz. tools/brand.py).
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
        save(brand.draw_monogram(brand.rounded(brand.flat(size, brand.CREAM))), f"icon-{size}.png")
    save(brand.draw_monogram(brand.flat(512, brand.CREAM), scale=0.72), "maskable-512.png")
    save(brand.draw_monogram(brand.rounded(brand.flat(180, brand.CREAM))), "apple-touch-icon.png")
    save(brand.draw_monogram(brand.flat(32, brand.CREAM)), "favicon-32.png")


if __name__ == "__main__":
    main()
