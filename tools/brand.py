#!/usr/bin/env python3
"""Genç marka yardımcıları: logo renkleri ve uygulama işareti.

Marka, "genç" kelime markası ve onun aksan renkli monogramı "G"dir
(bkz. Genc.html #logo, #gmono). Palet sade: krem zemin, mürekkep metin,
aksan kırmızısı monogram. Uygulama ikonlarında krem zemin üzerine kırmızı
"G" basılır (bkz. tools/assets/gmono_mask.png). Tüm ikon üreticileri bu
modülü kullanır.
"""

import os
from PIL import Image, ImageDraw

# Genc.html --paper / --ink / --brand ile aynı tonlar.
CREAM = (247, 240, 230)   # #F7F0E6 zemin
INK = (20, 16, 13)        # #14100D metin
ACCENT = (229, 64, 42)    # #E5402A aksan (monogram)

# İşaret kutusu (Genc.html #gmono ile aynı 44x44 ölçüsü).
BOX = 44.0
# "G" monogramının yüksek çözünürlüklü alfa maskesi (tools/assets/gmono_mask.png).
_MASK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "gmono_mask.png")
_GLYPH_MASK = None


def flat(size, color):
    """Düz renkli opak RGBA tuval."""
    return Image.new("RGBA", (size, size), color + (255,))


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

    `scale` işareti kutunun merkezine göre küçültür; uyarlanabilir simgelerin
    güvenli alanına sığdırmak için kullanılır.
    '''
    global _GLYPH_MASK
    if _GLYPH_MASK is None:
        _GLYPH_MASK = Image.open(_MASK_PATH).convert("L")
    m = _GLYPH_MASK
    if scale != 1.0:
        m = m.resize((max(1, int(m.width * scale)), max(1, int(m.height * scale))), Image.LANCZOS)
        layer = Image.new("L", (size, size), 0)
        layer.paste(m, ((size - m.width) // 2, (size - m.height) // 2))
        m = layer
    return m.resize((size, size), Image.LANCZOS)


def draw_monogram(img, color=ACCENT, scale=1.0):
    '''Zemin üzerine "G" monogramını çizer.'''
    mask = monogram_mask(img.width, scale)
    img.paste(color + (255,), (0, 0), mask)
    return img
