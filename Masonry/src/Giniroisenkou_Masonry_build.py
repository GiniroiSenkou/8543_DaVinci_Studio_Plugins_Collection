"""Giniroisenkou_Masonry_build.py - builds, checks and packages Masonry.

    python src/Giniroisenkou_Masonry_build.py

1. writes the macros (Giniroisenkou_Masonry_gen.py) to build/Edit/Effects/Masonry/
2. re-computes the macro maths in Python and checks every layout
   (cells inside the frame, equal gaps, the clip always covers its cell)
3. draws a 320x180 Effects-panel thumbnail beside every .setting
4. draws docs/Giniroisenkou_Masonry_layouts.png (cell numbers) and
   docs/Giniroisenkou_Masonry_thumbnails.png
5. packs Giniroisenkou_Masonry.drfx in the plugin folder (drag-install file)

Needs Python 3 with Pillow.
"""
import os
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Giniroisenkou_Masonry_gen as gen  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build", "Edit", "Effects", "Masonry")
DOCS = os.path.join(ROOT, "docs")
PALETTE = [(92, 124, 170), (176, 106, 88), (84, 146, 104), (184, 150, 74), (124, 104, 176),
           (150, 150, 158), (70, 150, 160), (170, 96, 140)]
BG, FG, DIM = (18, 18, 21), (236, 236, 240), (150, 150, 160)


def font(size, bold=False):
    for name in (("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
                 ("arialbd.ttf" if bold else "arial.ttf")):
        for d in ("/usr/share/fonts/truetype/dejavu", r"C:\Windows\Fonts", ""):
            try:
                return ImageFont.truetype(os.path.join(d, name), size)
            except OSError:
                pass
    return ImageFont.load_default()


# ---------------------------------------------------------------- maths twin
def geometry(layout, cell, out_w=1080, out_h=1920, spacing=30, src_aspect=16 / 9,
             zoom=1.0, pan_x=0.0, pan_y=0.0, scroll=0.0):
    """Same formulas as HIDDEN in the generator. Returns px values, y down."""
    ac = out_w / out_h
    a_s = ac if src_aspect is None else src_aspect
    rx, ry, rw, rh = gen.LAYOUTS[layout][2][cell - 1]
    sx = spacing / gen.DW
    sy = spacing / gen.DW * ac
    cx = sx + (rx / gen.DW) * (1 - sx)
    cy = sy + (ry / gen.DH) * (1 - sy)
    cw = (rw / gen.DW) * (1 - sx) - sx
    ch = (rh / gen.DH) * (1 - sy) - sy
    fh = ac / a_s
    sc = max(cw, ch / fh) * zoom
    scr = scroll / gen.DH
    nx = cx + cw / 2
    ny = 1 - (cy + ch / 2 - scr)            # Fusion: y up
    ox = pan_x * (sc - cw) / 2
    oy = pan_y * (sc * fh - ch) / 2
    pw = max(out_w * sc + 4, 2)
    ph = max(pw / a_s, 2)
    x_off = pw / 2 - (nx + ox) * out_w
    y_off = ph / 2 - (ny + oy) * out_h
    return dict(cell=(cx * out_w, cy * out_h, cw * out_w, ch * out_h),
                picture=(pw, ph), offset=(x_off, y_off), scale=sc)


def self_check():
    frames = [(1080, 1920), (1080, 1350), (2160, 3840), (1920, 1080)]
    aspects = [16 / 9, 9 / 16, None, 1.0]
    n = 0
    for li, (_, _, cells) in enumerate(gen.LAYOUTS):
        for fw, fh in frames:
            rects = []
            for ci in range(1, len(cells) + 1):
                for a in aspects:
                    g = geometry(li, ci, fw, fh, src_aspect=a)
                    x, y, w, h = g["cell"]
                    pw, ph = g["picture"]
                    xo, yo = g["offset"]
                    # picture placed on the frame (Crop: bottom-left origin)
                    left = -xo
                    right = pw - xo
                    bottom = -yo
                    top = ph - yo
                    cell_bottom = fh - (y + h)
                    assert left <= x + 0.5 and right >= x + w - 0.5, ("x cover", li, ci, fw, fh, a)
                    assert bottom <= cell_bottom + 0.5 and top >= cell_bottom + h - 0.5, ("y cover", li, ci, fw, fh, a)
                    n += 1
                rects.append(geometry(li, ci, fw, fh)["cell"])
            gap = 30 * fw / 1080
            if li != 3:                         # Scroll 12 is taller than the frame
                for x, y, w, h in rects:
                    assert x >= gap - 0.5 and y >= gap - 0.5, ("margin", li)
                    assert x + w <= fw - gap + 0.5 and y + h <= fh - gap + 0.5, ("margin", li)
            for i, (x1, y1, w1, h1) in enumerate(rects):     # no overlaps, gap kept
                for x2, y2, w2, h2 in rects[i + 1:]:
                    sep_x = max(x2 - (x1 + w1), x1 - (x2 + w2))
                    sep_y = max(y2 - (y1 + h1), y1 - (y2 + h2))
                    assert max(sep_x, sep_y) >= gap - 0.5, ("overlap", li)
    return n


# ----------------------------------------------------------------- drawing
def draw_layout(d, li, x0, y0, height, numbers=True, fsize=None):
    """Draw layout li as a 9:16 phone frame at (x0, y0) with the given height."""
    w = height * 9 / 16
    s = height / 1920
    d.rounded_rectangle([x0, y0, x0 + w, y0 + height], radius=max(2, int(height * 0.03)), fill=(8, 8, 10))
    cells = gen.LAYOUTS[li][2]
    f = font(fsize or max(8, int(height / 14)), True)
    for ci in range(1, len(cells) + 1):
        x, y, cw, ch = geometry(li, ci)["cell"]
        if y + ch > 1920:
            ch = max(0, 1920 - 1 - y)
        if y >= 1920 or ch <= 0:
            continue
        box = [x0 + x * s, y0 + y * s, x0 + (x + cw) * s, y0 + (y + ch) * s]
        d.rounded_rectangle(box, radius=max(1, int(28 * s)), fill=PALETTE[(ci - 1) % len(PALETTE)])
        if numbers:
            d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), str(ci), font=f, fill=FG, anchor="mm")
    return w


