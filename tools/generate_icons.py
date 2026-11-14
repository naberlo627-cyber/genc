#!/usr/bin/env python3
"""Genç uygulama ikonlarını üretir (icons/ klasörüne PNG yazar)."""
import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
C1 = (109, 74, 255)   # #6D4AFF
C2 = (255, 79, 139)   # #FF4F8B


def gradient(size):
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            px[x, y] = (
                round(C1[0] + (C2[0] - C1[0]) * t),
                round(C1[1] + (C2[1] - C1[1]) * t),
                round(C1[2] + (C2[2] - C1[2]) * t),
            )
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


def draw_letter(img, ratio):
    size = img.width
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, int(size * ratio))
    box = d.textbbox((0, 0), "G", font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1]), "G", font=font, fill="white")
    return img


def save(img, name):
    img.save(os.path.join(OUT, name))
    print("yazıldı:", name, img.size)


def main():
    os.makedirs(OUT, exist_ok=True)
    for size in (192, 512):
        save(draw_letter(rounded(gradient(size), 0.22), 0.60), f"icon-{size}.png")
    save(draw_letter(gradient(512), 0.42), "maskable-512.png")
    save(draw_letter(gradient(180), 0.60), "apple-touch-icon.png")
    save(draw_letter(rounded(gradient(32), 0.22), 0.60), "favicon-32.png")


if __name__ == "__main__":
    main()
