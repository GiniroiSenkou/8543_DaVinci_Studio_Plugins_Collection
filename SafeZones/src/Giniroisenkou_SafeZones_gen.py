#!/usr/bin/env python3
"""
Giniroisenkou_SafeZones_gen.py - builds every overlay, guide, thumbnail and preview for SafeZones.

The 1080x1920 frame IS the phone screen. For every Platform x View it draws what the
app puts on that screen:

  view 0  1st view - Full-screen : video fills the frame, the app GUI floats on top
  view 1  3rd view - Feed scroll : the screen is the app feed, the video sits in the
                                   media slot (cropped the way the app crops it)
  view 2  Comments open          : comment sheet up, video shrunk into the space above
  view 3  Profile grid           : profile page, video as the first grid thumbnail

Opaque app screens have a transparent HOLE where the video shows, so the overlay
itself masks the video - the Fusion macro only has to scale the video into SLOT.

Output (build/):
  gui_<p>_<v>_<theme>.png    GUI overlays (full-screen ones are theme-free, stored once)
  guide_<p>_<v>.png          guide layers (covered areas, safe box, crop lines, slot)
  slots.json                 slot rect + default fit per platform/view (read by the macro builder)

Icons: Lucide (ISC). Brand marks: Simple Icons (CC0). Font: Roboto (Apache-2.0).
Placeholder text only - no personal data.
"""
import json, math, os, re, subprocess, sys
from xml.sax.saxutils import escape
from PIL import ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.environ.get("SZ_TOOLS", os.path.join(HERE, "..", "_tools"))
LUCIDE = os.path.join(TOOLS, "lucide", "icons")
SIMPLE = os.path.join(TOOLS, "si", "icons")
FONTDIR = os.path.join(TOOLS, "fonts")
RESVG = os.path.join(TOOLS, "resvg.exe" if os.name == "nt" else "resvg")
OUT = os.path.join(HERE, "..", "build")

W, H = 1080, 1920

PLATFORMS = [  # key, label
    ("igreel", "Instagram Reel"),
    ("igstory", "Instagram Story"),
    ("tiktok", "TikTok"),
    ("shorts", "YouTube Shorts"),
    ("fbreel", "Facebook Reel"),
    ("fbstory", "Facebook Story"),
    ("linkedin", "LinkedIn Video"),
    ("insta360", "Insta360 Community"),
]
VIEWS = [("full", "1st view - Full-screen"), ("feed", "3rd view - Feed scroll"),
         ("comments", "Comments open"), ("grid", "Profile grid")]
THEMES = ["dark", "light"]

# ------------------------------------------------------------------ primitives
FONT_FILES = {400: "Roboto-Regular.ttf", 500: "Roboto-Medium.ttf", 700: "Roboto-Bold.ttf", 900: "Roboto-Black.ttf"}
_fcache = {}


def font(size, weight):
    k = (int(size), weight)
    if k not in _fcache:
        _fcache[k] = ImageFont.truetype(os.path.join(FONTDIR, FONT_FILES[weight]), int(size))
    return _fcache[k]


def tw(s, size, weight=400):
    return font(size, weight).getlength(s)


_icons = {}


def icon_inner(name):
    if name not in _icons:
        t = open(os.path.join(LUCIDE, name + ".svg"), encoding="utf-8").read()
        body = t[t.index(">", t.index("<svg")) + 1: t.rindex("</svg>")]
        _icons[name] = re.sub(r"\s+", " ", body).strip()
    return _icons[name]


def brand_path(name):
    t = open(os.path.join(SIMPLE, name + ".svg"), encoding="utf-8").read()
    return re.search(r'<path d="([^"]+)"', t).group(1)


class Doc:
    def __init__(self, w=W, h=H):
        self.w, self.h = w, h
        self.parts, self.defs = [], []
        self._gid = 0

    def add(self, s):
        self.parts.append(s)
        return self

    def gid(self, p="g"):
        self._gid += 1
        return f"{p}{self._gid}"

    def svg(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}"><defs>'
                '<filter id="sh" x="-30%" y="-30%" width="160%" height="160%">'
                '<feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#000" flood-opacity="0.45"/></filter>'
                '<filter id="shs" x="-30%" y="-30%" width="160%" height="160%">'
                '<feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#000" flood-opacity="0.35"/></filter>'
                + "".join(self.defs) + "</defs>" + "".join(self.parts) + "</svg>")

    # --- shapes
    def rect(self, x, y, w, h, fill="#000", r=0, op=1, stroke=None, sw=0, dash=None, extra=""):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        if dash:
            st += f' stroke-dasharray="{dash}"'
        return self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" '
                        f'fill="{fill}"' + ("" if "opacity" in extra else f' opacity="{op}"') + f'{st} {extra}/>')

    def circle(self, cx, cy, r, fill="#fff", op=1, stroke=None, sw=0, extra=""):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        return self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"' + ("" if "opacity" in extra else f' opacity="{op}"') + f'{st} {extra}/>')

    def line(self, x1, y1, x2, y2, color, sw=2, op=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" '
                        f'opacity="{op}" stroke-linecap="round"{d}/>')

    def text(self, x, cy, s, size, color="#fff", weight=400, anchor="start", op=1, extra=""):
        base = cy + size * 0.36
        return self.add(f'<text x="{x:.1f}" y="{base:.1f}" font-family="Roboto" font-size="{size}" '
                        f'font-weight="{weight}" fill="{color}" opacity="{op}" text-anchor="{anchor}" xml:space="preserve" {extra}>'
                        f'{escape(s)}</text>')

    def runs(self, x, cy, parts, size, extra=""):
        """parts: list of (text, color, weight). Returns end x."""
        for s, color, weight in parts:
            self.text(x, cy, s, size, color, weight, extra=extra)
            x += tw(s, size, weight)
        return x

    def icon(self, name, cx, cy, size, color="#fff", sw=2.0, fill="none", extra=""):
        s = size / 24.0
        return self.add(f'<g transform="translate({cx - size / 2:.1f},{cy - size / 2:.1f}) scale({s:.4f})" '
                        f'fill="{fill}" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
                        f'stroke-linejoin="round" {extra}>{icon_inner(name)}</g>')

    def brand(self, name, cx, cy, size, color):
        if name == "linkedin":  # no Simple Icons mark any more: plain "in" badge
            self.rect(cx - size / 2, cy - size / 2, size, size, color, r=size * .16)
            return self.text(cx, cy + size * .04, "in", size * .62, "#FFFFFF" if color != "#FFFFFF" else "#0A66C2",
                             900, anchor="middle")
        s = size / 24.0
        return self.add(f'<g transform="translate({cx - size / 2:.1f},{cy - size / 2:.1f}) scale({s:.4f})">'
                        f'<path d="{brand_path(name)}" fill="{color}"/></g>')

    def vgrad(self, y0, y1, color, a0, a1):
        g = self.gid("vg")
        self.defs.append(f'<linearGradient id="{g}" x1="0" y1="0" x2="0" y2="1">'
                         f'<stop offset="0" stop-color="{color}" stop-opacity="{a0}"/>'
                         f'<stop offset="1" stop-color="{color}" stop-opacity="{a1}"/></linearGradient>')
        return self.add(f'<rect x="0" y="{y0}" width="{self.w}" height="{y1 - y0}" fill="url(#{g})"/>')

    def ring(self, cx, cy, r, sw=5):
        g = self.gid("rg")
        self.defs.append(f'<linearGradient id="{g}" x1="0" y1="1" x2="1" y2="0">'
                         '<stop offset="0" stop-color="#FEDA75"/><stop offset=".35" stop-color="#FA7E1E"/>'
                         '<stop offset=".65" stop-color="#D62976"/><stop offset="1" stop-color="#962FBF"/>'
                         '</linearGradient>')
        return self.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#{g})" stroke-width="{sw}"/>')

    def avatar(self, cx, cy, r, tone="#8e8e8e", border=None, bw=0):
        g = self.gid("av")
        self.defs.append(f'<linearGradient id="{g}" x1="0" y1="0" x2="1" y2="1">'
                         f'<stop offset="0" stop-color="#9aa5b1"/><stop offset="1" stop-color="#5b6570"/></linearGradient>')
        self.circle(cx, cy, r, f"url(#{g})", stroke=border, sw=bw)
        # generic head + shoulders glyph
        self.add(f'<circle cx="{cx}" cy="{cy - r * .18:.1f}" r="{r * .32:.1f}" fill="#d9dee3" opacity=".9"/>')
        self.add(f'<path d="M{cx - r * .58:.1f},{cy + r * .62:.1f} a{r * .58:.1f},{r * .5:.1f} 0 0 1 {r * 1.16:.1f},0" '
                 f'fill="#d9dee3" opacity=".9"/>')
        return self

    def pill(self, x, cy, label, size, fg, bg=None, stroke=None, sw=2, padx=None, h=None, weight=700, r=None):
        padx = size * .75 if padx is None else padx
        h = size * 1.7 if h is None else h
        w = tw(label, size, weight) + 2 * padx
        r = h / 2 if r is None else r
        self.rect(x, cy - h / 2, w, h, bg or "none", r=r, stroke=stroke, sw=sw)
        self.text(x + padx, cy, label, size, fg, weight)
        return x + w

    def hole_bg(self, color, holes):
        """Opaque screen with transparent holes. holes: list of ('rect',x,y,w,h,r) or ('circle',cx,cy,r)."""
        d = f"M0,0 H{self.w} V{self.h} H0 Z "
        for h in holes:
            if h[0] == "rect":
                _, x, y, w, hh, r = h
                d += rr_path(x, y, w, hh, r) + " "
            else:
                _, cx, cy, r = h
                d += f"M{cx - r},{cy} a{r},{r} 0 1 0 {2 * r},0 a{r},{r} 0 1 0 {-2 * r},0 Z "
        return self.add(f'<path d="{d}" fill="{color}" fill-rule="evenodd"/>')


