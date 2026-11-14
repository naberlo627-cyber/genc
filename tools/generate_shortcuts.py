#!/usr/bin/env python3
"""Genç uygulama kısayolu simgelerini üretir (icons/ klasörüne PNG yazar).

Her kısayol kendi glifini alır; Android ve masaüstü aynı ikonla tekrar etmez.
"""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")
# Uygulama içi logo gradyanıyla aynı duraklar (bkz. Genc.html --logo-c*).
STOPS = [
    (0.00, (109, 74, 255)),   # #6D4AFF
    (0.55, (180, 77, 224)),   # #B44DE0
    (1.00, (255, 79, 139)),   # #FF4F8B
]
SIZE = 192
PAD = 34


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
            px[x, y] = tuple(round(lo[1][c] + (hi[1][c] - lo[1][c]) * k) for c in range(3))
    return img


def base():
    """Yuvarlak köşeli gradyan arka plan."""
    img = gradient(SIZE).convert("RGBA")
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, SIZE - 1, SIZE - 1], radius=int(SIZE * 0.26), fill=255
    )
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def glyph(img, draw):
    pass


def draw_play(d):
    c = SIZE / 2
    r = (SIZE - 2 * PAD) / 2
    d.polygon(
        [(c - r * 0.55, c - r), (c - r * 0.55, c + r), (c + r * 0.85, c)],
        fill="white",
    )


def draw_search(d):
    c = SIZE / 2
    r = (SIZE - 2 * PAD) / 2 * 0.72
    w = 13
    d.ellipse([c - r - w, c - r - w, c + r + w, c + r + w], outline="white", width=w)
    d.line([(c + r * 0.75, c + r * 0.75), (c + r * 1.5, c + r * 1.5)], fill="white", width=w)


def draw_ticket(d):
    c = SIZE / 2
    w, h = (SIZE - 2 * PAD), (SIZE - 2 * PAD) * 0.66
    l, t, r, b = c - w / 2, c - h / 2, c + w / 2, c + h / 2
    rad = 16
    d.rounded_rectangle([l, t, r, b], radius=rad, outline="white", width=13)
    notch = 22
    d.ellipse([l - notch / 2, c - notch / 2, l + notch / 2, c + notch / 2], fill=(0, 0, 0, 0))
    d.ellipse([r - notch / 2, c - notch / 2, r + notch / 2, c + notch / 2], fill=(0, 0, 0, 0))
    d.line([(c, t + 8), (c, b - 8)], fill="white", width=9)


def draw_user(d):
    c = SIZE / 2
    hr = (SIZE - 2 * PAD) * 0.24
    d.ellipse([c - hr, c - hr * 2.3, c + hr, c + hr * 0.3], outline="white", width=13)
    bw = (SIZE - 2 * PAD) * 0.72
    d.arc(
        [c - bw / 2, c - hr * 0.1, c + bw / 2, c + bw * 0.95],
        start=200,
        end=340,
        fill="white",
        width=13,
    )


def draw_pin(d):
    c = SIZE / 2
    r = (SIZE - 2 * PAD) * 0.34
    top = c - r * 1.25
    d.ellipse([c - r, top, c + r, top + 2 * r], outline="white", width=13)
    d.polygon([(c - r * 0.72, top + 2 * r * 0.82), (c + r * 0.72, top + 2 * r * 0.82), (c, c + r * 1.55)], fill="white")
    ir = r * 0.38
    d.ellipse([c - ir, top + r - ir, c + ir, top + r + ir], fill=(0, 0, 0, 0))


def draw_calendar(d):
    c = SIZE / 2
    w, h = (SIZE - 2 * PAD) * 0.94, (SIZE - 2 * PAD) * 0.86
    l, t, r, b = c - w / 2, c - h / 2, c + w / 2, c + h / 2
    d.rounded_rectangle([l, t, r, b], radius=14, outline="white", width=13)
    d.line([(l + 6, t + h * 0.34), (r - 6, t + h * 0.34)], fill="white", width=11)
    d.line([(l + w * 0.3, t - 10), (l + w * 0.3, t + 14)], fill="white", width=12)
    d.line([(r - w * 0.3, t - 10), (r - w * 0.3, t + 14)], fill="white", width=12)


SHORTCUTS = {
    "shortcut-bilet-al": draw_ticket,
    "shortcut-videolar": draw_play,
    "shortcut-ara": draw_search,
    "shortcut-biletlerim": draw_calendar,
    "shortcut-yakin": draw_pin,
    "shortcut-profil": draw_user,
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in SHORTCUTS.items():
        img = base()
        fn(ImageDraw.Draw(img))
        img.save(os.path.join(OUT, name + ".png"))
        print("yazıldı:", name + ".png", img.size)


if __name__ == "__main__":
    main()
