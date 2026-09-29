#!/usr/bin/env python3
"""
thumbs.py - 320x180 Effects-panel thumbnails (Resolve shows <name>.png beside <name>.setting)
and per-platform preview strips for the README.
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Giniroisenkou_SafeZones_gen as G
import Giniroisenkou_SafeZones_preview as PV

BRANDS = [  # stem, platform label, brand icon, colour(s), glyph under the logo
    ("SafeZones_InstagramReel", "Instagram Reel", "instagram", ("#F58529", "#DD2A7B", "#8134AF"), "clapperboard"),
    ("SafeZones_InstagramStory", "Instagram Story", "instagram", ("#FEDA75", "#D62976", "#4F5BD5"), "circle-dashed"),
    ("SafeZones_TikTok", "TikTok", "tiktok", ("#25F4EE", "#000000", "#FE2C55"), "music"),
    ("SafeZones_YouTubeShorts", "YouTube Shorts", "youtubeshorts", ("#FF0033", "#CC0029", "#8A001C"), "zap"),
    ("SafeZones_FacebookReel", "Facebook Reel", "facebook", ("#0866FF", "#0A55D6", "#0A3FA8"), "clapperboard"),
    ("SafeZones_FacebookStory", "Facebook Story", "facebook", ("#4FA3FF", "#0866FF", "#0A3FA8"), "circle-dashed"),
    ("SafeZones_LinkedIn", "LinkedIn Video", "linkedin", ("#0A66C2", "#004182", "#00264D"), "briefcase-business"),
    ("SafeZones_Insta360", "Insta360", "insta360", ("#FFD400", "#3A3A3A", "#111111"), "camera"),
]


def phone(d, x, y, w, h, fill="#111"):
    d.rect(x, y, w, h, fill, r=w * .16, stroke="#ffffff", sw=3, extra='opacity=".95"')


def thumb_svg(label, brand, cols, glyph):
    d = G.Doc(320, 180)
    g = d.gid("tg")
    d.defs.append(f'<linearGradient id="{g}" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="{cols[0]}"/>'
                  f'<stop offset=".5" stop-color="{cols[1]}"/><stop offset="1" stop-color="{cols[2]}"/></linearGradient>')
    d.add(f'<rect width="320" height="180" fill="url(#{g})"/>')
    # little phone with the danger zones
    px, py, pw, ph = 214, 16, 84, 148
    d.rect(px, py, pw, ph, "#0b0b0b", r=14, stroke="#fff", sw=3)
    d.rect(px + 6, py + 8, pw - 12, 16, "#FF3B30", r=4, op=.75)
    d.rect(px + pw - 22, py + 62, 14, 58, "#FF3B30", r=4, op=.75)
    d.rect(px + 6, py + ph - 34, pw - 32, 26, "#FF3B30", r=4, op=.75)
    d.rect(px + 8, py + 28, pw - 34, ph - 66, "none", r=4, stroke="#34C759", sw=2.5, dash="6 4")
    d.brand(brand, 60, 62, 64, "#111111" if brand == "insta360" else "#FFFFFF")
    d.icon(glyph, 120, 62, 40, "#FFFFFF", 2.2)
    d.text(22, 128, label, 26, "#FFFFFF", 700, extra='filter="url(#shs)"')
    d.text(22, 158, "SafeZones", 18, "#FFFFFF", 500, op=.85)
    return d.svg()


def main_svg():
    d = G.Doc(320, 180)
    d.add('<rect width="320" height="180" fill="#101014"/>')
    for i, (_, _, brand, cols, _) in enumerate(BRANDS):
        cx = 30 + i * 37
        d.circle(cx, 46, 16, cols[0] if brand == "insta360" else cols[1])
        d.brand(brand, cx, 46, 18, "#111111" if brand == "insta360" else "#FFFFFF")
    d.text(20, 108, "SafeZones", 36, "#FFFFFF", 900)
    d.text(20, 146, "phone-screen GUI preview", 20, "#BBBBBB", 500)
    d.rect(262, 88, 40, 72, "#000", r=8, stroke="#fff", sw=2.5)
    d.rect(266, 92, 32, 8, "#FF3B30", r=2, op=.8)
    d.rect(266, 146, 32, 10, "#FF3B30", r=2, op=.8)
    return d.svg()


def write_thumbs(build):
    G.render(main_svg(), os.path.join(build, "SafeZones.png"))
    for stem, label, brand, cols, glyph in BRANDS:
        G.render(thumb_svg(label, brand, cols, glyph), os.path.join(build, stem + ".png"))


def strips(build, docs):
    table = json.load(open(os.path.join(build, "slots.json")))
    frame = PV.test_frame()
    F = PV.F
    for pi, (stem, label, *_rest) in enumerate(BRANDS):
        sts = [s for s in table["states"] if s["platform"] == pi]
        tw_, th, pad = 324, 576, 18
        im = Image.new("RGB", (pad + 4 * (tw_ + pad), 90 + th + pad), (18, 18, 20))
        d = ImageDraw.Draw(im)
        d.text((pad, 26), f"{label} - the four views", font=F(34, True), fill=(240, 240, 240))
        for st in sts:
            x = pad + st["view"] * (tw_ + pad)
            d.text((x, 66), table["views"][st["view"]], font=F(20, True), fill=(190, 190, 195))
            c = PV.compose(build, st, "dark", frame, guides=(st["view"] == 0)).convert("RGB")
            im.paste(c.resize((tw_, th), Image.LANCZOS), (x, 90))
        im.save(os.path.join(docs, f"Giniroisenkou_{stem}_views.png"), optimize=True)


def thumb_sheet(build, out):
    names = ["SafeZones"] + [b[0] for b in BRANDS]
    cols = 3
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 330 + 10, rows * 190 + 10), (40, 40, 40))
    for i, n in enumerate(names):
        sheet.paste(Image.open(os.path.join(build, n + ".png")).convert("RGB"), (10 + (i % cols) * 330, 10 + (i // cols) * 190))
    sheet.save(out, optimize=True)


if __name__ == "__main__":
    b = sys.argv[1] if len(sys.argv) > 1 else os.path.join(G.HERE, "..", "build")
    dd = sys.argv[2] if len(sys.argv) > 2 else os.path.join(G.HERE, "..", "docs")
    os.makedirs(dd, exist_ok=True)
    write_thumbs(b)
    strips(b, dd)