def rr_path(x, y, w, h, r):
    if r <= 0:
        return f"M{x},{y} H{x + w} V{y + h} H{x} Z"
    return (f"M{x + r},{y} H{x + w - r} A{r},{r} 0 0 1 {x + w},{y + r} V{y + h - r} "
            f"A{r},{r} 0 0 1 {x + w - r},{y + h} H{x + r} A{r},{r} 0 0 1 {x},{y + h - r} "
            f"V{y + r} A{r},{r} 0 0 1 {x + r},{y} Z")


# ------------------------------------------------------------------ themes
def pal(platform, theme):
    dark = theme == "dark"
    base = dict(bg="#000000" if dark else "#FFFFFF", fg="#F5F5F5" if dark else "#0A0A0A",
                sub="#A8A8A8" if dark else "#737373", sep="#262626" if dark else "#DBDBDB",
                card="#1F1F1F" if dark else "#EFEFEF", ph="#2A2A2A" if dark else "#CFCFCF",
                ph2="#333333" if dark else "#BDBDBD", btn="#262626" if dark else "#EFEFEF",
                sheet="#1C1C1E" if dark else "#FFFFFF", accent="#0095F6")
    if platform in ("tiktok",):
        base.update(accent="#FE2C55", sheet="#161616" if dark else "#FFFFFF", btn="#2F2F2F" if dark else "#F1F1F2")
    if platform == "shorts":
        base.update(bg="#0F0F0F" if dark else "#FFFFFF", accent="#FF0033", sheet="#212121" if dark else "#FFFFFF",
                    btn="#272727" if dark else "#F2F2F2", sub="#AAAAAA" if dark else "#606060")
    if platform in ("fbreel", "fbstory"):
        base.update(bg="#18191A" if dark else "#FFFFFF", fg="#E4E6EB" if dark else "#050505",
                    sub="#B0B3B8" if dark else "#65676B", sep="#3E4042" if dark else "#CED0D4",
                    card="#242526" if dark else "#FFFFFF", band="#000000" if dark else "#C9CCD1",
                    btn="#3A3B3C" if dark else "#E4E6EB", sheet="#242526" if dark else "#FFFFFF", accent="#0866FF")
    if platform == "linkedin":
        base.update(bg="#1B1F23" if dark else "#FFFFFF", fg="#E9E9E9" if dark else "#191919",
                    sub="#B0B0B0" if dark else "#666666", sep="#38434F" if dark else "#E8E8E8",
                    band="#000000" if dark else "#F4F2EE", btn="#38434F" if dark else "#EEF3F8",
                    sheet="#1B1F23" if dark else "#FFFFFF", accent="#71B7FB" if dark else "#0A66C2")
    if platform == "insta360":
        base.update(bg="#0D0D0D" if dark else "#FFFFFF", accent="#FFD400", sheet="#1A1A1A" if dark else "#FFFFFF",
                    btn="#262626" if dark else "#F2F2F2")
    base.setdefault("band", base["sep"])
    return base


WHITE = "#FFFFFF"
SH = 'filter="url(#sh)"'
SHS = 'filter="url(#shs)"'


def counted(d, name, cx, cy, size, label, fill="none", sw=2.0, lsize=30, gap=None, weight=500):
    d.icon(name, cx, cy, size, WHITE, sw=sw, fill=fill, extra=SH)
    if label:
        gap = size * .62 + lsize * .6 if gap is None else gap
        d.text(cx, cy + gap, label, lsize, WHITE, weight, anchor="middle", extra=SH)


def progress(d, n=3, cur=1, frac=.45, y=20):
    x0, x1, gap = 24, W - 24, 8
    seg = (x1 - x0 - gap * (n - 1)) / n
    for i in range(n):
        x = x0 + i * (seg + gap)
        d.rect(x, y, seg, 5, WHITE, r=2.5, op=.35)
        if i < cur:
            d.rect(x, y, seg, 5, WHITE, r=2.5)
        elif i == cur:
            d.rect(x, y, seg * frac, 5, WHITE, r=2.5)


# ================================================================== FULL-SCREEN
def full_igreel(d):
    d.vgrad(0, 260, "#000", .45, 0)
    d.vgrad(1280, H, "#000", 0, .6)
    x = d.runs(40, 82, [("Reels", WHITE, 700)], 58, extra=SH)
    d.icon("chevron-down", x + 30, 86, 42, WHITE, 2.4, extra=SH)
    d.icon("camera", 1022, 82, 66, WHITE, 2.0, extra=SH)
    # right action rail
    counted(d, "heart", 1010, 1135, 74, "24.8K")
    counted(d, "message-circle", 1010, 1290, 70, "312")
    counted(d, "repeat-2", 1010, 1445, 72, "1,204")
    counted(d, "send", 1010, 1600, 68, "2,391")
    d.icon("ellipsis", 1010, 1728, 60, WHITE, 2.4, extra=SH)
    d.rect(978, 1800, 64, 64, "#6b5bd6", r=14, stroke=WHITE, sw=4)
    d.icon("music", 1010, 1832, 34, WHITE, 2.2)
    # bottom-left block
    d.avatar(82, 1628, 40, border=WHITE, bw=2)
    x = d.runs(140, 1628, [("username", WHITE, 700)], 38, extra=SH)
    d.pill(x + 22, 1628, "Follow", 32, WHITE, stroke=WHITE, sw=2.5, padx=22, h=60, r=16)
    d.runs(40, 1712, [("Caption text goes here with the hook… ", WHITE, 400), ("more", "#d0d0d0", 400)], 36, extra=SH)
    d.icon("music", 58, 1790, 32, WHITE, 2.2, extra=SH)
    d.text(88, 1790, "username · Original audio", 32, WHITE, 400, extra=SH)


def full_igstory(d):
    d.vgrad(0, 330, "#000", .4, 0)
    d.vgrad(1620, H, "#000", 0, .45)
    progress(d)
    d.avatar(72, 112, 38)
    x = d.runs(126, 112, [("username", WHITE, 700), ("  5h", "#e0e0e0", 400)], 38, extra=SH)
    d.icon("ellipsis", 948, 112, 60, WHITE, 2.4, extra=SH)
    d.icon("x", 1030, 112, 66, WHITE, 2.2, extra=SH)
    d.rect(36, 1788, 790, 104, "none", r=52, stroke=WHITE, sw=3, extra='opacity=".85"')
    d.text(84, 1840, "Send message", 38, WHITE, 400, op=.9)
    d.icon("heart", 900, 1840, 74, WHITE, 2.0, extra=SH)
    d.icon("send", 1012, 1840, 68, WHITE, 2.0, extra=SH)


