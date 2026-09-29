#!/usr/bin/env python3
"""
Builds the Effects-panel thumbnails (320x180 PNG next to every .setting, kept under ~46 KB
because Resolve 21.1 only shows small PNGs) and the docs images from stills grabbed IN RESOLVE.

Workflow used:
  1. python Giniroisenkou_Title_Sliding_gen.py        -> build/Edit/Effects/Title_Sliding/*.setting
  2. apply each preset to a 1080x1920 test clip, grab stills (Color page > Grab Still,
     Gallery > Export) and save them as renders/<preset>.png  (hold frame, ~frame 40)
     plus renders/anim_<frame>.png for the animation strip
  3. python Giniroisenkou_Title_Sliding_thumbs.py
  4. python Giniroisenkou_Title_Sliding_package.py    -> Giniroisenkou_Title_Sliding.drfx
Needs Pillow and DejaVu Sans Bold (set FONT for another bold TTF).
"""
import io, os, glob, re
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REN = os.path.join(ROOT, "build", "renders")
OUT = os.path.join(ROOT, "build", "Edit", "Effects", "Title_Sliding")
DOCS = os.path.join(ROOT, "docs")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# preset, label, band centre (0 bottom - 1 top) used to crop the 16:9 thumbnail
PRESETS = [("Title_Sliding", "Anime slide", 0.30), ("Title_Sliding_News", "News", 0.285),
           ("Title_Sliding_Breaking", "Breaking", 0.285), ("Title_Sliding_Cinema", "Cinema", 0.5)]


def small_png(im, limit=46000):
    for colors in (256, 128, 64, 32):
        b = io.BytesIO()
        im.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).save(b, "PNG", optimize=True)
        if b.tell() < limit:
            break
    return b.getvalue()


def main():
    os.makedirs(DOCS, exist_ok=True)
    for name, lab, py in PRESETS:
        im = Image.open(os.path.join(REN, name + ".png")).convert("RGB")
        k = im.width / 1080
        h = int(608 * k)
        cy = int((1 - py) * im.height)
        y0 = max(0, min(im.height - h, cy - h // 2))
        th = im.crop((0, y0, im.width, y0 + h)).resize((320, 180), Image.LANCZOS)
        d = ImageDraw.Draw(th)
        f = ImageFont.truetype(FONT, 15)
        d.rectangle((6, 6, 16 + d.textlength(lab, font=f), 26), fill=(0, 0, 0))
        d.text((11, 8), lab, font=f, fill=(255, 255, 255))
        with open(os.path.join(OUT, name + ".png"), "wb") as fh:
            fh.write(small_png(th))
    # presets sheet
    W, H = 360, 640
    f = ImageFont.truetype(FONT, 22)
    s = Image.new("RGB", (4 * W + 80, H + 70), (18, 18, 20))
    d = ImageDraw.Draw(s)
    for i, (name, _, _) in enumerate(PRESETS):
        x = 16 + i * (W + 16)
        s.paste(Image.open(os.path.join(REN, name + ".png")).convert("RGB").resize((W, H), Image.LANCZOS), (x, 16))
        d.text((x, H + 28), name, font=f, fill=(235, 235, 235))
    s.save(os.path.join(DOCS, "Giniroisenkou_Title_Sliding_presets.png"), optimize=True)
    # animation strip
    frames = sorted(glob.glob(os.path.join(REN, "anim_*.png")), key=lambda p: int(re.findall(r"\d+", os.path.basename(p))[0]))
    if frames:
        cw, ch = 540, 200
        rows = (len(frames) + 1) // 2
        s = Image.new("RGB", (2 * cw + 48, rows * (ch + 44) + 16), (18, 18, 20))
        d = ImageDraw.Draw(s)
        f = ImageFont.truetype(FONT, 19)
        for i, p in enumerate(frames):
            im = Image.open(p).convert("RGB")
            cy = int((1 - 0.30) * im.height)
            im = im.crop((0, cy - int(300 * im.width / 1080), im.width, cy + int(100 * im.width / 1080))).resize((cw, ch), Image.LANCZOS)
            x, y = 16 + (i % 2) * (cw + 16), 16 + (i // 2) * (ch + 44)
            s.paste(im, (x, y))
            d.text((x, y + ch + 8), "frame " + re.findall(r"\d+", os.path.basename(p))[0], font=f, fill=(220, 220, 220))
        s.save(os.path.join(DOCS, "Giniroisenkou_Title_Sliding_animation.png"), optimize=True)


if __name__ == "__main__":
    main()
