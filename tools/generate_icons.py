#!/usr/bin/env python3
"""Genç uygulama ikonlarını üretir (icons/ klasörüne PNG yazar).

İkon, uygulama içi logonun kutusuz halidir: köşegen gradyan zemin üzerinde
beyaz dört uçlu ışıltı (yıldız) işareti.
"""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")

# Uygulama içi logo gradyanıyla aynı renk durakları (bkz. Genc.html --logo-c*).
STOPS = [
    (0.00, (109, 74, 255)),   # #6D4AFF
    (0.55, (180, 77, 224)),   # #B44DE0
    (1.00, (255, 79, 139)),   # #FF4F8B
]

# Işıltı işaretinin 44x44 logo kutusundaki noktaları (dış uç + iç köşe).
SPARKLE_44 = [
    (22.0, 8.4), (25.4, 18.6), (35.6, 22.0), (25.4, 25.4),
    (22.0, 35.6), (18.6, 25.4), (8.4, 22.0), (18.6, 18.6),
]


def lerp(a, b, t):
    return round(a + (b - a) * t)


def gradient(size):
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            lo, hi = STOPS[0], STOPS[-1]
            for i in range(len(STOPS) - 1):
                if STOPS[i][0] <= t <= STOPS[i + 1][0]:
                    lo, hi = STOPS[i], STOPS[i + 1]
                    break
            span = (hi[0] - lo[0]) or 1
            k = (t - lo[0]) / span
            px[x, y] = tuple(lerp(lo[1][c], hi[1][c], k) for c in range(3))
    return img


def rounded(img, radius_ratio):
    size = img.width
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * radius_ratio), fill=255
    )
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def draw_sparkle(img, border=False):
    size = img.width
    d = ImageDraw.Draw(img)
    scale = size / 44.0
    d.polygon([(x * scale, y * scale) for x, y in SPARKLE_44], fill=(255, 255, 255, 255))
    if border:
        inset = 4.7 * scale
        d.rounded_rectangle(
            [inset, inset, size - inset, size - inset],
            radius=9.4 * scale,
            outline=(255, 255, 255, 61),
            width=max(1, round(1.3 * scale)),
        )
    return img


def save(img, name):
    img.save(os.path.join(OUT, name))
    print("yazıldı:", name, img.size)


def main():
    os.makedirs(OUT, exist_ok=True)
    for size in (192, 512):
        save(draw_sparkle(rounded(gradient(size), 0.30), border=True), f"icon-{size}.png")
    save(draw_sparkle(gradient(512)), "maskable-512.png")
    save(draw_sparkle(rounded(gradient(180), 0.30), border=True), "apple-touch-icon.png")
    save(draw_sparkle(rounded(gradient(32), 0.30)), "favicon-32.png")


if __name__ == "__main__":
    main()