def full_tiktok(d):
    d.vgrad(0, 260, "#000", .4, 0)
    d.vgrad(1260, H, "#000", 0, .6)
    d.rect(34, 80, 100, 50, "none", r=10, stroke=WHITE, sw=3, extra=SH)
    d.text(84, 105, "LIVE", 28, WHITE, 900, anchor="middle")
    tabs = [("Explore", .6), ("Following", .6), ("For You", 1)]
    widths = [tw(t, 44, 700) for t, _ in tabs]
    x = 540 - (sum(widths) + 2 * 44) / 2 + 30
    for (t, op), w in zip(tabs, widths):
        d.text(x, 105, t, 44, WHITE, 700, op=op, extra=SH)
        if op == 1:
            d.rect(x + w / 2 - 30, 146, 60, 6, WHITE, r=3)
        x += w + 44
    d.icon("search", 1026, 105, 64, WHITE, 2.6, extra=SH)
    # rail
    d.avatar(1005, 1005, 50, border=WHITE, bw=4)
    d.circle(1005, 1058, 22, "#FE2C55")
    d.icon("plus", 1005, 1058, 26, WHITE, 4)
    counted(d, "heart", 1005, 1185, 92, "86.1K", fill=WHITE, sw=1.2, lsize=30, weight=700)
    d.icon("message-circle", 1005, 1340, 86, WHITE, 1.2, fill=WHITE, extra=SH)
    for dx in (-18, 0, 18):
        d.circle(1005 + dx, 1340, 5.5, "#555")
    d.text(1005, 1402, "1,029", 30, WHITE, 700, anchor="middle", extra=SH)
    counted(d, "bookmark", 1005, 1490, 82, "8,540", fill=WHITE, sw=1.2, lsize=30, weight=700)
    counted(d, "forward", 1005, 1640, 86, "2,331", fill=WHITE, sw=1.2, lsize=30, weight=700)
    d.circle(1005, 1800, 50, "#1d1d1d", stroke="#3a3a3a", sw=10)
    d.circle(1005, 1800, 24, "#8c6ad6")
    d.text(36, 1598, "username", 44, WHITE, 700, extra=SH)
    d.runs(36, 1660, [("Caption text goes here #fyp #edit ", WHITE, 400), ("more", "#cfcfcf", 700)], 38, extra=SH)
    d.icon("music", 52, 1726, 32, WHITE, 2.4, extra=SH)
    d.text(82, 1726, "original sound - username", 34, WHITE, 400, extra=SH)
    d.rect(0, 1912, W, 4, WHITE, op=.3)
    d.rect(0, 1912, W * .35, 4, WHITE, op=.85)


def full_shorts(d):
    d.vgrad(0, 230, "#000", .4, 0)
    d.vgrad(1300, H, "#000", 0, .6)
    d.icon("search", 878, 86, 62, WHITE, 2.4, extra=SH)
    d.icon("camera", 966, 86, 62, WHITE, 2.2, extra=SH)
    d.icon("ellipsis-vertical", 1040, 86, 62, WHITE, 2.6, extra=SH)
    rail = [("thumbs-up", "12K", WHITE), ("thumbs-down", "Dislike", "none"), ("message-square-text", "345", "none"),
            ("forward", "Share", "none"), ("audio-waveform", "Remix", "none")]
    y = 1010
    for name, lab, fill in rail:
        d.circle(1005, y, 56, "#000", op=.35)
        d.icon(name, 1005, y, 58, WHITE, 2.2, fill="none", extra=SH)
        d.text(1005, y + 84, lab, 28, WHITE, 500, anchor="middle", extra=SH)
        y += 160
    d.rect(969, 1790, 72, 72, "#b05a3c", r=14, stroke=WHITE, sw=4)
    d.icon("music", 1005, 1826, 36, WHITE, 2.2)
    d.avatar(74, 1640, 34)
    x = d.runs(124, 1640, [("@username", WHITE, 700)], 36, extra=SH)
    d.pill(x + 22, 1640, "Subscribe", 30, "#0F0F0F", bg=WHITE, padx=24, h=64)
    d.text(40, 1722, "Video title goes here #shorts", 40, WHITE, 400, extra=SH)
    x0 = 40
    d.rect(x0, 1770, 330, 58, "#000", r=29, op=.45)
    d.icon("music", x0 + 34, 1799, 30, WHITE, 2.2)
    d.text(x0 + 60, 1799, "Original sound", 30, WHITE, 500)
    d.rect(0, 1912, W, 4, WHITE, op=.35)
    d.rect(0, 1912, W * .28, 4, "#FF0033")


def full_fbreel(d):
    d.vgrad(0, 250, "#000", .4, 0)
    d.vgrad(1300, H, "#000", 0, .6)
    d.text(40, 88, "Reels", 56, WHITE, 700, extra=SH)
    d.icon("search", 880, 88, 60, WHITE, 2.4, extra=SH)
    d.icon("camera", 962, 88, 62, WHITE, 2.2, extra=SH)
    d.avatar(1040, 88, 30, border=WHITE, bw=2)
    counted(d, "thumbs-up", 1008, 1180, 70, "4.2K")
    counted(d, "message-circle", 1008, 1340, 70, "218")
    counted(d, "forward", 1008, 1500, 72, "96")
    d.icon("ellipsis", 1008, 1635, 60, WHITE, 2.4, extra=SH)
    d.rect(976, 1740, 64, 64, "#3b7a57", r=14, stroke=WHITE, sw=4)
    d.icon("music", 1008, 1772, 32, WHITE, 2.2)
    d.avatar(80, 1640, 38, border=WHITE, bw=2)
    d.runs(132, 1640, [("Username", WHITE, 700), (" · ", WHITE, 700), ("Follow", WHITE, 700)], 38, extra=SH)
    d.runs(40, 1722, [("Caption text goes here with the hook… ", WHITE, 400), ("See more", "#d0d0d0", 700)], 36, extra=SH)
    d.icon("music", 58, 1798, 32, WHITE, 2.2, extra=SH)
    d.text(88, 1798, "Username · Original audio", 32, WHITE, 400, extra=SH)


def full_fbstory(d):
    d.vgrad(0, 330, "#000", .4, 0)
    d.vgrad(1620, H, "#000", 0, .45)
    progress(d)
    d.avatar(72, 114, 38, border="#0866FF", bw=4)
    x = d.runs(126, 102, [("Username", WHITE, 700)], 36, extra=SH)
    d.text(126, 138, "3h", 30, "#e6e6e6", 400, extra=SH)
    d.icon("globe", 180, 138, 28, "#e6e6e6", 2.2, extra=SH)
    d.icon("ellipsis", 948, 112, 60, WHITE, 2.4, extra=SH)
    d.icon("x", 1030, 112, 66, WHITE, 2.2, extra=SH)
    d.rect(36, 1790, 560, 100, "none", r=50, stroke=WHITE, sw=3, extra='opacity=".85"')
    d.text(80, 1840, "Send message…", 36, WHITE, 400, op=.9)
    for cx, col, ic, fill in [(690, "#0866FF", "thumbs-up", WHITE), (800, "#F33E58", "heart", WHITE),
                              (910, "#F7B125", "face-grinning", "none"), (1020, "#F7B125", "face-slightly-frowning", "none")]:
        d.circle(cx, 1840, 46, col)
        d.icon(ic, cx, 1840, 50, WHITE if ic in ("thumbs-up", "heart") else "#5a3d00", 2.2, fill=fill)


def full_linkedin(d):
    d.vgrad(0, 240, "#000", .4, 0)
    d.vgrad(1300, H, "#000", 0, .6)
    d.icon("arrow-left", 48, 84, 58, WHITE, 2.4, extra=SH)
    d.icon("search", 950, 84, 58, WHITE, 2.4, extra=SH)
    d.icon("ellipsis", 1034, 84, 58, WHITE, 2.4, extra=SH)
    counted(d, "thumbs-up", 1008, 1210, 70, "1,284")
    counted(d, "message-square", 1008, 1370, 66, "96")
    counted(d, "repeat-2", 1008, 1530, 70, "42")
    counted(d, "send", 1008, 1690, 64, "Send", lsize=28)
    d.avatar(80, 1610, 40, border=WHITE, bw=2)
    x = d.runs(136, 1594, [("Full Name", WHITE, 700), ("  · 1st", "#dcdcdc", 400)], 36, extra=SH)
    d.text(136, 1636, "Job title at Company", 30, "#e6e6e6", 400, extra=SH)
    d.pill(640, 1612, "+ Follow", 30, WHITE, stroke=WHITE, sw=2.5, padx=22, h=60, r=30)
    d.runs(40, 1712, [("Caption text goes here with the hook… ", WHITE, 400), ("more", "#d0d0d0", 700)], 34, extra=SH)
    d.rect(0, 1912, W, 4, WHITE, op=.3)
    d.rect(0, 1912, W * .3, 4, WHITE, op=.9)


