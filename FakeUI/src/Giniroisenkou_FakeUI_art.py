"""FakeUI - draws every PNG from Giniroisenkou_FakeUI_layouts.py.

build/  static page art (photo holes transparent), slot-number overlays,
        320x180 Effects-panel thumbnails  -> packed into the .drfx
docs/   full mock-ups with sample pictures for the README

Drawn at 2x and downsampled for clean edges. Mock-up text uses the real fonts when
they are found (Windows fonts folder, or fonts/ for DM Serif Display), otherwise
DejaVu / Liberation stand-ins.
"""
import colorsys
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from Giniroisenkou_FakeUI_layouts import *  # noqa: F401,F403

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SS = 2
PFX = "FakeUI"                 # resource names inside Resolve
DOC = "Giniroisenkou_FakeUI"   # file names in docs/

FONT_DIRS = [os.path.join(ROOT, "fonts"), r"C:\Windows\Fonts",
             os.environ.get("FAKEUI_FONTS", ""), "/usr/share/fonts/truetype"]
FONT_FILES = {
    (UI, "Bold"): ["segoeuib.ttf", "dejavu/DejaVuSans-Bold.ttf"],
    (UI, "Regular"): ["segoeui.ttf", "dejavu/DejaVuSans.ttf"],
    (TNR, "Bold"): ["timesbd.ttf", "liberation/LiberationSerif-Bold.ttf"],
    (TNR, "Regular"): ["times.ttf", "liberation/LiberationSerif-Regular.ttf"],
    (GEO, "Regular"): ["georgia.ttf", "liberation/LiberationSerif-Regular.ttf"],
    (GEO, "Italic"): ["georgiai.ttf", "liberation/LiberationSerif-Italic.ttf"],
    (GEO, "Bold"): ["georgiab.ttf", "liberation/LiberationSerif-Bold.ttf"],
    (ARIAL, "Bold"): ["arialbd.ttf", "liberation/LiberationSans-Bold.ttf"],
    (ARIAL, "Regular"): ["arial.ttf", "liberation/LiberationSans-Regular.ttf"],
    (DIDONE, "Regular"): ["DMSerifDisplay-Regular.ttf", "liberation/LiberationSerif-Regular.ttf"],
    (DIDONE, "Italic"): ["DMSerifDisplay-Italic.ttf", "liberation/LiberationSerif-Italic.ttf"],
}
_fcache = {}


def font(fs, px):
    key = (tuple(fs), int(px))
    if key not in _fcache:
        for name in FONT_FILES[tuple(fs)]:
            for d in FONT_DIRS:
                p = os.path.join(d, name) if d else ""
                if p and os.path.exists(p):
                    _fcache[key] = ImageFont.truetype(p, int(px))
                    break
            if key in _fcache:
                break
    return _fcache[key]


