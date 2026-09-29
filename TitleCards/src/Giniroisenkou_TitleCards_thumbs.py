#!/usr/bin/env python3
"""
Builds the Effects-panel thumbnails (320x180 PNG next to every .setting) and the
docs contact sheet + teaser from stills rendered IN RESOLVE.

Workflow used for this pack:
  1. put a clip on a test timeline and apply each effect (Background = Black Card,
     or White Card for Ink Burst / Outline Giant, whose shapes are black)
  2. park on a frame after the In Length and export it as renders/r_<EffectName>.png
     (Color page > right-click the viewer > Grab Still / Export, or the scripting call
     project.ExportCurrentFrameAsStill(path) - that is how this pack's set was made)
  3. python Giniroisenkou_TitleCards_thumbs.py renders/

A portrait (vertical-timeline) export is cropped to its centred 16:9 band, which is
where a 16:9 clip's effect output sits. Needs Pillow and the DejaVu Sans font.
"""
import os, re, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import importlib.util
spec = importlib.util.spec_from_file_location("gen", os.path.join(HERE, "Giniroisenkou_TitleCards_gen.py"))
gen = importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
OUT = os.path.join(ROOT, "build", "Edit", "Effects", "TitleCards")
DOCS = os.path.join(ROOT, "docs")

CAT_COLOURS = {"Episode Card": (255, 184, 0), "Kinetic": (0, 214, 201)}
CAT_ORDER = ["Episode Card", "Kinetic"]
SPECIAL = {"RGBSplit": "RGB Split"}


def display(short):
    return SPECIAL.get(short) or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", short)


def band(img):
    im = img.convert("RGB")
    if im.height > im.width:                      # vertical export: keep the 16:9 picture
        h = round(im.width * 9 / 16)
        t = (im.height - h) // 2
        im = im.crop((0, t, im.width, t + h))
    return im


def card(fx, img, W, H, number):
    im = band(img)
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((l, t, l + W, t + H)).convert("RGBA")
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    g0 = int(H * 0.62)
    for yy in range(g0, H):
        gd.line([(0, yy), (W, yy)], fill=(8, 8, 12, int(200 * ((yy - g0) / (H - g0)) ** 1.2)))
    im = Image.alpha_composite(im, grad)
    d = ImageDraw.Draw(im)
    k = W / 320
    f1 = ImageFont.truetype(FONT, int(19 * k))
    f2 = ImageFont.truetype(FONT_REG, int(11 * k))
    col = CAT_COLOURS[fx.category]
    x0 = int(10 * k)
    d.text((x0, H - int(44 * k)), f"#{number:02d}  {display(fx.short)}", font=f1, fill=(255, 255, 255, 255),
           stroke_width=max(1, int(1 * k)), stroke_fill=(0, 0, 0, 180))
    chip = fx.category.upper()
    fw = d.textlength(chip, font=f2)
    cy = H - int(18 * k)
    d.rounded_rectangle((x0, cy - int(1 * k), x0 + fw + int(10 * k), cy + int(13 * k)), radius=int(4 * k), fill=col + (235,))
    d.text((x0 + int(5 * k), cy), chip, font=f2, fill=(10, 10, 14, 255))
    d.text((x0 + fw + int(16 * k), cy), "TitleCards", font=f2, fill=(230, 230, 235, 230))
    return im.convert("RGB")


def main(render_dir):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DOCS, exist_ok=True)
    cards = {}
    for n, fx in enumerate(gen.EFFECTS, 1):
        img = Image.open(os.path.join(render_dir, f"r_{fx.name}.png"))
        # Resolve 21.1 leaves Effects-panel icons blank above ~48 KB -> 256-colour PNGs
        rgb = card(fx, img, 320, 180, n)
        dst = os.path.join(OUT, fx.name + ".png")
        for colours, dither in [(256, Image.Dither.FLOYDSTEINBERG), (256, Image.Dither.NONE), (128, Image.Dither.NONE), (64, Image.Dither.NONE)]:
            rgb.quantize(colours, method=Image.Quantize.MEDIANCUT, dither=dither).save(dst, optimize=True)
            if os.path.getsize(dst) < 40000:
                break
        cards[fx.name] = card(fx, img, 480, 270, n)
    cols, W, H, pad = 4, 480, 270, 12
    rows = (len(gen.EFFECTS) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * W + (cols + 1) * pad, rows * H + (rows + 1) * pad), (24, 24, 28))
    for i, fx in enumerate(gen.EFFECTS):
        sheet.paste(cards[fx.name], (pad + (i % cols) * (W + pad), pad + (i // cols) * (H + pad)))
    sheet.save(os.path.join(DOCS, "Giniroisenkou_TitleCards_thumbnails.png"), optimize=True)
    pick = ["TitleCards_StackCut", "TitleCards_OverflowNumber", "TitleCards_Spine", "TitleCards_DiagonalBand",
            "TitleCards_CircleStamp", "TitleCards_EchoColumns", "TitleCards_RGBSplit", "TitleCards_InkBurst"]
    W2, H2 = 320, 180
    teaser = Image.new("RGB", (4 * W2 + 5 * 8, 2 * H2 + 3 * 8), (24, 24, 28))
    for i, n in enumerate(pick):
        teaser.paste(cards[n].resize((W2, H2), Image.LANCZOS), (8 + (i % 4) * (W2 + 8), 8 + (i // 4) * (H2 + 8)))
    teaser.save(os.path.join(DOCS, "Giniroisenkou_TitleCards_teaser.png"), optimize=True)
    print("thumbnails:", len(gen.EFFECTS))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "renders"))