def full_insta360(d):
    d.vgrad(0, 250, "#000", .45, 0)
    d.vgrad(1260, H, "#000", 0, .6)
    tabs = [("Following", .6), ("For You", 1)]
    widths = [tw(t, 42, 700) for t, _ in tabs]
    x = 540 - (sum(widths) + 50) / 2
    for (t, op), w in zip(tabs, widths):
        d.text(x, 100, t, 42, WHITE, 700, op=op, extra=SH)
        if op == 1:
            d.rect(x + w / 2 - 28, 140, 56, 6, "#FFD400", r=3)
        x += w + 50
    d.icon("search", 1026, 100, 60, WHITE, 2.5, extra=SH)
    d.avatar(1005, 1030, 48, border=WHITE, bw=4)
    d.circle(1005, 1082, 20, "#FFD400")
    d.icon("plus", 1005, 1082, 24, "#111", 4)
    counted(d, "heart", 1005, 1200, 84, "3,412", fill=WHITE, sw=1.2, lsize=30, weight=700)
    counted(d, "message-circle", 1005, 1355, 78, "208", fill=WHITE, sw=1.2, lsize=30, weight=700)
    counted(d, "star", 1005, 1505, 80, "1,120", fill=WHITE, sw=1.2, lsize=30, weight=700)
    counted(d, "forward", 1005, 1655, 80, "Share", fill=WHITE, sw=1.2, lsize=28, weight=700)
    d.text(36, 1575, "username", 42, WHITE, 700, extra=SH)
    d.runs(36, 1636, [("Caption text goes here #360 ", WHITE, 400), ("more", "#cfcfcf", 700)], 36, extra=SH)
    d.rect(36, 1690, 470, 60, "#000", r=30, op=.5)
    d.icon("camera", 74, 1720, 32, "#FFD400", 2.4)
    d.text(104, 1720, "Shot with 360 camera", 30, WHITE, 500)
    d.pill(522, 1720, "Use template", 28, "#111", bg="#FFD400", padx=22, h=60)
    d.rect(0, 1912, W, 4, WHITE, op=.3)
    d.rect(0, 1912, W * .4, 4, "#FFD400")


FULL = dict(igreel=full_igreel, igstory=full_igstory, tiktok=full_tiktok, shorts=full_shorts,
            fbreel=full_fbreel, fbstory=full_fbstory, linkedin=full_linkedin, insta360=full_insta360)

# covered areas (x, y, w, h, label) and safe box for the guides, px on the 1080x1920 frame
DANGER = {
    "igreel": ([(0, 0, 1080, 170, "Top bar"), (915, 1060, 165, 860, "Action rail"),
                (0, 1570, 915, 350, "Name · caption · audio")], (40, 180, 860, 1370)),
    "igstory": ([(0, 0, 1080, 170, "Progress · name"), (0, 1770, 1080, 150, "Reply bar")], (40, 190, 1000, 1560)),
    "tiktok": ([(0, 0, 1080, 165, "Tabs"), (905, 940, 175, 980, "Action rail"),
                (0, 1555, 905, 365, "Name · caption · sound")], (40, 180, 850, 1360)),
    "shorts": ([(0, 0, 1080, 140, "Top icons"), (920, 940, 160, 980, "Action rail"),
                (0, 1590, 920, 330, "Channel · title · sound")], (40, 150, 865, 1420)),
    "fbreel": ([(0, 0, 1080, 160, "Top bar"), (920, 1120, 160, 800, "Action rail"),
                (0, 1590, 920, 330, "Name · caption · audio")], (40, 170, 865, 1400)),
    "fbstory": ([(0, 0, 1080, 170, "Progress · name"), (0, 1770, 1080, 150, "Reply · reactions")], (40, 190, 1000, 1560)),
    "linkedin": ([(0, 0, 1080, 150, "Top bar"), (925, 1150, 155, 770, "Action rail"),
                  (0, 1545, 925, 375, "Name · headline · caption")], (40, 160, 870, 1370)),
    "insta360": ([(0, 0, 1080, 160, "Tabs"), (910, 960, 170, 960, "Action rail"),
                  (0, 1530, 910, 390, "Name · caption · template")], (40, 170, 855, 1350)),
}
# crop lines worth knowing in full-screen (label, y0, y1)
CROPS = {
    "igreel": [("Feed 4:5", 285, 1635), ("Grid 3:4", 240, 1680)],
    "tiktok": [("Grid 3:4", 240, 1680)],
    "fbreel": [("Feed 4:5", 285, 1635)],
    "linkedin": [("Feed 4:5", 285, 1635)],
    "insta360": [("Card 3:4", 240, 1680)],
}


# ================================================================== FEED (3rd view)
def navbar(d, p, y0, icons, active=0):
    d.rect(0, y0, W, H - y0, p["bg"])
    d.line(0, y0, W, y0, p["sep"], 2)
    n = len(icons)
    for i, name in enumerate(icons):
        cx = W / n * (i + .5)
        fill = p["fg"] if (i == active and name in ("house",)) else "none"
        d.icon(name, cx, y0 + (H - y0) / 2 - 6, 60, p["fg"], 2.2 if i != active else 2.6, fill=fill)


def na_banner(d, text):
    w = tw(text, 32, 500) + 64
    d.rect(540 - w / 2, 300, w, 70, "#000", r=35, op=.72)
    d.text(540, 335, text, 32, WHITE, 500, anchor="middle")


def feed_igreel(d, p):
    slot = (0, 250, 1080, 1350)
    d.hole_bg(p["bg"], [("rect",) + slot + (0,)])
    d.text(36, 66, "Instagram", 52, p["fg"], 700)
    d.icon("heart", 930, 66, 64, p["fg"], 2.1)
    d.icon("square-plus", 1030, 66, 62, p["fg"], 2.1)
    d.ring(76, 186, 44, 5)
    d.avatar(76, 186, 36)
    d.text(136, 168, "username", 36, p["fg"], 700)
    d.text(136, 208, "Original audio", 30, p["fg"], 400, op=.85)
    d.icon("ellipsis", 1030, 186, 56, p["fg"], 2.4)
    d.circle(1024, 1548, 30, "#000", op=.55)
    d.icon("volume-x", 1024, 1548, 34, WHITE, 2.2)
    x = 30
    for name, lab in [("heart", "1,234"), ("message-circle", "56"), ("repeat-2", "12"), ("send", "8")]:
        d.icon(name, x + 32, 1648, 64, p["fg"], 2.0)
        d.text(x + 74, 1648, lab, 32, p["fg"], 700)
        x += 74 + tw(lab, 32, 700) + 40
    d.icon("bookmark", 1036, 1648, 62, p["fg"], 2.0)
    d.runs(30, 1708, [("username ", p["fg"], 700), ("Caption text goes here with the hook… ", p["fg"], 400),
                      ("more", p["sub"], 400)], 34)
    d.runs(30, 1754, [("friend_01 ", p["fg"], 700), ("Love this edit!", p["fg"], 400)], 34)
    d.text(30, 1798, "View all 56 comments", 32, p["sub"], 400)
    navbar(d, p, 1828, ["house", "clapperboard", "send", "search", "circle-user"])
    return slot, "width", "Your video · feed post (max 4:5)"


def feed_tiktok(d, p):
    tile_w, tile_h = 522, 696
    slot = (12, 250, tile_w, tile_h)
    holes = [("rect",) + slot + (10,)]
    d.hole_bg(p["bg"], holes)
    d.icon("arrow-left", 48, 90, 58, p["fg"], 2.4)
    d.rect(96, 52, 790, 76, p["btn"], r=12)
    d.icon("search", 140, 90, 40, p["sub"], 2.4)
    d.text(176, 90, "search term", 34, p["fg"], 400)
    d.text(912, 90, "Search", 36, p["accent"], 700)
    x = 30
    for i, t in enumerate(["Top", "Videos", "Users", "Sounds", "Shop", "LIVE"]):
        wdt = tw(t, 34, 700 if i == 0 else 500)
        d.text(x, 185, t, 34, p["fg"] if i == 0 else p["sub"], 700 if i == 0 else 500)
        if i == 0:
            d.rect(x, 222, wdt, 5, p["fg"], r=2)
        x += wdt + 50
    d.line(0, 226, W, 226, p["sep"], 2)
    d.rect(546, 250, tile_w, tile_h, p["ph"], r=10)
    d.icon("play", 546 + tile_w / 2, 250 + tile_h / 2, 90, p["sub"], 2, fill=p["sub"])
    d.text(30, 250 + tile_h - 34, "3d ago", 28, WHITE, 500, extra=SH)
    for col, x0 in enumerate((12, 546)):
        d.text(x0 + 6, 985, "Caption text goes here" if col == 0 else "Another video caption", 34, p["fg"], 500)
        d.text(x0 + 6, 1030, "#fyp #edit" if col == 0 else "#trend", 34, p["fg"], 500)
        d.avatar(x0 + 26, 1086, 18)
        d.text(x0 + 54, 1086, "username" if col == 0 else "creator_02", 28, p["sub"], 400)
        d.icon("heart", x0 + tile_w - 110, 1086, 32, p["sub"], 2.2)
        d.text(x0 + tile_w - 88, 1086, "12.3K", 28, p["sub"], 400)
    for x0 in (12, 546):
        d.rect(x0, 1130, tile_w, tile_h, p["ph"], r=10)
    return slot, "fill", "Your video · search tile 3:4"


