#!/usr/bin/env python3
"""Genç marka yardımcıları: logo renkleri ve uygulama işareti.

Marka, "genç" kelime markası ve onun "G" monogramıdır (bkz. Genc.html
#logo, #gmono). Yeni logo koyu zemin üzerine krem harfler ve aksan renkli
"ç" ile gelir (bkz. tools/assets/logo_source.png). Uygulama ikonlarında
koyu zemin üzerine krem "G" basılır (bkz. tools/assets/gmono_mask.png).
Tüm ikon üreticileri bu modülü kullanır.
"""

import os
from PIL import Image, ImageDraw

# Genc.html --paper / --ink / --brand ve logodan örneklenen tonlar.
DARK = (22, 26, 28)       # #161A1C logo zemini (ikon arka planı)
CREAM = (247, 240, 230)   # #F7F0E6 krem (metin/glif)
INK = (20, 16, 13)        # #14100D mürekkep
ACCENT = (229, 64, 42)    # #E5402A aksan (logodaki "ç")

# İkon kompozisyonu: koyu zemin üzerine krem glif (logoya sadık).
ICON_BG = DARK
ICON_FG = CREAM

# İşaret kutusu (Genc.html #gmono ile aynı oran).
BOX = 44.0
_MASK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "gmono_mask.png")
_GLYPH_MASK = None


def flat(size, color):
    """Düz renkli opak RGBA tuval."""
    return Image.new("RGBA", (size, size), color + (255,))


def blank(size):
    """Şeffaf RGBA tuval (uyarlanabilir simge ön katmanı için)."""
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


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
    '''"G" monogramının alfa maskesi (verilen piksel boyutunda).

    `scale` glif kutusunun tuvale oranıdır; küçük değerler glifi küçültüp
    çevresine boşluk bırakır (uyarlanabilir simgelerin güvenli alanı için).
    '''
    global _GLYPH_MASK
    if _GLYPH_MASK is None:
        _GLYPH_MASK = Image.open(_MASK_PATH).convert("L")
    box = max(1, int(round(size * scale)))
    m = _GLYPH_MASK.resize((box, box), Image.LANCZOS)
    if box == size:
        return m
    layer = Image.new("L", (size, size), 0)
    layer.paste(m, ((size - box) // 2, (size - box) // 2))
    return layer


def draw_monogram(img, color=ICON_FG, scale=1.0):
    '''Zemin üzerine "G" monogramını çizer.'''
    mask = monogram_mask(img.width, scale)
    img.paste(color + (255,), (0, 0), mask)
    return img
