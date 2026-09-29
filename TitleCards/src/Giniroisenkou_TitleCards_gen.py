#!/usr/bin/env python3
"""
TitleCards generator -- emits the Fusion macros of the "TitleCards" pack for
DaVinci Resolve's Edit page (Effects > TitleCards).

28 drop-on-a-clip title-card generators, styled after the way anime episode
cards and kinetic-type loading screens present a word + a number/tag. No
copyrighted names, logos or artwork are used anywhere -- every default is a
generic placeholder ("Title", "#", "01") and every technique below is a
plain, original Fusion node graph (text, transform, blur, colour gain) --
never a copy of any specific show's actual assets.

Every effect follows the same pattern, one .setting per type:

  <Code>Ctrl  (BrightnessContrast, image passes through untouched)
              carries every Inspector control + the hidden maths as simple
              expressions. All control ids start with "k" so they never
              collide with BrightnessContrast's own inputs.
  ...content nodes...  build the title graphic from TextPlus/Transform/Crop/
              Blur/ColorGain, reading the Ctrl through expressions.
  TCScaleOff / TCBgPlate / TCOverBg / TCFinal   (shared "finish" chain)
              nudge/scale the content, lay it over a black/white/transparent
              plate, then composite that over the incoming clip.

Shared Inspector controls on every type: Word, Number Prefix, Tag, Subtitle,
Quote Line, In/Hold/Out Length, Background (transparent/black/white),
Colour preset (+ custom RGB), and a Scale/Offset nudge. A type that doesn't
use one of the text fields just ignores it -- e.g. "Tag" can hold a real
episode number or any other short word, exactly like a real prefix+word
lockup.

Usage:  python Giniroisenkou_TitleCards_gen.py   -> build/Edit/Effects/TitleCards/*.setting
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "build", "Edit", "Effects", "TitleCards")
PACK = "TitleCards"


# --------------------------------------------------------------------------
# small expression helpers
# --------------------------------------------------------------------------
def mix(a, b, t):
    return f"(({a})+(({b})-({a}))*({t}))"

def frac(e):
    return f"(({e})-floor({e}))"

def mod(a, b):
    return f"(({a})-({b})*floor(({a})/({b})))"

def hsh(a, b):
    return frac(f"sin(({a})*12.9898+({b})*78.233)*43758.5453")

def chain(sel_expr, values, last):
    e = str(last)
    for i in range(len(values) - 1, -1, -1):
        e = f"iif({sel_expr}=={i}, {values[i]}, {e})"
    return e

def ease_out(e):
    return f"(1-(1-({e}))*(1-({e})))"

def ease_in(e):
    return f"(({e})*({e}))"

def pop(p, amt=0.18):
    return f"(1+{amt}*sin(min(1,max(0,({p})))*3.14159265))"

def PT(x, y):
    """layout coords are written top-down (0 = top); Fusion is bottom-up"""
    return f"Point({x}, 1-({y}))"

def cat(*parts):
    return " .. ".join(parts)

def T(expr):
    return f"Text({expr})"


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'

def sv(s):
    return V(q(s))


# text-field references (node-level expressions -- always "C.xxx", auto
# expanded to "<Code>Ctrl.kxxx" by fusion_expr when the .setting is written)
WORD_U = "string.upper(C.Word.Value)"
WORD_R = "C.Word.Value"
PREFIXV = "C.Prefix.Value"
TAGV = "C.Tag.Value"
TAGFULL = cat(PREFIXV, TAGV)
SUBV = "C.Sub.Value"
QUOTEV = "C.Quote.Value"
NL = r'"\n"'
SP = r'" "'


# --------------------------------------------------------------------------
# node descriptions (same shape as the other packs in this collection)
# --------------------------------------------------------------------------
class Src:
    def __init__(self, node, out="Output"):
        self.node, self.out = node, out

class V:
    def __init__(self, v):
        self.v = v

class E:
    def __init__(self, default, expr):
        self.default, self.expr = default, expr

class Node:
    def __init__(self, name, kind, inputs, pos=(0, 0)):
        self.name, self.kind, self.inputs, self.pos = name, kind, inputs, pos


class FX:
    def __init__(self, name, code, category, blurb, help, controls, hidden, nodes, out, preview=None):
        self.name = f"{PACK}_{name}"
        self.short = name
        self.code = code
        self.ctrl = code + "Ctrl"
        self.category = category
        self.blurb = blurb
        self.help = help
        self.controls = controls
        self.hidden = hidden
        self.nodes = nodes
        self.out = out
        self.extra_inputs = []
        self.preview = preview or {}


# control helpers: (id, kind, name, default, extra, tooltip)
def label(text):
    import re
    return ("Lbl" + re.sub(r"\W", "", text)[:18], "label", text, None, {}, "")

def fl(cid, name, default, lo, hi, tip, amin=None, amax=None):
    ex = {"min": lo, "max": hi}
    if amin is not None: ex["amin"] = amin
    if amax is not None: ex["amax"] = amax
    return (cid, "float", name, default, ex, tip)

def it(cid, name, default, lo, hi, tip, amin=None, amax=None):
    ex = {"min": lo, "max": hi}
    if amin is not None: ex["amin"] = amin
    if amax is not None: ex["amax"] = amax
    return (cid, "int", name, default, ex, tip)

def cb(cid, name, default, options, tip):
    return (cid, "combo", name, default, {"combo": options}, tip)

def txt(cid, name, default, tip, lines=1):
    return (cid, "text", name, default, {"lines": lines}, tip)


# --------------------------------------------------------------------------
# content-building helpers
# --------------------------------------------------------------------------
def ttext(name, text_expr, size, alpha_expr, pos, center=None, style="Bold", rgb=None, extra=None):
    ins = [("UseFrameFormatSettings", V(1)),
           ("StyledText", E("TITLE", text_expr)),
           ("Font", sv("Arial")),
           ("Style", sv(style)),
           ("Size", size),
           ("Center", center if center is not None else V("{ 0.5, 0.5 }"))]
    r, g, b = rgb if rgb else ("C.PalR", "C.PalG", "C.PalB")
    # Text+ does not premultiply: fading Alpha1 alone leaves the colour glowing (additive),
    # so colour is multiplied by the same alpha
    A = f"({alpha_expr})"
    ins += [("Red1", E(1, f"({r})*{A}")), ("Green1", E(1, f"({g})*{A}")), ("Blue1", E(1, f"({b})*{A}")),
            ("Alpha1", E(1, alpha_expr))]
    for k, v in (extra or []):
        ins.append((k, v))
    return Node(name, "TextPlus", ins, pos)


def head_meta(px, head_expr, meta_expr, alpha_expr, headY=0.44, metaY=0.56, headSize=0.13, metaSize=0.045, x=110):
    hN, mN, gN = f"{px}Head", f"{px}Meta", f"{px}HM"
    head = ttext(hN, head_expr, V(headSize), alpha_expr, (x, -40), center=E("{ 0.5, 0.5 }", PT("0.5", str(headY))))
    meta = ttext(mN, meta_expr, V(metaSize), alpha_expr, (x, 40), center=E("{ 0.5, 0.5 }", PT("0.5", str(metaY))))
    merge = Node(gN, "Merge", [("Background", Src(hN)), ("Foreground", Src(mN))], (x + 110, 0))
    return [head, meta, merge], gN


def scrolling_ribbons(px, rep_text_expr, count, y_positions, speeds, size, alpha_expr):
    nodes, names = [], []
    for i in range(count):
        rep = ttext(f"{px}R{i}", T(rep_text_expr), V(size), alpha_expr, (60 + i * 10, -150 + i * 50),
                    center=E("{ 0.5, 0.5 }", PT("0.5", str(y_positions[i]))))
        panx = frac(f"time*{speeds[i]}*0.015")
        xf = Node(f"{px}RX{i}", "Transform", [("Input", Src(rep.name)),
                  ("Center", E("{ 0.5, 0.5 }", PT(panx, str(y_positions[i]))))], (160 + i * 10, -150 + i * 50))
        nodes += [rep, xf]
        names.append(xf.name)
    return nodes, names


CONTRAST = "iif(C.PalR+C.PalG+C.PalB>2.2, 0.05, 1)"
CRGB = (CONTRAST, CONTRAST, CONTRAST)


def finish_nodes(content_name, x=900):
    return [
        Node("TCScaleOff", "Transform", [("Input", Src(content_name)),
              ("Size", E(1, "C.Scale")),
              ("Center", E("{ 0.5, 0.5 }", "Point(0.5+C.OffX, 0.5+C.OffY)"))], (x, 0)),
        Node("TCBgPlate", "Background", [("UseFrameFormatSettings", V(1)),
              ("TopLeftRed", E(0, "C.BgWhite")), ("TopLeftGreen", E(0, "C.BgWhite")),
              ("TopLeftBlue", E(0, "C.BgWhite")), ("TopLeftAlpha", E(0, "C.BgAlpha"))], (x + 110, -60)),
        Node("TCOverBg", "Merge", [("Background", Src("TCBgPlate")), ("Foreground", Src("TCScaleOff"))], (x + 220, 0)),
        Node("TCFinal", "Merge", [("Background", Src("C")), ("Foreground", Src("TCOverBg"))], (x + 330, 0)),
    ]


def common_controls(inlen=8, hold=60, outlen=10, palette=0):
    return [
        it("InLen", "In Length (fr)", inlen, 1, 90, "How many frames the title takes to appear.", 1),
        cb("OutMode", "Out Point", 0, ["At clip end (auto)", "After Hold frames"],
           "At clip end: the title stays until the clip ends, then fades out. After Hold: leaves after the Hold frames below."),
        it("Hold", "Hold (fr, only for After Hold)", hold, 0, 600, "Frames the title stays fully visible when Out Point = After Hold.", 0),
        it("OutLen", "Out Length (fr)", outlen, 1, 90, "How many frames the title takes to disappear.", 1),
        cb("Background", "Background", 0, ["Over Clip (transparent)", "Black Card", "White Card"],
           "Draw the title over the clip below, or replace it with a solid black or white card."),
        cb("Palette", "Colour", palette, ["White", "Gold", "Red", "Orange", "Lavender", "Custom"],
           "Preset title colour, or choose Custom to set your own."),
        fl("CustR", "Custom Red", 1, 0, 1, "Only used when Colour = Custom.", 0, 1),
        fl("CustG", "Custom Green", 1, 0, 1, "Only used when Colour = Custom.", 0, 1),
        fl("CustB", "Custom Blue", 1, 0, 1, "Only used when Colour = Custom.", 0, 1),
        fl("Scale", "Nudge Scale", 1, 0.3, 2.5, "Fine-tune the overall size.", 0.1),
        fl("OffX", "Nudge X", 0, -0.4, 0.4, "Fine-tune the horizontal position.", -1, 1),
        fl("OffY", "Nudge Y", 0, -0.4, 0.4, "Fine-tune the vertical position.", -1, 1),
    ]


def text_controls(word="Title", prefix="#", tag="01", sub="Salt in the Wind", quote="Night Harbour"):
    return [
        txt("Word", "Word", word, "Main title word or short phrase.", 1),
        txt("Prefix", "Number Prefix", prefix, 'Shown before the Tag, e.g. "#". Leave blank for none.', 1),
        txt("Tag", "Tag", tag, "Episode number or any short word/phrase - not limited to numbers.", 1),
        txt("Sub", "Subtitle", sub, "Smaller line(s) under the title. Press Enter for your own line breaks.", 3),
        txt("Quote", "Quote Line", quote, "Optional quote / caption line. Press Enter for your own line breaks.", 3),
    ]


def common_hidden():
    return [
        ("Prog", "min(1, max(0, time/max(kInLen,1)))"),
        ("OutStart", "iif(kOutMode<0.5, max(kInLen, comp.RenderEnd-kOutLen), kInLen+kHold)"),
        ("OutProg", "min(1, max(0, (time-kOutStart)/max(kOutLen,1)))"),
        ("Opacity", "kProg*(1-kOutProg)"),
        ("BgAlpha", "iif(kBackground<0.5,0,1)"),
        ("BgWhite", "iif(kBackground>1.5,1,0)"),
        ("PalR", chain("kPalette", [1, 0.96, 0.85, 1.0, 0.74], "kCustR")),
        ("PalG", chain("kPalette", [1, 0.82, 0.10, 0.45, 0.68], "kCustG")),
        ("PalB", chain("kPalette", [1, 0.35, 0.13, 0.12, 0.98], "kCustB")),
    ]


def make(display_name, code, category, blurb, help_text, content_nodes, content_out,
         text_defaults=None, common_kw=None):
    td = dict(word="Title", prefix="#", tag="01", sub="Salt in the Wind", quote="Night Harbour")
    if text_defaults:
        td.update(text_defaults)
    controls = ([label(display_name.upper() + "  -  title card")]
                + text_controls(**td)
                + common_controls(**(common_kw or {})))
    hidden = common_hidden()
    nodes = content_nodes + finish_nodes(content_out)
    return FX(display_name.replace(" ", ""), code, category, blurb, help_text, controls, hidden, nodes, "TCFinal")


# ==========================================================================
#  THE 28 TITLE TYPES
# ==========================================================================
EFFECTS = []

# ---- 1 Stack Cut ----------------------------------------------------------
def _stackcut():
    px = "SC"
    hcut = "iif(time<C.InLen,0,iif(time>C.OutStart,0,1))"
    nodes, out = head_meta(px, T(WORD_U), T(cat(TAGFULL, SP, SUBV)), hcut,
                            headY=0.45, metaY=0.58, headSize=0.15, metaSize=0.05)
    return make("Stack Cut", px, "Episode Card",
        "hard, no-fade cut on and off - word over prefix+tag and a short line",
        "Stack Cut - the whole block appears and disappears on a single frame, no fade. A classic hard-cut title card.",
        nodes, out, common_kw=dict(inlen=1, hold=60, outlen=1))
EFFECTS.append(_stackcut())

# ---- 2 Ghost Settle --------------------------------------------------------
def _ghostsettle():
    px = "GS"
    txt_ = T(cat(WORD_U, NL, TAGFULL))
    base = ttext(f"{px}Txt", txt_, V(0.13), "C.Opacity", (110, 0))
    blur = Node(f"{px}Blur", "Blur", [("Input", Src(f"{px}Txt")),
              ("XBlurSize", E(0, f"(1-{ease_out('C.Prog')})*38"))], (220, 0))
    return make("Ghost Settle", px, "Episode Card",
        "text drifts into focus from a heavy blur, then settles sharp",
        "Ghost Settle - starts as a soft blurred ghost and sharpens into focus as it appears.",
        [base, blur], f"{px}Blur", common_kw=dict(inlen=16, hold=55, outlen=10))
EFFECTS.append(_ghostsettle())

# ---- 3 Spine ---------------------------------------------------------------
def _spine():
    px = "SP"
    txt_ = T(cat(WORD_U, NL, TAGFULL))
    y = f"(0.5+(1-{ease_out('C.Prog')})*(-0.85)+{ease_out('C.OutProg')}*(0.85))"
    node = ttext(f"{px}Txt", txt_, V(0.11), "C.Opacity", (110, 0))
    xf = Node(f"{px}Xf", "Transform", [("Input", Src(f"{px}Txt")), ("Angle", V(-90)),
              ("Center", E("{ 0.5, 0.5 }", PT("0.14", y)))], (220, 0))
    return make("Spine", px, "Episode Card",
        "vertical text along the left edge, drops in from above and exits below",
        "Spine - the title runs vertically along the edge of the frame, dropping in and dropping back out.",
        [node, xf], f"{px}Xf", common_kw=dict(inlen=10, hold=55, outlen=8))
EFFECTS.append(_spine())

# ---- 4 Overflow Number ------------------------------------------------------
def _overflownumber():
    px = "ON"
    small = ttext(f"{px}Small", T(WORD_U), V(0.045), "C.Opacity", (110, -50), center=E("{ 0.5, 0.5 }", PT("0.16", "0.14")))
    big = ttext(f"{px}Big", T(TAGFULL), V(0.55), "C.Opacity", (110, 50), center=E("{ 0.5, 0.5 }", PT("0.78", "0.72")))
    merge = Node(f"{px}M", "Merge", [("Background", Src(f"{px}Small")), ("Foreground", Src(f"{px}Big"))], (220, 0))
    return make("Overflow Number", px, "Episode Card",
        "tiny word top-left, the tag blown up huge bottom-right, spilling off frame",
        "Overflow Number - the word stays small in the corner while the number/tag floods the frame oversized.",
        [small, big, merge], f"{px}M", common_kw=dict(inlen=8, hold=55, outlen=8))
EFFECTS.append(_overflownumber())

# ---- 5 Whisper --------------------------------------------------------------
def _whisper():
    px = "WH"
    node = ttext(f"{px}Txt", T(QUOTEV), E(0.055, "0.055*(1+0.015*sin(time*0.15))"), "C.Opacity*0.92", (110, 0))
    return make("Whisper", px, "Episode Card",
        "one quiet line, barely breathing, no hard motion",
        "Whisper - a single soft line that breathes gently in place. Uses the Quote Line field.",
        [node], f"{px}Txt", text_defaults=dict(quote="the night doesn't ask permission"),
        common_kw=dict(inlen=20, hold=70, outlen=20))
EFFECTS.append(_whisper())

# ---- 6 Edge Crop -------------------------------------------------------------
def _edgecrop():
    px = "EC"
    head = ttext(f"{px}Head", T(TAGFULL), V(0.42), "C.Opacity*0.9", (110, -50), center=E("{ 0.5, 0.5 }", PT("1.02", "0.5")))
    metaX = f"(0.28-(1-{ease_out('C.Prog')})*0.18)"
    meta = ttext(f"{px}Meta", T(WORD_U), V(0.07), "C.Opacity", (110, 50), center=E("{ 0.5, 0.5 }", PT(metaX, "0.5")))
    merge = Node(f"{px}M", "Merge", [("Background", Src(f"{px}Head")), ("Foreground", Src(f"{px}Meta"))], (220, 0))
    return make("Edge Crop", px, "Episode Card",
        "giant tag pushed off the right edge, the word slides in from the left",
        "Edge Crop - the tag hangs off the right edge of frame while the word slides in from the left and settles.",
        [head, meta, merge], f"{px}M", common_kw=dict(inlen=14, hold=55, outlen=8))
EFFECTS.append(_edgecrop())

# ---- 7 Number Block -----------------------------------------------------------
def _numberblock():
    px = "NB"
    hy = f"(0.35-(1-{ease_out('C.Prog')})*0.7)"
    my = f"(0.62+(1-{ease_out('C.Prog')})*0.7)"
    head = ttext(f"{px}Head", T(WORD_U), V(0.13), "C.Opacity", (110, -50), center=E("{ 0.5, 0.5 }", PT("0.5", hy)))
    meta = ttext(f"{px}Meta", T(TAGFULL), V(0.09), "C.Opacity", (110, 50), center=E("{ 0.5, 0.5 }", PT("0.5", my)))
    merge = Node(f"{px}M", "Merge", [("Background", Src(f"{px}Head")), ("Foreground", Src(f"{px}Meta"))], (220, 0))
    return make("Number Block", px, "Episode Card",
        "word drops from above, tag rises from below, meeting in the middle",
        "Number Block - the word and the tag slide in from opposite edges and settle into a block.",
        [head, meta, merge], f"{px}M", common_kw=dict(inlen=12, hold=55, outlen=8))
EFFECTS.append(_numberblock())

# ---- 8 Ember Title -------------------------------------------------------------
def _embertitle():
    px = "EM"
    flick = "C.Opacity*(0.82+0.18*sin(time*9.1)*sin(time*3.7+1))"
    node = ttext(f"{px}Txt", T(SUBV), V(0.075), flick, (110, 0))
    return make("Ember Title", px, "Episode Card",
        "a single line that flickers like a dying ember while it holds",
        "Ember Title - the subtitle line flickers unevenly, like light from embers, for as long as it's held.",
        [node], f"{px}Txt", common_kw=dict(inlen=10, hold=70, outlen=10, palette=3))
EFFECTS.append(_embertitle())

# ---- 9 Smoke Stack ---------------------------------------------------------------
def _smokestack():
    px = "SM"
    txt_ = T(cat(WORD_R, NL, SUBV))
    r = mix("0.55", "C.PalR", "C.Prog")
    g = mix("0.55", "C.PalG", "C.Prog")
    b = mix("0.6", "C.PalB", "C.Prog")
    node = ttext(f"{px}Txt", txt_, V(0.1), "C.Opacity", (110, 0), rgb=(r, g, b))
    blur = Node(f"{px}Blur", "Blur", [("Input", Src(f"{px}Txt")),
              ("XBlurSize", E(0, f"(1-{ease_out('C.Prog')})*22"))], (220, 0))
    return make("Smoke Stack", px, "Episode Card",
        "grey smoke-blur clears into colour as the stack settles",
        "Smoke Stack - the text resolves out of a soft grey blur into full colour as it settles in.",
        [node, blur], f"{px}Blur", common_kw=dict(inlen=18, hold=55, outlen=10))
EFFECTS.append(_smokestack())

# ---- 10 Warm Stack -----------------------------------------------------------------
def _warmstack():
    px = "WS"
    metaA = "min(1,max(0,(time-C.InLen*0.35)/max(C.InLen*0.65,1)))*(1-C.OutProg)"
    head = ttext(f"{px}Head", T(WORD_U), V(0.12), "C.Opacity", (110, -50), center=E("{ 0.5, 0.5 }", PT("0.5", "0.42")))
    meta = ttext(f"{px}Meta", T(SUBV), V(0.05), metaA, (110, 50), center=E("{ 0.5, 0.5 }", PT("0.5", "0.58")))
    merge = Node(f"{px}M", "Merge", [("Background", Src(f"{px}Head")), ("Foreground", Src(f"{px}Meta"))], (220, 0))
    return make("Warm Stack", px, "Episode Card",
        "word settles first, the line below catches up a beat later",
        "Warm Stack - the title appears, then the subtitle line follows half a beat behind.",
        [head, meta, merge], f"{px}M", common_kw=dict(inlen=10, hold=55, outlen=10, palette=1))
EFFECTS.append(_warmstack())

# ---- 11 Heat Fade --------------------------------------------------------------------
def _heatfade():
    px = "HF"
    r = mix("C.PalR", "0.15", "C.OutProg")
    g = mix("C.PalG", "0.05", "C.OutProg")
    b = mix("C.PalB", "0.35", "C.OutProg")
    node = ttext(f"{px}Txt", T(WORD_U), V(0.14), "C.Opacity", (110, 0), rgb=(r, g, b))
    return make("Heat Fade", px, "Episode Card",
        "warm and bright while held, cools toward dark as it exits",
        "Heat Fade - the title glows in its colour while held, then cools down as it fades out.",
        [node], f"{px}Txt", common_kw=dict(inlen=6, hold=60, outlen=16, palette=2))
EFFECTS.append(_heatfade())

# ---- 12 Lavender Lockup ------------------------------------------------------------------
def _lavenderlockup():
    px = "LL"
    nodes, out = head_meta(px, T(WORD_U), T(TAGFULL), "C.Opacity", headY=0.46, metaY=0.57, headSize=0.115, metaSize=0.045)
    pop_ = Node(f"{px}Pop", "Transform", [("Input", Src(out)), ("Size", E(1, pop("C.Prog", 0.1)))], (500, 0))
    return make("Lavender Lockup", px, "Episode Card",
        "clean centred word-over-tag lockup with a soft pop-in",
        "Lavender Lockup - a tidy, centred word-and-tag lockup that pops gently into place.",
        nodes + [pop_], f"{px}Pop", common_kw=dict(inlen=10, hold=55, outlen=10, palette=4))
EFFECTS.append(_lavenderlockup())

# ---- 13 Spaced Stack -----------------------------------------------------------------------
def _spacedstack():
    px = "SS"
    spaced = f'(string.gsub({WORD_U}, "(.)", "%1 "))'
    head = ttext(f"{px}Head", T(spaced), V(0.1), "C.Opacity", (110, -50))
    meta = ttext(f"{px}Meta", T(TAGFULL), V(0.045), "C.Opacity", (110, 50), center=E("{ 0.5, 0.5 }", PT("0.5", "0.62")))
    merge = Node(f"{px}M", "Merge", [("Background", Src(f"{px}Head")), ("Foreground", Src(f"{px}Meta"))], (220, 0))
    return make("Spaced Stack", px, "Episode Card",
        "letters pushed apart for a wide, spaced-out headline",
        "Spaced Stack - the word is rendered with extra space between every letter for a wide title-card feel.",
        [head, meta, merge], f"{px}M", common_kw=dict(inlen=10, hold=55, outlen=10))
EFFECTS.append(_spacedstack())

# ---- 14 Logo Plate ---------------------------------------------------------------------------
def _logoplate():
    px = "LP"
    nodes, out = head_meta(px, T(WORD_U), T(TAGFULL), "C.Opacity", headY=0.44, metaY=0.56, headSize=0.12, metaSize=0.045)
    lineA = f"C.Opacity*min(1,{ease_out('C.Prog')}*2)"
    line = ttext(f"{px}Line", T('string.rep("―", 20)'), E(0.02, f"0.02*{pop('C.Prog', 0.15)}"), lineA,
                 (300, -80), center=E("{ 0.5, 0.5 }", PT("0.5", "0.51")), rgb=("C.PalR", "C.PalG", "C.PalB"))
    merge = Node(f"{px}M", "Merge", [("Background", Src(out)), ("Foreground", Src(f"{px}Line"))], (420, 0))
    return make("Logo Plate", px, "Episode Card",
        "word-and-tag lockup with a thin accent line that pops in beneath it",
        "Logo Plate - a clean lockup with a thin coloured accent line that pops in beneath the title like a logo bug.",
        nodes + [line, merge], f"{px}M", common_kw=dict(inlen=12, hold=55, outlen=10))
EFFECTS.append(_logoplate())

# ---- 15 Letter Focus -----------------------------------------------------------------------------
def _letterfocus():
    px = "LF"
    cx = mix("0.22", "0.5", ease_out("C.Prog"))
    sz = mix("3.2", "1.0", ease_out("C.Prog"))
    node = ttext(f"{px}Txt", T(WORD_U), V(0.13), "C.Opacity", (110, 0))
    xf = Node(f"{px}Xf", "Transform", [("Input", Src(f"{px}Txt")), ("Size", E(1, sz)),
              ("Center", E("{ 0.5, 0.5 }", PT(cx, "0.5")))], (220, 0))
    return make("Letter Focus", px, "Episode Card",
        "starts zoomed tight on one letter, pulls back to reveal the whole word",
        "Letter Focus - opens zoomed in tight on the start of the word, then pulls back to reveal it all.",
        [node, xf], f"{px}Xf", common_kw=dict(inlen=16, hold=55, outlen=8))
EFFECTS.append(_letterfocus())

# ---- 16 Letter Cycle -----------------------------------------------------------------------------
def _lettercycle():
    px = "LC"
    rate = 5
    wlen = "max(1,string.len(C.Word.Value))"
    nodes, names = [], []
    for i in range(8):
        sel = f"max(0, 1-abs({mod(f'floor(time/{rate})', wlen)} - {i}))"
        a = f"({sel})*iif(time<C.InLen,1,0)"
        n = ttext(f"{px}S{i}", T(f"string.sub(C.Word.Value,{i+1},{i+1})"), V(0.2), a, (110 + i * 10, -80))
        nodes.append(n)
        names.append(n.name)
    full = ttext(f"{px}Full", T(WORD_U), V(0.13), "iif(time<C.InLen,0,C.Opacity)", (300, 80))
    nodes.append(full)
    names.append(full.name)
    prev = names[0]
    merges = []
    for nm in names[1:]:
        m = Node(f"{px}Mg{nm}", "Merge", [("Background", Src(prev)), ("Foreground", Src(nm))], (400, 0))
        merges.append(m)
        prev = m.name
    return make("Letter Cycle", px, "Kinetic",
        "cycles one letter at a time before locking onto the full word",
        "Letter Cycle - flips through the word's letters one at a time, then locks onto the whole word.",
        nodes + merges, prev, common_kw=dict(inlen=max(rate * 8, 24), hold=55, outlen=10))
EFFECTS.append(_lettercycle())

# ---- 17 RGB Split ----------------------------------------------------------------------------------
def _rgbsplit():
    px = "RG"
    base = ttext(f"{px}Base", T(WORD_U), V(0.15), "C.Opacity", (60, 0), rgb=("1", "1", "1"))
    r = Node(f"{px}R", "ColorGain", [("Input", Src(f"{px}Base")), ("GainRed", V(1)), ("GainGreen", V(0)), ("GainBlue", V(0))], (160, -60))
    g = Node(f"{px}G", "ColorGain", [("Input", Src(f"{px}Base")), ("GainRed", V(0)), ("GainGreen", V(1)), ("GainBlue", V(0))], (160, 0))
    b = Node(f"{px}B", "ColorGain", [("Input", Src(f"{px}Base")), ("GainRed", V(0)), ("GainGreen", V(0)), ("GainBlue", V(1))], (160, 60))
    amt = "(0.006*(1-C.Prog)*3+0.006)"
    shR = Node(f"{px}SR", "Transform", [("Input", Src(f"{px}R")), ("Edges", V(2)),
              ("Center", E("{ 0.5, 0.5 }", PT(f"0.5+{amt}", "0.5")))], (260, -60))
    shB = Node(f"{px}SB", "Transform", [("Input", Src(f"{px}B")), ("Edges", V(2)),
              ("Center", E("{ 0.5, 0.5 }", PT(f"0.5-{amt}", "0.5")))], (260, 60))
    mrg = Node(f"{px}MRG", "Merge", [("Background", Src(f"{px}SR")), ("Foreground", Src(f"{px}G")), ("ApplyMode", V('FuID { "Screen" }'))], (360, -20))
    mrgb = Node(f"{px}MRGB", "Merge", [("Background", Src(f"{px}MRG")), ("Foreground", Src(f"{px}SB")), ("ApplyMode", V('FuID { "Screen" }'))], (460, 0))
    return make("RGB Split", px, "Kinetic",
        "chromatic channel split that snaps together as the title lands",
        "RGB Split - the red and blue channels start split apart and snap together as the title settles in.",
        [base, r, g, b, shR, shB, mrg, mrgb], f"{px}MRGB", common_kw=dict(inlen=10, hold=55, outlen=8))
EFFECTS.append(_rgbsplit())

# ---- 18 Slice Reveal --------------------------------------------------------------------------------
def _slicereveal():
    px = "SR"
    n = 4
    nodes, names = [], []
    for i in range(n):
        delay = i * 2
        pi = f"min(1,max(0,(time-{delay})/max(C.InLen,1)))"
        dirn = -1 if i % 2 == 0 else 1
        x = f"({dirn}*(1-{ease_out(pi)}))"
        if i == n - 1:
            a = "C.Opacity"
        else:
            a = f"C.Opacity*max(0,1-{ease_out(pi)})"
        node = ttext(f"{px}W{i}", T(WORD_U), V(0.15), a, (110 + i * 10, -100 + i * 40),
                     center=E("{ 0.5, 0.5 }", PT(f"0.5+{x}", "0.5")))
        nodes.append(node)
        names.append(node.name)
    prev = names[0]
    merges = []
    for nm in names[1:]:
        m = Node(f"{px}M{nm}", "Merge", [("Background", Src(prev)), ("Foreground", Src(nm))], (500, 0))
        merges.append(m)
        prev = m.name
    return make("Slice Reveal", px, "Kinetic",
        "layered copies of the word slide in from alternating sides in quick succession before the last one locks",
        "Slice Reveal - overlapping copies of the word slide in from alternating sides in quick succession before the final one locks into place.",
        nodes + merges, prev, common_kw=dict(inlen=8, hold=55, outlen=8))
EFFECTS.append(_slicereveal())

# ---- 19 Echo Columns ---------------------------------------------------------------------------------
def _echocolumns():
    px = "EK"
    rep = f'string.rep({WORD_U} .. "   ", 14)'
    ys = [0.15, 0.38, 0.62, 0.85]
    speeds = [7, -5, 6, -8]
    ribAlpha = "iif(time<C.InLen*0.7, C.Opacity*0.5, 0)"
    ribNodes, ribNames = scrolling_ribbons(px, rep, 4, ys, speeds, 0.06, ribAlpha)
    slamA = "iif(time<C.InLen*0.55,0,C.Opacity)"
    slam = ttext(f"{px}Slam", T(WORD_U), V(0.15), slamA, (400, 0))
    names = ribNames + [slam.name]
    prev = names[0]
    merges = []
    for nm in names[1:]:
        m = Node(f"{px}M{nm}", "Merge", [("Background", Src(prev)), ("Foreground", Src(nm))], (500, 0))
        merges.append(m)
        prev = m.name
    return make("Echo Columns", px, "Kinetic",
        "scrolling repeated columns of the word, then one clean copy slams into place",
        "Echo Columns - fast scrolling repeats of the word race by before the real title slams into place.",
        ribNodes + [slam] + merges, prev, common_kw=dict(inlen=16, hold=55, outlen=10))
EFFECTS.append(_echocolumns())

# ---- 20 Circle Stamp -----------------------------------------------------------------------------------
def _circlestamp():
    px = "CS"
    dot = ttext(f"{px}Dot", T('"•"'), V(1.5), f"C.Opacity*0.85*{pop('C.Prog', 0.12)}", (110, -60))
    word = ttext(f"{px}Word", T(WORD_U), V(0.11), "C.Opacity", (110, 60), rgb=CRGB)
    merge = Node(f"{px}M", "Merge", [("Background", Src(f"{px}Dot")), ("Foreground", Src(f"{px}Word"))], (220, 0))
    return make("Circle Stamp", px, "Kinetic",
        "a solid coloured disc pops in behind the word like a wax stamp",
        "Circle Stamp - a filled dot pops in behind the word, like a wax stamp landing on the title.",
        [dot, word, merge], f"{px}M", common_kw=dict(inlen=8, hold=55, outlen=10))
EFFECTS.append(_circlestamp())

# ---- 21 Frame Fill -----------------------------------------------------------------------------------
def _framefill():
    px = "FF"
    sz = mix("0.34", "0.16", ease_out("C.Prog"))
    cx = "(0.5+0.02*sin(time*0.05))"
    node = ttext(f"{px}Txt", T(WORD_U), E(0.2, sz), "C.Opacity", (110, 0), center=E("{ 0.5, 0.5 }", PT(cx, "0.5")))
    return make("Frame Fill", px, "Kinetic",
        "the word floods the whole frame oversized, then eases back to a normal title size",
        "Frame Fill - the word starts huge, filling the frame, then eases back down to a normal title size.",
        [node], f"{px}Txt", common_kw=dict(inlen=14, hold=55, outlen=8))
EFFECTS.append(_framefill())

# ---- 22 Box Lockup -----------------------------------------------------------------------------------
def _boxlockup():
    px = "BL"
    bracket = T(cat('"[ "', WORD_U, '" ]"'))
    nodes, out = head_meta(px, bracket, T(TAGFULL), "C.Opacity", headY=0.46, metaY=0.58, headSize=0.1, metaSize=0.045)
    return make("Box Lockup", px, "Kinetic",
        "the word locked inside brackets, with the tag stacked below",
        "Box Lockup - the word sits inside a bracketed lockup, tag stacked underneath.",
        nodes, out, common_kw=dict(inlen=8, hold=55, outlen=8))
EFFECTS.append(_boxlockup())

# ---- 23 Diagonal Band --------------------------------------------------------------------------------
def _diagonalband():
    px = "DB"
    slide = f"(-1.3*(1-{ease_out('C.Prog')}) + 1.3*{ease_out('C.OutProg')})"
    band = ttext(f"{px}Band", T('string.rep("█", 24)'), V(0.22), "C.Opacity", (60, -100), rgb=("C.PalR", "C.PalG", "C.PalB"))
    tilt = Node(f"{px}Tilt", "Transform", [("Input", Src(f"{px}Band")), ("Angle", V(-7)),
              ("Center", E("{ 0.5, 0.5 }", PT(f"0.5+{slide}", "0.5")))], (160, -100))
    txt_ = ttext(f"{px}Txt", T(WORD_U), V(0.11), "C.Opacity", (260, 60), rgb=CRGB)
    txtTilt = Node(f"{px}TxtTilt", "Transform", [("Input", Src(f"{px}Txt")), ("Angle", V(-7)),
              ("Center", E("{ 0.5, 0.5 }", PT(f"0.5+{slide}", "0.5")))], (360, 60))
    merge = Node(f"{px}M", "Merge", [("Background", Src(f"{px}Tilt")), ("Foreground", Src(f"{px}TxtTilt"))], (460, 0))
    return make("Diagonal Band", px, "Kinetic",
        "a tilted colour band slides across, carrying the word with it",
        "Diagonal Band - a tilted band of colour slides in carrying the title, then slides back out.",
        [band, tilt, txt_, txtTilt, merge], f"{px}M", common_kw=dict(inlen=10, hold=55, outlen=10, palette=2))
EFFECTS.append(_diagonalband())

# ---- 24 Name Echo -------------------------------------------------------------------------------------
def _nameecho():
    """staggered copies (no TimeSpeed: time-offset nodes don't work on generated text in a clip effect)"""
    px = "NE"
    nodes, names = [], []
    for i in range(4, -1, -1):          # oldest / faintest echo first, main copy (i=0) on top
        pi = f"min(1,max(0,(time-{i * 2})/max(C.InLen,1)))"
        x = f"(0.5-0.28*(1-{ease_out(pi)}))"
        if i == 0:
            a = "C.Opacity"
        else:
            a = f"{round(0.6 ** i, 4)}*max(0,1-{ease_out(pi)})*min(1,C.Prog*3)*(1-C.OutProg)"
        n = ttext(f"{px}W{i}", T(WORD_U), V(0.14), a, (110 + (4 - i) * 10, -100 + (4 - i) * 40),
                  center=E("{ 0.5, 0.5 }", PT(x, "0.5")))
        nodes.append(n)
        names.append(n.name)
    prev = names[0]
    for nm in names[1:]:
        m = Node(f"{px}M{nm}", "Merge", [("Background", Src(prev)), ("Foreground", Src(nm))], (500, 0))
        nodes.append(m)
        prev = m.name
    return make("Name Echo", px, "Kinetic",
        "the word slides in leaving a trail of fading ghost copies behind it",
        "Name Echo - the title slides in from the left, leaving a soft trail of fading ghost copies that catch up and vanish.",
        nodes, prev, common_kw=dict(inlen=12, hold=55, outlen=10))
EFFECTS.append(_nameecho())

# ---- 25 Outline Giant ---------------------------------------------------------------------------------
def _outlinegiant():
    px = "OG"
    back = ttext(f"{px}Back", T(WORD_U), V(0.145), "C.Opacity", (110, -60), rgb=("0", "0", "0"))
    front = ttext(f"{px}Front", T(WORD_U), V(0.13), "C.Opacity", (110, 60))
    merge = Node(f"{px}M", "Merge", [("Background", Src(f"{px}Back")), ("Foreground", Src(f"{px}Front"))], (220, 0))
    return make("Outline Giant", px, "Kinetic",
        "a giant black silhouette behind a slightly smaller coloured word, faking a bold outline",
        "Outline Giant - a larger dark silhouette sits just behind the coloured word, giving it a bold stroked look.",
        [back, front, merge], f"{px}M", common_kw=dict(inlen=8, hold=55, outlen=8))
EFFECTS.append(_outlinegiant())

# ---- 26 Ribbon Loop -----------------------------------------------------------------------------------
def _ribbonloop():
    px = "RL"
    rep = f'string.rep({WORD_U} .. "   -   ", 10)'
    ys = [0.28, 0.72]
    speeds = [4, -4]
    ribAlpha = "C.Opacity*0.35"
    ribNodes, ribNames = scrolling_ribbons(px, rep, 2, ys, speeds, 0.05, ribAlpha)
    slam = ttext(f"{px}Slam", T(TAGFULL), V(0.16), "C.Opacity", (400, 0))
    names = ribNames + [slam.name]
    prev = names[0]
    merges = []
    for nm in names[1:]:
        m = Node(f"{px}M{nm}", "Merge", [("Background", Src(prev)), ("Foreground", Src(nm))], (500, 0))
        merges.append(m)
        prev = m.name
    return make("Ribbon Loop", px, "Kinetic",
        "thin ribbons of repeating text loop past behind the tag while it holds",
        "Ribbon Loop - two thin ribbons of scrolling text loop continuously behind the tag for as long as it's held.",
        ribNodes + [slam] + merges, prev, common_kw=dict(inlen=8, hold=70, outlen=10))
EFFECTS.append(_ribbonloop())

# ---- 27 Ink Burst -------------------------------------------------------------------------------------
def _inkburst():
    px = "IB"
    blobs = [(-0.22, -0.15, 0, 0.22), (0.2, -0.1, 4, 0.16), (-0.1, 0.18, 8, 0.19),
             (0.15, 0.2, 2, 0.14), (0, -0.02, 6, 0.28)]
    nodes, names = [], []
    for i, (dx, dy, delay, scale) in enumerate(blobs):
        p = f"min(1,max(0,(time-{delay})/8))"
        a = f"({p})*C.Opacity"
        n = ttext(f"{px}B{i}", T('"•"'), E(scale * 3, f"{scale * 3}*{pop(p, 0.3)}"), a, (110 + i * 10, -120 + i * 40),
                  center=E("{ 0.5, 0.5 }", PT(f"0.5+{dx}", f"0.5+{dy}")), rgb=("0.03", "0.03", "0.03"))
        nodes.append(n)
        names.append(n.name)
    word = ttext(f"{px}Word", T(WORD_U), V(0.12), "iif(time<C.InLen*0.7,0,C.Opacity)", (400, 0))
    nodes.append(word)
    names.append(word.name)
    prev = names[0]
    merges = []
    for nm in names[1:]:
        m = Node(f"{px}M{nm}", "Merge", [("Background", Src(prev)), ("Foreground", Src(nm))], (500, 0))
        merges.append(m)
        prev = m.name
    return make("Ink Burst", px, "Kinetic",
        "scattered ink blots pop in and settle, then the word stamps on top",
        "Ink Burst - small ink-blot shapes pop in and scatter into place, then the word lands on top.",
        nodes + merges, prev, common_kw=dict(inlen=14, hold=55, outlen=10))
EFFECTS.append(_inkburst())

# ---- 28 Red Slash --------------------------------------------------------------------------------------
def _redslash():
    px = "RD"
    half = "max(1,floor(string.len(C.Word.Value)/2))"
    leftExpr = f"string.upper(string.sub(C.Word.Value,1,{half}))"
    rightExpr = f"string.upper(string.sub(C.Word.Value,{half}+1,string.len(C.Word.Value)))"
    leftX = f"(-1*(1-{ease_out('C.Prog')}) + {ease_out('C.OutProg')})"
    rightX = f"((1-{ease_out('C.Prog')}) - {ease_out('C.OutProg')})"
    leftT = ttext(f"{px}L", T(leftExpr), V(0.15), "C.Opacity", (110, -60),
                  center=E("{ 0.5, 0.5 }", PT(f"0.42+{leftX}*0.6", "0.5")))
    rightT = ttext(f"{px}R", T(rightExpr), V(0.15), "C.Opacity", (110, 60),
                   center=E("{ 0.5, 0.5 }", PT(f"0.58+{rightX}*0.6", "0.5")))
    merge = Node(f"{px}M", "Merge", [("Background", Src(f"{px}L")), ("Foreground", Src(f"{px}R"))], (220, 0))
    barText = ttext(f"{px}Bar", T('string.rep("―", 40)'), V(0.05),
                     "C.Opacity*max(0,1-abs(time-C.InLen)*0.3)", (220, -40), rgb=("C.PalR", "C.PalG", "C.PalB"))
    barTilt = Node(f"{px}BarT", "Transform", [("Input", Src(f"{px}Bar")), ("Angle", V(-18))], (320, -40))
    final = Node(f"{px}Fin", "Merge", [("Background", Src(f"{px}M")), ("Foreground", Src(f"{px}BarT"))], (420, 0))
    return make("Red Slash", px, "Kinetic",
        "the word splits in two and slides together from opposite sides, crossed by a bright flash",
        "Red Slash - the word splits into two halves that slide together from opposite sides, crossed by a quick bright flash.",
        [leftT, rightT, merge, barText, barTilt, final], f"{px}Fin",
        common_kw=dict(inlen=8, hold=55, outlen=8, palette=2))
EFFECTS.append(_redslash())


# ==========================================================================
#  .setting writer
# ==========================================================================
import re


def fusion_expr(e, fx, self_ref=False):
    if self_ref:
        e = re.sub(r"\bC\.(\w+)\.Value", lambda m: f"k{m.group(1)}.Value", e)
        return re.sub(r"\bC\.(\w+)", lambda m: f"k{m.group(1)}", e)
    return re.sub(r"\bC\.(\w+)", lambda m: f"{fx.ctrl}.k{m.group(1)}", e)


def user_control(cid, kind, name, default, ex, tip):
    L = []
    if kind == "label":
        L += [f'LINKS_Name = {q(name)}', 'LINKID_DataType = "Number"', 'INPID_InputControl = "LabelControl"',
              'INP_External = false', 'INP_Passive = true']
    elif kind == "combo":
        for opt in ex["combo"]:
            L.append(f'{{ CCS_AddString = {q(opt)}, }}')
        L += [f'LINKS_Name = {q(name)}', 'LINKID_DataType = "Number"', 'INPID_InputControl = "ComboControl"',
              'INP_Integer = true', 'CC_LabelPosition = "Horizontal"', f'INP_Default = {default}',
              'INP_MinScale = 0', f'INP_MaxScale = {len(ex["combo"])-1}',
              'INP_MinAllowed = 0', f'INP_MaxAllowed = {len(ex["combo"])-1}']
    elif kind == "check":
        L += [f'LINKS_Name = {q(name)}', 'LINKID_DataType = "Number"', 'INPID_InputControl = "CheckboxControl"',
              'INP_Integer = true', f'INP_Default = {default}', 'INP_MinScale = 0', 'INP_MaxScale = 1']
    elif kind == "text":
        L += [f'LINKS_Name = {q(name)}', 'LINKID_DataType = "Text"', 'INPID_InputControl = "TextEditControl"',
              f'TEC_Lines = {ex.get("lines", 1)}']
    else:
        L += [f'LINKS_Name = {q(name)}', 'LINKID_DataType = "Number"', 'INPID_InputControl = "SliderControl"',
              f'INP_Default = {default}']
        if kind == "int":
            L.append('INP_Integer = true')
        if "min" in ex: L.append(f'INP_MinScale = {ex["min"]}')
        if "max" in ex: L.append(f'INP_MaxScale = {ex["max"]}')
        if "amin" in ex: L.append(f'INP_MinAllowed = {ex["amin"]}')
        if "amax" in ex: L.append(f'INP_MaxAllowed = {ex["amax"]}')
    if tip:
        L.append(f'INPS_StatusText = {q(tip)}')
    L.append('ICS_ControlPage = "Controls"')
    return f"k{cid} = {{ " + ", ".join(L) + " },"


def hidden_control(cid):
    return (f'k{cid} = {{ LINKS_Name = "{cid}", LINKID_DataType = "Number", '
            f'INPID_InputControl = "SliderControl", IC_Visible = false, INP_Passive = true, '
            f'ICS_ControlPage = "Controls" }},')


def value_str(v, fx):
    if isinstance(v, Src):
        node = fx.ctrl if v.node == "C" else v.node
        return f'Input {{ SourceOp = "{node}", Source = "{v.out}", }}'
    if isinstance(v, E):
        return f"Input {{ Value = {v.default}, Expression = {q(fusion_expr(v.expr, fx))}, }}"
    return f"Input {{ Value = {v.v}, }}"


def build_setting(fx):
    T_ = "\t"
    o = ["{", f"{T_}Tools = ordered() {{", f"{T_*2}{fx.name} = MacroOperator {{",
         f"{T_*3}CtrlWZoom = false,", f"{T_*3}NameSet = true,",
         f"{T_*3}CustomData = {{ HelpPage = {q(fx.help)}, }},",
         f"{T_*3}Inputs = ordered() {{",
         f'{T_*4}MainInput1 = InstanceInput {{ SourceOp = "{fx.ctrl}", Source = "Input", }},']
    n = 1
    for cid, kind, cname, d, ex, tip in fx.controls:
        if kind == "label":
            o.append(f'{T_*4}Input{n} = InstanceInput {{ SourceOp = "{fx.ctrl}", Source = "k{cid}", }},')
        elif kind == "text":
            o.append(f'{T_*4}Input{n} = InstanceInput {{ SourceOp = "{fx.ctrl}", Source = "k{cid}", Name = {q(cname)}, }},')
        else:
            o.append(f'{T_*4}Input{n} = InstanceInput {{ SourceOp = "{fx.ctrl}", Source = "k{cid}", Name = {q(cname)}, Default = {d}, }},')
        n += 1
    o += [f"{T_*3}}},", f"{T_*3}Outputs = {{",
          f'{T_*4}MainOutput1 = InstanceOutput {{ SourceOp = "{fx.out}", Source = "Output", }},',
          f"{T_*3}}},", f"{T_*3}ViewInfo = GroupInfo {{ Pos = {{ 0, 0 }}, }},", f"{T_*3}Tools = ordered() {{"]

    o += [f"{T_*4}{fx.ctrl} = BrightnessContrast {{", f"{T_*5}CtrlWZoom = false,", f"{T_*5}NameSet = true,",
          f"{T_*5}Inputs = {{"]
    for cid, kind, _, d, _, _ in fx.controls:
        if kind == "label":
            continue
        if kind == "text":
            o.append(f"{T_*6}k{cid} = Input {{ Value = {q(d)}, }},")
        else:
            o.append(f"{T_*6}k{cid} = Input {{ Value = {d}, }},")
    for hid, expr in fx.hidden:
        o.append(f"{T_*6}k{hid} = Input {{ Value = 0, Expression = {q(fusion_expr(expr, fx, self_ref=True))}, }},")
    o += [f"{T_*5}}},", f"{T_*5}ViewInfo = OperatorInfo {{ Pos = {{ 0, 0 }}, }},", f"{T_*5}UserControls = ordered() {{"]
    for c in fx.controls:
        o.append(f"{T_*6}" + user_control(*c))
    for hid, _ in fx.hidden:
        o.append(f"{T_*6}" + hidden_control(hid))
    o += [f"{T_*5}}},", f"{T_*4}}},"]

    for nd in fx.nodes:
        o += [f"{T_*4}{nd.name} = {nd.kind} {{", f"{T_*5}CtrlWZoom = false,", f"{T_*5}NameSet = true,", f"{T_*5}Inputs = {{"]
        for k, v in nd.inputs:
            o.append(f"{T_*6}{k} = {value_str(v, fx)},")
        o += [f"{T_*5}}},", f"{T_*5}ViewInfo = OperatorInfo {{ Pos = {{ {nd.pos[0]}, {nd.pos[1]} }}, }},", f"{T_*4}}},"]
    o += [f"{T_*3}}},", f"{T_*2}}},", f"{T_}}},", f'{T_}ActiveTool = "{fx.name}"', "}"]
    return "\n".join(o) + "\n"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for f in os.listdir(OUT_DIR):
        if f.endswith(".setting"):
            os.remove(os.path.join(OUT_DIR, f))
    for fx in EFFECTS:
        with open(os.path.join(OUT_DIR, fx.name + ".setting"), "w", encoding="utf-8", newline="\n") as f:
            f.write(build_setting(fx))
    print("wrote", len(EFFECTS), "effects to", OUT_DIR)


if __name__ == "__main__":
    main()