def feed_shorts(d, p):
    cw, ch = 522, 928
    slot = (12, 300, cw, ch)
    d.hole_bg(p["bg"], [("rect",) + slot + (18,)])
    d.brand("youtube", 70, 70, 76, "#FF0033")
    d.text(118, 70, "YouTube", 50, p["fg"], 700)
    d.icon("bell", 900, 70, 60, p["fg"], 2.1)
    d.icon("search", 1010, 70, 60, p["fg"], 2.3)
    x = 24
    for i, t in enumerate(["All", "Shorts", "Music", "Gaming", "News", "Live"]):
        wdt = tw(t, 32, 500) + 48
        d.rect(x, 146, wdt, 70, p["fg"] if i == 0 else p["btn"], r=14)
        d.text(x + 24, 181, t, 32, p["bg"] if i == 0 else p["fg"], 500)
        x += wdt + 18
    d.brand("youtubeshorts", 48, 262, 44, "#FF0033")
    d.text(84, 262, "Shorts", 40, p["fg"], 700)
    d.rect(546, 300, cw, ch, p["ph"], r=18)
    for x0, title in ((12, "Video title goes here"), (546, "Another short title")):
        d.icon("ellipsis-vertical", x0 + cw - 40, 342, 48, WHITE, 2.6, extra=SH)
        d.text(x0 + 24, 300 + ch - 118, title, 36, WHITE, 700, extra=SH)
        d.text(x0 + 24, 300 + ch - 70, "#shorts", 36, WHITE, 700, extra=SH)
        d.text(x0 + 24, 300 + ch - 28, "1.2M views", 30, WHITE, 400, extra=SH)
    d.rect(0, 1260, W, 560, p["ph"], r=0)
    d.icon("play", 540, 1540, 110, p["sub"], 2, fill=p["sub"])
    navbar(d, p, 1812, ["house", "zap", "circle-plus", "square-play", "circle-user"])
    return slot, "fill", "Your video · Shorts shelf card"


def fb_topbar(d, p):
    d.brand("facebook", 66, 66, 72, "#0866FF")
    d.icon("plus", 850, 66, 54, p["fg"], 2.4)
    d.icon("search", 940, 66, 56, p["fg"], 2.4)
    d.icon("message-circle", 1030, 66, 56, p["fg"], 2.2)


def feed_fbreel(d, p):
    slot = (0, 330, 1080, 1350)
    d.hole_bg(p["bg"], [("rect",) + slot + (0,)])
    fb_topbar(d, p)
    d.rect(0, 118, W, 12, p["band"])
    d.avatar(74, 196, 42)
    x = d.runs(132, 178, [("Username", p["fg"], 700), (" · ", p["fg"], 700), ("Follow", p["accent"], 700)], 36)
    d.text(132, 222, "2h · ", 30, p["sub"], 400)
    d.icon("globe", 132 + tw("2h · ", 30) + 14, 222, 28, p["sub"], 2.2)
    d.icon("ellipsis", 950, 196, 52, p["sub"], 2.4)
    d.icon("x", 1030, 196, 54, p["sub"], 2.2)
    d.runs(30, 286, [("Caption text goes here with the hook… ", p["fg"], 400), ("See more", p["sub"], 500)], 36)
    d.rect(24, 1612, 150, 50, "#000", r=10, op=.55)
    d.icon("clapperboard", 54, 1637, 30, WHITE, 2.2)
    d.text(78, 1637, "Reels", 28, WHITE, 700)
    d.circle(46, 1726, 20, "#0866FF")
    d.icon("thumbs-up", 46, 1726, 24, WHITE, 2.4, fill=WHITE)
    d.circle(78, 1726, 20, "#F33E58", stroke=p["bg"], sw=3)
    d.icon("heart", 78, 1726, 22, WHITE, 2.2, fill=WHITE)
    d.text(110, 1726, "1.2K", 32, p["sub"], 400)
    d.text(1050, 1726, "56 comments  12 shares", 32, p["sub"], 400, anchor="end")
    d.line(24, 1760, 1056, 1760, p["sep"], 2)
    for cx, name, lab in [(180, "thumbs-up", "Like"), (540, "message-circle", "Comment"), (900, "forward", "Share")]:
        wl = tw(lab, 32, 500)
        d.icon(name, cx - wl / 2 - 26, 1800, 44, p["sub"], 2.2)
        d.text(cx - wl / 2 + 8, 1800, lab, 32, p["sub"], 500)
    navbar(d, p, 1840, ["house", "tv", "users", "store", "bell", "menu"])
    return slot, "width", "Your video · feed post (max 4:5)"


def feed_fbstory(d, p):
    cw, ch = 300, 533
    slot = (336, 316, cw, ch)
    d.hole_bg(p["bg"], [("rect",) + slot + (24,)])
    fb_topbar(d, p)
    d.rect(0, 118, W, 12, p["band"])
    d.avatar(76, 200, 42)
    d.rect(136, 162, 780, 76, "none", r=38, stroke=p["sep"], sw=2)
    d.text(172, 200, "What's on your mind?", 34, p["sub"], 400)
    d.icon("image", 1010, 200, 52, "#45BD62", 2.2)
    d.rect(0, 282, W, 12, p["band"])
    # create story card
    d.rect(20, 316, cw, ch, p["card"], r=24, stroke=p["sep"], sw=2)
    d.rect(20, 316, cw, ch * .7, p["ph2"], r=24)
    d.circle(170, 316 + ch * .7, 34, "#0866FF", stroke=p["card"], sw=6)
    d.icon("plus", 170, 316 + ch * .7, 34, WHITE, 3.4)
    d.text(170, 316 + ch * .88, "Create story", 30, p["fg"], 500, anchor="middle")
    # our card decorations
    d.circle(378, 360, 30, "none", stroke="#0866FF", sw=5)
    d.avatar(378, 360, 25)
    d.text(356, 316 + ch - 36, "Username", 30, WHITE, 700, extra=SH)
    for x0 in (652, 968):
        d.rect(x0, 316, cw, ch, p["ph"], r=24)
        d.circle(x0 + 42, 360, 30, "none", stroke="#0866FF", sw=5)
        d.avatar(x0 + 42, 360, 25)
    d.rect(0, 880, W, 12, p["band"])
    d.avatar(74, 960, 42)
    d.text(132, 942, "Friend Name", 36, p["fg"], 700)
    d.text(132, 986, "1h · ", 30, p["sub"], 400)
    d.text(30, 1060, "A regular post keeps the feed going below the stories row.", 34, p["fg"], 400)
    d.rect(0, 1110, W, 730, p["ph"])
    navbar(d, p, 1840, ["house", "tv", "users", "store", "bell", "menu"])
    return slot, "fill", "Your story · card in the stories row"


def feed_linkedin(d, p):
    slot = (0, 330, 1080, 1350)
    d.hole_bg(p["bg"], [("rect",) + slot + (0,)])
    d.avatar(58, 62, 34)
    d.rect(116, 26, 820, 72, p["btn"], r=8)
    d.icon("search", 156, 62, 40, p["sub"], 2.4)
    d.text(190, 62, "Search", 32, p["sub"], 400)
    d.icon("message-square", 1020, 62, 52, p["fg"], 2.2)
    d.rect(0, 118, W, 12, p["band"])
    d.avatar(76, 196, 42)
    d.runs(134, 170, [("Full Name", p["fg"], 700), ("  · 2nd", p["sub"], 400)], 34)
    d.text(134, 208, "Job title at Company", 28, p["sub"], 400)
    d.text(134, 242, "2h · ", 28, p["sub"], 400)
    d.icon("globe", 134 + tw("2h · ", 28) + 14, 242, 26, p["sub"], 2.2)
    d.text(1044, 180, "+ Follow", 32, p["accent"], 700, anchor="end")
    d.runs(30, 292, [("Caption text goes here with the hook… ", p["fg"], 400), ("more", p["sub"], 500)], 34)
    for i, (col, ic) in enumerate([("#378FE9", "thumbs-up"), ("#6DAE4F", "hand-heart"), ("#DF704D", "heart")]):
        d.circle(46 + i * 30, 1712, 18, col, stroke=p["bg"], sw=3)
        d.icon(ic, 46 + i * 30, 1712, 20, WHITE, 2.4)
    d.text(126, 1712, "128", 30, p["sub"], 400)
    d.text(1050, 1712, "12 comments · 4 reposts", 30, p["sub"], 400, anchor="end")
    d.line(24, 1742, 1056, 1742, p["sep"], 2)
    for cx, name, lab in [(135, "thumbs-up", "Like"), (405, "message-square", "Comment"), (675, "repeat-2", "Repost"),
                          (945, "send", "Send")]:
        d.icon(name, cx, 1772, 40, p["sub"], 2.2)
        d.text(cx, 1810, lab, 24, p["sub"], 500, anchor="middle")
    d.rect(0, 1834, W, 86, p["bg"])
    d.line(0, 1834, W, 1834, p["sep"], 2)
    for i, (name, lab) in enumerate([("house", "Home"), ("square-play", "Video"), ("users", "My Network"),
                                     ("bell", "Notifications"), ("briefcase-business", "Jobs")]):
        cx = 108 + i * 216
        d.icon(name, cx, 1864, 42, p["fg"] if i == 0 else p["sub"], 2.2)
        d.text(cx, 1904, lab, 20, p["fg"] if i == 0 else p["sub"], 500, anchor="middle")
    return slot, "width", "Your video · feed post (max 4:5)"


