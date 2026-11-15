#!/usr/bin/env python3
"""Genç marka yardımcıları: logo gradyanı ve uygulama işareti.

Marka artık ayrı bir kutu + bilet simgesi değil; "Genç" kelime markası
(bkz. Genc.html #logo) ve onun monogramı olan "G". Uygulama ikonlarında
gradyan zemin üzerine beyaz "G" monogramı basılır (bkz. tools/assets/
gmono_mask.png; Genc.html #gmono ile aynı form). Tüm ikon üreticileri bu
modülü kullanır.
"""

import os
from PIL import Image, ImageDraw

# Uygulama içi logo gradyanıyla aynı duraklar (bkz. Genc.html --logo-c*).
# Premium "Aurora" paleti: tek renk ailesi içinde komşu tonlar (indigo ->
# menekşe -> fuşya). Eski gökkuşağı (mor -> pembe -> kırmızı -> sarı) 4 ayrı
# renk ailesi kullanıp "çocuk uygulaması" hissi veriyordu; dar ton aralığı
# (235°-292°) marka rengiyle (--brand #5B3DF5) uyumlu ve daha kaliteli durur.
STOPS = [
    (0.00, (67, 56, 202)),    # #4338CA indigo
    (0.38, (124, 58, 237)),   # #7C3AED menekşe
    (0.72, (168, 85, 247)),   # #A855F7 mor
    (1.00, (217, 70, 239)),   # #D946EF fuşya
]

# İşaret kutusu (Genc.html #gmono ile aynı 44x44 ölçüsü).
BOX = 44.0
# "G" monogramının yüksek çözünürlüklü alfa maskesi (tools/assets/gmono_mask.png).
_MASK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "gmono_mask.png")
_GLYPH_MASK = None
INSET = 4.7
INSET_RADIUS = 9.4


def lerp(a, b, t):
    return round(a + (b - a) * t)


def gradient(size):
    """Köşegen logo gradyanı (opak RGBA)."""
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
    return img.convert("RGBA")


def gloss(img):
    """Sol üste düşen yumuşak beyaz parlama (cam/kalite hissi)."""
    size = img.width
    ss = 2
    big = size * ss
    lay = Image.new("L", (big, big), 0)
    px = lay.load()
    cx, cy, r = 0.30 * big, 0.22 * big, 0.85 * big
    for y in range(big):
        for x in range(big):
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / r
            if dist >= 1:
                continue
            a = 0.38 * (1 - dist) ** 1.6
            px[x, y] = int(a * 255)
    lay = lay.resize((size, size), Image.LANCZOS)
    out = img.copy()
    out.paste((255, 255, 255), (0, 0), lay)
    return out


def _apply_mask(img, mask):
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def rounded(img, radius_ratio=0.30):
    size = img.width
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * radius_ratio), fill=255
    )
    return _apply_mask(img, mask)


def circle(img):
    size = img.width
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    return _apply_mask(img, mask)


def monogram_mask(size, scale=1.0):
    """Beyaz "G" monogramının alfa maskesi (verilen piksel boyutunda).

    `scale` işareti kutunun merkezine göre küçültür; uyarlanabilir simgelerin
    güvenli alanına sığdırmak için kullanılır.
    """
    global _GLYPH_MASK
    if _GLYPH_MASK is None:
        _GLYPH_MASK = Image.open(_MASK_PATH).convert("L")
    m = _GLYPH_MASK
    if scale != 1.0:
        box = [0, 0, m.width, m.height]
        m = m.resize((max(1, int(m.width * scale)), max(1, int(m.height * scale))), Image.LANCZOS)
        layer = Image.new("L", (size, size), 0)
        layer.paste(m, ((size - m.width) // 2, (size - m.height) // 2))
        m = layer
    return m.resize((size, size), Image.LANCZOS)


def draw_monogram(img, border=False, scale=1.0):
    """Gradyan zemin üzerine beyaz "G" monogramını çizer."""
    size = img.width
    mask = monogram_mask(size, scale)
    img.paste((255, 255, 255, 255), (0, 0), mask)
    if border:
        s = size / BOX
        inset = INSET * s
        ImageDraw.Draw(img).rounded_rectangle(
            [inset, inset, size - inset, size - inset],
            radius=INSET_RADIUS * s,
            outline=(255, 255, 255, 61),
            width=max(1, round(1.3 * s)),
        )
    return img