def thumbnail(name, li, title, subtitle):
    im = Image.new("RGB", (320, 180), BG)
    d = ImageDraw.Draw(im)
    draw_layout(d, li, 16, 12, 156)
    d.text((124, 40), title, font=font(22, True), fill=FG)
    y = 76
    for line in subtitle:
        d.text((124, y), line, font=font(14), fill=DIM)
        y += 20
    im.save(os.path.join(BUILD, name + ".png"))
    return im


def docs_layouts():
    n = len(gen.LAYOUTS)
    h, pad, top = 640, 40, 70
    w = int(h * 9 / 16)
    im = Image.new("RGB", (pad + n * (w + pad), top + h + 2 * pad + 40), BG)
    d = ImageDraw.Draw(im)
    d.text((pad, 22), "Masonry layouts - cell numbers", font=font(28, True), fill=FG)
    for li, (label, preset, cells) in enumerate(gen.LAYOUTS):
        x = pad + li * (w + pad)
        draw_layout(d, li, x, top, h, fsize=30)
        d.text((x, top + h + 18), label.split("  ")[0], font=font(22, True), fill=FG)
        d.text((x, top + h + 48), preset, font=font(16), fill=DIM)
    d.text((pad + 3 * (w + pad), top + h + 72), "(first screen shown; scroll for the rest)",
           font=font(14), fill=DIM)
    im.save(os.path.join(DOCS, "Giniroisenkou_Masonry_layouts.png"))


def main():
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(DOCS, exist_ok=True)
    for name, dflt in gen.effects():
        with open(os.path.join(BUILD, name + ".setting"), "w", encoding="utf-8", newline="\n") as f:
            f.write(gen.build(name, dflt))
    checks = self_check()

    thumbs = [thumbnail("Masonry", 0, "Masonry", ["all layouts", "pick Layout + Cell"])]
    for li, (label, preset, cells) in enumerate(gen.LAYOUTS):
        short = label.split("  ")[0]
        thumbs.append(thumbnail(preset, li, short, [label.split("  ")[1].strip("()"), f"{len(cells)} cells"]))
    sheet = Image.new("RGB", (3 * 320 + 4 * 12, 2 * 180 + 3 * 12), (40, 40, 44))
    for i, t in enumerate(thumbs):
        sheet.paste(t, (12 + (i % 3) * 332, 12 + (i // 3) * 192))
    sheet.save(os.path.join(DOCS, "Giniroisenkou_Masonry_thumbnails.png"))
    docs_layouts()

    drfx = os.path.join(ROOT, "Giniroisenkou_Masonry.drfx")
    with zipfile.ZipFile(drfx, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(BUILD)):
            z.write(os.path.join(BUILD, fn), "Edit/Effects/Masonry/" + fn)
    print(f"{checks} geometry checks passed; {len(thumbs)} effects -> {drfx}")


if __name__ == "__main__":
    main()