def cards_2col(d, p, y0, tile_w, tile_h, first_is_slot=True):
    for col, x0 in enumerate((12, 546)):
        if not (first_is_slot and col == 0):
            d.rect(x0, y0, tile_w, tile_h, p["ph"], r=16)
        d.text(x0 + 8, y0 + tile_h + 38, "Video title goes here" if col == 0 else "Another creator post", 32, p["fg"], 700)
        d.avatar(x0 + 26, y0 + tile_h + 92, 18)
        d.text(x0 + 54, y0 + tile_h + 92, "username" if col == 0 else "creator_02", 28, p["sub"], 400)
        d.icon("heart", x0 + tile_w - 100, y0 + tile_h + 92, 30, p["sub"], 2.2)
        d.text(x0 + tile_w - 80, y0 + tile_h + 92, "3.4K", 28, p["sub"], 400)


def feed_insta360(d, p):
    tw_, th = 522, 696
    slot = (12, 250, tw_, th)
    d.hole_bg(p["bg"], [("rect",) + slot + (16,)])
    d.text(36, 70, "Community", 50, p["fg"], 700)
    d.icon("search", 930, 70, 56, p["fg"], 2.4)
    d.icon("bell", 1026, 70, 56, p["fg"], 2.2)
    x = 36
    for i, t in enumerate(["Explore", "Following", "Tutorials", "Challenges"]):
        wdt = tw(t, 34, 700 if i == 0 else 500)
        d.text(x, 178, t, 34, p["fg"] if i == 0 else p["sub"], 700 if i == 0 else 500)
        if i == 0:
            d.rect(x, 212, wdt, 6, p["accent"], r=3)
        x += wdt + 50
    d.rect(24, 262, 170, 50, "#000", r=25, op=.55)
    d.icon("camera", 56, 287, 28, "#FFD400", 2.4)
    d.text(80, 287, "360 cam", 26, WHITE, 500)
    cards_2col(d, p, 250, tw_, th)
    for x0 in (12, 546):
        d.rect(x0, 1100, tw_, 820, p["ph"], r=16)
    return slot, "fill", "Your video · Explore card 3:4"


# ================================================================== COMMENTS
COMMENTS = [("friend_01", "2h", "Love this edit!", "124"), ("creator_02", "1h", "How did you do the transition?", "56"),
            ("someone_03", "45m", "The colours are unreal", "12"), ("friend_04", "20m", "Saving this one", "8"),
            ("user_05", "5m", "Where is this?", "3")]


def comment_rows(d, p, y, x0=40, fb=False):
    for name, t, txt, likes in COMMENTS:
        if y > 1640:
            break
        d.avatar(x0 + 36, y + 36, 36)
        if fb:
            bw = max(tw(name, 30, 700), tw(txt, 32, 400)) + 48
            d.rect(x0 + 90, y - 8, bw, 104, p["btn"], r=36)
            d.text(x0 + 114, y + 22, name, 30, p["fg"], 700)
            d.text(x0 + 114, y + 62, txt, 32, p["fg"], 400)
            d.runs(x0 + 114, y + 124, [(t + "   ", p["sub"], 400), ("Like   Reply", p["sub"], 700)], 28)
        else:
            d.runs(x0 + 92, y + 8, [(name + "  ", p["fg"], 700), (t, p["sub"], 400)], 30)
            d.text(x0 + 92, y + 50, txt, 34, p["fg"], 400)
            d.text(x0 + 92, y + 94, "Reply", 28, p["sub"], 500)
            d.icon("heart", 1030, y + 30, 36, p["sub"], 2.2)
            d.text(1030, y + 70, likes, 26, p["sub"], 400, anchor="middle")
        y += 150


def sheet(d, p, y0, r=36):
    d.rect(0, y0, W, H - y0 + 40, p["sheet"], r=r)
    d.rect(490, y0 + 22, 100, 10, p["sub"], r=5, op=.6)


def comments_generic(d, p, platform):
    tops = dict(igreel=700, tiktok=620, shorts=760, fbreel=680, linkedin=700, insta360=640)
    y0 = tops[platform]
    slot = (0, 0, 1080, y0)
    d.hole_bg("#000", [("rect",) + slot + (0,)])
    sheet(d, p, y0)
    fb = platform in ("fbreel", "linkedin")
    if platform == "igreel":
        d.text(540, y0 + 86, "Comments", 36, p["fg"], 700, anchor="middle")
        d.icon("send", 1024, y0 + 86, 44, p["fg"], 2.1)
    elif platform == "tiktok":
        d.text(540, y0 + 70, "1,029 comments", 32, p["fg"], 700, anchor="middle")
        d.icon("x", 1024, y0 + 70, 44, p["fg"], 2.4)
    elif platform == "shorts":
        d.runs(40, y0 + 80, [("Comments  ", p["fg"], 700), ("345", p["sub"], 400)], 38)
        d.icon("sliders-horizontal", 930, y0 + 80, 44, p["fg"], 2.2)
        d.icon("x", 1024, y0 + 80, 48, p["fg"], 2.4)
    elif platform == "insta360":
        d.text(540, y0 + 70, "208 comments", 32, p["fg"], 700, anchor="middle")
        d.icon("x", 1024, y0 + 70, 44, p["fg"], 2.4)
    else:
        d.runs(40, y0 + 80, [("Most relevant ", p["fg"], 700)], 36)
        d.icon("chevron-down", 40 + tw("Most relevant ", 36, 700) + 18, y0 + 82, 36, p["fg"], 2.4)
    d.line(0, y0 + 140, W, y0 + 140, p["sep"], 2)
    comment_rows(d, p, y0 + 170, fb=fb)
    # input bar
    d.rect(0, 1740, W, 180, p["sheet"])
    d.line(0, 1740, W, 1740, p["sep"], 2)
    d.avatar(70, 1830, 34)
    ph = {"igreel": "Add a comment for username…", "tiktok": "Add comment…", "shorts": "Add a comment…",
          "fbreel": "Write a comment…", "linkedin": "Add a comment…", "insta360": "Say something…"}[platform]
    d.rect(124, 1784, 920, 92, p["btn"], r=46)
    d.text(160, 1830, ph, 32, p["sub"], 400)
    if platform == "tiktok":
        d.icon("at-sign", 940, 1830, 40, p["fg"], 2.2)
        d.icon("face-slightly-smiling", 1002, 1830, 40, p["fg"], 2.2)
    return slot, "fit", "Video shrinks into the space above the sheet"


# ================================================================== PROFILE GRID
def grid_tiles(d, p, y0, tw_, th, gap, n_rows, slot_first=True, badge=None, views="12.4K", top_icon=None):
    for r in range(n_rows):
        for c in range(3):
            x = c * (tw_ + gap)
            y = y0 + r * (th + gap)
            if r == 0 and c == 0 and slot_first:
                pass
            else:
                d.rect(x, y, tw_, th, p["ph"] if (r + c) % 2 == 0 else p["ph2"])
            d.icon("play", x + 34, y + th - 34, 30, WHITE, 2.4, extra=SHS)
            d.text(x + 58, y + th - 34, views, 28, WHITE, 700, extra=SHS)
            if top_icon:
                d.icon(top_icon, x + tw_ - 36, y + 36, 36, WHITE, 2.2, extra=SHS)


