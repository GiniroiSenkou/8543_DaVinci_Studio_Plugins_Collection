#!/usr/bin/env python3
"""
Builds the preview images from frames rendered IN RESOLVE (1080x1920, the effect on a
clip of your own footage, exported with Project > Export current frame as still):

    renders/r_<Preset>.png   a held frame (animation finished)
    renders/a_<Preset>.png   an early frame of the In animation

Writes
    build/Edit/Effects/MangaPanels/MangaPanels_<Preset>.png   Effects-panel icon, 320x180,
        256-colour PNG under 40 KB (Resolve 21.1 shows no icon above ~48 KB)
    docs/Giniroisenkou_MangaPanels_<Preset>.png               540x960 preview per preset
    docs/Giniroisenkou_MangaPanels_overview.png               the four presets side by side
    docs/Giniroisenkou_MangaPanels_animations.png             In animations (early frame / held frame)

Needs Pillow and the bundled Archivo Black font (fonts/).
Usage:  python Giniroisenkou_MangaPanels_thumbs.py [renders_dir]
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "build", "Edit", "Effects", "MangaPanels")
DOCS = os.path.join(ROOT, "docs")
FONT = os.path.join(ROOT, "fonts", "ArchivoBlack-Regular.ttf")
PRESETS = [("PinkPortrait", "Pink Portrait", "Colour flash"), ("RedVictor", "Red Victor", "Flash + word slide"),
           ("Teal", "Teal", "Halftone dots grow"), ("Gold", "Gold", "Word slide")]
BG = (22, 20, 24)


def icon(img, label):
    """320x180 card: the upper-middle band of the 9:16 frame (where the big word sits) + label"""
    W, H = 320, 180
    s = W / img.width
    im = img.resize((W, round(img.height * s)), Image.LANCZOS)
    top = int(im.height * 0.16)
    im = im.crop((0, top, W, top + H)).convert("RGBA")
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for yy in range(int(H * 0.55), H):
        a = int(215 * max(0.0, (yy - H * 0.55) / (H * 0.45)) ** 1.2)
        gd.line([(0, yy), (W, yy)], fill=(10, 8, 12, a))
    im = Image.alpha_composite(im, grad)
    d = ImageDraw.Draw(im)
    d.text((12, H - 44), label.upper(), font=ImageFont.truetype(FONT, 21), fill=(255, 255, 255, 255))
    d.text((13, H - 18), "MANGAPANELS", font=ImageFont.truetype(FONT, 10), fill=(235, 235, 240, 220))
    return im.convert("RGB")


def main(rdir):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DOCS, exist_ok=True)
    held, early = {}, {}
    for key, label, _ in PRESETS:
        held[key] = Image.open(os.path.join(rdir, f"r_{key}.png")).convert("RGB")
        early[key] = Image.open(os.path.join(rdir, f"a_{key}.png")).convert("RGB")
        dst = os.path.join(OUT, f"MangaPanels_{key}.png")
        rgb = icon(held[key], label)
        for colours in (256, 128, 64):
            rgb.quantize(colours, method=Image.Quantize.MEDIANCUT).save(dst, optimize=True)
            if os.path.getsize(dst) < 40000:
                break
        held[key].resize((540, 960), Image.LANCZOS).save(
            os.path.join(DOCS, f"Giniroisenkou_MangaPanels_{key}.png"), optimize=True)
    # overview: 4 presets
    w, h, pad = 360, 640, 12
    sheet = Image.new("RGB", (4 * w + 5 * pad, h + 2 * pad), BG)
    for i, (key, _, _) in enumerate(PRESETS):
        sheet.paste(held[key].resize((w, h), Image.LANCZOS), (pad + i * (w + pad), pad))
    sheet.save(os.path.join(DOCS, "Giniroisenkou_MangaPanels_overview.png"), optimize=True)
    # animations: early frame over held frame, captioned
    w, h, cap = 270, 480, 34
    f = ImageFont.truetype(FONT, 15)
    an = Image.new("RGB", (4 * w + 5 * pad, 2 * h + 3 * pad + cap), BG)
    d = ImageDraw.Draw(an)
    for i, (key, label, anim) in enumerate(PRESETS):
        x = pad + i * (w + pad)
        d.text((x, 10), f"{label}: {anim}", font=f, fill=(235, 235, 240))
        an.paste(early[key].resize((w, h), Image.LANCZOS), (x, cap))
        an.paste(held[key].resize((w, h), Image.LANCZOS), (x, cap + h + pad))
    an.save(os.path.join(DOCS, "Giniroisenkou_MangaPanels_animations.png"), optimize=True)
    print("previews written")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "renders"))
