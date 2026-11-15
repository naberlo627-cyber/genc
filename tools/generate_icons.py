#!/usr/bin/env python3
"""Genç PWA ikonlarını üretir (icons/ klasörüne PNG yazar).

İkon, uygulama içi logonun kutusuz halidir: köşegen gradyan zemin üzerinde
beyaz konum iğnesi. Gradyan ve işaret ortak modülden gelir (tools/brand.py).
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
        save(brand.draw_ticket(brand.rounded(brand.gradient(size)), border=True), f"icon-{size}.png")
    save(brand.draw_ticket(brand.gradient(512)), "maskable-512.png")
    save(brand.draw_ticket(brand.rounded(brand.gradient(180)), border=True), "apple-touch-icon.png")
    save(brand.draw_ticket(brand.rounded(brand.gradient(32))), "favicon-32.png")


if __name__ == "__main__":
    main()