def grid_igreel(d, p):
    tw_, th, gap = 358, 477, 3
    slot = (0, 955, tw_, th)
    d.hole_bg(p["bg"], [("rect",) + slot + (0,)])
    x = d.runs(40, 70, [("username", p["fg"], 700)], 44)
    d.icon("chevron-down", x + 24, 74, 36, p["fg"], 2.4)
    d.icon("square-plus", 910, 70, 58, p["fg"], 2.1)
    d.icon("menu", 1016, 70, 58, p["fg"], 2.3)
    d.ring(130, 262, 100, 6)
    d.avatar(130, 262, 90)
    for cx, n, lab in [(480, "128", "posts"), (690, "2,450", "followers"), (900, "512", "following")]:
        d.text(cx, 240, n, 40, p["fg"], 700, anchor="middle")
        d.text(cx, 290, lab, 30, p["fg"], 400, anchor="middle")
    d.text(40, 400, "Display Name", 34, p["fg"], 700)
    d.text(40, 446, "Short bio line goes here", 32, p["fg"], 400)
    d.text(40, 490, "link.example", 32, "#E0F1FF" if p["bg"] == "#000000" else "#00376B", 500)
    for x0, lab in [(40, "Edit profile"), (534, "Share profile")]:
        d.rect(x0, 540, 480, 76, p["btn"], r=16)
        d.text(x0 + 240, 578, lab, 32, p["fg"], 700, anchor="middle")
    for i in range(5):
        cx = 110 + i * 190
        d.circle(cx, 728, 64, "none", stroke=p["sep"], sw=3)
        d.circle(cx, 728, 56, p["ph"])
        d.text(cx, 832, ["Travel", "Food", "Edits", "Friends", "New"][i], 28, p["fg"], 400, anchor="middle")
    d.icon("plus", 870, 728, 50, p["fg"], 2.2)
    for i, name in enumerate(["grid-3x3", "clapperboard", "square-user"]):
        cx = 180 + i * 360
        d.icon(name, cx, 905, 52, p["fg"] if i == 0 else p["sub"], 2.2)
    d.rect(0, 947, 360, 4, p["fg"])
    grid_tiles(d, p, 955, tw_, th, gap, 2, top_icon="clapperboard")
    navbar(d, p, 1828, ["house", "clapperboard", "send", "search", "circle-user"], active=4)
    return slot, "fill", "Your video · grid thumbnail 3:4"


def grid_igstory(d, p):
    # story saved as a highlight: the cover is a circle crop of the story
    cx, cy, r = 110, 728, 56
    slot = (cx - r, cy - r, 2 * r, 2 * r)
    d.hole_bg(p["bg"], [("circle", cx, cy, r)])
    x = d.runs(40, 70, [("username", p["fg"], 700)], 44)
    d.icon("chevron-down", x + 24, 74, 36, p["fg"], 2.4)
    d.icon("square-plus", 910, 70, 58, p["fg"], 2.1)
    d.icon("menu", 1016, 70, 58, p["fg"], 2.3)
    d.avatar(130, 262, 90)
    for cxx, n, lab in [(480, "128", "posts"), (690, "2,450", "followers"), (900, "512", "following")]:
        d.text(cxx, 240, n, 40, p["fg"], 700, anchor="middle")
        d.text(cxx, 290, lab, 30, p["fg"], 400, anchor="middle")
    d.text(40, 400, "Display Name", 34, p["fg"], 700)
    d.text(40, 446, "Short bio line goes here", 32, p["fg"], 400)
    for x0, lab in [(40, "Edit profile"), (534, "Share profile")]:
        d.rect(x0, 540, 480, 76, p["btn"], r=16)
        d.text(x0 + 240, 578, lab, 32, p["fg"], 700, anchor="middle")
    for i in range(5):
        cxx = 110 + i * 190
        d.circle(cxx, 728, 64, "none", stroke=p["sep"], sw=3)
        if i:
            d.circle(cxx, 728, 56, p["ph"])
        d.text(cxx, 832, ["Your story", "Food", "Edits", "Friends", "New"][i], 28, p["fg"], 400, anchor="middle")
    for i, name in enumerate(["grid-3x3", "clapperboard", "square-user"]):
        d.icon(name, 180 + i * 360, 905, 52, p["fg"] if i == 0 else p["sub"], 2.2)
    d.rect(0, 947, 360, 4, p["fg"])
    grid_tiles(d, p, 955, 358, 477, 3, 2, slot_first=False)
    navbar(d, p, 1828, ["house", "clapperboard", "send", "search", "circle-user"], active=4)
    return slot, "fill", "Your story · highlight cover (circle crop)"


def grid_tiktok(d, p):
    tw_, th, gap = 358, 477, 3
    slot = (0, 875, tw_, th)
    d.hole_bg(p["bg"], [("rect",) + slot + (0,)])
    d.icon("user-plus", 50, 70, 54, p["fg"], 2.2)
    x = tw("username", 40, 700)
    d.text(540 - x / 2 - 12, 70, "username", 40, p["fg"], 700)
    d.icon("chevron-down", 540 + x / 2 + 4, 74, 34, p["fg"], 2.4)
    d.icon("menu", 1026, 70, 56, p["fg"], 2.3)
    d.avatar(540, 250, 100)
    d.text(540, 390, "@username", 34, p["fg"], 500, anchor="middle")
    for cx, n, lab in [(300, "128", "Following"), (540, "2,450", "Followers"), (780, "12.3K", "Likes")]:
        d.text(cx, 468, n, 40, p["fg"], 700, anchor="middle")
        d.text(cx, 516, lab, 30, p["sub"], 400, anchor="middle")
    for x0, lab in [(170, "Edit profile"), (560, "Share profile")]:
        d.rect(x0, 580, 360, 84, p["btn"], r=12)
        d.text(x0 + 180, 622, lab, 32, p["fg"], 700, anchor="middle")
    d.text(540, 720, "Short bio line goes here", 32, p["fg"], 400, anchor="middle")
    for i, name in enumerate(["grid-3x3", "lock", "repeat-2", "heart"]):
        d.icon(name, 135 + i * 270, 815, 48, p["fg"] if i == 0 else p["sub"], 2.2)
    d.rect(60, 865, 150, 5, p["fg"], r=2)
    grid_tiles(d, p, 875, tw_, th, gap, 2)
    d.rect(0, 1830, W, 90, p["bg"])
    d.line(0, 1830, W, 1830, p["sep"], 2)
    for i, (name, lab) in enumerate([("house", "Home"), ("users", "Friends"), (None, ""), ("message-square", "Inbox"),
                                     ("user", "Profile")]):
        cx = 108 + i * 216
        if name is None:
            d.rect(cx - 50, 1848, 100, 60, p["fg"], r=14)
            d.icon("plus", cx, 1878, 40, p["bg"], 3.2)
        else:
            d.icon(name, cx, 1864, 48, p["fg"], 2.2 if i != 4 else 2.8)
            d.text(cx, 1904, lab, 22, p["fg"], 500, anchor="middle")
    return slot, "fill", "Your video · grid thumbnail 3:4"


def grid_shorts(d, p):
    tw_, th, gap = 356, 633, 6
    slot = (0, 780, tw_, th)
    d.hole_bg(p["bg"], [("rect",) + slot + (8,)])
    d.icon("arrow-left", 48, 70, 56, p["fg"], 2.4)
    d.icon("search", 930, 70, 56, p["fg"], 2.3)
    d.icon("ellipsis-vertical", 1030, 70, 56, p["fg"], 2.6)
    d.rect(30, 128, 1020, 180, p["ph2"], r=20)
    d.avatar(120, 430, 80)
    d.text(230, 392, "Channel Name", 46, p["fg"], 700)
    d.text(230, 446, "@username · 12.4K subscribers · 128 videos", 28, p["sub"], 400)
    d.text(40, 520, "Short channel description goes here…", 30, p["sub"], 400)
    d.rect(40, 568, 1000, 84, p["fg"], r=42)
    d.text(540, 610, "Subscribe", 34, p["bg"], 700, anchor="middle")
    x = 40
    for i, t in enumerate(["Home", "Videos", "Shorts", "Playlists", "Posts"]):
        wdt = tw(t, 32, 500)
        d.text(x, 722, t, 32, p["fg"] if i == 2 else p["sub"], 500)
        if i == 2:
            d.rect(x, 762, wdt, 5, p["fg"], r=2)
        x += wdt + 64
    d.line(0, 767, W, 767, p["sep"], 2)
    for r in range(2):
        for c in range(3):
            x0, y0 = c * (tw_ + gap) + (gap if c else 0) * 0, 780 + r * (th + gap)
            x0 = c * (tw_ + gap)
            if not (r == 0 and c == 0):
                d.rect(x0, y0, tw_, th, p["ph"] if (r + c) % 2 == 0 else p["ph2"], r=8)
            d.text(x0 + 20, y0 + th - 34, "12K views", 30, WHITE, 700, extra=SHS)
            d.icon("ellipsis-vertical", x0 + tw_ - 30, y0 + 34, 38, WHITE, 2.6, extra=SHS)
    navbar(d, p, 1812, ["house", "zap", "circle-plus", "square-play", "circle-user"], active=4)
    return slot, "fill", "Your video · Shorts tab tile 9:16"


