#!/usr/bin/env python3
"""
Title_Sliding generator -- writes the Fusion macros (.setting) of the "Title_Sliding"
pack for DaVinci Resolve's Edit page (Effects > Title_Sliding).

The look: a title that slides side to side over a (semi-transparent) black band,
with a thin line separating the title from a subtitle -- the anime opening-credit
look -- plus news lower-thirds (tag box, ticker) built from the same parts.

One macro, several presets (same controls, different defaults):
    Title_Sliding            anime opening-credit strip (black band, white line)
    Title_Sliding_News       TV lower third: navy band, red tag, ticker underneath
    Title_Sliding_Breaking   red "BREAKING NEWS" bar, yellow line, ticker
    Title_Sliding_Cinema     centred film credit on a soft band, lines top and bottom

Node graph (all maths lives on TSCtrl as hidden expression controls, ids start with k):

    input -> TSCtrl (BrightnessContrast, pass-through, holds every control)
          -> TSBand  (rect)        band
          -> TSAcc   (rect)        accent block (leading edge / left / right)
          -> TSLine1 (rect)        separator line (between / top edge / ...)
          -> TSLine2 (rect)        second line (only for "top & bottom")
          -> TSMTitle  <- TSClipT <- TSTitle (Text+)
          -> TSMSub    <- TSClipS <- TSSub   (Text+)
          -> TSTag   (rect)        news tag box
          -> TSMTag    <- TSClipG <- TSTagT  (Text+)
          -> TSTick  (rect)        ticker strip
          -> TSMTick   <- TSClipK <- TSTickT (Text+)       = output

  * "rect" = CustomTool drawing an anti-aliased coloured rectangle over its input.
    Positions: x normalised 0..1 of the width, y normalised 0..1 of the height (y up);
    sizes in "px at 1080" (scaled by the short side / 1080, so vertical and horizontal
    timelines look the same).
  * text: Text+ sized to the input image, then a CustomTool clips it to the band so the
    words appear from behind the band's edge while they slide.
  * colours: tiny Background tools that are not in the image chain -- they only hold
    native colour pickers (TopLeftRed/Green/Blue) that the rect tools read.

Rules learned on Resolve 21.1 (see the other plugins in this collection):
  * the effect returns an image the SAME SIZE as its input (a clip-level comp runs at
    the source clip's resolution); nothing is sized from "frame format".
  * CustomTool per-pixel maths: + - * / min max abs floor only.
  * installed from a .drfx dragged onto Resolve, never as loose .setting files.

Usage:  python Giniroisenkou_Title_Sliding_gen.py  -> build/Edit/Effects/Title_Sliding/*.setting
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "build", "Edit", "Effects", "Title_Sliding")
PACK = "Title_Sliding"
FONT_K = 1.38     # Text+ Size = px / width * FONT_K   (Arial line height 1.117 / 0.81, measured for FakeUI)

# ---------------------------------------------------------------------------- presets
BASE = dict(
    # text
    Title="BREAKTHROUGH", Sub="Opening Theme 2", ShowSub=1,
    Font="Arial", Style="Bold", TitlePx=74, SubPx=36, Spacing=1.1, SubSpacing=1.25,
    TitleCol=(1, 1, 1), SubCol=(0.82, 0.82, 0.82), Align=0, Margin=70,
    # layout
    PosY=0.30, BandH=210, BandL=0.0, BandW=0.86, Split=0.5,
    BandCol=(0, 0, 0), BandOp=0.82,
    LineMode=0, LinePx=3, LineCol=(1, 1, 1), LineOp=1.0, LineInset=40,
    AccentPx=0, AccentMode=0, AccentCol=(0.85, 0.1, 0.1),
    # animation
    Dir=0, Exit=0, Start=0, ExitAt=0, InDur=16, OutDur=12, Ease=0,
    LineLead=4, TextDelay=5, Travel=0.35, Drift=0.6,
    # news parts
    ShowTag=0, Tag="LIVE", TagPx=34, TagW=190, TagH=56, TagCol=(0.86, 0.08, 0.12), TagTextCol=(1, 1, 1),
    ShowTick=0, Tick="Latest updates  \u2022  Weather: sunny on the coast  \u2022  Traffic: slow on the ring road  \u2022  ",
    TickPx=30, TickH=58, TickSpeed=5, TickRep=420, TickCol=(0.96, 0.96, 0.96), TickTextCol=(0.08, 0.08, 0.1),
)

PRESETS = {
    "": dict(),   # master = anime opening strip
    "News": dict(
        Title="Storm reaches the coast", Sub="City  \u2022  live from the port", Font="Arial", Style="Bold",
        TitlePx=64, SubPx=34, Spacing=1.0, SubSpacing=1.0, Margin=40,
        PosY=0.31, BandH=170, BandL=0.04, BandW=0.92, BandCol=(0.05, 0.09, 0.22), BandOp=0.95,
        LineMode=0, LinePx=2, LineCol=(0.86, 0.08, 0.12), LineInset=40, Split=0.55,
        AccentPx=12, AccentMode=1, AccentCol=(0.86, 0.08, 0.12),
        Dir=0, Exit=1, InDur=14, OutDur=12, Ease=1, LineLead=2, TextDelay=6, Travel=0.25, Drift=0,
        ShowTag=1, Tag="LIVE", TagW=150, ShowTick=1),
    "Breaking": dict(
        Title="BREAKING NEWS", Sub="Headline goes here", Font="Arial", Style="Bold",
        TitlePx=78, SubPx=38, Spacing=1.04, SubSpacing=1.0, Margin=44,
        PosY=0.31, BandH=190, BandL=0.0, BandW=1.0, BandCol=(0.80, 0.04, 0.08), BandOp=0.97,
        LineMode=0, LinePx=4, LineCol=(1.0, 0.82, 0.0), LineInset=0, Split=0.52,
        AccentPx=0, Dir=1, Exit=1, InDur=12, OutDur=10, Ease=1, LineLead=3, TextDelay=4, Travel=0.3, Drift=0,
        ShowTag=1, Tag="LIVE", TagW=150, TagCol=(1.0, 0.82, 0.0), TagTextCol=(0.1, 0.02, 0.02),
        ShowTick=1, TickCol=(0.08, 0.08, 0.1), TickTextCol=(1, 1, 1)),
    "Cinema": dict(
        Title="A FILM BY YOUR NAME", Sub="Your City  \u2014  2026", Font="Georgia", Style="Regular",
        TitlePx=46, SubPx=28, Spacing=1.22, SubSpacing=1.4, Align=1, Margin=0,
        PosY=0.5, BandH=200, BandL=0.0, BandW=1.0, BandCol=(0, 0, 0), BandOp=0.45,
        LineMode=3, LinePx=2, LineCol=(0.92, 0.85, 0.7), LineOp=0.9, LineInset=180,
        Dir=0, Exit=0, InDur=24, OutDur=20, Ease=0, LineLead=8, TextDelay=10, Travel=0.12, Drift=0.35),
}

ALIGN = ["Left", "Centre", "Right"]
LINEMODE = ["Between title & subtitle", "Top edge", "Bottom edge", "Top & bottom edges", "No line"]
ACCENT = ["Leading edge (rides the slide)", "Left end", "Right end"]
DIRS = ["Left \u2192 Right", "Right \u2192 Left"]
EXITS = ["Keep going (exit the other side)", "Go back (exit where it came in)", "No exit (stays)"]
EASES = ["Smooth", "Snappy", "Linear"]


# ------------------------------------------------------------------ serializer helpers
def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def num(v):
    if isinstance(v, float):
        return repr(round(v, 6))
    return str(v)


def C(e):
    """C.Name -> TSCtrl.kName"""
    return re.sub(r"\bC\.(\w+)", lambda m: f"TSCtrl.k{m.group(1)}", e)


def CS(e):
    """same, inside TSCtrl itself (bare kName)"""
    return re.sub(r"\bC\.(\w+)", lambda m: f"k{m.group(1)}", e)


def clamp(e, lo=0, hi=1):
    return f"min(max({e},{lo}),{hi})"


def I(v=None, expr=None, src=None):
    if src:
        return f'Input {{ SourceOp = "{src}", Source = "Output", }}'
    parts = []
    if v is not None:
        parts.append(f"Value = {q(v) if isinstance(v, str) else num(v)}")
    if expr is not None:
        parts.append(f"Expression = {q(expr)}")
    return "Input { " + ", ".join(parts) + ", }"


def tool(name, regid, inputs, pos):
    body = "".join(f"\t\t\t\t\t\t{k} = {v},\n" for k, v in inputs.items())
    return (f"\t\t\t\t{name} = {regid} {{\n\t\t\t\t\tCtrlWZoom = false,\n\t\t\t\t\tNameSet = true,\n"
            f"\t\t\t\t\tInputs = {{\n{body}\t\t\t\t\t}},\n"
            f"\t\t\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {pos[0]}, {pos[1]} }} }},\n\t\t\t\t}},\n")


# ------------------------------------------------------------------ Ctrl user controls
# (id, kind, label, extra, tooltip)   kind: label / float / int / combo / check
def CONTROLS():
    return [
        ("LblLay", "label", "LAYOUT", {}, ""),
        ("PosY", "float", "Band Height Position (0 bottom - 1 top)", dict(min=0, max=1), "Vertical centre of the band."),
        ("BandH", "float", "Band Thickness (px)", dict(min=40, max=600, amin=0), "Height of the band, px at 1080."),
        ("BandL", "float", "Band Start X (0 left)", dict(min=0, max=1), "Left end of the band, 0 = frame edge."),
        ("BandW", "float", "Band Length", dict(min=0.05, max=1, amin=0), "Length of the band, 1 = whole width."),
        ("Split", "float", "Title / Subtitle Split", dict(min=0.2, max=0.8), "Where the band divides between title (top) and subtitle (bottom)."),
        ("Align", "combo", "Text Alignment", dict(combo=ALIGN), "Where the text sits on the band."),
        ("Margin", "float", "Text Margin (px)", dict(min=0, max=300), "Gap between the band end and the text."),
        ("ShowSub", "check", "Show Subtitle", {}, "Second, smaller line under the separator."),

        ("LblBand", "label", "BACKGROUND BAND", {}, ""),
        ("BandOp", "float", "Background Opacity", dict(min=0, max=1, amin=0, amax=1), "0 = no band (text + line only), 1 = solid."),

        ("LblLine", "label", "SEPARATOR LINE", {}, ""),
        ("LineMode", "combo", "Line Position", dict(combo=LINEMODE), "Where the thin line is drawn."),
        ("LinePx", "float", "Line Thickness (px)", dict(min=1, max=20, amin=0), "Thickness at 1080."),
        ("LineOp", "float", "Line Opacity", dict(min=0, max=1, amin=0, amax=1), ""),
        ("LineInset", "float", "Line Inset (px)", dict(min=0, max=400, amin=0), "Shortens the line at both ends."),

        ("LblAcc", "label", "ACCENT BAR", {}, ""),
        ("AccentPx", "float", "Accent Bar Width (px, 0 = off)", dict(min=0, max=80, amin=0), "Coloured block at one end of the band."),
        ("AccentMode", "combo", "Accent Bar Position", dict(combo=ACCENT), "Leading edge = the block rides the front of the slide."),

        ("LblAnim", "label", "ANIMATION", {}, ""),
        ("Dir", "combo", "Slide Direction", dict(combo=DIRS), "Which side the band and title come in from."),
        ("Exit", "combo", "Exit", dict(combo=EXITS), "How it leaves at the end of the clip."),
        ("Ease", "combo", "Easing", dict(combo=EASES), "Smooth = soft landing, Snappy = fast then settle."),
        ("Start", "int", "Start Delay (frames)", dict(min=0, max=120, amin=0), "Frames after the clip starts before the slide begins."),
        ("ExitAt", "int", "Exit At Frame (0 = end of clip)", dict(min=0, max=600, amin=0), "Leave earlier than the clip end."),
        ("InDur", "int", "Slide In (frames)", dict(min=1, max=60, amin=1), ""),
        ("OutDur", "int", "Slide Out (frames)", dict(min=1, max=60, amin=1), ""),
        ("LineLead", "int", "Line Leads By (frames)", dict(min=0, max=20, amin=0), "The line shoots across first, the band follows."),
        ("TextDelay", "int", "Text Delay (frames)", dict(min=0, max=30, amin=0), "Title starts sliding after the band."),
        ("Travel", "float", "Text Slide Distance", dict(min=0, max=1, amin=0), "How far the text travels while sliding in (band lengths)."),
        ("Drift", "float", "Text Drift (px / frame)", dict(min=-3, max=3), "Slow side-to-side drift while the title holds. 0 = still."),

        ("LblTag", "label", "NEWS TAG BOX", {}, ""),
        ("ShowTag", "check", "Show Tag Box", {}, "Small box on top of the band (LIVE, BREAKING...)."),
        ("TagW", "float", "Tag Width (px)", dict(min=40, max=700, amin=0), ""),
        ("TagH", "float", "Tag Height (px)", dict(min=20, max=200, amin=0), ""),

        ("LblTick", "label", "NEWS TICKER", {}, ""),
        ("ShowTick", "check", "Show Ticker", {}, "Scrolling text strip under the band."),
        ("TickH", "float", "Ticker Height (px)", dict(min=20, max=200, amin=0), ""),
        ("TickSpeed", "float", "Ticker Speed (px / frame)", dict(min=0, max=30), ""),
        ("TickRep", "int", "Ticker Restarts Every (frames)", dict(min=30, max=3000, amin=1), "Set longer for long ticker text."),
    ]


def HIDDEN():
    """hidden Ctrl expressions (order matters only for readability)"""
    ease = lambda p: (f"iif(kEase == 0, 1-(1-{p})*(1-{p})*(1-{p}), "
                      f"iif(kEase == 1, 1-(1-{p})*(1-{p})*(1-{p})*(1-{p})*(1-{p}), {p}))")
    pin = lambda d: clamp(f"(kT-({d}))/max(kInDur,1)")
    pout = lambda d: clamp(f"(kT-(kEnd-kOutDur-({d})))/max(kOutDur,1)")
    H = [
        ("W", "max(self.Input.OriginalWidth, 16)"),
        ("H", "max(self.Input.OriginalHeight, 16)"),
        ("S", "min(kW,kH)/1080"),
        ("T", "time-comp.RenderStart-kStart"),
        ("End", "iif(kExitAt > 0, kExitAt-kStart, comp.RenderEnd-comp.RenderStart-kStart)"),
        ("Cont", "iif(kExit == 0, 1, 0)"),
        ("Back", "iif(kExit == 1, 1, 0)"),
        ("NoEx", "iif(kExit == 2, 0, 1)"),
        # timings: line first, band after LineLead, text after TextDelay; exits reversed
        ("PiL", pin("0")), ("PoL", pout("0")),
        ("PiB", pin("kLineLead")), ("PoB", pout("kLineLead*0")),
        ("PiT", pin("kLineLead+kTextDelay")), ("PoT", pout("kTextDelay")),
    ]
    for k in ("PiL", "PoL", "PiB", "PoB", "PiT", "PoT"):
        H.append(("E" + k[1:], ease(f"k{k}")))
    for part in ("L", "B", "T"):
        eo = f"(kEo{part}*kNoEx)"
        ei = f"kEi{part}"
        lc = f"((1-kDir)*(kCont*{eo})+kDir*((1-{ei})+kBack*{eo}))"
        rc = f"((1-kDir)*((1-{ei})+kBack*{eo})+kDir*(kCont*{eo}))"
        H.append((f"X0{part}", f"kBandL+kBandW*min({lc},1)"))
        H.append((f"X1{part}", f"kBandL+kBandW*(1-min({rc},1))"))
    H += [
        # vertical layout (normalised y, y up)
        ("Hy", "kBandH*kS/kH"),                                  # band height, normalised
        ("Top", "kPosY+kHy/2"), ("Bot", "kPosY-kHy/2"),
        ("SplitY", "iif(kShowSub > 0.5, kBot+kHy*(1-kSplit), kPosY)"),
        ("TitleY", "iif(kShowSub > 0.5, (kTop+kSplitY)/2, kPosY)"),
        ("SubY", "(kBot+kSplitY)/2"),
        ("LineY1", "iif(kLineMode == 0, kSplitY, iif(kLineMode == 2, kBot, kTop))"),
        ("LineY2", "iif(kLineMode == 3, kBot, -10)"),
        ("LineA", "iif(kLineMode == 4, 0, kLineOp)"),
        ("Ins", "kLineInset*kS/kW"),
        # accent block
        ("Aw", "min(kAccentPx*kS/kW, max(kX1B-kX0B,0))"),
        ("Lead", "iif(kDir < 0.5, iif(kCont*kEoB*kNoEx > 0, 0, 1), iif(kCont*kEoB*kNoEx > 0, 1, 0))"),
        ("Ax0", "iif(kAccentMode == 1, kX0B, iif(kAccentMode == 2, kX1B-kAw, iif(kLead > 0.5, kX1B-kAw, kX0B)))"),
        # text x (anchor point) with slide + drift
        ("Sgn", "1-2*kDir"),
        ("TxBase", "iif(kAlign == 0, kBandL+kMargin*kS/kW, iif(kAlign == 1, kBandL+kBandW/2, kBandL+kBandW-kMargin*kS/kW))"),
        ("TxOut", "kEoT*kNoEx*iif(kExit == 0, 1, -1)"),
        ("Tx", "kTxBase+kSgn*(kBandW*kTravel*(kTxOut-(1-kEiT))+kDrift*kS/kW*max(kT-kLineLead-kTextDelay,0))"),
        ("Fade", f"{clamp('kEiT*2')}*{clamp('(1-kEoT*kNoEx)*2')}"),
        # tag box: sits on the band's top edge, at the left end
        ("TgX0", "max(kBandL, kX0B)"),
        ("TgX1", "min(kBandL+kTagW*kS/kW, kX1B)"),
        ("TgY", "kTop+kTagH*kS/kH/2"),
        ("TgA", "kShowTag"),
        # ticker: under the band
        ("TkY", "kBot-kTickH*kS/kH/2"),
        ("TkA", "kShowTick"),
        ("TkX", "kBandL+kBandW*0.3-(kT-kTickRep*floor(kT/max(kTickRep,1)))*kTickSpeed*kS/kW"),
    ]
    return H


# ------------------------------------------------------------------ custom tools
def rect(name, src, x0, x1, yc, hpx, col_holder, alpha, pos):
    """anti-aliased rectangle over the input.  x0/x1/yc normalised, hpx = height in px at 1080"""
    m = (f"min(max((x-n1)*w+0.5,0),1)*min(max((n2-x)*w+0.5,0),1)"
         f"*min(max((s1-abs(y-n3))*h+0.5,0),1)*n8")
    ins = {
        "NumberIn1": I(0, C(x0)), "NumberIn2": I(0, C(x1)), "NumberIn3": I(0.5, C(yc)),
        "NumberIn4": I(10, C(hpx)),
        "NumberIn5": I(0, f"{col_holder}.TopLeftRed"), "NumberIn6": I(0, f"{col_holder}.TopLeftGreen"),
        "NumberIn7": I(0, f"{col_holder}.TopLeftBlue"), "NumberIn8": I(1, C(alpha)),
        "Setup1": I("n4*min(w,h)/1080/h/2"),
        "Intermediate1": I(m),
        "RedExpression": I("r1*(1-i1)+n5*i1"), "GreenExpression": I("g1*(1-i1)+n6*i1"),
        "BlueExpression": I("b1*(1-i1)+n7*i1"), "AlphaExpression": I("a1*(1-i1)+i1"),
        "Image1": I(src=src),
    }
    return tool(name, "Custom", ins, pos)


def clip(name, src, x0, x1, fade, pos):
    """keep the text only between x0..x1 (normalised), times fade"""
    m = "min(max((x-n1)*w+0.5,0),1)*min(max((n2-x)*w+0.5,0),1)*n3"
    ins = {"NumberIn1": I(0, C(x0)), "NumberIn2": I(1, C(x1)), "NumberIn3": I(1, C(fade)),
           "Intermediate1": I(m),
           "RedExpression": I("r1*i1"), "GreenExpression": I("g1*i1"), "BlueExpression": I("b1*i1"),
           "AlphaExpression": I("a1*i1"), "Image1": I(src=src)}
    return tool(name, "Custom", ins, pos)


def text(name, p, key, px, col, x, y, anchor, spacing, pos, font=None, style=None):
    ins = {
        "UseFrameFormatSettings": I(0),
        "Width": I(1920, "TSCtrl.kW"), "Height": I(1080, "TSCtrl.kH"),
        "StyledText": I(p[key]),
        "Font": I(font or p["Font"]), "Style": I(style or p["Style"]),
        # Size is exposed as a px slider on the Text+ itself (TSPx), converted here
        "Size": I(0.05, f"{name}.PxSize*TSCtrl.kS/TSCtrl.kW*{FONT_K}"),
        "Center": I(None, C(f"Point({x}, {y})")),
        "HorizontalLeftCenterRight": I(0, anchor),
        "VerticalTopCenterBottom": I(0),
        "CharacterSpacing": I(spacing),
        "Red1": I(col[0]), "Green1": I(col[1]), "Blue1": I(col[2]), "Alpha1": I(1),
        "PxSize": I(px),
    }
    t = tool(name, "TextPlus", ins, pos)
    # PxSize is a user control on the Text+ tool
    uc = (f"\t\t\t\t\tUserControls = ordered() {{ PxSize = {{ LINKS_Name = \"Size (px)\", LINKID_DataType = \"Number\", "
          f"INPID_InputControl = \"SliderControl\", INP_Default = {px}, INP_MinScale = 8, INP_MaxScale = 300, "
          f"INP_MinAllowed = 1, ICS_ControlPage = \"Text\", }}, }},\n")
    return t.replace("\t\t\t\t\tViewInfo", uc + "\t\t\t\t\tViewInfo", 1)


def holder(name, col, pos):
    return tool(name, "Background", {
        "UseFrameFormatSettings": I(0), "Width": I(8), "Height": I(8),
        "TopLeftRed": I(col[0]), "TopLeftGreen": I(col[1]), "TopLeftBlue": I(col[2]), "TopLeftAlpha": I(1),
    }, pos)


def merge(name, bg, fg, pos):
    return tool(name, "Merge", {"Background": I(src=bg), "Foreground": I(src=fg), "PerformDepthMerge": I(0)}, pos)


# ------------------------------------------------------------------ Ctrl node
def ctrl_tool(p):
    ctrls = CONTROLS()
    ins = {}
    for cid, kind, _, _, _ in ctrls:
        if kind != "label":
            ins["k" + cid] = I(p[cid])
    for hid, e in HIDDEN():
        ins["k" + hid] = I(0, CS(e))
    body = "".join(f"\t\t\t\t\t\t{k} = {v},\n" for k, v in ins.items())
    ucs = []
    for cid, kind, name, ex, tip in ctrls:
        L = [f"LINKS_Name = {q(name)}"]
        if kind == "label":
            L += ['LINKID_DataType = "Number"', 'INPID_InputControl = "LabelControl"', "INP_External = false",
                  "INP_Passive = true", "LBLC_DropDownButton = false"]
        elif kind == "combo":
            L += [f"{{ CCS_AddString = {q(o)}, }}" for o in ex["combo"]]
            L += ['LINKID_DataType = "Number"', 'INPID_InputControl = "ComboControl"', "INP_Integer = true",
                  'CC_LabelPosition = "Horizontal"', f"INP_Default = {p[cid]}", "INP_MinScale = 0",
                  f"INP_MaxScale = {len(ex['combo'])-1}", "INP_MinAllowed = 0", f"INP_MaxAllowed = {len(ex['combo'])-1}"]
        elif kind == "check":
            L += ['LINKID_DataType = "Number"', 'INPID_InputControl = "CheckboxControl"', "INP_Integer = true",
                  f"INP_Default = {p[cid]}", "INP_MinScale = 0", "INP_MaxScale = 1"]
        else:
            L += ['LINKID_DataType = "Number"', 'INPID_InputControl = "SliderControl"', f"INP_Default = {num(p[cid])}"]
            if kind == "int":
                L.append("INP_Integer = true")
            for k, f in (("min", "INP_MinScale"), ("max", "INP_MaxScale"), ("amin", "INP_MinAllowed"), ("amax", "INP_MaxAllowed")):
                if k in ex:
                    L.append(f"{f} = {num(ex[k])}")
        if tip:
            L.append(f"INPS_StatusText = {q(tip)}")
        L.append('ICS_ControlPage = "Controls"')
        ucs.append(f"\t\t\t\t\t\tk{cid} = {{ " + ", ".join(L) + " },\n")
    for hid, _ in HIDDEN():
        ucs.append(f'\t\t\t\t\t\tk{hid} = {{ LINKS_Name = "{hid}", LINKID_DataType = "Number", '
                   f'INPID_InputControl = "SliderControl", IC_Visible = false, INP_Passive = true, '
                   f'INP_MinScale = -100000, INP_MaxScale = 100000, ICS_ControlPage = "Controls" }},\n')
    return ("\t\t\t\tTSCtrl = BrightnessContrast {\n\t\t\t\t\tCtrlWZoom = false,\n\t\t\t\t\tNameSet = true,\n"
            f"\t\t\t\t\tInputs = {{\n{body}\t\t\t\t\t}},\n"
            "\t\t\t\t\tViewInfo = OperatorInfo { Pos = { 0, 0 } },\n"
            "\t\t\t\t\tUserControls = ordered() {\n" + "".join(ucs) + "\t\t\t\t\t},\n\t\t\t\t},\n")


# ------------------------------------------------------------------ macro
def build(preset):
    p = dict(BASE)
    p.update(PRESETS[preset])
    name = PACK + ("_" + preset if preset else "")
    tools = [ctrl_tool(p)]
    for hn, key in (("TSColBand", "BandCol"), ("TSColLine", "LineCol"), ("TSColAcc", "AccentCol"),
                    ("TSColTag", "TagCol"), ("TSColTick", "TickCol")):
        tools.append(holder(hn, p[key], (0, 100 + 40 * len(tools))))

    tools += [
        rect("TSBand", "TSCtrl", "C.X0B", "C.X1B", "C.PosY", "C.BandH", "TSColBand", "C.BandOp", (110, 0)),
        rect("TSAcc", "TSBand", "C.Ax0", "C.Ax0+C.Aw", "C.PosY", "C.BandH", "TSColAcc", "iif(C.AccentPx > 0, 1, 0)", (220, 0)),
        rect("TSLine1", "TSAcc", "max(C.X0L, C.BandL+C.Ins)", "min(C.X1L, C.BandL+C.BandW-C.Ins)", "C.LineY1",
             "C.LinePx", "TSColLine", "C.LineA", (330, 0)),
        rect("TSLine2", "TSLine1", "max(C.X0L, C.BandL+C.Ins)", "min(C.X1L, C.BandL+C.BandW-C.Ins)", "C.LineY2",
             "C.LinePx", "TSColLine", "C.LineA", (440, 0)),
        text("TSTitle", p, "Title", p["TitlePx"], p["TitleCol"], "C.Tx", "C.TitleY", "TSCtrl.kAlign-1",
             p["Spacing"], (550, -120)),
        clip("TSClipT", "TSTitle", "C.X0B", "C.X1B", "C.Fade", (550, -60)),
        merge("TSMTitle", "TSLine2", "TSClipT", (550, 0)),
        text("TSSub", p, "Sub", p["SubPx"], p["SubCol"], "C.Tx", "C.SubY", "TSCtrl.kAlign-1",
             p["SubSpacing"], (660, -120)),
        clip("TSClipS", "TSSub", "C.X0B", "C.X1B", "C.Fade*C.ShowSub", (660, -60)),
        merge("TSMSub", "TSMTitle", "TSClipS", (660, 0)),
        rect("TSTag", "TSMSub", "C.TgX0", "C.TgX1", "C.TgY", "C.TagH", "TSColTag", "C.TgA", (770, 0)),
        text("TSTagT", p, "Tag", p["TagPx"], p["TagTextCol"], "(C.TgX0+C.TgX1)/2", "C.TgY", "0", 1.08, (770, -120),
             font="Arial", style="Bold"),
        clip("TSClipG", "TSTagT", "C.TgX0", "C.TgX1", "C.TgA", (770, -60)),
        merge("TSMTag", "TSTag", "TSClipG", (880, 0)),
        rect("TSTick", "TSMTag", "C.X0B", "C.X1B", "C.TkY", "C.TickH", "TSColTick", "C.TkA", (990, 0)),
        text("TSTickT", p, "Tick", p["TickPx"], p["TickTextCol"], "C.TkX", "C.TkY", "-1", 1.0, (990, -120),
             style="Regular"),
        clip("TSClipK", "TSTickT", "C.X0B", "C.X1B", "C.TkA", (990, -60)),
        merge("TSMTick", "TSTick", "TSClipK", (1100, 0)),
    ]
    out = "TSMTick"

    # ---------------------------------------------------------- Inspector (order = on screen)
    L = []
    idx = [0]

    def add(op, src, name=None, default=None, group=None):
        idx[0] += 1
        s = f'Input{idx[0]} = InstanceInput {{ SourceOp = "{op}", Source = "{src}"'
        if name:
            s += f", Name = {q(name)}"
        if group is not None:
            s += f", ControlGroup = {group}"
        if default is not None:
            s += f", Default = {q(default) if isinstance(default, str) else num(default)}"
        L.append(s + ", }")

    def color(op, pfx, label, col, group):
        add(op, pfx + "Red", label, col[0], group)
        add(op, pfx + "Green", None, col[1], group)
        add(op, pfx + "Blue", None, col[2], group)

    ctrl_ids = {c[0]: c for c in CONTROLS()}

    def cc(cid):
        c = ctrl_ids[cid]
        if c[1] == "label":
            add("TSCtrl", "k" + cid)
        else:
            add("TSCtrl", "k" + cid, c[2], p[cid])

    g = [100]

    def grp():
        g[0] += 1
        return g[0]

    # TEXT section (native Text+ inputs)
    add("TSTitle", "StyledText", "Title")
    gf = grp()
    add("TSTitle", "Font", "Title Font", group=gf)
    add("TSTitle", "Style", "Title Style", group=gf)
    add("TSTitle", "PxSize", "Title Size (px)", p["TitlePx"])
    add("TSTitle", "CharacterSpacing", "Title Letter Spacing", p["Spacing"])
    gt = grp()
    add("TSTitle", "Red1", "Title Colour", p["TitleCol"][0], gt)
    add("TSTitle", "Green1", None, p["TitleCol"][1], gt)
    add("TSTitle", "Blue1", None, p["TitleCol"][2], gt)
    add("TSSub", "StyledText", "Subtitle")
    gs = grp()
    add("TSSub", "Font", "Subtitle Font", group=gs)
    add("TSSub", "Style", "Subtitle Style", group=gs)
    add("TSSub", "PxSize", "Subtitle Size (px)", p["SubPx"])
    add("TSSub", "CharacterSpacing", "Subtitle Letter Spacing", p["SubSpacing"])
    gc = grp()
    add("TSSub", "Red1", "Subtitle Colour", p["SubCol"][0], gc)
    add("TSSub", "Green1", None, p["SubCol"][1], gc)
    add("TSSub", "Blue1", None, p["SubCol"][2], gc)

    for cid in ("LblLay", "PosY", "BandH", "BandL", "BandW", "Split", "Align", "Margin", "ShowSub", "LblBand"):
        cc(cid)
    color("TSColBand", "TopLeft", "Background Colour", p["BandCol"], grp())
    cc("BandOp")
    for cid in ("LblLine", "LineMode"):
        cc(cid)
    color("TSColLine", "TopLeft", "Line Colour", p["LineCol"], grp())
    for cid in ("LinePx", "LineOp", "LineInset", "LblAcc", "AccentPx", "AccentMode"):
        cc(cid)
    color("TSColAcc", "TopLeft", "Accent Bar Colour", p["AccentCol"], grp())
    for cid in ("LblAnim", "Dir", "Exit", "Ease", "Start", "ExitAt", "InDur", "OutDur", "LineLead", "TextDelay",
                "Travel", "Drift", "LblTag", "ShowTag"):
        cc(cid)
    add("TSTagT", "StyledText", "Tag Text")
    add("TSTagT", "PxSize", "Tag Text Size (px)", p["TagPx"])
    cc("TagW"); cc("TagH")
    color("TSColTag", "TopLeft", "Tag Colour", p["TagCol"], grp())
    gg = grp()
    add("TSTagT", "Red1", "Tag Text Colour", p["TagTextCol"][0], gg)
    add("TSTagT", "Green1", None, p["TagTextCol"][1], gg)
    add("TSTagT", "Blue1", None, p["TagTextCol"][2], gg)
    cc("LblTick"); cc("ShowTick")
    add("TSTickT", "StyledText", "Ticker Text")
    add("TSTickT", "PxSize", "Ticker Text Size (px)", p["TickPx"])
    for cid in ("TickH", "TickSpeed", "TickRep"):
        cc(cid)
    color("TSColTick", "TopLeft", "Ticker Colour", p["TickCol"], grp())
    gk = grp()
    add("TSTickT", "Red1", "Ticker Text Colour", p["TickTextCol"][0], gk)
    add("TSTickT", "Green1", None, p["TickTextCol"][1], gk)
    add("TSTickT", "Blue1", None, p["TickTextCol"][2], gk)

    help_ = ("Title Sliding - a title that slides side to side over a black band with a thin separator "
             "line (anime opening-credit look), plus news lower thirds with a tag box and ticker. "
             "Put it on an Adjustment Clip above your footage (or directly on a clip).")
    ins_txt = '\t\t\t\tMainInput1 = InstanceInput { SourceOp = "TSCtrl", Source = "Input", },\n'
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


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for f in os.listdir(OUT_DIR):
        if f.endswith(".setting"):
            os.remove(os.path.join(OUT_DIR, f))
    names = []
    for pr in PRESETS:
        name, txt = build(pr)
        with open(os.path.join(OUT_DIR, name + ".setting"), "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
        names.append(name)
    print("wrote", names)


if __name__ == "__main__":
    main()
