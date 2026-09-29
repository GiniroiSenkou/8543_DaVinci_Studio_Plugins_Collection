#!/usr/bin/env python3
"""
MangaPanels generator -- writes the Fusion macros (.setting) of the "MangaPanels"
pack for DaVinci Resolve's Edit page (Effects > MangaPanels).

The look: the "coloured manga panel" of anime character-intro cards. Your clip or
still is reduced to two tones (ink lines / shadows + paper), recoloured as a duotone
of one accent colour (ink = dark shade, paper = the accent), printed with a halftone
dot screen, paper grain and a slight colour misregistration. On top: a huge word
BEHIND the subject, an optional distressed vertical Japanese line, a small top
caption and a big bottom-left name. In / out animations, slow push-in.

One macro, four presets (same controls, different defaults):
    MangaPanels_PinkPortrait    hot pink, dots on paper, vertical text right, colour flash in
    MangaPanels_RedVictor       crimson, flat red field + huge white word behind the subject
    MangaPanels_Teal            teal, mid-tone screentone, vertical text left, halftone-grow in
    MangaPanels_Gold            gold, whole-frame screen, word slide + push-in

Node graph (every control + the hidden maths lives on MPCtrl; ids start with k):

    input -> MPCtrl (BrightnessContrast, pass-through)
          -> MPFit    Merge onto MPCanvas (transparent Background, W x H) = the panel canvas
                      (fill / fit, zoom, reframe, push-in)
          -> MPInk    CustomTool: r = ink (lines + shadows), g = tone, b = subject mask,
                      a = lines only
          -> MPDots   CustomTool: r = ink coverage incl. halftone screen + halftone-grow,
                      g/b = misregistration fringes
          -> MPColour CustomTool: duotone paper / ink colours, fringes, paper grain = the LOOK
          -> MPField  CustomTool: what sits BEHIND the subject (scene / flat / screentone /
                      transparent)
          -> + big word -> + vertical text (behind) -> + top line -> + name   = back plate
    look  -> + word*overlap -> + top*overlap -> + name*overlap -> MPSubj (alpha = mask)
                                                                       = front plate
    back plate + front plate -> + vertical text (in front) -> MPFinal (flash, border)

  * The macro builds its own canvas (default 1080x1920, 9:16), because a clip-level
    Fusion comp runs at the SOURCE clip's resolution (4K, 16:9...). The source size is
    read with  self.Input.OriginalWidth  (verified on Resolve 21.1), so no
    "source aspect" control is needed.
  * Sizes are "px at 1080" (scaled by the short side of the canvas / 1080).
  * CustomTool maths: + - * / min max abs floor sqrt sin cos (trig in DEGREES).
  * Colour pickers are tiny Background tools outside the image chain (MPPaperCol,
    MPInkCol) read through expressions.
  * Installed from a .drfx dragged onto Resolve, never as loose .setting files.

Usage:  python Giniroisenkou_MangaPanels_gen.py  -> build/Edit/Effects/MangaPanels/*.setting
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "build", "Edit", "Effects", "MangaPanels")
PACK = "MangaPanels"
CTRL = "MPCtrl"

# Text+ Size for a wanted em size in px:  px / W * LINE_H / TEXT_K   (FakeUI calibration)
TEXT_K = 0.81
LINE_H = {"Anton": 1.505, "Archivo Black": 1.088, "Noto Sans JP": 1.448, "Noto Sans JP Black": 1.448}

# ------------------------------------------------------------------ colours
# (name, paper = accent, ink = dark shade of the accent)
PALETTES = [
    ("Hot Pink",    (1.00, 0.36, 0.64), (0.29, 0.02, 0.15)),
    ("Magenta",     (0.93, 0.17, 0.68), (0.23, 0.00, 0.19)),
    ("Crimson Red", (0.86, 0.07, 0.13), (0.20, 0.00, 0.03)),
    ("Teal",        (0.13, 0.73, 0.73), (0.00, 0.15, 0.18)),
    ("Gold",        (0.98, 0.77, 0.22), (0.29, 0.16, 0.02)),
]
CUSTOM = len(PALETTES)                      # combo index of "Custom"
TEXT_COLOURS = ["White", "Paper colour", "Ink colour", "Black"]
CANVAS = [("9:16  1080 x 1920", 1080, 1920), ("4:5  1080 x 1350", 1080, 1350),
          ("1:1  1080 x 1080", 1080, 1080), ("16:9  1920 x 1080", 1920, 1080),
          ("9:16 4K  2160 x 3840", 2160, 3840), ("Same as clip", 0, 0)]

# ------------------------------------------------------------------ presets
BASE = dict(
    # look
    Palette=0, PaperCol=(1.0, 0.36, 0.64), InkCol=(0.29, 0.02, 0.15), Swap=0,
    Expo=1.2, Contrast=1.5, Shadow=0.16, ShadowSoft=0.02, LineW=2.0, LineAmt=1.5, LineThr=0.15,
    # halftone
    Tone=0, Dot=12.0, DotScale=1.0, DotAngle=45.0, Density=1.1, MidLo=0.30, MidHi=0.70, Texture=0.25,
    # print
    Grain=0.35, GrainSize=1.5, GrainAnim=1, Misreg=1.5, MisregAng=35.0, Border=0.0,
    # frame
    Canvas=0, Fit=0, Zoom=1.0, RX=0.0, RY=0.0, PushFrom=1.0, PushTo=1.06,
    # subject
    Layer=0, Mask=0, KeyThr=0.5, KeySoft=0.10, OvX=0.5, OvY=0.42, OvW=0.30, OvH=0.36, Behind=0,
    # big word
    ShowWord=1, Word="ICHIBAN", WordFont=("Anton", "Regular"), WordPx=520, WordCol=0, WordOp=1.0,
    WordSpacing=0.95, WordX=0.5, WordY=0.60, WordAngle=0.0, WordOver=0.0,
    # vertical text
    ShowVert=1, Vert="\u899a\u9192\u306e\u523b", VertFont=("Noto Sans JP", "Black"), VertPx=190, VertSide=0,
    VertY=0.93, VertMargin=40, VertCol=2, Rough=0.55, RoughSize=3.0, Jitter=2.0, VertFront=0,
    # captions
    ShowTop=1, Top="CHAPTER 01  \u2014  FIRST LIGHT", TopFont=("Archivo Black", "Regular"), TopPx=34, TopSpacing=1.25,
    ShowName=1, Name="YOUR NAME", NameFont=("Anton", "Regular"), NamePx=170, NameStretch=1.15, NameSpacing=1.0,
    CapCol=0, NameOver=0.6, Margin=60,
    # animation
    AnimIn=1, InLen=12, AnimOut=0, OutLen=10, FlashCol=0, SlideFrom=0,
)

PRESETS = {
    "PinkPortrait": dict(
        Palette=0, Tone=0, Dot=11.0, Texture=0.3, Behind=0,
        ShowWord=0, Word="HEART",
        Vert="\u60c5\u71b1\u306e\u8272", VertSide=0, VertCol=0,
        Top="CHAPTER 01  \u2014  PINK HOUR", Name="YOUR NAME", NameOver=0.5,
        AnimIn=1, AnimOut=0, PushFrom=1.0, PushTo=1.06),
    "RedVictor": dict(
        Palette=2, Tone=0, Dot=13.0, Texture=0.2, Shadow=0.14, Behind=1,
        ShowWord=1, Word="VICTORY", WordPx=380, WordCol=0, WordY=0.62, WordSpacing=0.92,
        ShowVert=0, Vert="\u52dd\u5229",
        ShowTop=1, Top="ROUND 01", Name="YOUR NAME", NamePx=190, NameOver=0.85, CapCol=0,
        AnimIn=4, AnimOut=3, InLen=14, SlideFrom=0),
    "Teal": dict(
        Palette=3, Tone=2, Dot=10.0, MidLo=0.28, MidHi=0.72, Texture=0.2, Behind=0,
        ShowWord=1, Word="CALM", WordPx=340, WordOp=0.35, WordCol=0, WordX=0.6, WordY=0.74,
        Vert="\u9759\u5bc2\u306e\u6d77", VertSide=1, VertCol=2,
        Top="EPISODE 02  \u2014  LOW TIDE", Name="YOUR NAME", CapCol=0, NameOver=0.5,
        AnimIn=2, InLen=18, AnimOut=2, OutLen=12),
    "Gold": dict(
        Palette=4, Tone=3, Dot=9.0, Density=1.0, Texture=0.0, Shadow=0.14, Behind=0,
        ShowWord=1, Word="GLORY", WordPx=400, WordCol=0, WordOp=0.9, WordX=0.58, WordY=0.64,
        Vert="\u6804\u5149\u3078", VertSide=1, VertCol=2,
        Top="FINAL ROUND", Name="YOUR NAME", CapCol=0, NameOver=0.6,
        AnimIn=3, InLen=14, AnimOut=3, PushFrom=1.0, PushTo=1.06),
}
PRESET_ORDER = ["PinkPortrait", "RedVictor", "Teal", "Gold"]


# ------------------------------------------------------------------ expression helpers
def clamp(e, lo=0, hi=1):
    return f"min(max({e},{lo}),{hi})"

def frac(e):
    return f"(({e})-floor({e}))"

def hsh(a, b):
    """pseudo random 0..1 (CustomTool trig is in degrees: the big factors make it chaotic anyway)"""
    return frac(f"sin(({a})*12.9898+({b})*78.233)*43758.5453")

def sel(e, i):
    """1 when e == i (integers), else 0 -- no comparison syntax in CustomTool"""
    return f"max(0,1-abs(({e})-{i}))"

def mix(a, b, t):
    return f"(({a})+(({b})-({a}))*({t}))"

def chain(sel_expr, values, last):
    """Ctrl-side lookup: iif(s==0, v0, iif(s==1, v1, ... last))"""
    e = str(last)
    for i in range(len(values) - 1, -1, -1):
        e = f"iif({sel_expr}=={i}, {values[i]}, {e})"
    return e

def cu(u):          # keep a sample coordinate 1.5 px inside the frame
    return clamp(u, "1.5/w", "1-1.5/w")

def cv(v):
    return clamp(v, "1.5/h", "1-1.5/h")

def lum_at(u, v):
    """luma of the premultiplied source, transparent = white paper"""
    return (f"(0.2126*getr1b({u},{v})+0.7152*getg1b({u},{v})+0.0722*getb1b({u},{v})"
            f"+1-geta1b({u},{v}))")

LUMA0 = "(0.2126*r1+0.7152*g1+0.0722*b1+1-a1)"


# ------------------------------------------------------------------ serializer
def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'

def num(v):
    return repr(round(v, 6)) if isinstance(v, float) else str(v)

def val(v):
    if isinstance(v, str):
        return q(v)
    if isinstance(v, (tuple, list)):
        return "{ " + ", ".join(num(x) for x in v) + " }"
    return num(v)

def X(e):
    """C.Name -> MPCtrl.kName"""
    return re.sub(r"\bC\.(\w+)", lambda m: f"{CTRL}.k{m.group(1)}", e)

def XS(e):
    """C.Name -> kName (inside the Ctrl itself)"""
    return re.sub(r"\bC\.(\w+)", lambda m: f"k{m.group(1)}", e)

def I(v=None, expr=None, src=None, out="Output"):
    if src:
        return f'Input {{ SourceOp = "{src}", Source = "{out}", }}'
    parts = []
    if v is not None:
        parts.append(f"Value = {val(v)}")
    if expr is not None:
        parts.append(f"Expression = {q(X(expr))}")
    return "Input { " + ", ".join(parts) + ", }"

def tool(name, regid, inputs, pos, extra=""):
    body = "".join(f"\t\t\t\t\t\t{k} = {v},\n" for k, v in inputs.items())
    return (f"\t\t\t\t{name} = {regid} {{\n\t\t\t\t\tCtrlWZoom = false,\n\t\t\t\t\tNameSet = true,\n"
            f"\t\t\t\t\tInputs = {{\n{body}\t\t\t\t\t}},\n{extra}"
            f"\t\t\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {pos[0]}, {pos[1]} }} }},\n\t\t\t\t}},\n")

def custom(name, image, pos, numbers=None, points=None, setup=None, inter=None, ch=None, image2=None):
    ins = {}
    for i, e in (numbers or {}).items():
        ins[f"NumberIn{i}"] = I(0, e)
    for i, e in (points or {}).items():
        ins[f"PointIn{i}"] = I((0.5, 0.5), e)
    for i, e in (setup or {}).items():
        ins[f"Setup{i}"] = I(e)
    for i, e in (inter or {}).items():
        ins[f"Intermediate{i}"] = I(e)
    names = {"r": "RedExpression", "g": "GreenExpression", "b": "BlueExpression", "a": "AlphaExpression"}
    for k in "rgba":
        ins[names[k]] = I((ch or {}).get(k, k + "1"))
    ins["Image1"] = I(src=image)
    if image2:
        ins["Image2"] = I(src=image2)
    return tool(name, "Custom", ins, pos)

def merge(name, bg, fg, pos, blend=None):
    ins = {"Background": I(src=bg), "Foreground": I(src=fg), "PerformDepthMerge": I(0)}
    if blend is not None:
        ins["Blend"] = I(1, blend)
    return tool(name, "Merge", ins, pos)

def holder(name, col, pos):
    return tool(name, "Background", {
        "UseFrameFormatSettings": I(0), "Width": I(8), "Height": I(8),
        "TopLeftRed": I(col[0]), "TopLeftGreen": I(col[1]), "TopLeftBlue": I(col[2]), "TopLeftAlpha": I(1),
    }, pos)


# ------------------------------------------------------------------ controls
def label(cid, text):
    return (cid, "label", text, None, "")

def fl(cid, name, lo, hi, tip, amin=None, amax=None):
    return (cid, "float", name, dict(min=lo, max=hi, amin=amin, amax=amax), tip)

def it(cid, name, lo, hi, tip, amin=None, amax=None):
    return (cid, "int", name, dict(min=lo, max=hi, amin=amin, amax=amax), tip)

def cb(cid, name, options, tip):
    return (cid, "combo", name, dict(combo=options), tip)

def ck(cid, name, tip):
    return (cid, "check", name, {}, tip)


def CONTROLS():
    return [
        label("LblLook", "LOOK  -  two tones + duotone"),
        cb("Palette", "Colour", [n for n, _, _ in PALETTES] + ["Custom (pickers below)"],
           "Accent colour. Paper = the accent, ink = a dark shade of it. Custom uses the two pickers."),
        ck("Swap", "Swap Ink / Paper", "Dark paper with bright ink (negative panel)."),
        fl("Expo", "Exposure", 0.3, 2.5, "Brighter = more paper, darker = more ink.", 0.05),
        fl("Contrast", "Contrast", 0.5, 3.0, "Contrast before the two-tone split.", 0.1),
        fl("Shadow", "Shadow Amount", 0.0, 0.8, "How much of the dark areas becomes solid ink.", 0, 1),
        fl("ShadowSoft", "Shadow Edge Softness", 0.0, 0.2, "0 = hard cut ink edge, higher = softer.", 0, 1),
        fl("LineW", "Line Weight (px at 1080)", 0.5, 8, "Thickness of the ink outlines.", 0.3),
        fl("LineAmt", "Line Amount", 0, 3, "How many outlines are drawn (0 = no outlines).", 0),
        fl("LineThr", "Line Threshold", 0, 1, "Ignore weak edges (texture, noise). Higher = cleaner.", 0),
        label("LblTone", "HALFTONE  -  printed dot screen"),
        cb("Tone", "Dots Sit On", ["Paper (light areas)", "Ink (paper dots in shadows)", "Mid-tones only",
                                   "Whole frame (pure halftone)", "Off"],
           "Which tone the dot screen is printed on."),
        fl("Dot", "Dot Size (px at 1080)", 4, 40, "Distance between dots.", 2),
        fl("DotScale", "Dot Scale", 0.3, 2, "Size of each dot inside its cell.", 0.05),
        fl("DotAngle", "Screen Angle", 0, 90, "Rotation of the dot grid (45 = classic).", -360, 360),
        fl("Density", "Dot Density", 0, 3, "More / fewer dots for the same image.", 0),
        fl("MidLo", "Mid-tone Low", 0, 1, "Mid-tones only: darkest tone that gets dots.", 0, 1),
        fl("MidHi", "Mid-tone High", 0, 1, "Mid-tones only: lightest tone that gets dots.", 0, 1),
        fl("Texture", "Screen Texture", 0, 1, "Faint dots across the whole frame, like printed paper.", 0, 1),
        label("LblPrint", "PRINT  -  paper and press"),
        fl("Grain", "Paper Grain", 0, 1, "Paper texture / print noise.", 0),
        fl("GrainSize", "Grain Size (px at 1080)", 1, 6, "Bigger = coarser paper.", 1),
        ck("GrainAnim", "Animated Grain", "Grain changes every frame (off = printed page stays still)."),
        fl("Misreg", "Misregistration (px)", 0, 4, "Colour plate offset of 1-3 px, like a cheap print.", 0),
        fl("MisregAng", "Misregistration Angle", -180, 180, "Direction of the offset in degrees."),
        fl("Border", "Panel Border (px at 1080)", 0, 40, "Ink frame around the panel (0 = none).", 0),
        label("LblFrame", "FRAME"),
        cb("Canvas", "Canvas", [n for n, _, _ in CANVAS],
           "Output size. 9:16 fills a vertical timeline; Same as clip keeps the source size."),
        cb("Fit", "Fit", ["Fill (crop)", "Fit (whole picture)"], "Fill crops the clip to the canvas; Fit shows it all on paper."),
        fl("Zoom", "Zoom", 0.5, 3, "Extra zoom on the clip.", 0.1),
        fl("RX", "Reframe X", -1, 1, "Slide the clip left / right inside the canvas (edge to edge).", -1, 1),
        fl("RY", "Reframe Y", -1, 1, "Slide the clip up / down.", -1, 1),
        fl("PushFrom", "Push-In From", 0.8, 1.3, "Zoom at the first frame of the clip.", 0.5),
        fl("PushTo", "Push-In To", 0.8, 1.3, "Zoom at the last frame (1.06 = slow push-in; same value = off).", 0.5),
        label("LblSubj", "SUBJECT  -  depth sandwich"),
        cb("Layer", "Layer", ["Full panel (one clip)", "Back plate (track below)", "Front subject (Magic Mask copy)"],
           "Full = everything on one clip. With Magic Mask: Back plate on the lower track, Front subject on "
           "a copy above it with Magic Mask (alpha out) in the Color page."),
        cb("Mask", "Subject Mask", ["None (text over everything)", "Clip alpha (cut-out / transparency)",
                                    "Luma key: bright subject", "Luma key: dark subject", "Green screen",
                                    "Oval holdout (no Studio)"],
           "What is 'the subject' that sits in front of the big word (Full panel only)."),
        fl("KeyThr", "Key Threshold", 0, 1, "Luma / green keys: where the subject starts.", 0, 1),
        fl("KeySoft", "Key / Oval Softness", 0.01, 0.5, "Softness of the mask edge.", 0.005),
        fl("OvX", "Oval Centre X", 0, 1, "Oval holdout position (0 = left, 1 = right)."),
        fl("OvY", "Oval Centre Y", 0, 1, "Oval holdout position (0 = bottom, 1 = top)."),
        fl("OvW", "Oval Width", 0.02, 1, "Oval width (fraction of the canvas width).", 0.01),
        fl("OvH", "Oval Height", 0.02, 1, "Oval height (fraction of the canvas height).", 0.01),
        cb("Behind", "Behind The Subject", ["Manga scene", "Flat paper colour", "Screentone field",
                                            "Transparent (layer over other tracks)"],
           "What fills the panel behind the subject. Flat colour + a big word = the classic intro card."),
        label("LblWord", "BIG WORD  -  behind the subject"),
        ck("ShowWord", "Show Big Word", "Huge word behind the subject."),
        cb("WordCol", "Word Colour", TEXT_COLOURS, "Colour of the big word."),
        fl("WordOp", "Word Opacity", 0, 1, "Opacity of the big word.", 0, 1),
        fl("WordX", "Word Position X", 0, 1, "Horizontal centre of the word."),
        fl("WordY", "Word Position Y", 0, 1, "Vertical centre of the word (0 = bottom, 1 = top)."),
        fl("WordOver", "Word Over Subject", 0, 1, "0 = fully behind the subject, 1 = on top of it.", 0, 1),
        label("LblVert", "VERTICAL TEXT  -  distressed ink"),
        ck("ShowVert", "Show Vertical Text", "Big vertical Japanese line down one side."),
        cb("VertSide", "Side", ["Right", "Left"], "Which side of the panel."),
        fl("VertY", "Start Height", 0.3, 1, "Where the first character sits (1 = top).", 0, 1),
        it("VertMargin", "Side Margin (px at 1080)", 0, 300, "Distance from the panel edge.", 0),
        cb("VertCol", "Vertical Text Colour", TEXT_COLOURS, "Ink colour is the classic look."),
        fl("Rough", "Roughness", 0, 1, "Distressed, eaten edges and speckles (0 = clean).", 0, 1),
        fl("RoughSize", "Rough Grain (px at 1080)", 1, 12, "Size of the speckles.", 0.5),
        fl("Jitter", "Edge Jitter (px at 1080)", 0, 8, "Wobble of the letter edges.", 0),
        ck("VertFront", "In Front Of Subject", "Off = behind the subject, on = over everything."),
        label("LblCap", "CAPTIONS  -  top line + name"),
        ck("ShowTop", "Show Top Line", "Small caption at the top centre."),
        ck("ShowName", "Show Name", "Big wide name at the bottom left."),
        fl("NameStretch", "Name Width Stretch", 0.6, 2.0, "Makes the name wider (1 = normal).", 0.3),
        cb("CapCol", "Caption Colour", TEXT_COLOURS, "Colour of the top line and the name."),
        fl("NameOver", "Captions Over Subject", 0, 1,
           "Opacity of the captions where they cross the subject (1 = solid on top, 0.5 = see-through).", 0, 1),
        it("Margin", "Caption Margin (px at 1080)", 0, 300, "Distance of the captions from the panel edge.", 0),
        label("LblAnim", "ANIMATION"),
        cb("AnimIn", "In", ["Hard cut", "Colour flash", "Halftone dots grow", "Word slide", "Flash + word slide"],
           "How the panel appears at the start of the clip."),
        it("InLen", "In Length (frames)", 1, 60, "Length of the In animation.", 1),
        cb("AnimOut", "Out", ["Hard cut", "Colour flash", "Halftone dots shrink", "Word slide out"],
           "How the panel leaves at the end of the clip. Trim the clip to set when."),
        it("OutLen", "Out Length (frames)", 1, 60, "Length of the Out animation.", 1),
        cb("FlashCol", "Flash Colour", ["White", "Paper colour", "Ink colour"], "Colour of the flash frames."),
        cb("SlideFrom", "Word Slides From", ["Right", "Left"], "Direction of the word slide."),
    ]


def HIDDEN():
    pal = PALETTES
    Kp = [f"C.PaperCol{c}" for c in "RGB"]
    return [
        # frame: source size, canvas size, fill scale
        ("SW", "max(self.Input.OriginalWidth,16)"),
        ("SH", "max(self.Input.OriginalHeight,16)"),
        ("W", chain("C.Canvas", [w for _, w, _ in CANVAS[:-1]], "min(C.SW,8192)")),
        ("H", chain("C.Canvas", [h for _, _, h in CANVAS[:-1]], "min(C.SH,8192)")),
        ("K", "min(C.W,C.H)/1080"),
        ("T", "time-comp.RenderStart"),
        ("DUR", "max(comp.RenderEnd-comp.RenderStart,1)"),
        ("PUSH", "C.PushFrom+(C.PushTo-C.PushFrom)*min(max(C.T/C.DUR,0),1)"),
        ("FS", "min(max(iif(C.Fit==0, max(C.W/C.SW, C.H/C.SH), min(C.W/C.SW, C.H/C.SH))*C.Zoom*C.PUSH,0.02),8)"),
        ("PX", "0.5+C.RX*max(C.FS*C.SW/C.W-1,0)*0.5"),
        ("PY", "0.5+C.RY*max(C.FS*C.SH/C.H-1,0)*0.5"),
        # colours (preset / custom picker, optional swap)
        ("PR0", chain("C.Palette", [p[1][0] for p in pal], "MPPaperCol.TopLeftRed")),
        ("PG0", chain("C.Palette", [p[1][1] for p in pal], "MPPaperCol.TopLeftGreen")),
        ("PB0", chain("C.Palette", [p[1][2] for p in pal], "MPPaperCol.TopLeftBlue")),
        ("IR0", chain("C.Palette", [p[2][0] for p in pal], "MPInkCol.TopLeftRed")),
        ("IG0", chain("C.Palette", [p[2][1] for p in pal], "MPInkCol.TopLeftGreen")),
        ("IB0", chain("C.Palette", [p[2][2] for p in pal], "MPInkCol.TopLeftBlue")),
        ("PR", "iif(C.Swap==1, C.IR0, C.PR0)"), ("PG", "iif(C.Swap==1, C.IG0, C.PG0)"), ("PB", "iif(C.Swap==1, C.IB0, C.PB0)"),
        ("IR", "iif(C.Swap==1, C.PR0, C.IR0)"), ("IG", "iif(C.Swap==1, C.PG0, C.IG0)"), ("IB", "iif(C.Swap==1, C.PB0, C.IB0)"),
        # text colours: White / Paper / Ink / Black
        *[(f"{p}{c}", chain(f"C.{src}", ["1", f"C.P{c}", f"C.I{c}"], "0"))
          for p, src in (("WC", "WordCol"), ("VC", "VertCol"), ("CC", "CapCol")) for c in "RGB"],
        # animation
        ("PI", "min(max(C.T/max(C.InLen,1),0),1)"),
        ("PO", "min(max((C.T-(C.DUR-C.OutLen))/max(C.OutLen,1),0),1)"),
        ("FLASH", "iif(C.AnimIn==1 or C.AnimIn==4, (1-C.PI)*(1-C.PI), 0)+iif(C.AnimOut==1, C.PO*C.PO, 0)"),
        ("HGA", "iif(C.AnimIn==2, 1-C.PI, 0)+iif(C.AnimOut==2, C.PO, 0)"),
        ("SLIDE", "iif(C.AnimIn==3 or C.AnimIn==4, (1-C.PI)*(1-C.PI)*(1-C.PI), 0)*1.3"
                  "-iif(C.AnimOut==3, C.PO*C.PO*C.PO, 0)*1.3"),
        ("SDIR", "iif(C.SlideFrom==0, 1, -1)"),
        ("FR", chain("C.FlashCol", ["1", "C.PR"], "C.IR")),
        ("FG", chain("C.FlashCol", ["1", "C.PG"], "C.IG")),
        ("FB", chain("C.FlashCol", ["1", "C.PB"], "C.IB")),
        ("SEED", "iif(C.GrainAnim==1, C.T, 0)"),
        ("RSEED", "floor(C.T/3)"),
    ]


# ------------------------------------------------------------------ the node graph
def build(pname, p):
    name = f"{PACK}_{pname}"
    tools = []
    T = tools.append

    # ---- controls node (pass-through)
    ctrls = CONTROLS()
    ins = {}
    for cid, kind, _, _, _ in ctrls:
        if kind != "label":
            ins["k" + cid] = I(p[cid])
    for hid, e in HIDDEN():
        ins["k" + hid] = f"Input {{ Value = 0, Expression = {q(XS(e))}, }}"
    uc = ["\t\t\t\t\tUserControls = ordered() {\n"]
    for cid, kind, cname, ex, tip in ctrls:
        L = []
        if kind == "label":
            L += [f"LINKS_Name = {q(cname)}", 'LINKID_DataType = "Number"', 'INPID_InputControl = "LabelControl"',
                  "INP_External = false", "INP_Passive = true"]
        elif kind == "combo":
            L += [f"{{ CCS_AddString = {q(o)}, }}" for o in ex["combo"]]
            L += [f"LINKS_Name = {q(cname)}", 'LINKID_DataType = "Number"', 'INPID_InputControl = "ComboControl"',
                  "INP_Integer = true", 'CC_LabelPosition = "Horizontal"', f"INP_Default = {p[cid]}",
                  "INP_MinScale = 0", f"INP_MaxScale = {len(ex['combo']) - 1}", "INP_MinAllowed = 0",
                  f"INP_MaxAllowed = {len(ex['combo']) - 1}"]
        elif kind == "check":
            L += [f"LINKS_Name = {q(cname)}", 'LINKID_DataType = "Number"', 'INPID_InputControl = "CheckboxControl"',
                  "INP_Integer = true", f"INP_Default = {p[cid]}", "INP_MinScale = 0", "INP_MaxScale = 1"]
        else:
            L += [f"LINKS_Name = {q(cname)}", 'LINKID_DataType = "Number"', 'INPID_InputControl = "SliderControl"',
                  f"INP_Default = {num(p[cid])}", f"INP_MinScale = {ex['min']}", f"INP_MaxScale = {ex['max']}"]
            if kind == "int":
                L.append("INP_Integer = true")
            if ex.get("amin") is not None:
                L.append(f"INP_MinAllowed = {ex['amin']}")
            if ex.get("amax") is not None:
                L.append(f"INP_MaxAllowed = {ex['amax']}")
        if tip:
            L.append(f"INPS_StatusText = {q(tip)}")
        L.append('ICS_ControlPage = "Controls"')
        uc.append(f"\t\t\t\t\t\tk{cid} = {{ " + ", ".join(L) + " },\n")
    for hid, _ in HIDDEN():
        uc.append(f'\t\t\t\t\t\tk{hid} = {{ LINKS_Name = "{hid}", LINKID_DataType = "Number", '
                  'INPID_InputControl = "SliderControl", IC_Visible = false, INP_Passive = true, '
                  'ICS_ControlPage = "Controls" },\n')
    uc.append("\t\t\t\t\t},\n")
    T(tool(CTRL, "BrightnessContrast", ins, (0, 0), extra="".join(uc)))

    # ---- colour pickers (not in the image chain)
    T(holder("MPPaperCol", p["PaperCol"], (0, -150)))
    T(holder("MPInkCol", p["InkCol"], (110, -150)))

    # ---- canvas + fit
    T(tool("MPCanvas", "Background", {
        "UseFrameFormatSettings": I(0), "Width": I(1080, "C.W"), "Height": I(1920, "C.H"),
        "TopLeftRed": I(0), "TopLeftGreen": I(0), "TopLeftBlue": I(0), "TopLeftAlpha": I(0),
    }, (110, -60)))
    T(tool("MPFit", "Merge", {
        "Background": I(src="MPCanvas"), "Foreground": I(src=CTRL), "PerformDepthMerge": I(0),
        "Size": I(1, "C.FS"), "Center": I((0.5, 0.5), "Point(C.PX, C.PY)"),
    }, (110, 0)))

    # ---- MPInk: two tones + subject mask
    taps = []
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1), (0.7071, 0.7071), (-0.7071, 0.7071),
                   (0.7071, -0.7071), (-0.7071, -0.7071)]:
        u = cu(f"x+({dx})*s1") if dx else "x"
        v = cv(f"y+({dy})*s2") if dy else "y"
        taps.append(lum_at(u, v))
    mean = "((" + "+".join(taps) + ")/8)"
    Lc = clamp(f"(({LUMA0})*n1-0.5)*n2+0.5")
    line = clamp(f"({mean}-({LUMA0})-n3*0.1)*n4*12")
    shadow = clamp("(n5-i1)/max(n6,0.004)+0.5")
    ks = "max(p3x,0.005)"
    ov = f"sqrt(((x-p1x)/max(p2x*0.5,0.001))*((x-p1x)/max(p2x*0.5,0.001))+((y-p1y)/max(p2y*0.5,0.001))*((y-p1y)/max(p2y*0.5,0.001)))"
    subj = (f"{sel('n7', 1)}*a1"
            f"+{sel('n7', 2)}*{clamp(f'(i1-n8)/{ks}+0.5')}*a1"
            f"+{sel('n7', 3)}*{clamp(f'(n8-i1)/{ks}+0.5')}*a1"
            f"+{sel('n7', 4)}*{clamp(f'(n8*0.4-(g1-max(r1,b1)))/{ks}+0.5')}*a1"
            f"+{sel('n7', 5)}*{clamp(f'(1-{ov})/({ks}*4)+0.5')}")
    T(custom("MPInk", "MPFit", (220, 0),
             numbers={1: "C.Expo", 2: "C.Contrast", 3: "C.LineThr", 4: "C.LineAmt", 5: "C.Shadow",
                      6: "C.ShadowSoft", 7: "C.Mask", 8: "C.KeyThr"},
             points={1: "Point(C.OvX, C.OvY)", 2: "Point(C.OvW, C.OvH)", 3: "Point(C.KeySoft, C.LineW)"},
             setup={1: "max(p3y*min(w,h)/1080,0.5)/w", 2: "max(p3y*min(w,h)/1080,0.5)/h"},
             inter={1: Lc, 2: line},
             ch={"r": "max(i2," + shadow + ")", "g": "i1", "b": subj, "a": "i2"}))

    # ---- MPDots: halftone screen, halftone-grow, misregistration fringes
    px, py = "(x*w)", "(y*h)"
    rx = f"({px}*n3+{py}*n4)"
    ry = f"(-{px}*n4+{py}*n3)"
    cx = f"((floor({rx}/s1)+0.5)*s1)"
    cy = f"((floor({ry}/s1)+0.5)*s1)"
    BX = f"(min(max(({cx})*n3-({cy})*n4,1.5),w-1.5)/w)"
    BY = f"(min(max(({cx})*n4+({cy})*n3,1.5),h-1.5)/h)"
    DD = f"sqrt(({rx}-{cx})*({rx}-{cx})+({ry}-{cy})*({ry}-{cy}))"
    tone = "getg1b(i1,i2)"

    def dot(f, k="1"):
        return clamp(f"s1*0.5*sqrt(max({f},0))*1.42*n2*({k})-i3+0.5")
    d_paper = clamp(f"(0.75-{tone})*n6*1.4")
    d_ink = clamp(f"({tone}-0.1)*n6*1.2")
    d_mid = clamp(f"(p2y-{tone})/max(p2y-p2x,0.01)*n6") + f"*{clamp(f'({tone}-p2x)*40+1')}"
    cov = (f"{sel('n5', 0)}*max(r1,{dot(d_paper)})"
           f"+{sel('n5', 1)}*r1*(1-{dot(d_ink)})"
           f"+{sel('n5', 2)}*max(r1,{dot(d_mid)})"
           f"+{sel('n5', 3)}*max(a1,{dot(d_paper)})"
           f"+{sel('n5', 4)}*r1")
    tex = clamp("s1*0.17*n2-i3+0.5") + "*n7"
    grow = dot(d_paper, "(1-n8)")
    full = mix(f"max({cov},{tex})", grow, "min(n8*4,1)")
    shifted = "getr1b(" + cu("x+s2") + "," + cv("y+s3") + ")"
    T(custom("MPDots", "MPInk", (330, 0),
             numbers={1: "C.Dot", 2: "C.DotScale", 3: "cos(C.DotAngle*0.0174533)", 4: "sin(C.DotAngle*0.0174533)",
                      5: "C.Tone", 6: "C.Density", 7: "C.Texture", 8: "C.HGA"},
             points={1: "Point(C.Misreg*cos(C.MisregAng*0.0174533), C.Misreg*sin(C.MisregAng*0.0174533))",
                     2: "Point(C.MidLo, C.MidHi)"},
             setup={1: "max(n1*min(w,h)/1080,2)", 2: "p1x*min(w,h)/1080/w", 3: "p1y*min(w,h)/1080/h"},
             inter={1: BX, 2: BY, 3: DD},
             ch={"r": clamp(full), "g": clamp(f"{shifted}-r1") + "*(1-min(n8*4,1))",
                 "b": clamp(f"r1-{shifted}") + "*(1-min(n8*4,1))", "a": "1"}))

    # ---- MPColour: duotone + fringes + paper grain  (= the look)
    G = f"(({hsh('floor(x*w/s1)+n8*0.37', 'floor(y*h/s1)+n8*1.91')})-0.5)"
    Gb = f"(({hsh('floor(x*w/(s1*7))+n8*0.11', 'floor(y*h/(s1*7))+3.7')})-0.5)"

    def colour(pc, ic):
        base = mix(pc, ic, "r1")
        fa = mix(base, f"(({pc})+({ic}))*0.5", "g1*(1-r1)")
        fb = mix(fa, "1", "b1*0.55")
        return f"max(({fb})*(1+({G}*0.8+{Gb}*0.35)*n7*0.45),0)"
    T(custom("MPColour", "MPDots", (440, 0),
             numbers={1: "C.PR", 2: "C.PG", 3: "C.PB", 4: "C.IR", 5: "C.IG", 6: "C.IB", 7: "C.Grain", 8: "C.SEED"},
             points={1: "Point(C.GrainSize, 0)"},
             setup={1: "max(p1x*min(w,h)/1080,1)"},
             ch={"r": colour("n1", "n4"), "g": colour("n2", "n5"), "b": colour("n3", "n6"), "a": "1"}))

    # ---- MPField: what sits behind the subject
    frx = "((x*w+y*h)*0.7071)"
    fry = "((-x*w+y*h)*0.7071)"
    fcx = f"((floor({frx}/s1)+0.5)*s1)"
    fcy = f"((floor({fry}/s1)+0.5)*s1)"
    fdd = f"sqrt(({frx}-{fcx})*({frx}-{fcx})+({fry}-{fcy})*({fry}-{fcy}))"
    fdot = clamp(f"s1*0.5*sqrt({clamp('(0.75-y)*0.9')})*1.42-{fdd}+0.5")

    def field(c, pc, ic):
        return (f"{sel('n1', 0)}*{c}1+{sel('n1', 1)}*{pc}"
                f"+{sel('n1', 2)}*{mix(pc, ic, fdot)}")
    T(custom("MPField", "MPColour", (550, 0),
             numbers={1: "C.Behind", 2: "C.PR", 3: "C.PG", 4: "C.PB", 5: "C.IR", 6: "C.IG", 7: "C.IB", 8: "C.Dot"},
             setup={1: "max(n8*1.6*min(w,h)/1080,3)"},
             ch={"r": field("r", "n2", "n5"), "g": field("g", "n3", "n6"), "b": field("b", "n4", "n7"),
                 "a": f"1-{sel('n1', 3)}"}))

    # ---- text layers
    def text(nm, key, font, px, colpfx, pos, extra=None):
        lh = LINE_H.get(font[0], 1.2)
        ins = {
            "UseFrameFormatSettings": I(0), "Width": I(1080, "C.W"), "Height": I(1920, "C.H"),
            "StyledText": I(p[key]), "Font": I(font[0]), "Style": I(font[1]),
            "Size": I(0.1, f"{nm}.PxSize*C.K/C.W*{lh}/{TEXT_K}"),
            "Red1": I(1, f"C.{colpfx}R"), "Green1": I(1, f"C.{colpfx}G"), "Blue1": I(1, f"C.{colpfx}B"),
            "Alpha1": I(1), "PxSize": I(px),
        }
        ins.update(extra or {})
        ucs = (f"\t\t\t\t\tUserControls = ordered() {{ PxSize = {{ LINKS_Name = \"Size (px at 1080)\", "
               f"LINKID_DataType = \"Number\", INPID_InputControl = \"SliderControl\", INP_Default = {px}, "
               f"INP_MinScale = 8, INP_MaxScale = 900, INP_MinAllowed = 1, ICS_ControlPage = \"Text\", }}, }},\n")
        return tool(nm, "TextPlus", ins, pos, extra=ucs)

    T(text("MPWord", "Word", p["WordFont"], p["WordPx"], "WC", (660, -160), {
        "Center": I((0.5, 0.5), "Point(C.WordX+C.SLIDE*C.SDIR, C.WordY)"),
        "CharacterSpacing": I(p["WordSpacing"]), "AngleZ": I(0.0),
        "HorizontalLeftCenterRight": I(0), "VerticalTopCenterBottom": I(0),
    }))
    T(text("MPVert", "Vert", p["VertFont"], p["VertPx"], "VC", (660, -110), {
        "Center": I((0.9, 0.9), "Point(iif(C.VertSide==0, 1-C.VertMargin*C.K/C.W, C.VertMargin*C.K/C.W), C.VertY)"),
        "Direction": I(3), "LineDirection": I(0), "Orientation": I(1),
        "HorizontalLeftCenterRight": I(0, "iif(C.VertSide==0, 1, -1)"), "VerticalTopCenterBottom": I(-1),
    }))
    rough_a = "geta1b(" + cu(f"x+({hsh('floor(y*h/2)', 'n3+5.3')}-0.5)*s2") + "," + cv(
        f"y+({hsh('floor(x*w/2)', 'n3+9.1')}-0.5)*s3") + ")"
    rn = f"(0.6*{hsh('floor(x*w/s1)', 'floor(y*h/s1)+n3*0.13')}+0.4*{hsh('floor(x*w/(s1*5))', 'floor(y*h/(s1*5))+2.1')})"
    ra = clamp(f"({rough_a}-n1*{rn})/max(1-n1*0.7,0.25)")
    T(custom("MPVertRough", "MPVert", (660, -60),
             numbers={1: "C.Rough", 2: "C.RoughSize", 3: "C.RSEED", 4: "C.Jitter"},
             setup={1: "max(n2*min(w,h)/1080,1)", 2: "n4*min(w,h)/1080/w", 3: "n4*min(w,h)/1080/h"},
             inter={1: ra},
             ch={"r": "r1/max(a1,0.0001)*i1", "g": "g1/max(a1,0.0001)*i1", "b": "b1/max(a1,0.0001)*i1", "a": "i1"}))
    T(text("MPTop", "Top", p["TopFont"], p["TopPx"], "CC", (770, -160), {
        "Center": I((0.5, 0.95), "Point(0.5, 1-C.Margin*C.K/C.H)"),
        "CharacterSpacing": I(p["TopSpacing"]),
        "HorizontalLeftCenterRight": I(0), "VerticalTopCenterBottom": I(-1),
    }))
    T(text("MPName", "Name", p["NameFont"], p["NamePx"], "CC", (880, -160), {
        "Center": I((0.05, 0.05), "Point(C.Margin*C.K/C.W, C.Margin*C.K/C.H)"),
        "CharacterSpacing": I(p["NameSpacing"]),
        "HorizontalLeftCenterRight": I(-1), "VerticalTopCenterBottom": I(1),
    }))
    T(tool("MPNameXf", "Transform", {
        "Input": I(src="MPName"),
        "Center": I((0.5, 0.5)),
        "Pivot": I((0.05, 0.05), "Point(C.Margin*C.K/C.W, C.Margin*C.K/C.H)"),
        "Size": I(1, "C.NameStretch"), "Aspect": I(1, "1/max(C.NameStretch,0.01)"),
    }, (880, -110)))

    # ---- back plate
    T(merge("MPB1", "MPField", "MPWord", (660, 0), "C.ShowWord*C.WordOp"))
    T(merge("MPB2", "MPB1", "MPVertRough", (770, 0), "C.ShowVert*(1-C.VertFront)"))
    T(merge("MPB3", "MPB2", "MPTop", (880, 0), "C.ShowTop"))
    T(merge("MPB4", "MPB3", "MPNameXf", (990, 0), "C.ShowName"))
    # ---- front plate (subject)
    T(merge("MPF1", "MPColour", "MPWord", (660, 120), "C.ShowWord*C.WordOp*C.WordOver"))
    T(merge("MPF2", "MPF1", "MPTop", (770, 120), "C.ShowTop*C.NameOver"))
    T(merge("MPF3", "MPF2", "MPNameXf", (880, 120), "C.ShowName*C.NameOver"))
    se = f"({sel('n1', 0)}*b2+{sel('n1', 2)})"
    T(custom("MPSubj", "MPF3", (990, 120), numbers={1: "C.Layer"}, image2="MPInk",
             ch={"r": f"r1*{se}", "g": f"g1*{se}", "b": f"b1*{se}", "a": f"a1*{se}"}))
    T(merge("MPAll", "MPB4", "MPSubj", (1100, 0)))
    T(merge("MPVF", "MPAll", "MPVertRough", (1210, 0), "C.ShowVert*C.VertFront"))

    # ---- MPFinal: colour flash + panel border
    inside = "min(min(x*w,(1-x)*w),min(y*h,(1-y)*h))"
    bm = clamp(f"s1-{inside}+0.5") + "*min(n5,1)"

    def fin(c, fc, ic):
        return mix(mix(f"{c}1", ic, bm), fc, "n1")
    T(custom("MPFinal", "MPVF", (1320, 0),
             numbers={1: "C.FLASH", 2: "C.FR", 3: "C.FG", 4: "C.FB", 5: "C.Border", 6: "C.IR", 7: "C.IG", 8: "C.IB"},
             setup={1: "n5*min(w,h)/1080"},
             ch={"r": fin("r", "n2", "n6"), "g": fin("g", "n3", "n7"), "b": fin("b", "n4", "n8"),
                 "a": mix(mix("a1", "1", bm), "1", "n1")}))
    out = "MPFinal"

    # ---------------------------------------------------------- Inspector (order = on screen)
    L = []
    idx = [0]
    g = [100]

    def add(op, src, nm=None, default=None, group=None):
        idx[0] += 1
        s = f'Input{idx[0]} = InstanceInput {{ SourceOp = "{op}", Source = "{src}"'
        if nm:
            s += f", Name = {q(nm)}"
        if group is not None:
            s += f", ControlGroup = {group}"
        if default is not None:
            s += f", Default = {q(default) if isinstance(default, str) else num(default)}"
        L.append(s + ", }")

    def grp():
        g[0] += 1
        return g[0]

    def color(op, label_, col):
        gg = grp()
        add(op, "TopLeftRed", label_, col[0], gg)
        add(op, "TopLeftGreen", None, col[1], gg)
        add(op, "TopLeftBlue", None, col[2], gg)

    cmap = {c[0]: c for c in ctrls}

    def cc(*cids):
        for cid in cids:
            c = cmap[cid]
            if c[1] == "label":
                add(CTRL, "k" + cid)
            else:
                add(CTRL, "k" + cid, c[2], p[cid])

    def txt(op, key, lab, font_lab):
        add(op, "StyledText", lab)
        gf = grp()
        add(op, "Font", font_lab + " Font", group=gf)
        add(op, "Style", font_lab + " Style", group=gf)
        add(op, "PxSize", font_lab + " Size (px at 1080)", None)

    cc("LblLook", "Palette")
    color("MPPaperCol", "Custom Paper Colour", p["PaperCol"])
    color("MPInkCol", "Custom Ink Colour", p["InkCol"])
    cc("Swap", "Expo", "Contrast", "Shadow", "ShadowSoft", "LineW", "LineAmt", "LineThr",
       "LblTone", "Tone", "Dot", "DotScale", "DotAngle", "Density", "MidLo", "MidHi", "Texture",
       "LblPrint", "Grain", "GrainSize", "GrainAnim", "Misreg", "MisregAng", "Border",
       "LblFrame", "Canvas", "Fit", "Zoom", "RX", "RY", "PushFrom", "PushTo",
       "LblSubj", "Layer", "Mask", "KeyThr", "KeySoft", "OvX", "OvY", "OvW", "OvH", "Behind",
       "LblWord", "ShowWord")
    txt("MPWord", "Word", "Word", "Word")
    add("MPWord", "CharacterSpacing", "Word Letter Spacing", p["WordSpacing"])
    add("MPWord", "AngleZ", "Word Rotation", 0.0)
    cc("WordCol", "WordOp", "WordX", "WordY", "WordOver", "LblVert", "ShowVert")
    txt("MPVert", "Vert", "Vertical Text", "Vertical")
    cc("VertSide", "VertY", "VertMargin", "VertCol", "Rough", "RoughSize", "Jitter", "VertFront",
       "LblCap", "ShowTop")
    txt("MPTop", "Top", "Top Line", "Top Line")
    add("MPTop", "CharacterSpacing", "Top Line Letter Spacing", p["TopSpacing"])
    cc("ShowName")
    txt("MPName", "Name", "Name", "Name")
    add("MPName", "CharacterSpacing", "Name Letter Spacing", p["NameSpacing"])
    cc("NameStretch", "CapCol", "NameOver", "Margin",
       "LblAnim", "AnimIn", "InLen", "AnimOut", "OutLen", "FlashCol", "SlideFrom")

    help_ = ("MangaPanels - turns your clip or still into a coloured manga panel (anime character-intro card): "
             "two-tone ink + paper, duotone accent colour, halftone dots, paper grain, misregistration, a big "
             "word behind the subject, distressed vertical Japanese text and name captions. See the README "
             "for the depth sandwich (Magic Mask) setup.")
    ins_txt = f'\t\t\t\tMainInput1 = InstanceInput {{ SourceOp = "{CTRL}", Source = "Input", }},\n'
    ins_txt += "".join(f"\t\t\t\t{s},\n" for s in L)
    return name, ("{\n\tTools = ordered() {\n"
                  f"\t\t{name} = MacroOperator {{\n\t\t\tCtrlWZoom = false,\n\t\t\tNameSet = true,\n"
                  f"\t\t\tCustomData = {{ HelpPage = {q(help_)}, }},\n"
                  f"\t\t\tInputs = ordered() {{\n{ins_txt}\t\t\t}},\n"
                  f'\t\t\tOutputs = {{\n\t\t\t\tMainOutput1 = InstanceOutput {{ SourceOp = "{out}", Source = "Output", }},\n\t\t\t}},\n'
                  "\t\t\tViewInfo = GroupInfo { Pos = { 0, 0 } },\n"
                  "\t\t\tTools = ordered() {\n" + "".join(tools) +
                  "\t\t\t},\n\t\t},\n\t},\n"
                  f'\tActiveTool = "{name}"\n}}\n')


def preset(pname):
    p = dict(BASE)
    p.update(PRESETS[pname])
    pal = PALETTES[p["Palette"]] if p["Palette"] < CUSTOM else None
    if pal:  # the custom pickers start at the preset's colours
        p["PaperCol"], p["InkCol"] = pal[1], pal[2]
    return p


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for f in os.listdir(OUT_DIR):
        if f.endswith(".setting"):
            os.remove(os.path.join(OUT_DIR, f))
    for pn in PRESET_ORDER:
        name, txt = build(pn, preset(pn))
        with open(os.path.join(OUT_DIR, name + ".setting"), "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
        print("wrote", name)


if __name__ == "__main__":
    main()