def grid_fbreel(d, p):
    tw_, th, gap = 358, 636, 3
    slot = (0, 990, tw_, th)
    d.hole_bg(p["bg"], [("rect",) + slot + (0,)])
    d.icon("arrow-left", 48, 70, 56, p["fg"], 2.4)
    d.text(110, 70, "Username", 40, p["fg"], 700)
    d.icon("search", 1030, 70, 56, p["fg"], 2.3)
    d.rect(0, 120, W, 360, p["ph2"])
    d.circle(190, 480, 108, p["bg"])
    d.avatar(190, 480, 98)
    d.text(50, 640, "Username", 52, p["fg"], 700)
    d.runs(50, 696, [("1.2K ", p["fg"], 700), ("friends", p["sub"], 400)], 34)
    d.rect(50, 752, 440, 84, p["accent"], r=14)
    d.text(270, 794, "+ Add to story", 32, WHITE, 700, anchor="middle")
    d.rect(506, 752, 440, 84, p["btn"], r=14)
    d.text(726, 794, "Edit profile", 32, p["fg"], 700, anchor="middle")
    d.rect(962, 752, 84, 84, p["btn"], r=14)
    d.icon("ellipsis", 1004, 794, 40, p["fg"], 2.4)
    x = 50
    for i, t in enumerate(["Posts", "Photos", "Reels"]):
        wdt = tw(t, 32, 700) + 48
        if i == 2:
            d.rect(x, 894, wdt, 68, "#263951" if p["bg"] != "#FFFFFF" else "#EBF5FF", r=34)
        d.text(x + 24, 928, t, 32, p["accent"] if i == 2 else p["sub"], 700)
        x += wdt + 20
    grid_tiles(d, p, 990, tw_, th, gap, 2, views="1.2K")
    navbar(d, p, 1840, ["house", "tv", "users", "store", "bell", "menu"])
    return slot, "fill", "Your video · Reels tab tile 9:16"


def grid_insta360(d, p):
    tw_, th = 522, 696
    slot = (12, 930, tw_, th)
    d.hole_bg(p["bg"], [("rect",) + slot + (16,)])
    d.icon("arrow-left", 48, 70, 56, p["fg"], 2.4)
    d.icon("ellipsis", 1030, 70, 56, p["fg"], 2.4)
    d.avatar(540, 250, 100)
    d.text(540, 400, "username", 42, p["fg"], 700, anchor="middle")
    d.text(540, 448, "Short bio line goes here", 30, p["sub"], 400, anchor="middle")
    for cx, n, lab in [(300, "128", "Following"), (540, "2,450", "Followers"), (780, "34.1K", "Likes")]:
        d.text(cx, 530, n, 40, p["fg"], 700, anchor="middle")
        d.text(cx, 578, lab, 30, p["sub"], 400, anchor="middle")
    d.rect(340, 640, 400, 84, p["accent"], r=42)
    d.text(540, 682, "Follow", 34, "#111", 700, anchor="middle")
    x = 60
    for i, t in enumerate(["Posts", "Liked", "Collections"]):
        wdt = tw(t, 34, 700 if i == 0 else 500)
        d.text(x, 800, t, 34, p["fg"] if i == 0 else p["sub"], 700 if i == 0 else 500)
        if i == 0:
            d.rect(x, 836, wdt, 6, p["accent"], r=3)
        x += wdt + 70
    d.line(0, 860, W, 860, p["sep"], 2)
    cards_2col(d, p, 930, tw_, th)
    return slot, "fill", "Your video · profile card 3:4"


# ------------------------------------------------------------------ state table
def build_state(pk, vk, theme):
    """Returns (svg_text, slot, fit, note)."""
    d = Doc()
    p = pal(pk, theme)
    na = None
    if vk == "full":
        FULL[pk](d)
        return d.svg(), (0, 0, W, H), "fit", "Full-screen", False
    if vk == "feed":
        fn = dict(igreel=feed_igreel, tiktok=feed_tiktok, shorts=feed_shorts, fbreel=feed_fbreel,
                  fbstory=feed_fbstory, linkedin=feed_linkedin, insta360=feed_insta360).get(pk)
        na = "Stories have no feed view - showing full-screen"
    elif vk == "comments":
        fn = ((lambda dd, pp: comments_generic(dd, pp, pk))
              if pk in ("igreel", "tiktok", "shorts", "fbreel", "linkedin", "insta360") else None)
        na = "Stories have no comments sheet - showing full-screen"
    else:
        fn = dict(igreel=grid_igreel, igstory=grid_igstory, tiktok=grid_tiktok, shorts=grid_shorts,
                  fbreel=grid_fbreel, insta360=grid_insta360).get(pk)
        na = ("LinkedIn has no profile video grid - showing full-screen" if pk == "linkedin"
              else "Facebook Stories don't live on the profile - showing full-screen")
    if fn is None:
        FULL[pk](d)
        na_banner(d, na)
        return d.svg(), (0, 0, W, H), "fit", "Not available", True
    slot, fit, note = fn(d, p)
    return d.svg(), slot, fit, note, False


def guide_svg(pk, vk, slot, fit, note, is_na):
    d = Doc()
    RED, GRN, AMB, CYN = "#FF3B30", "#34C759", "#FFCC00", "#00E5FF"

    def tag(x, y, s, col):
        wdt = tw(s, 26, 700) + 28
        d.rect(x, y - 21, wdt, 42, "#000", r=21, op=.7)
        d.text(x + 14, y, s, 26, col, 700)

    if vk == "full" or is_na:
        zones, safe = DANGER[pk]
        for (x, y, w, h, lab) in zones:
            d.rect(x, y, w, h, RED, op=.28)
            d.rect(x + 1.5, y + 1.5, w - 3, h - 3, "none", stroke=RED, sw=3, extra='opacity=".9"')
            tx = min(max(x + 16, 16), W - tw(lab, 26, 700) - 60)
            ty = y + 36 if y > 0 else y + h - 30
            tag(tx, ty, lab, "#FF8A80")
        sx, sy, sw, sh = safe
        d.rect(sx, sy, sw, sh, "none", stroke=GRN, sw=4, dash="18 12")
        tag(sx + 16, sy + 40, "Safe area", "#A5F3B8")
        for lab, y0, y1 in CROPS.get(pk, []):
            for yy in (y0, y1):
                d.line(0, yy, W, yy, AMB, 3, op=.95, dash="10 10")
            tag(W - tw(lab, 26, 700) - 60, y0 + 36, lab, AMB)
        d.line(W / 2, H / 2 - 30, W / 2, H / 2 + 30, WHITE, 2, op=.6)
        d.line(W / 2 - 30, H / 2, W / 2 + 30, H / 2, WHITE, 2, op=.6)
    else:
        x, y, w, h = slot
        d.rect(x - 2, y - 2, w + 4, h + 4, "none", stroke=CYN, sw=4, dash="16 10")
        label = note
        tx = x + 16 if x + 16 + tw(label, 26, 700) + 40 < W else 16
        ty = y + 40 if y > 60 else y + h - 40
        tag(tx, ty, label, CYN)
    return d.svg()


def render(svg_text, png_path):
    tmp = png_path + ".svg"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(svg_text)
    subprocess.run([RESVG, "--use-fonts-dir", FONTDIR, "--skip-system-fonts", "--font-family", "Roboto",
                    tmp, png_path], check=True)
    os.remove(tmp)


def build_all(out=OUT):
    os.makedirs(out, exist_ok=True)
    table = {"platforms": [l for _, l in PLATFORMS], "views": [l for _, l in VIEWS], "themes": THEMES,
             "states": []}
    for pi, (pk, pl) in enumerate(PLATFORMS):
        for vi, (vk, vl) in enumerate(VIEWS):
            st = None
            for ti, theme in enumerate(THEMES):
                svg, slot, fit, note, is_na = build_state(pk, vk, theme)
                themed = not (vk == "full" or is_na)
                name = f"gui_{pk}_{vk}_{theme if themed else 'any'}.png"
                if themed or ti == 0:
                    render(svg, os.path.join(out, name))
                st = st or dict(platform=pi, view=vi, slot=slot, fit=fit, note=note, na=is_na, gui={})
                st["gui"][theme] = name
            gname = f"guide_{pk}_{vk}.png"
            render(guide_svg(pk, vk, st["slot"], st["fit"], st["note"], st["na"]), os.path.join(out, gname))
            st["guide"] = gname
            table["states"].append(st)
            print(f"{pl:16s} {vk:9s} slot={st['slot']} fit={st['fit']} na={st['na']}")
    with open(os.path.join(out, "slots.json"), "w") as f:
        json.dump(table, f, indent=1)
    return table


if __name__ == "__main__":
    build_all(sys.argv[1] if len(sys.argv) > 1 else OUT)