def hexc(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def s(*v):
    return [x * SS for x in v]


def finish(img):
    return img.resize((W, H), Image.LANCZOS)


def punch(img, slots):
    mask = Image.new("L", img.size, 255)
    d = ImageDraw.Draw(mask)
    for _, _, (x, y, w, h), shape in slots:
        (d.ellipse if shape == "circle" else d.rectangle)(s(x, y, x + w - 1, y + h - 1), fill=0)
    img.putalpha(Image.fromarray(np.minimum(np.array(img.getchannel("A")), np.array(mask))))
    return img


# ------------------------------------------------------------------ icons ---
def rrect(d, box, r, **kw):
    d.rounded_rectangle(s(*box), radius=r * SS, **kw)


def icon_plus_square(d, cx, cy, c, size=44, sw=4):
    h = size / 2
    rrect(d, (cx - h, cy - h, cx + h, cy + h), 11, outline=c, width=sw * SS)
    d.line(s(cx - 11, cy, cx + 11, cy), fill=c, width=sw * SS)
    d.line(s(cx, cy - 11, cx, cy + 11), fill=c, width=sw * SS)


def icon_menu(d, cx, cy, c):
    for dy in (-14, 0, 14):
        d.line(s(cx - 20, cy + dy, cx + 20, cy + dy), fill=c, width=4 * SS)


def icon_play_square(d, cx, cy, c, size=44):
    h = size / 2
    rrect(d, (cx - h, cy - h, cx + h, cy + h), 11, outline=c, width=4 * SS)
    d.polygon(s(cx - 7, cy - 10, cx - 7, cy + 10, cx + 11, cy), fill=c)


def icon_grid(d, cx, cy, c, size=40):
    h = size / 2
    rrect(d, (cx - h, cy - h, cx + h, cy + h), 6, outline=c, width=4 * SS)
    for k in (-1, 1):
        o = k * size / 6
        d.line(s(cx + o, cy - h, cx + o, cy + h), fill=c, width=3 * SS)
        d.line(s(cx - h, cy + o, cx + h, cy + o), fill=c, width=3 * SS)


def icon_person(d, cx, cy, c, size=44, framed=True):
    h = size / 2
    if framed:
        rrect(d, (cx - h, cy - h, cx + h, cy + h), 11, outline=c, width=4 * SS)
        d.ellipse(s(cx - 7, cy - 12, cx + 7, cy + 2), outline=c, width=3 * SS)
        d.arc(s(cx - 15, cy + 5, cx + 15, cy + 31), 200, 340, fill=c, width=3 * SS)
    else:
        d.ellipse(s(cx - h, cy - h, cx + h, cy + h), outline=c, width=4 * SS)
        d.ellipse(s(cx - 8, cy - 13, cx + 8, cy + 3), fill=c)
        d.chord(s(cx - 16, cy + 6, cx + 16, cy + 34), 180, 360, fill=c)


def icon_person_plus(d, cx, cy, c):
    d.ellipse(s(cx - 16, cy - 16, cx - 2, cy - 2), outline=c, width=3 * SS)
    d.arc(s(cx - 24, cy + 2, cx + 6, cy + 30), 180, 360, fill=c, width=3 * SS)
    d.line(s(cx + 10, cy - 6, cx + 24, cy - 6), fill=c, width=3 * SS)
    d.line(s(cx + 17, cy - 13, cx + 17, cy + 1), fill=c, width=3 * SS)


def icon_home(d, cx, cy, c):
    d.line(s(cx - 20, cy - 2, cx, cy - 20, cx + 20, cy - 2), fill=c, width=4 * SS, joint="curve")
    d.line(s(cx - 16, cy - 5, cx - 16, cy + 20, cx + 16, cy + 20, cx + 16, cy - 5), fill=c, width=4 * SS, joint="curve")


def icon_search(d, cx, cy, c):
    d.ellipse(s(cx - 18, cy - 18, cx + 8, cy + 8), outline=c, width=4 * SS)
    d.line(s(cx + 6, cy + 6, cx + 20, cy + 20), fill=c, width=5 * SS)


def icon_link(img, x, y, c):
    t = Image.new("RGBA", (48 * SS, 48 * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    d.rounded_rectangle(s(4, 16, 26, 32), radius=8 * SS, outline=c, width=3 * SS)
    d.rounded_rectangle(s(22, 16, 44, 32), radius=8 * SS, outline=c, width=3 * SS)
    t = t.rotate(-45, resample=Image.BICUBIC)
    img.alpha_composite(t, (x * SS - 8 * SS, y * SS - 8 * SS))


def status_bar(d, fg):
    x = 880
    for i, bh in enumerate((10, 16, 22, 28)):
        d.rounded_rectangle(s(x + i * 10, 62 - bh, x + i * 10 + 6, 62), radius=2 * SS, fill=fg)
    cx, cy = 944, 64
    for r in (8, 17, 26):
        d.arc(s(cx - r, cy - r, cx + r, cy + r), 225, 315, fill=fg, width=4 * SS)
    d.rounded_rectangle(s(978, 38, 1024, 62), radius=6 * SS, outline=fg, width=3 * SS)
    d.rounded_rectangle(s(982, 42, 1014, 58), radius=3 * SS, fill=fg)
    d.rounded_rectangle(s(1026, 46, 1030, 54), radius=1 * SS, fill=fg)


# ----------------------------------------------------------- profile art ---
def profile_nav(d, t):
    fg, bg = hexc(t["fg"]), hexc(t["bg"])
    d.rectangle(s(0, NAV_Y, W, H), fill=bg)
    d.rectangle(s(0, NAV_Y, W, NAV_Y + 1), fill=hexc(t["line"]))
    ny = 1834
    icon_home(d, 108, ny, fg)
    icon_search(d, 324, ny, fg)
    icon_plus_square(d, 540, ny, fg)
    icon_play_square(d, 756, ny, fg)
    icon_person(d, 972, ny, fg, size=52, framed=False)
    rrect(d, (400, 1896, 680, 1906), 5, fill=fg)


def profile_art(theme, button):
    t = PROFILE_THEMES[theme]
    fg, muted = hexc(t["fg"]), hexc(t["muted"])
    img = Image.new("RGBA", (W * SS, H * SS), hexc(t["bg"]))
    d = ImageDraw.Draw(img)
    status_bar(d, fg)
    icon_plus_square(d, 900, 142, fg)
    icon_menu(d, 1000, 142, fg)
    icon_link(img, 48, 686, hexc(t["link"]))
    rrect(d, (48, 760, 480, 836), 16, fill=hexc(t["primary"]) if button == 0 else hexc(t["btn"]))
    rrect(d, (494, 760, 926, 836), 16, fill=hexc(t["btn"]))
    rrect(d, (940, 760, 1032, 836), 16, fill=hexc(t["btn"]))
    icon_person_plus(d, 986, 798, fg)
    for cx in HL_X:
        r = HL_D / 2 + 8
        d.ellipse(s(cx - r, HL_Y - r, cx + r, HL_Y + r), outline=hexc(t["ring"]), width=3 * SS)
    for cx, ic in ((180, icon_grid), (540, icon_play_square), (900, icon_person)):
        ic(d, cx, 1150, fg if cx == 180 else muted)
    d.rectangle(s(0, 1196, 360, 1199), fill=fg)
    punch(img, PROFILE_SLOTS)
    profile_nav(ImageDraw.Draw(img), t)   # nav bar covers the grid overflow
    return finish(img)


# ------------------------------------------------------------- news art ---
def paper(style_hex, grain, vignette, seed):
    base = np.array(hexc(style_hex)[:3], dtype=np.float32)
    rng = np.random.default_rng(seed)
    arr = np.ones((H * SS, W * SS, 3), np.float32) * base
    if grain:
        n = rng.normal(0, 1, (H * SS // 4, W * SS // 4)).astype(np.float32)
        n = np.array(Image.fromarray(n).resize((W * SS, H * SS), Image.BICUBIC))
        arr += (n * 0.6 + rng.normal(0, 0.6, (H * SS, W * SS)).astype(np.float32))[..., None] * grain * 0.5
    if vignette:
        yy, xx = np.mgrid[0:H * SS, 0:W * SS].astype(np.float32)
        r = np.sqrt(((xx / (W * SS)) - 0.5) ** 2 * 1.6 + ((yy / (H * SS)) - 0.5) ** 2)
        arr *= (1 - vignette * np.clip(r - 0.25, 0, 1) ** 1.5)[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")


def news_art(style):
    st = NEWS_STYLES[style]
    img = paper(st["paper"], st["grain"], st["vignette"], 7 + style)
    d = ImageDraw.Draw(img)
    col = {"ink": hexc(st["ink"]), "accent": hexc(st["accent"])}
    for x0, y0, x1, y1, role in NEWS_RULES:
        d.rectangle(s(x0, y0, x1, y1), fill=col[role])
    holes = [sl for sl in NEWS_SLOTS if sl[0] != "logo"]
    for _, _, (x, y, w, h), _ in holes:
        d.rectangle(s(x - 2, y - 2, x + w + 1, y + h + 1), outline=col["ink"], width=1 * SS)
    punch(img, holes)
    return finish(img)


# --------------------------------------------------------- magazine art ---
def mag_barcode():
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = BARCODE
    d.rectangle(s(x0, y0, x1, y1), fill=(255, 255, 255, 255))
    rnd = random.Random(4)
    x = x0 + 12
    while x < x1 - 14:
        w = rnd.choice((1.5, 1.5, 3, 4.5))
        d.rectangle(s(x, y0 + 10, x + w, y1 - 26), fill=(0, 0, 0, 255))
        x += w + rnd.choice((1.5, 3, 3, 4.5))
    d.text(s((x0 + x1) / 2, y1 - 13), "9 771234 567003", font=font((ARIAL, "Regular"), 13 * SS),
           fill=(0, 0, 0, 255), anchor="mm")
    return finish(img)


def mag_shade():
    """dark gradients top and bottom, helps the masthead and cover lines read"""
    y = np.linspace(0, 1, H)[:, None]
    top = np.clip(1 - y / 0.30, 0, 1) ** 1.6 * 0.60
    bot = np.clip((y - 0.62) / 0.38, 0, 1) ** 1.4 * 0.70
    a = np.repeat(np.maximum(top, bot) * 255, W, axis=1).astype(np.uint8)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.putalpha(Image.fromarray(a))
    return img


# -------------------------------------------------------- placeholders ---
def placeholders(slots, skip=()):
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, (key, label, (x, y, w, h), shape) in enumerate(slots):
        if key in skip:
            continue
        r, g, b = [int(v * 255) for v in colorsys.hsv_to_rgb((i * 0.137) % 1, 0.55, 0.85)]
        d.rectangle(s(x, y, x + w, y + h), fill=(r, g, b, 255))
        for k in range(-h, w, 28):
            d.line(s(x + k, y + h, x + k + h, y), fill=(255, 255, 255, 60), width=6 * SS)
        short = label.split(" (")[0]
        if short.startswith(("Highlight", "Post")):
            short = short[0] + short.split()[-1]
        vis_bottom = min(y + h, NAV_Y) if key.startswith("post") else y + h
        vh = vis_bottom - y
        f = font((ARIAL, "Bold"), max(22, min(min(w, vh) * 0.22, 90)) * SS)
        d.text(s(x + w / 2, y + vh / 2), short, font=f, fill=(255, 255, 255, 255), anchor="mm",
               stroke_width=3 * SS, stroke_fill=(0, 0, 0, 160))
    return img.resize((W, H), Image.LANCZOS)


# ------------------------------------------------- sample pictures (docs) ---
def scene(seed, w, h):
    rnd = random.Random(seed)
    hue = rnd.random()
    top = colorsys.hsv_to_rgb(hue, 0.55, 0.95)
    bot = colorsys.hsv_to_rgb((hue + 0.08) % 1, 0.35, 1.0)
    yy = np.linspace(0, 1, h)[:, None, None]
    arr = np.repeat((np.array(top)[None, None] * (1 - yy) + np.array(bot)[None, None] * yy) * 255, w, axis=1)
    img = Image.fromarray(arr.astype(np.uint8)).convert("RGB")
    d = ImageDraw.Draw(img)
    sr = rnd.uniform(0.08, 0.16) * w
    sx, sy = rnd.uniform(0.2, 0.8) * w, rnd.uniform(0.2, 0.45) * h
    d.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=(255, 240, 200))
    horizon = rnd.uniform(0.55, 0.7) * h
    d.rectangle((0, horizon, w, h), fill=tuple(int(c * 255) for c in colorsys.hsv_to_rgb((hue + 0.5) % 1, 0.6, 0.55)))
    for k in range(3):
        hill = tuple(int(c * 255) for c in colorsys.hsv_to_rgb((hue + 0.3 + k * 0.05) % 1, 0.45, 0.35 + k * 0.1))
        pts = [(0, horizon)] + [(i * w / 8, horizon - rnd.uniform(0.02, 0.18) * h * (1 - k * 0.25)) for i in range(9)] + [(w, horizon)]
        d.polygon(pts, fill=hill)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def portrait(w, h):
    """stylised fashion-cover picture: studio backdrop and a figure silhouette"""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx / w) - 0.5) ** 2 + ((yy / h) - 0.42) ** 2 * 0.5)
    c0, c1 = np.array([214, 160, 128]), np.array([96, 52, 44])
    arr = c0 * (1 - np.clip(r * 1.7, 0, 1))[..., None] + c1 * np.clip(r * 1.7, 0, 1)[..., None]
    img = Image.fromarray(arr.astype(np.uint8)).convert("RGB")
    d = ImageDraw.Draw(img)
    k = w / 1080
    skin, coat, hair = (226, 190, 165), (24, 22, 26), (46, 30, 24)
    d.ellipse((300 * k, 960 * k, 780 * k, 1400 * k), fill=coat)                        # shoulders
    d.polygon([(150 * k, h), (330 * k, 1200 * k), (540 * k, 1120 * k), (750 * k, 1200 * k), (930 * k, h)], fill=coat)
    d.rectangle((500 * k, 860 * k, 580 * k, 1000 * k), fill=skin)                     # neck
    d.ellipse((380 * k, 360 * k, 700 * k, 880 * k), fill=hair)                        # hair
    d.ellipse((410 * k, 440 * k, 670 * k, 900 * k), fill=skin)                        # face
    d.polygon([(380 * k, 600 * k), (410 * k, 380 * k), (560 * k, 330 * k), (700 * k, 420 * k), (690 * k, 560 * k), (540 * k, 440 * k)], fill=hair)
    return img.filter(ImageFilter.GaussianBlur(1.2))


def cover(img, w, h):
    iw, ih = img.size
    k = max(w / iw, h / ih)
    img = img.resize((max(w, round(iw * k)), max(h, round(ih * k))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


# ----------------------------------------------------------- mock-ups ----
def draw_texts(img, fields, colors):
    d = ImageDraw.Draw(img)
    for f in fields:
        fnt, col = font(f["font"], f["size"]), colors[f["color"]]
        text = f["text"]
        if f.get("cs", 1.0) > 1.0:   # letter spacing (approximation of Text+ Character Spacing)
            text = "\n".join(("\u200a" * 2).join(line) for line in text.split("\n"))
        if f["va"] == "top":
            anchor = {"left": "la", "center": "ma", "right": "ra"}[f["align"]]
            sp = f["size"] * f.get("ls", 1.0) * 1.15 - fnt.getbbox("Hg")[3]
            d.multiline_text((f["x"], f["y"]), text, font=fnt, fill=col, anchor=anchor, align=f["align"], spacing=sp)
        else:
            d.text((f["x"], f["y"]), text, font=fnt, fill=col, anchor={"left": "lm", "center": "mm", "right": "rm"}[f["align"]])


def colors_for(tpl, variant, button=0):
    if tpl == "Profile":
        t = PROFILE_THEMES[variant]
        c = {k: hexc(t[k]) for k in ("fg", "muted", "link")}
        c["btn1"] = hexc(t["onprimary"]) if button == 0 else c["fg"]
        return c
    if tpl == "News":
        st = NEWS_STYLES[variant]
        return {"ink": hexc(st["ink"]), "accent": hexc(st["accent"])}
    return {"mast": hexc(MAG_COLORS[0][2]), "text": hexc(MAG_COLORS[1][2]), "accent": hexc(MAG_COLORS[2][2])}


def art_layers(build, tpl, variant, button=0, barcode=True, shade=0.6):
    if tpl == "Profile":
        return [Image.open(os.path.join(build, f"{PFX}_Profile_{variant}{button}.png"))]
    if tpl == "News":
        return [Image.open(os.path.join(build, f"{PFX}_News_{variant}.png"))]
    sh = Image.open(os.path.join(build, f"{PFX}_Magazine_shade.png"))
    sh.putalpha(sh.getchannel("A").point(lambda a: int(a * shade)))
    out = [sh]
    if barcode:
        out.append(Image.open(os.path.join(build, f"{PFX}_Magazine_barcode.png")))
    return out


def mock(build, tpl, variant=0, button=0, slots_img=None, pics=True, bw=False):
    T = TEMPLATES[tpl]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    if pics:
        for i, (key, _, (x, y, w, h), _) in enumerate(T["slots"]):
            if key == "logo":
                continue
            ph = portrait(w, h) if tpl == "Magazine" else cover(scene(i * 11 + 3, 640, 640), w, h)
            if bw:
                ph = ph.convert("L").convert("RGB")
            img.paste(ph, (x, y))
    if slots_img is not None:
        img.alpha_composite(slots_img)
    for layer in art_layers(build, tpl, variant, button):
        img.alpha_composite(layer)
    draw_texts(img, T["text"], colors_for(tpl, variant, button))
    return img


def thumb(page, title, sub):
    t = Image.new("RGBA", (320, 180), (24, 24, 28, 255))
    t.paste(page.resize((96, 170), Image.LANCZOS), (10, 5))
    d = ImageDraw.Draw(t)
    d.rectangle((10, 5, 105, 174), outline=(90, 90, 100, 255))
    d.text((120, 58), title, font=font((ARIAL, "Bold"), 23), fill=(245, 245, 245, 255))
    d.text((120, 92), sub, font=font((ARIAL, "Regular"), 15), fill=(170, 170, 180, 255))
    d.text((120, 150), "FakeUI", font=font((ARIAL, "Bold"), 14), fill=(0, 149, 246, 255))
    return t.convert("RGB")


def contact_sheet(imgs, labels, path, scale=0.3):
    w, h = int(W * scale), int(H * scale)
    sheet = Image.new("RGB", (len(imgs) * (w + 24) + 24, h + 70), (30, 30, 34))
    d = ImageDraw.Draw(sheet)
    for i, (im, lb) in enumerate(zip(imgs, labels)):
        x = 24 + i * (w + 24)
        sheet.paste(im.convert("RGB").resize((w, h), Image.LANCZOS), (x, 20))
        d.text((x + w / 2, h + 44), lb, font=font((ARIAL, "Bold"), 17), fill=(235, 235, 235), anchor="mm")
    sheet.save(path, optimize=True)


def build_art(build):
    """static art + placeholders (these go inside the .drfx)"""
    for th in PROFILE_THEMES:
        for b in PROFILE_BUTTONS:
            profile_art(th, b).save(os.path.join(build, f"{PFX}_Profile_{th}{b}.png"), optimize=True)
    for stl in NEWS_STYLES:
        news_art(stl).save(os.path.join(build, f"{PFX}_News_{stl}.png"), optimize=True)
    mag_barcode().save(os.path.join(build, f"{PFX}_Magazine_barcode.png"), optimize=True)
    mag_shade().save(os.path.join(build, f"{PFX}_Magazine_shade.png"), optimize=True)
    for tpl, T in TEMPLATES.items():
        placeholders(T["slots"], skip=("logo",)).save(os.path.join(build, f"{PFX}_{tpl}_slots.png"), optimize=True)


def build_docs_and_thumbs(build, docs):
    pages = {
        "profile_dark": mock(build, "Profile", 0, 0),
        "profile_light": mock(build, "Profile", 1, 1),
        "news_newsprint": mock(build, "News", 0),
        "news_vintage": mock(build, "News", 2, bw=True),
        "magazine": mock(build, "Magazine"),
    }
    for n, im in pages.items():
        im.convert("RGB").save(os.path.join(docs, f"{DOC}_{n}.png"), optimize=True)
    contact_sheet([pages["profile_dark"], pages["news_newsprint"], pages["magazine"], pages["profile_light"], pages["news_vintage"]],
                  ["Profile - Dark", "Italian daily - Newsprint", "Fashion magazine", "Profile - Light", "Italian daily - Vintage, B&W"],
                  os.path.join(docs, f"{DOC}_overview.png"), 0.28)
    slot_pages = {tpl: mock(build, tpl, slots_img=placeholders(T["slots"]), pics=False) for tpl, T in TEMPLATES.items()}
    contact_sheet(list(slot_pages.values()), ["Profile slots", "Italian daily slots", "Magazine slot"],
                  os.path.join(docs, f"{DOC}_slots.png"), 0.34)
    thumbs = {
        "FakeUI_Profile": (pages["profile_dark"], "Profile page", "page + editable text"),
        "FakeUI_Profile_Photo": (slot_pages["Profile"], "Profile photo", "clip into a slot"),
        "FakeUI_News": (pages["news_newsprint"], "Italian daily", "front page + text"),
        "FakeUI_News_Photo": (slot_pages["News"], "Daily photo", "clip into a slot"),
        "FakeUI_Magazine": (pages["magazine"], "Magazine", "cover + cover lines"),
        "FakeUI_Magazine_Photo": (slot_pages["Magazine"], "Cover photo", "clip as the cover"),
    }
    tl = []
    for name, (im, a, b) in thumbs.items():
        t = thumb(im, a, b)
        t.save(os.path.join(build, name + ".png"))
        tl.append(t)
    sheet = Image.new("RGB", (2 * 330 + 10, 3 * 190 + 10), (12, 12, 14))
    for i, t in enumerate(tl):
        sheet.paste(t, (10 + (i % 2) * 330, 10 + (i // 2) * 190))
    sheet.save(os.path.join(docs, f"{DOC}_thumbnails.png"), optimize=True)
