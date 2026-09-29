#!/usr/bin/env python3
"""
Builds the Effects-panel thumbnails (320x180 PNG next to every .setting) and the
docs contact sheet from stills rendered IN RESOLVE.

Workflow used for this pack:
  1. python Giniroisenkou_Trends_sampleclip.py   -> sample_clip.mp4 (CC0 cat photo + moving light)
  2. put the clip on a 1280x720 test timeline, apply each effect with the settings in
     FX.preview (see Giniroisenkou_Trends_gen.py) and export the frame as
     renders/r_<EffectName>.png  (Resolve: Project > Export current frame as still)
  3. python Giniroisenkou_Trends_thumbs.py renders/

Needs Pillow and the DejaVu Sans font (any bold TTF works: set FONT below).
"""
import os, re, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import importlib.util
spec = importlib.util.spec_from_file_location("gen", os.path.join(HERE, "Giniroisenkou_Trends_gen.py"))
gen = importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
OUT = os.path.join(ROOT, "build", "Edit", "Effects", "Trends")
DOCS = os.path.join(ROOT, "docs")

CAT_COLOURS = {"Motion": (255, 94, 58), "Glitch": (0, 214, 201), "Retro": (255, 184, 0),
               "Look": (255, 82, 160), "Mirror": (135, 110, 255), "Distort": (80, 170, 255),
               "Text": (255, 255, 255)}
CAT_ORDER = ["Motion", "Glitch", "Retro", "Look", "Mirror", "Distort", "Text"]

SPECIAL = {"RGBSplit": "RGB Split", "VHS": "VHS", "Filter2016": "Filter 2016", "TealOrange": "Teal & Orange"}

def display(short):
    return SPECIAL.get(short) or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", short)


def card(fx, img, W, H, big=False):
    im = img.convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((l, t, l + W, t + H)).convert("RGBA")
    # bottom gradient for the label
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    g0 = int(H * 0.45)
    for yy in range(g0, H):
        a = int(210 * ((yy - g0) / (H - g0)) ** 1.3)
        gd.line([(0, yy), (W, yy)], fill=(8, 8, 12, a))
    im = Image.alpha_composite(im, grad)
    d = ImageDraw.Draw(im)
    k = W / 320
    f1 = ImageFont.truetype(FONT, int(25 * k))
    f2 = ImageFont.truetype(FONT_REG, int(12 * k))
    col = CAT_COLOURS[fx.category]
    x0, y0 = int(12 * k), H - int(52 * k)
    d.text((x0, y0), display(fx.short), font=f1, fill=(255, 255, 255, 255),
           stroke_width=max(1, int(1 * k)), stroke_fill=(0, 0, 0, 160))
    # category chip + pack name
    chip = fx.category.upper()
    fw = d.textlength(chip, font=f2)
    cy = H - int(20 * k)
    d.rounded_rectangle((x0, cy - int(1 * k), x0 + fw + int(10 * k), cy + int(14 * k)), radius=int(4 * k), fill=col + (235,))
    d.text((x0 + int(5 * k), cy), chip, font=f2, fill=(10, 10, 14, 255))
    d.text((x0 + fw + int(16 * k), cy), "Trends", font=f2, fill=(230, 230, 235, 230))
    return im.convert("RGB")


def main(render_dir):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DOCS, exist_ok=True)
    cards = {}
    for fx in gen.EFFECTS:
        src = os.path.join(render_dir, f"r_{fx.name}.png")
        img = Image.open(src)
        # Resolve 21.1 leaves Effects-panel icons blank when the PNG is bigger than ~48 KB,
        # so thumbnails are saved as 256-colour PNGs (~20-30 KB)
        rgb = card(fx, img, 320, 180)
        dst = os.path.join(OUT, fx.name + ".png")
        for colours, dither in [(256, Image.Dither.FLOYDSTEINBERG), (256, Image.Dither.NONE), (128, Image.Dither.NONE), (64, Image.Dither.NONE)]:
            rgb.quantize(colours, method=Image.Quantize.MEDIANCUT, dither=dither).save(dst, optimize=True)
            if os.path.getsize(dst) < 40000:
                break
        cards[fx.name] = card(fx, img, 480, 270, big=True)
    # contact sheet grouped by category
    fxs = sorted(gen.EFFECTS, key=lambda f: (CAT_ORDER.index(f.category), f.short))
    cols, W, H, pad = 4, 480, 270, 12
    rows = (len(fxs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * W + (cols + 1) * pad, rows * H + (rows + 1) * pad), (24, 24, 28))
    for i, fx in enumerate(fxs):
        x, y = pad + (i % cols) * (W + pad), pad + (i // cols) * (H + pad)
        sheet.paste(cards[fx.name], (x, y))
    sheet.save(os.path.join(DOCS, "Giniroisenkou_Trends_thumbnails.png"), optimize=True)
    # small 2x4 teaser for the collection README
    pick = ["Trends_EchoTrails", "Trends_GlitchSlices", "Trends_NeonEdges", "Trends_Kaleidoscope",
            "Trends_VHS", "Trends_Duotone", "Trends_LightLeak", "Trends_Halftone"]
    W2, H2 = 320, 180
    teaser = Image.new("RGB", (4 * W2 + 5 * 8, 2 * H2 + 3 * 8), (24, 24, 28))
    for i, n in enumerate(pick):
        teaser.paste(cards[n].resize((W2, H2), Image.LANCZOS), (8 + (i % 4) * (W2 + 8), 8 + (i // 4) * (H2 + 8)))
    teaser.save(os.path.join(DOCS, "Giniroisenkou_Trends_teaser.png"), optimize=True)
    print("thumbnails:", len(gen.EFFECTS))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "renders"))
