#!/usr/bin/env python3
"""Genç marka yardımcıları: logo gradyanı ve logo işareti.

Logo işareti 44x44'lük kutuda tanımlıdır (bkz. Genc.html #logo): eski mor-pembe
ile yeni kırmızı-sarının harmanlandığı gradyan zemin üzerinde beyaz bilet
(bkz. TICKET). Tüm ikon üreticileri bu modülü kullanır.
"""

from PIL import Image, ImageDraw

# Uygulama içi logo gradyanıyla aynı duraklar (bkz. Genc.html --logo-c*).
# Eski palet (mor -> mor-pembe -> pembe) ile yeni palet (mor -> kırmızı ->
# sarı) harmanlandı: mor, orkide, gül ve altın sarısı bir gün batımı geçişi.
STOPS = [
    (0.00, (109, 74, 255)),   # #6D4AFF mor (her iki paletin de başı)
    (0.34, (180, 77, 224)),   # #B44DE0 eski mor-pembe (eski renk geri geldi)
    (0.66, (240, 71, 126)),   # #F0477E harman: kırmızı-pembe
    (1.00, (255, 200, 61)),   # #FFC83D altın sarısı
]

# Logo işareti (44x44 kutu): yatay bilet — gövde + üst/alt orta çentik +
# yatay perforasyon (kesik çizgi). Genc.html #logo ile birebir aynı olmalı.
BOX = 44.0
TICKET = {"x0": 7.0, "y0": 13.0, "x1": 37.0, "y1": 31.0, "r": 4.0}
NOTCH_CX = 22.0          # üst ve alt kenarın ortasındaki çentik
NOTCH_R = 4.0
PERF_Y = 22.0            # yatay perforasyonun dikey merkezi
PERF_CX = (13.5, 22.0, 30.5)   # kesik çizgi parçalarının merkezleri
PERF_W = 1.1             # parça yarı genişliği
PERF_HH = 1.5            # parça yarı yüksekliği
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


def ticket_mask(size, scale=1.0):
    """Beyaz bilet işaretinin alfa maskesi (verilen piksel boyutunda).

    `scale` işareti kutunun merkezine göre küçültür; uyarlanabilir simgelerin
    güvenli alanına sığdırmak için kullanılır.
    """
    s = size / BOX
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    mid = (size / 2.0, size / 2.0)

    def T(x, y):
        return (mid[0] + (x * s - mid[0]) * scale, mid[1] + (y * s - mid[1]) * scale)

    # Gövde (yuvarlatılmış dikdörtgen).
    x0, y0 = T(TICKET["x0"], TICKET["y0"])
    x1, y1 = T(TICKET["x1"], TICKET["y1"])
    d.rounded_rectangle([x0, y0, x1, y1], radius=TICKET["r"] * s * scale, fill=255)

    # Üst/alt orta çentikler (oyulur); daire kenarın üzerinde olduğu için
    # gövde içinde kalan yarısı ısırık oluşturur.
    rr = NOTCH_R * s * scale
    for cy in (TICKET["y0"], TICKET["y1"]):
        a = T(NOTCH_CX, cy)
        d.ellipse([a[0] - rr, a[1] - rr, a[0] + rr, a[1] + rr], fill=0)

    # Yatay perforasyon (oyulur): üç yuvarlatılmış kesik.
    for cx in PERF_CX:
        a = T(cx, PERF_Y)
        w = PERF_W * s * scale
        hh = PERF_HH * s * scale
        d.rounded_rectangle([a[0] - w, a[1] - hh, a[0] + w, a[1] + hh], radius=w, fill=0)

    return mask


def draw_ticket(img, border=False, scale=1.0):
    """Gradyan zemin üzerine beyaz bilet işareti çizer."""
    size = img.width
    ss = 4  # kenar yumuşatma için üst örnekleme
    mask = ticket_mask(size * ss, scale).resize((size, size), Image.LANCZOS)
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
