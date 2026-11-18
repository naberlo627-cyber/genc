#!/usr/bin/env python3
"""Genç uygulama kısayolu simgelerini üretir (icons/ klasörüne PNG yazar).

Her kısayol kendi glifini alır; Android ve masaüstü aynı ikonla tekrar etmez.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brand  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")
SIZE = 192
PAD = 34


def base():
    """Yuvarlak köşeli krem arka plan."""
    return brand.rounded(brand.flat(SIZE, brand.CREAM), 0.26)


def draw_play(d):
    c = SIZE / 2
    r = (SIZE - 2 * PAD) / 2
    d.polygon(
        [(c - r * 0.55, c - r), (c - r * 0.55, c + r), (c + r * 0.85, c)],
        fill=brand.INK,
    )


def draw_search(d):
    c = SIZE / 2
    r = (SIZE - 2 * PAD) / 2 * 0.72
    w = 13
    d.ellipse([c - r - w, c - r - w, c + r + w, c + r + w], outline=brand.INK, width=w)
    d.line([(c + r * 0.75, c + r * 0.75), (c + r * 1.5, c + r * 1.5)], fill=brand.INK, width=w)


def draw_ticket(d):
    c = SIZE / 2
    w, h = (SIZE - 2 * PAD), (SIZE - 2 * PAD) * 0.66
    l, t, r, b = c - w / 2, c - h / 2, c + w / 2, c + h / 2
    rad = 16
    d.rounded_rectangle([l, t, r, b], radius=rad, outline=brand.INK, width=13)
    notch = 22
    d.ellipse([l - notch / 2, c - notch / 2, l + notch / 2, c + notch / 2], fill=(0, 0, 0, 0))
    d.ellipse([r - notch / 2, c - notch / 2, r + notch / 2, c + notch / 2], fill=(0, 0, 0, 0))
    d.line([(c, t + 8), (c, b - 8)], fill=brand.INK, width=9)


def draw_user(d):
    c = SIZE / 2
    hr = (SIZE - 2 * PAD) * 0.24
    d.ellipse([c - hr, c - hr * 2.3, c + hr, c + hr * 0.3], outline=brand.INK, width=13)
    bw = (SIZE - 2 * PAD) * 0.72
    d.arc(
        [c - bw / 2, c - hr * 0.1, c + bw / 2, c + bw * 0.95],
        start=200,
        end=340,
        fill=brand.INK,
        width=13,
    )


def draw_pin(d):
    c = SIZE / 2
    r = (SIZE - 2 * PAD) * 0.34
    top = c - r * 1.25
    d.ellipse([c - r, top, c + r, top + 2 * r], outline=brand.INK, width=13)
    d.polygon([(c - r * 0.72, top + 2 * r * 0.82), (c + r * 0.72, top + 2 * r * 0.82), (c, c + r * 1.55)], fill=brand.INK)
    ir = r * 0.38
    d.ellipse([c - ir, top + r - ir, c + ir, top + r + ir], fill=(0, 0, 0, 0))


def draw_calendar(d):
    c = SIZE / 2
    w, h = (SIZE - 2 * PAD) * 0.94, (SIZE - 2 * PAD) * 0.86
    l, t, r, b = c - w / 2, c - h / 2, c + w / 2, c + h / 2
    d.rounded_rectangle([l, t, r, b], radius=14, outline=brand.INK, width=13)
    d.line([(l + 6, t + h * 0.34), (r - 6, t + h * 0.34)], fill=brand.INK, width=11)
    d.line([(l + w * 0.3, t - 10), (l + w * 0.3, t + 14)], fill=brand.INK, width=12)
    d.line([(r - w * 0.3, t - 10), (r - w * 0.3, t + 14)], fill=brand.INK, width=12)


def draw_spark(d):
    """Haftalık özet: marka yıldızı (dört uçlu parıltı)."""
    c = SIZE / 2
    r = (SIZE - 2 * PAD) / 2
    inner = r * 0.30
    d.polygon(
        [
            (c, c - r),
            (c + inner, c - inner),
            (c + r, c),
            (c + inner, c + inner),
            (c, c + r),
            (c - inner, c + inner),
            (c - r, c),
            (c - inner, c - inner),
        ],
        fill=brand.INK,
    )


def draw_bell(d):
    """Bildirimler: çan."""
    c = SIZE / 2
    w = (SIZE - 2 * PAD) * 0.62
    h = (SIZE - 2 * PAD) * 0.62
    l, t = c - w / 2, c - h / 2
    r, b = c + w / 2, c + h / 2
    # Gövde: üstte yarım daire, yanlarda düz, altta düz taban.
    d.pieslice([l, t, r, t + w], start=180, end=360, fill=brand.INK)
    d.rectangle([l, t + w / 2, r, b - h * 0.18], fill=brand.INK)
    # Taban kenarı ve tokmak.
    d.rounded_rectangle([l - 8, b - h * 0.18 - 10, r + 8, b - h * 0.18 + 6], radius=8, fill=brand.INK)
    d.ellipse([c - 13, b - h * 0.18 + 6, c + 13, b - h * 0.18 + 34], fill=brand.INK)


def draw_heart(d):
    """Hoşlandıklarım: kalp."""
    c = SIZE / 2
    r = (SIZE - 2 * PAD) * 0.30
    top = c - r * 0.55
    d.ellipse([c - 2 * r, top - r, c, top + r], fill=brand.INK)
    d.ellipse([c, top - r, c + 2 * r, top + r], fill=brand.INK)
    d.polygon([(c - 2 * r, top), (c + 2 * r, top), (c, c + r * 2.1)], fill=brand.INK)


SHORTCUTS = {
    "shortcut-bilet-al": draw_ticket,
    "shortcut-videolar": draw_play,
    "shortcut-ara": draw_search,
    "shortcut-biletlerim": draw_calendar,
    "shortcut-yakin": draw_pin,
    "shortcut-profil": draw_user,
    "shortcut-hafta": draw_spark,
    "shortcut-bildirimler": draw_bell,
    "shortcut-hoslandiklarim": draw_heart,
}


# Android kısayol simgeleri: res/drawable-<yoğunluk>/sc_<kimlik>.png.
# Android, kısayol simgesini yoğunluğa göre seçer; hepsi 192 px'den ölçeklenir.
ANDROID_RES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "android", "app", "src", "main", "res",
)
ANDROID_DENSITIES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}
# Android kısayol kimliği (shortcuts.xml) -> üretici adı.
ANDROID_IDS = {
    "sc_hafta": "shortcut-hafta",
    "sc_bilet_al": "shortcut-bilet-al",
    "sc_yakin": "shortcut-yakin",
    "sc_ara": "shortcut-ara",
    "sc_biletlerim": "shortcut-biletlerim",
    "sc_profil": "shortcut-profil",
    "sc_videolar": "shortcut-videolar",
    "sc_bildirimler": "shortcut-bildirimler",
    "sc_hoslandiklarim": "shortcut-hoslandiklarim",
}


def render(fn):
    img = base()
    fn(ImageDraw.Draw(img))
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in SHORTCUTS.items():
        img = render(fn)
        img.save(os.path.join(OUT, name + ".png"))
        print("yazıldı:", name + ".png", img.size)

    for sid, src in ANDROID_IDS.items():
        img = render(SHORTCUTS[src])
        for dens, size in ANDROID_DENSITIES.items():
            path = os.path.join(ANDROID_RES, "drawable-" + dens, sid + ".png")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            img.resize((size, size), Image.LANCZOS).save(path)
        print("yazıldı: Android", sid, list(ANDROID_DENSITIES.values()))


if __name__ == "__main__":
    main()
