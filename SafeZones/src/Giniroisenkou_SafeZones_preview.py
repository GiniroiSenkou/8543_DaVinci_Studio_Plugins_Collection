#!/usr/bin/env python3
"""
Giniroisenkou_SafeZones_preview.py - composites a synthetic test frame through every SafeZones state exactly the way
the Fusion macro does (video scaled into the slot, GUI on top, optional guides), and writes
docs/ previews + Resolve Effects-panel thumbnails. No personal footage is used.
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.environ.get("SZ_TOOLS", os.path.join(HERE, "..", "_tools"))
FONTDIR = os.path.join(TOOLS, "fonts")
W, H = 1080, 1920


def F(size, bold=False):
    return ImageFont.truetype(os.path.join(FONTDIR, "Roboto-Bold.ttf" if bold else "Roboto-Regular.ttf"), size)


def test_frame(w=W, h=H):
    """Colourful 9:16 test card: gradient sky, subject, horizon, text blocks near every edge."""
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        t = y / h
        r = int(40 + 180 * t)
        g = int(120 + 60 * (1 - t))
        b = int(210 - 90 * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    d = ImageDraw.Draw(im)
    d.ellipse((w * .5 - 330, h * .62 - 330, w * .5 + 330, h * .62 + 330), fill=(255, 190, 90))  # sun
    d.polygon([(0, h * .72), (w * .3, h * .6), (w * .55, h * .7), (w * .8, h * .56), (w, h * .66), (w, h), (0, h)],
              fill=(28, 60, 72))
    # subject: simple person silhouette
    cx, cy = w * .5, h * .47
    d.ellipse((cx - 120, cy - 330, cx + 120, cy - 90), fill=(250, 238, 225))
    d.rounded_rectangle((cx - 230, cy - 60, cx + 230, cy + 520), 180, fill=(236, 72, 99))
    d.rectangle((0, 0, w - 1, h - 1), outline=(255, 255, 255), width=6)
    for gy in range(0, h, 240):
        d.line((0, gy, w, gy), fill=(255, 255, 255), width=1)
    tb = lambda x, y, s, a="la": d.text((x, y), s, font=F(64, True), fill=(255, 255, 255), anchor=a,
                                       stroke_width=5, stroke_fill=(0, 0, 0))
    tb(w / 2, 90, "TOP TEXT", "ma")
    tb(w / 2, h * .32, "HOOK TEXT", "mm")
    tb(w - 30, h * .62, "RIGHT", "rm")
    tb(30, h * .82, "BOTTOM TEXT", "lm")
    tb(w / 2, h - 60, "VERY BOTTOM", "ms")
    return im


def cut_to_shape(frame, aspect):
    """Upload shape: centre-cut the timeline image to `aspect` (w/h). Nothing is squeezed."""
    if aspect is None:
        return frame
    fw, fh = frame.size
    if aspect < fw / fh:
        cw, ch = round(fh * aspect), fh
    else:
        cw, ch = fw, round(fw / aspect)
    x, y = (fw - cw) // 2, (fh - ch) // 2
    return frame.crop((x, y, x + cw, y + ch))


def place(frame, slot, fit, zoom=1.0, px=0.0, py=0.0, upload=None):
    """Mirror of the macro. fit: fill = cover the slot, fit = whole video inside, width = match slot width."""
    up = cut_to_shape(frame, upload)
    uw_px, uh_px = up.size
    ca = uw_px / uh_px
    # upload fitted into the phone frame (normalised units of the 1080x1920 frame)
    uw, uh = (1.0, (W / H) / ca) if ca >= W / H else (ca / (W / H), 1.0)
    x, y, w, h = slot
    sw, sh = w / W, h / H
    if fit == "fill":
        s = max(sw / uw, sh / uh)
    elif fit == "fit":
        s = min(sw / uw, sh / uh)
    else:
        s = sw / uw
    s *= zoom
    pw, ph = uw * s * W, uh * s * H
    ox = x + (w - pw) / 2 + px * max(0, (pw - w) / 2)
    oy = y + (h - ph) / 2 - py * max(0, (ph - h) / 2)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    canvas.paste(up.resize((max(1, round(pw)), max(1, round(ph))), Image.LANCZOS).convert("RGBA"),
                 (round(ox), round(oy)))
    return canvas


def compose(build, st, theme, frame, guides=False, fit=None, upload=None):
    img = place(frame, st["slot"], fit or st["fit"], upload=upload)
    gui = Image.open(os.path.join(build, st["gui"][theme])).convert("RGBA")
    img.alpha_composite(gui)
    if guides:
        img.alpha_composite(Image.open(os.path.join(build, st["guide"])).convert("RGBA"))
    return img


def contact(build, table, frame, theme, guides, out, scale=.25):
    P, V = len(table["platforms"]), len(table["views"])
    tw_, th = int(W * scale), int(H * scale)
    pad, lab_h, top = 24, 46, 90
    sheet = Image.new("RGB", (pad + V * (tw_ + pad) + 260, top + P * (th + pad + lab_h)), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 30), f"SafeZones - every platform x view ({theme} theme{', guides on' if guides else ''})",
           font=F(34, True), fill=(240, 240, 240))
    for st in table["states"]:
        pi, vi = st["platform"], st["view"]
        x = 260 + vi * (tw_ + pad)
        y = top + pi * (th + pad + lab_h)
        im = compose(build, st, theme, frame, guides).convert("RGB").resize((tw_, th), Image.LANCZOS)
        sheet.paste(im, (x, y + lab_h))
        if pi == 0:
            pass
        d.text((x, y + 8), table["views"][vi], font=F(22, True), fill=(200, 200, 205))
        if vi == 0:
            d.text((pad, y + lab_h + th / 2), table["platforms"][pi].replace(" ", "\n", 1), font=F(28, True),
                   fill=(240, 240, 240), anchor="lm")
    sheet.save(out, optimize=True)
    return out


if __name__ == "__main__":
    build = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "build")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "docs")
    os.makedirs(out, exist_ok=True)
    table = json.load(open(os.path.join(build, "slots.json")))
    frame = test_frame()
    frame.save(os.path.join(out, "test_frame.png"))
    contact(build, table, frame, "dark", False, os.path.join(out, "SafeZones_all_dark.png"))
    contact(build, table, frame, "light", False, os.path.join(out, "SafeZones_all_light.png"))
    contact(build, table, frame, "dark", True, os.path.join(out, "SafeZones_all_guides.png"))
    print("previews written to", out)
