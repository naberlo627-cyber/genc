#!/usr/bin/env python3
"""Genç marka yardımcıları: logo gradyanı ve logo işareti.

Logo işareti 44x44'lük kutuda tanımlıdır (bkz. Genc.html #logo): eski mor ile
yeni kırmızı/sarının harmanlandığı gradyan zemin üzerinde beyaz konum iğnesi.
Tüm ikon üreticileri bu modülü kullanır.
"""
import math

from PIL import Image, ImageDraw

# Uygulama içi logo gradyanıyla aynı duraklar (bkz. Genc.html --logo-c*).
STOPS = [
    (0.00, (109, 74, 255)),   # #6D4AFF eski mor
    (0.50, (232, 67, 127)),   # #E8437F pembe/kırmızı
    (1.00, (255, 200, 61)),   # #FFC83D altın sarısı
]

# Logo işareti (44x44 kutu): konum iğnesi başı, deliği ve ucu.
BOX = 44.0
PIN_HEAD = (22.0, 18.2)
PIN_R = 11.6
PIN_HOLE = 4.4
PIN_TIP = (22.0, 35.4)
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


def pin_mask(size, scale=1.0):
    """Beyaz konum iğnesinin alfa maskesi (verilen piksel boyutunda).

    `scale` iğneyi kutunun merkezine göre küçültür; uyarlanabilir simgelerin
    güvenli alanına sığdırmak için kullanılır.
    """
    s = size / BOX
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    cx, cy = PIN_HEAD[0] * s, PIN_HEAD[1] * s
    tx, ty = PIN_TIP[0] * s, PIN_TIP[1] * s
    mid = (size / 2.0, size / 2.0)
    cx, cy = mid[0] + (cx - mid[0]) * scale, mid[1] + (cy - mid[1]) * scale
    tx, ty = mid[0] + (tx - mid[0]) * scale, mid[1] + (ty - mid[1]) * scale
    r = PIN_R * s * scale
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    ang = math.atan2(ty - cy, tx - cx)
    dist = math.hypot(tx - cx, ty - cy)
    beta = math.acos(max(-1.0, min(1.0, r / dist)))
    p1 = (cx + r * math.cos(ang + beta), cy + r * math.sin(ang + beta))
    p2 = (cx + r * math.cos(ang - beta), cy + r * math.sin(ang - beta))
    d.polygon([p1, p2, (tx, ty)], fill=255)
    hr = PIN_HOLE * s * scale
    d.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=0)
    return mask


def draw_pin(img, border=False, scale=1.0):
    """Gradyan zemin üzerine beyaz konum iğnesi çizer."""
    size = img.width
    ss = 4  # kenar yumuşatma için üst örnekleme
    mask = pin_mask(size * ss, scale).resize((size, size), Image.LANCZOS)
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
