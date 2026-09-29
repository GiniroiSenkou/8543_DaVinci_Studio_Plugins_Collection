#!/usr/bin/env python3
"""
Trends generator -- emits the Fusion macros of the "Trends" pack for
DaVinci Resolve's Edit page (Effects > Trends).

28 single-purpose, drop-on-a-clip effects for trending IG / TikTok looks.
Every effect follows the same pattern:

  <Code>Ctrl  (BrightnessContrast, image passes through untouched)
              carries every Inspector control + the hidden maths as simple
              expressions.  All control ids start with "k" so they never
              collide with BrightnessContrast's own inputs (Contrast, Gain...).
  ...nodes... read the Ctrl through expressions.

Rules learned on Resolve 21.1 (see the other plugins in this collection):
  * the effect must return an image the SAME SIZE as its input
    (a clip-level comp runs at the SOURCE clip's resolution, e.g. 3840x2160,
    not the timeline's) -> no Background / Mask nodes sized by "frame format";
    per-pixel work is done in a CustomTool fed by the input itself.
  * CustomTool per-pixel maths uses only + - * / min max abs floor sqrt sin
    cos atan2 and the get??b() samplers (no comparisons / if()).
  * effects are installed from a .drfx (drag onto Resolve), never as loose
    .setting files.

Usage:  python Giniroisenkou_Trends_gen.py   -> build/Edit/Effects/Trends/*.setting
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "build", "Edit", "Effects", "Trends")
PACK = "Trends"


# --------------------------------------------------------------------------
# small expression helpers (strings valid in BOTH Fusion and the python
# preview renderer, Giniroisenkou_Trends_preview.py)
# --------------------------------------------------------------------------
def clamp(e, lo=0, hi=1):
    return f"min(max({e},{lo}),{hi})"

def safe(e, axis="x"):
    """clamp a sample coordinate 1.5 px inside the frame (get??b returns black at the edge)"""
    d = "w" if axis == "x" else "h"
    return clamp(e, f"1.5/{d}", f"1-1.5/{d}")

def frac(e):
    return f"(({e})-floor({e}))"

def hsh(a, b):
    """pseudo random 0..1 from two numbers"""
    return frac(f"sin(({a})*12.9898+({b})*78.233)*43758.5453")

def sel(e, i):
    """1 when e == i (integers), else 0 -- no comparison syntax"""
    return f"max(0,1-abs(({e})-{i}))"

def mod(a, b):
    return f"(({a})-({b})*floor(({a})/({b})))"

def chain(sel_expr, values, last):
    """Ctrl-side (simple expression) lookup: iif(s==0, v0, iif(s==1, v1, ... last))"""
    e = str(last)
    for i in range(len(values) - 1, -1, -1):
        e = f"iif({sel_expr}=={i}, {values[i]}, {e})"
    return e

LUMA = "(0.2126*r1+0.7152*g1+0.0722*b1)"

def luma_at(u, v):
    return f"(0.2126*getr1b({u},{v})+0.7152*getg1b({u},{v})+0.0722*getb1b({u},{v}))"

def dsin(e):
    """CustomTool trig works in DEGREES (Ctrl-side simple expressions use radians)"""
    return f"sin(({e})*57.29578)"

def dcos(e):
    return f"cos(({e})*57.29578)"

def mix(a, b, t):
    return f"(({a})+(({b})-({a}))*({t}))"


# --------------------------------------------------------------------------
# node descriptions
# --------------------------------------------------------------------------
class Src:
    def __init__(self, node, out="Output"):
        self.node, self.out = node, out

class V:          # plain value (number or raw fusion literal)
    def __init__(self, v):
        self.v = v

class E:          # value + expression
    def __init__(self, default, expr):
        self.default, self.expr = default, expr

class Node:
    def __init__(self, name, kind, inputs, pos=(0, 0)):
        self.name, self.kind, self.inputs, self.pos = name, kind, inputs, pos


def custom(name, image, numbers=None, points=None, setup=None, inter=None, ch=None, pos=(110, 0)):
    """CustomTool node. numbers/points are Ctrl-side expressions (C.xxx),
    setup/inter/ch are CustomTool per-frame / per-pixel expressions."""
    ins = []
    for i, e in (numbers or {}).items():
        ins.append((f"NumberIn{i}", E(0, e)))
    for i, e in (points or {}).items():
        ins.append((f"PointIn{i}", E("{ 0.5, 0.5 }", e)))
    for i, e in (setup or {}).items():
        ins.append((f"Setup{i}", V('"' + e + '"')))
    for i, e in (inter or {}).items():
        ins.append((f"Intermediate{i}", V('"' + e + '"')))
    names = {"r": "RedExpression", "g": "GreenExpression", "b": "BlueExpression", "a": "AlphaExpression"}
    for k in "rgba":
        e = (ch or {}).get(k, k + "1")
        ins.append((names[k], V('"' + e + '"')))
    ins.append(("Image1", Src(image)))
    n = Node(name, "Custom", ins, pos)
    n.custom = dict(numbers=numbers or {}, points=points or {}, setup=setup or {},
                    inter=inter or {}, ch={k: (ch or {}).get(k, k + "1") for k in "rgba"})
    return n


class FX:
    def __init__(self, name, code, category, blurb, help, controls, hidden, nodes, out,
                 extra_inputs=None, preview=None):
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
        self.extra_inputs = extra_inputs or []
        self.preview = preview or {}


# control helpers:  (id, kind, name, default, extra, tooltip)
def label(text):
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

def mixc(default=1.0):
    return fl("Mix", "Mix", default, 0, 1, "Blend with the original clip: 0 = original, 1 = full effect.", 0, 1)

def beat_controls(every_default=0, decay_default=8):
    return [
        it("Every", "Pulse Every (frames, 0 = steady)", every_default, 0, 60,
           "Re-trigger the effect on a beat: e.g. 15 = every 15 frames (half a second at 30 fps). 0 = constant.", 0),
        it("Decay", "Pulse Length (frames)", decay_default, 1, 30, "How long each pulse takes to fade out.", 1),
        it("Offset", "Beat Offset (frames)", 0, 0, 60, "Shift the beat so the pulse lands on your music hit.", 0),
    ]

# pulse envelope (Ctrl side): 1 when Every = 0, else a quadratic decay after each beat
PULSE = ("PUL", "iif(C.Every < 1, 1, max(0, 1-" + mod("time+C.Offset", "max(C.Every,1)") + "/max(C.Decay,1))^2)")


# ==========================================================================
#  THE EFFECTS
# ==========================================================================
EFFECTS = []

# ---------------------------------------------------------------- 1 EchoTrails
def _echo():
    ctl = "C"
    nodes, prev = [], "C"
    tints = [(2.094, 4.188, 6.283), (4.188, 6.282, 8.377), (6.282, 8.376, 10.471),
             (8.376, 10.470, 12.565), (10.470, 12.564, 14.659), (12.564, 14.658, 16.753)]
    for i in range(1, 7):
        x = 110 * i
        nodes.append(Node(f"ETTime{i}", "TimeSpeed", [
            ("Input", Src("C")), ("Speed", V(1)),
            ("Delay", E(0, f"C.Spacing*{i}*(1-2*C.Dir)")),
            ("InterpolateBetweenFrames", V(0)),
        ], (x, -60)))
        tr, tg, tb = tints[i - 1]
        nodes.append(Node(f"ETTint{i}", "ColorGain", [
            ("Input", Src(f"ETTime{i}")),
            ("GainRed", E(1, f"1-C.Rainbow*(0.5-0.5*cos({tr}))")),
            ("GainGreen", E(1, f"1-C.Rainbow*(0.5-0.5*cos({tg}))")),
            ("GainBlue", E(1, f"1-C.Rainbow*(0.5-0.5*cos({tb}))")),
        ], (x, -25)))
        dec = "*".join(["C.Decay"] * (i - 1)) or "1"
        nodes.append(Node(f"ETMerge{i}", "Merge", [
            ("Background", Src(prev)), ("Foreground", Src(f"ETTint{i}")),
            ("Blend", E(0.5, f"iif({i} <= C.Count, C.Strength*{dec}, 0)")),
        ], (x, 0)))
        prev = f"ETMerge{i}"
    return FX("EchoTrails", "ET", "Motion",
              "motion trails / ghosting, rainbow tint, past or future echoes",
              "Echo Trails - layers delayed copies of the clip for a ghost / trail look. More echoes + bigger "
              "spacing = longer trails. Rainbow tints each echo a different colour.",
              [label("ECHO TRAILS  -  ghost copies of the clip"),
               it("Count", "Echoes", 4, 1, 6, "How many delayed copies are layered (1-6).", 1, 6),
               it("Spacing", "Spacing (frames)", 2, 1, 10, "Frames between each echo. Bigger = longer trail.", 1),
               fl("Strength", "Strength", 0.6, 0, 1, "Opacity of the first echo.", 0, 1),
               fl("Decay", "Decay", 0.75, 0, 1, "Each next echo is this much weaker (0.75 = 75% of the previous).", 0, 1),
               fl("Rainbow", "Rainbow Tint", 0.0, 0, 1, "Tint each echo a different colour (0 = natural).", 0, 1),
               cb("Dir", "Trail From", 0, ["Past", "Future"], "Past = trail behind the motion, Future = ghosts ahead.")],
              [], nodes, prev, preview={"t": 30, "Count": 6, "Spacing": 3, "Strength": 0.85, "Decay": 0.8})
EFFECTS.append(_echo())

# ---------------------------------------------------------------- 2 RGBSplit
def _rgb():
    J = "(1+C.Jitter*sin(floor(time/max(C.Hold,1))*12.9898+C.Seed*78.233))"
    nodes = [
        Node("RSR", "ColorGain", [("Input", Src("C")), ("GainRed", V(1)), ("GainGreen", V(0)), ("GainBlue", V(0))], (110, -60)),
        Node("RSG", "ColorGain", [("Input", Src("C")), ("GainRed", V(0)), ("GainGreen", V(1)), ("GainBlue", V(0))], (110, 0)),
        Node("RSB", "ColorGain", [("Input", Src("C")), ("GainRed", V(0)), ("GainGreen", V(0)), ("GainBlue", V(1))], (110, 60)),
        Node("RSShiftR", "Transform", [("Input", Src("RSR")), ("Edges", V(2)),
             ("Center", E("{ 0.5, 0.5 }", f"Point(0.5+C.Amount*0.005*cos(C.Angle*0.0174533)*{J}, 0.5+C.Amount*0.005*sin(C.Angle*0.0174533)*{J})"))], (220, -60)),
        Node("RSShiftB", "Transform", [("Input", Src("RSB")), ("Edges", V(2)),
             ("Center", E("{ 0.5, 0.5 }", f"Point(0.5-C.Amount*0.005*cos(C.Angle*0.0174533)*{J}, 0.5-C.Amount*0.005*sin(C.Angle*0.0174533)*{J})"))], (220, 60)),
        Node("RSAddRG", "Merge", [("Background", Src("RSShiftR")), ("Foreground", Src("RSG")), ("ApplyMode", V('FuID { "Screen" }'))], (330, 0)),
        Node("RSAddRGB", "Merge", [("Background", Src("RSAddRG")), ("Foreground", Src("RSShiftB")), ("ApplyMode", V('FuID { "Screen" }'))], (440, 0)),
        Node("RSMix", "Merge", [("Background", Src("C")), ("Foreground", Src("RSAddRGB")), ("Blend", E(1, "C.Mix"))], (550, 0)),
    ]
    return FX("RGBSplit", "RS", "Glitch",
              "chromatic RGB split with beat-held glitch jitter",
              "RGB Split - pulls the red and blue channels apart. Jitter makes the split jump every few frames.",
              [label("RGB SPLIT  -  chromatic aberration"),
               fl("Amount", "Split Amount", 1.0, 0, 5, "Distance between the colour channels.", 0),
               fl("Angle", "Angle", 0, -180, 180, "Direction of the split in degrees (0 = horizontal)."),
               fl("Jitter", "Glitch Jitter", 0.5, 0, 3, "Random jumps of the split amount.", 0),
               it("Hold", "Jitter Hold (frames)", 2, 1, 12, "Frames each jitter value is held.", 1),
               it("Seed", "Seed", 1, 1, 100, "Change for a different random pattern."),
               mixc()],
              [], nodes, "RSMix", preview={"t": 7, "Amount": 3})
EFFECTS.append(_rgb())

# ---------------------------------------------------------------- 3 Flicker (rebuilt: one CustomTool)
def _flicker():
    ON = "n1"
    OFF = f"(({LUMA})+(r1-({LUMA}))*(1-n3))"
    def ch(c):
        look = f"(({LUMA})+({c}1-({LUMA}))*(1-n3))*n4"
        return f"{c}1*(1-{ON})+{ON}*n2*{look}"
    nodes = [custom("FLCore", "C",
                    numbers={1: "C.OFF", 2: "C.OffOpacity", 3: "C.Desat", 4: "C.OffGain"},
                    ch={"r": ch("r"), "g": ch("g"), "b": ch("b"), "a": f"a1*(1-{ON})+{ON}*n2*a1"})]
    return FX("Flicker", "FL", "Motion",
              "strobe / flicker between this clip and the one below",
              "Flicker - switches the clip off every few frames. With Off-Frame Opacity at 0 the clip below "
              "shows through (put two clips on V1/V2 for a two-clip strobe).",
              [label("FLICKER  -  strobe on / off"),
               it("Rate", "Flicker Every (frames)", 2, 1, 12, "Length of each on / off step in frames.", 1),
               it("Offset", "Phase Offset", 0, 0, 12, "Shift which frames are 'off'.", 0),
               fl("OffOpacity", "Off-Frame Opacity (0 = show clip below)", 0.0, 0, 1,
                  "How visible the clip is on 'off' frames. 0 = transparent (the track below shows).", 0, 1),
               fl("Desat", "Off-Frame B&W", 0.0, 0, 1, "Makes the off frames black & white.", 0, 1),
               fl("OffGain", "Off-Frame Brightness", 1.0, 0, 3, "Brightness of the off frames (above 1 = white flash).", 0)],
              [("OFF", "floor((time+C.Offset)/max(C.Rate,1))-2*floor((time+C.Offset)/(2*max(C.Rate,1)))")],
              nodes, "FLCore", preview={"t": 2, "OffOpacity": 1, "OffGain": 1.8, "Desat": 1})
EFFECTS.append(_flicker())

# ---------------------------------------------------------------- 4 Stutter
def _stutter():
    H = "max(C.Hold,1)"
    R = "max(C.Repeat,1)"
    st = (f"iif(C.Mode < 0.5, floor(time/{H})*{H}, iif(C.Mode < 1.5, floor(time/({H}*{R}))*{H}*{R}+(time-{H}*floor(time/{H})), "
          f"iif(time-floor(time/(2*{H}))*2*{H} < {H}, time, 2*(floor(time/(2*{H}))*2*{H})+2*{H}-time)))")
    nodes = [Node("STTime", "TimeStretcher", [("Input", Src("C")), ("SourceTime", E(0, st)),
                                             ("InterpolateBetweenFrames", V(0))], (110, 0))]
    return FX("Stutter", "ST", "Motion",
              "choppy frame-hold, stutter loop, or back-and-forth wobble",
              "Stutter - Choppy holds each frame for N frames (low-fps look). Stutter Loop repeats a short chunk. "
              "Wobble plays a chunk forward then backward.",
              [label("STUTTER  -  choppy / loop / wobble"),
               cb("Mode", "Style", 0, ["Choppy (hold frames)", "Stutter Loop", "Wobble (back & forth)"],
                  "Choppy = low frame rate look. Stutter Loop = repeat each chunk. Wobble = forward / backward."),
               it("Hold", "Hold / Chunk Length (frames)", 3, 1, 24, "Frames per hold or per loop chunk.", 1),
               it("Repeat", "Loop Repeats", 3, 1, 8, "Stutter Loop only: how many times each chunk repeats.", 1)],
              [], nodes, "STTime", preview={"t": 10})
EFFECTS.append(_stutter())

# ---------------------------------------------------------------- 5 NumberCounter
def _counter():
    P = "min(1, max(0, (time-C.StartAt)/max(C.Dur,1)))"
    S = "max(0, (time-C.StartAt)/max(C.FPS,1))"
    txt = ("Text(C.Prefix.Value .. iif(C.Mode < 0.5, string.format(\"%.\" .. floor(C.Decimals) .. \"f\", "
           f"C.From+(C.To-C.From)*(iif(C.Ease > 0.5, 1-(1-{P})*(1-{P})*(1-{P}), {P}))), "
           f"iif(C.Mode < 1.5, string.format(\"%02d:%02d.%02d\", floor({S}/60), floor({S})-60*floor({S}/60), "
           f"floor(({S}-floor({S}))*100)), string.format(\"%04d\", floor(time+C.From)))) .. C.Suffix.Value)")
    nodes = [
        Node("NCText", "TextPlus", [("UseFrameFormatSettings", V(1)), ("StyledText", E('"0"', txt)),
                                     ("Font", V('"Arial"')), ("Style", V('"Bold"')), ("Size", V(0.12)),
                                     ("Center", V("{ 0.5, 0.5 }")), ("Red1", V(1)), ("Green1", V(1)), ("Blue1", V(1))], (110, -40)),
        Node("NCOver", "Merge", [("Background", Src("C")), ("Foreground", Src("NCText"))], (220, 0)),
    ]
    extra = [
        'Font = InstanceInput { SourceOp = "NCText", Source = "Font", Name = "Font", ControlGroup = 20, }',
        'Style = InstanceInput { SourceOp = "NCText", Source = "Style", Name = "Style", ControlGroup = 20, }',
        'Size = InstanceInput { SourceOp = "NCText", Source = "Size", Name = "Size", Default = 0.12, }',
        'Center = InstanceInput { SourceOp = "NCText", Source = "Center", Name = "Position", }',
        'Red1 = InstanceInput { SourceOp = "NCText", Source = "Red1", Name = "Color", ControlGroup = 21, Default = 1, }',
        'Green1 = InstanceInput { SourceOp = "NCText", Source = "Green1", Name = "Green", ControlGroup = 21, Default = 1, }',
        'Blue1 = InstanceInput { SourceOp = "NCText", Source = "Blue1", Name = "Blue", ControlGroup = 21, Default = 1, }',
        'Alpha1 = InstanceInput { SourceOp = "NCText", Source = "Alpha1", Name = "Alpha", ControlGroup = 21, Default = 1, }',
    ]
    return FX("NumberCounter", "NC", "Text",
              "animated counter, mm:ss.cc timer, or frame number with prefix/suffix",
              "Number Counter - counts From -> To over Duration frames (with ease-out), or shows a running timer "
              "or the frame number. Prefix / Suffix add text like '$' or ' likes'.",
              [label("NUMBER COUNTER  -  count up / timer"),
               cb("Mode", "Mode", 0, ["Counter (From -> To)", "Timer mm:ss.cc", "Frame Number"],
                  "Counter animates between two numbers, Timer shows elapsed time, Frame Number shows the frame."),
               fl("From", "From", 0, 0, 1000, "Start value."),
               fl("To", "To", 100, 0, 100000, "End value."),
               it("StartAt", "Start at Frame", 0, 0, 300, "Frame (inside the clip) where counting starts.", 0),
               it("Dur", "Count Duration (frames)", 60, 1, 600, "How long the count takes.", 1),
               ("Ease", "check", "Ease Out", 1, {}, "Slow down near the end value."),
               it("Decimals", "Decimals", 0, 0, 3, "Digits after the decimal point.", 0, 6),
               it("FPS", "Timer FPS", 30, 1, 120, "Timeline frame rate for Timer mode.", 1),
               ("Prefix", "text", "Prefix", "", {}, "Text before the number, e.g. $"),
               ("Suffix", "text", "Suffix", "", {}, "Text after the number, e.g.  likes")],
              [], nodes, "NCOver", extra_inputs=extra, preview={"t": 40, "To": 1250})
EFFECTS.append(_counter())

# ---------------------------------------------------------------- 6 ShakePunch
def _shake():
    B = "max(C.Beat,1)"
    ph = mod("time+C.Offset", B)
    env = f"max(0, 1-({ph})/max(C.Decay,1))"
    nodes = [Node("SPXf", "Transform", [
        ("Input", Src("C")), ("Edges", V(3)),
        ("Center", E("{ 0.5, 0.5 }", "Point(0.5+C.Shake*0.01*(0.6*sin(time*C.Speed*0.1*1.7)+0.4*sin(time*C.Speed*0.1*3.1+1)), "
                                     "0.5+C.Shake*0.01*(0.6*sin(time*C.Speed*0.1*1.3+2)+0.4*sin(time*C.Speed*0.1*2.7+4)))")),
        ("Size", E(1, f"C.Zoom+C.Punch*{env}*{env}")),
        ("Angle", E(0, "C.RotShake*(0.6*sin(time*C.Speed*0.1*1.1+3)+0.4*sin(time*C.Speed*0.1*2.3))")),
    ], (110, 0))]
    return FX("ShakePunch", "SP", "Motion",
              "handheld shake + zoom punch on a beat interval",
              "Shake Punch - smooth handheld shake plus a zoom 'punch' every Beat frames. Set Beat to your music "
              "(30 fps: 15 = 120 BPM). Base Zoom hides the edges.",
              [label("SHAKE + PUNCH  -  handheld + beat zoom"),
               fl("Shake", "Shake Amount", 1.0, 0, 5, "Strength of the handheld shake.", 0),
               fl("Speed", "Shake Speed", 1.0, 0, 5, "How fast it shakes.", 0),
               fl("RotShake", "Rotation Shake (deg)", 1.0, 0, 10, "Rotation wobble in degrees.", 0),
               fl("Zoom", "Base Zoom", 1.08, 1, 1.5, "Zoom that hides the moving edges.", 1),
               fl("Punch", "Beat Punch Zoom", 0.12, 0, 0.5, "Extra zoom on each beat.", 0),
               it("Beat", "Beat Every (frames)", 15, 1, 60, "Frames between punches.", 1),
               it("Decay", "Punch Decay (frames)", 6, 1, 30, "How fast a punch settles.", 1),
               it("Offset", "Beat Offset (frames)", 0, 0, 60, "Shift the punches onto the music hit.", 0)],
              [], nodes, "SPXf", preview={"t": 16, "Shake": 3, "RotShake": 3})
EFFECTS.append(_shake())

# ---------------------------------------------------------------- 7 Filter2016 (rebuilt tone+vignette in one CustomTool)
def _f2016():
    L = LUMA
    def tone(c, gain):
        x = f"({c}1*{gain})"
        lx = f"(({L})*1)"
        sat = f"({lx}+({x}-{lx})*n1)"
        con = f"((({sat})-0.5*a1)*(1+n2)+0.5*a1)"
        return f"max(({con})*(1-n4*0.08)+n4*0.08*a1,0)*i1"
    vig = f"(1-n5*{clamp(f'(sqrt((x-0.5)*(x-0.5)+(y-0.5)*(y-0.5))*1.4142-0.45)/0.55')})"
    nodes = [
        custom("F16Tone", "C", numbers={1: "C.Sat", 2: "C.Contrast", 3: "C.Warm", 4: "C.Fade", 5: "C.Vignette"},
               inter={1: vig},
               ch={"r": tone("r", "(1+n3*0.08)"), "g": tone("g", "1"), "b": tone("b", "(1-n3*0.10)")}),
        Node("F16Glow", "SoftGlow", [("Input", Src("F16Tone")), ("Threshold", V(0.6)), ("Gain", E(0.4, "C.Glow")),
                                     ("XGlowSize", V(12))], (220, 0)),
    ]
    return FX("Filter2016", "F16", "Look",
              "oversaturated 2016-Instagram look (warmth, faded blacks, glow, vignette)",
              "Filter 2016 - the punchy old-Instagram look: boosted saturation, warm tint, lifted (faded) blacks, "
              "soft glow on highlights and a dark vignette.",
              [label("FILTER 2016  -  old-Instagram look"),
               fl("Sat", "Saturation", 1.45, 0, 3, "1 = original saturation.", 0),
               fl("Contrast", "Contrast", 0.12, -0.5, 1, "Extra contrast (0 = none)."),
               fl("Warm", "Warmth", 0.5, -1, 1, "Positive = warmer / orange, negative = cooler."),
               fl("Fade", "Faded Blacks", 0.3, 0, 1, "Lifts the blacks to a matte grey.", 0),
               fl("Glow", "Glow", 0.4, 0, 2, "Soft glow on bright areas.", 0),
               fl("Vignette", "Vignette", 0.25, 0, 1, "Darkens the corners.", 0, 1)],
              [], nodes, "F16Glow", preview={"t": 0})
EFFECTS.append(_f2016())

# ---------------------------------------------------------------- 8 MirrorTiles
def _mirror():
    nodes = [Node("MTXf", "Transform", [
        ("Input", Src("C")), ("Edges", V(3)),
        ("Size", E(0.5, "1/max(C.Tiles,0.01)")),
        ("Center", E("{ 0.5, 0.5 }", "Point(0.5+time*C.PanX*0.002, 0.5+time*C.PanY*0.002)")),
        ("Angle", E(0, "C.Rot+time*C.Spin*0.5")),
    ], (110, 0))]
    return FX("MirrorTiles", "MT", "Mirror",
              "mirrored tiling with scroll and spin",
              "Mirror Tiles - repeats the clip as mirrored tiles. Scroll and Spin animate the tiling.",
              [label("MIRROR TILES  -  mirrored repeat"),
               fl("Tiles", "Tiles Across", 2, 1, 6, "How many tiles across the frame.", 1),
               fl("PanX", "Scroll X", 0, -10, 10, "Scroll speed left / right."),
               fl("PanY", "Scroll Y", 0, -10, 10, "Scroll speed up / down."),
               fl("Rot", "Rotation", 0, -180, 180, "Fixed rotation in degrees."),
               fl("Spin", "Spin Speed", 0, -10, 10, "Continuous rotation speed.")],
              [], nodes, "MTXf", preview={"t": 0, "Tiles": 2.5})
EFFECTS.append(_mirror())


# ========================================================================= NEW 20
# ---------------------------------------------------------------- 9 ZoomBlur
def _zoomblur():
    N = 12
    def ch(c):
        taps = []
        for k in range(N):
            s = f"(1-n1*{k/(N-1):.4f})"
            taps.append(f"get{c}1b(p1x+(x-p1x)*{s},p1y+(y-p1y)*{s})")
        return "(" + "+".join(taps) + f")/{N}"
    nodes = [custom("ZBCore", "C", numbers={1: "C.Amount*0.45*C.PUL", 2: "C.Mix"},
                    points={1: "Point(C.CX, C.CY)"},
                    ch={c: mix(f"{c}1", ch(c), "n2") for c in "rgba"})]
    return FX("ZoomBlur", "ZB", "Motion",
              "radial zoom blur / speed burst, optional beat pulse",
              "Zoom Blur - streaks everything out from a centre point, like a fast zoom. Use Pulse Every to hit it "
              "on the beat, or keyframe Amount for a transition.",
              [label("ZOOM BLUR  -  radial speed streaks"),
               fl("Amount", "Amount", 0.35, 0, 1, "Length of the zoom streaks.", 0, 1),
               fl("CX", "Centre X", 0.5, 0, 1, "Zoom centre left-right (0 = left edge, 1 = right)."),
               fl("CY", "Centre Y", 0.5, 0, 1, "Zoom centre up-down (0 = bottom, 1 = top)."),
               *beat_controls(0, 8), mixc()],
              [PULSE], nodes, "ZBCore", preview={"t": 0, "Amount": 0.5})
EFFECTS.append(_zoomblur())

# ---------------------------------------------------------------- 10 DreamyGlow
def _dreamy():
    L = LUMA
    def tone(c, g):
        x = f"({c}1*{g})"
        sat = f"({L}+({x}-{L})*(1-n3*0.35))"
        return f"max(({sat})*(1-n1*0.25)+n1*0.25*a1,0)"
    nodes = [
        custom("DGTone", "C", numbers={1: "C.Haze", 2: "C.Warm", 3: "C.Soft"},
               ch={"r": tone("r", "(1+n2*0.06)"), "g": tone("g", "(1+n2*0.01)"), "b": tone("b", "(1-n2*0.06)")}),
        Node("DGGlow", "SoftGlow", [("Input", Src("DGTone")), ("Threshold", E(0.45, "C.Thresh")),
                                    ("Gain", E(0.8, "C.Glow")), ("XGlowSize", E(20, "C.Size"))], (220, 0)),
        Node("DGMix", "Merge", [("Background", Src("C")), ("Foreground", Src("DGGlow")), ("Blend", E(1, "C.Mix"))], (330, 0)),
    ]
    return FX("DreamyGlow", "DG", "Look",
              "soft dreamy bloom with haze and warm tint",
              "Dreamy Glow - soft bloom around the highlights with a light haze and a warm tint. Great for golden "
              "hour, portraits and aesthetic edits.",
              [label("DREAMY GLOW  -  soft bloom + haze"),
               fl("Glow", "Glow", 0.8, 0, 3, "Strength of the bloom.", 0),
               fl("Size", "Glow Size", 20, 1, 80, "How far the glow spreads.", 0),
               fl("Thresh", "Threshold", 0.45, 0, 1, "Only areas brighter than this glow.", 0, 1),
               fl("Haze", "Haze", 0.3, 0, 1, "Milky lifted blacks.", 0, 1),
               fl("Warm", "Warmth", 0.4, -1, 1, "Positive = warm, negative = cool."),
               fl("Soft", "Soften Colours", 0.3, 0, 1, "Gently reduces saturation for a pastel feel.", 0, 1),
               mixc()],
              [], nodes, "DGMix", preview={"t": 0, "Glow": 1.2})
EFFECTS.append(_dreamy())

# ---------------------------------------------------------------- 11 VHS
def _vhs():
    LN = "floor(y*540)"
    band = clamp("1-abs(y-(1-" + frac("n5*0.011") + "))*14")
    J = f"(({hsh(LN, 'n5')})-0.5)*n2*0.006"
    TB = f"{band}*n7*0.04*(({hsh(LN + '*1.3', 'n5+4.1')})-0.3)"
    U = safe(f"x+{J}+{TB}")
    R = f"getr1b({U}+s1,y)"
    G = f"getg1b({U},y)"
    Bs = f"getb1b({U}-s1,y)"
    def ch(S, gain):
        return f"max(({S}*(1-n6*0.5)+i4*n6*0.5)*{gain}*i2+i3*a1,0)"
    nodes = [custom("VHCore", "C",
                    numbers={1: "C.Chroma", 2: "C.Jitter", 3: "C.Scan", 4: "C.Noise", 5: "floor(time)",
                             6: "C.Bleed", 7: "C.Track"},
                    setup={1: "n1*0.005"},
                    inter={1: U,
                           2: "(1-n3*0.35*(0.5+0.5*sin(y*h*180)))",
                           3: f"(({hsh('floor(x*w*0.5)+n5*7.13', 'floor(y*h*0.5)')})-0.5)*n4*0.22",
                           4: f"({R}+{G}+{Bs})/3"},
                    ch={"r": ch(R, 1.06), "g": ch(G, 1.0), "b": ch(Bs, 0.9)})]
    return FX("VHS", "VH", "Retro",
              "90s VHS tape: colour bleed, line jitter, scanlines, noise, tracking band",
              "VHS - camcorder / tape look: shifted colour channels, wobbly lines, scanlines, noise and a rolling "
              "tracking band.",
              [label("VHS  -  90s tape look"),
               fl("Chroma", "Colour Shift", 1.5, 0, 6, "Red / blue offset (colour bleeding).", 0),
               fl("Jitter", "Line Jitter", 1.0, 0, 5, "Horizontal wobble of the lines.", 0),
               fl("Scan", "Scanlines", 0.5, 0, 1, "Darkness of the scanlines.", 0, 1),
               fl("Noise", "Noise", 0.35, 0, 1, "Tape noise.", 0, 1),
               fl("Bleed", "Washed Colour", 0.35, 0, 1, "Muddy, washed-out colour.", 0, 1),
               fl("Track", "Tracking Band", 1.0, 0, 3, "Rolling tracking distortion band.", 0)],
              [], nodes, "VHCore", preview={"t": 30})
EFFECTS.append(_vhs())

# ---------------------------------------------------------------- 12 FilmGrain
def _grain():
    GX = "floor(x*w/s1)"
    GY = "floor(y*h/s1)"
    def nz(k):
        return f"(({hsh(GX + f'+n4*17.0+{k*3.1}', GY + f'+{k*1.7}')})-0.5)"
    wgt = f"(0.35+2.6*{clamp(LUMA)}*(1-{clamp(LUMA)}))*n1*0.35"
    def ch(c, k):
        return f"max({c}1*s2+(i1*(1-n3)+{nz(k)}*n3)*i2*a1,0)"
    nodes = [custom("FGCore", "C",
                    numbers={1: "C.Amount", 2: "C.GSize", 3: "C.Colour", 4: "floor(time)", 5: "C.Flick"},
                    setup={1: "max(n2*min(w,h)/1080,1)", 2: f"1+n5*0.06*(({hsh('n4', '1.3')})-0.5)"},
                    inter={1: nz(0), 2: wgt},
                    ch={"r": ch("r", 1), "g": ch("g", 2), "b": ch("b", 3)})]
    return FX("FilmGrain", "FG", "Retro",
              "animated film grain with exposure flicker",
              "Film Grain - fine moving grain, strongest in the mid-tones like real film, plus optional exposure "
              "flicker. Colour Grain adds chroma noise.",
              [label("FILM GRAIN  -  analog texture"),
               fl("Amount", "Amount", 0.5, 0, 2, "Grain strength.", 0),
               fl("GSize", "Grain Size (px at 1080)", 1.5, 1, 6, "Bigger = coarser grain.", 1),
               fl("Colour", "Colour Grain", 0.25, 0, 1, "0 = mono grain, 1 = colour noise.", 0, 1),
               fl("Flick", "Exposure Flicker", 0.3, 0, 2, "Frame-to-frame brightness flicker.", 0)],
              [], nodes, "FGCore", preview={"t": 3, "Amount": 1.2, "GSize": 2})
EFFECTS.append(_grain())

# ---------------------------------------------------------------- 13 Vignette
def _vignette():
    ay = "((1-n4)+n4*h/w)"
    d = f"sqrt((x-p1x)*(x-p1x)+((y-p1y)*{ay})*((y-p1y)*{ay}))*1.4142"
    v = clamp(f"({d}-(n2-n3*0.5))/max(n3,0.001)")
    k = f"(({v})*({v})*(3-2*({v}))*n1)"
    nodes = [custom("VGCore", "C", numbers={1: "C.Amount", 2: "C.Size", 3: "C.Soft", 4: "C.Round", 5: "C.Shade"},
                    points={1: "Point(C.CX, C.CY)"}, inter={1: k},
                    ch={c: f"{c}1*(1-i1)+n5*a1*i1" for c in "rgb"})]
    return FX("Vignette", "VG", "Look",
              "dark or white vignette with size, softness and centre",
              "Vignette - darkens (or whitens) the edges to pull the eye to the subject. Move the centre onto a face.",
              [label("VIGNETTE  -  frame the subject"),
               fl("Amount", "Amount", 0.6, 0, 1, "Strength of the vignette.", 0, 1),
               fl("Size", "Size", 0.75, 0.1, 1.5, "Size of the clear centre area.", 0),
               fl("Soft", "Softness", 0.6, 0.01, 1.5, "Edge softness.", 0.01),
               fl("Round", "Roundness", 0.0, 0, 1, "0 = follows the frame shape, 1 = perfect circle.", 0, 1),
               fl("Shade", "Colour (black - white)", 0.0, 0, 1, "0 = black vignette, 1 = white (dreamy) vignette.", 0, 1),
               fl("CX", "Centre X", 0.5, 0, 1, "Centre left-right."),
               fl("CY", "Centre Y", 0.5, 0, 1, "Centre up-down (0 = bottom, 1 = top).")],
              [], nodes, "VGCore", preview={"t": 0, "Amount": 0.85})
EFFECTS.append(_vignette())

# ---------------------------------------------------------------- 14 Duotone
DUO = [("Pink / Blue",      (0.12, 0.05, 0.45), (1.00, 0.45, 0.75)),
       ("Teal / Orange",    (0.02, 0.25, 0.30), (1.00, 0.62, 0.25)),
       ("Purple / Yellow",  (0.25, 0.05, 0.40), (1.00, 0.92, 0.30)),
       ("Black / Red",      (0.03, 0.02, 0.02), (0.95, 0.12, 0.15)),
       ("Navy / Mint",      (0.03, 0.08, 0.25), (0.55, 1.00, 0.80)),
       ("Plum / Green",     (0.12, 0.07, 0.20), (0.30, 0.95, 0.45)),
       ("Sepia",            (0.15, 0.08, 0.03), (1.00, 0.90, 0.72)),
       ("Magenta / Cyan",   (0.35, 0.00, 0.40), (0.20, 0.95, 1.00))]
def _duotone():
    hid = []
    for j, nm in enumerate(["SR", "SG", "SB"]):
        hid.append((nm, chain("C.Preset", [s[j] for _, s, _ in DUO], 0)))
    for j, nm in enumerate(["HR", "HG", "HB"]):
        hid.append((nm, chain("C.Preset", [hh[j] for _, _, hh in DUO], 1)))
    t = clamp(f"({LUMA}-0.5*a1)*n8+0.5")
    nodes = [custom("DTCore", "C",
                    numbers={1: "iif(C.Swap==1, C.HR, C.SR)", 2: "iif(C.Swap==1, C.HG, C.SG)", 3: "iif(C.Swap==1, C.HB, C.SB)",
                             4: "iif(C.Swap==1, C.SR, C.HR)", 5: "iif(C.Swap==1, C.SG, C.HG)", 6: "iif(C.Swap==1, C.SB, C.HB)",
                             7: "C.Mix", 8: "C.Contrast"},
                    inter={1: t},
                    ch={"r": mix("r1", "(n1+(n4-n1)*i1)*a1", "n7"),
                        "g": mix("g1", "(n2+(n5-n2)*i1)*a1", "n7"),
                        "b": mix("b1", "(n3+(n6-n3)*i1)*a1", "n7")})]
    return FX("Duotone", "DT", "Look",
              "two-colour poster look with 8 colour pairs",
              "Duotone - maps the dark parts to one colour and the bright parts to another, like a poster / Spotify-"
              "style cover. Pick a pair, Swap flips them.",
              [label("DUOTONE  -  two-colour poster"),
               cb("Preset", "Colours", 0, [n for n, _, _ in DUO], "Shadow / highlight colour pair."),
               cb("Swap", "Swap Colours", 0, ["Off", "On"], "Swap the shadow and highlight colours."),
               fl("Contrast", "Contrast", 1.2, 0.3, 3, "Contrast before colouring.", 0.1),
               mixc()],
              hid, nodes, "DTCore", preview={"t": 0})
EFFECTS.append(_duotone())

# ---------------------------------------------------------------- 15 Pixelate
def _pixelate():
    u = safe("(floor(x/s1)+0.5)*s1")
    v = safe("(floor(y/s2)+0.5)*s2", "y")
    P = "min(1, max(0, (time-C.StartAt)/max(C.Dur,1)))"
    nodes = [custom("PXCore", "C", numbers={1: "C.BS", 2: "C.Mix"},
                    setup={1: "max(n1*min(w,h)/1080,1)/w", 2: "max(n1*min(w,h)/1080,1)/h"},
                    inter={1: u, 2: v},
                    ch={c: mix(f"{c}1", f"get{c}1b(i1,i2)", "n2") for c in "rgba"})]
    return FX("Pixelate", "PX", "Retro",
              "mosaic / 8-bit blocks, static or animated in / out",
              "Pixelate - turns the image into big blocks. Animate: Pixel In starts blocky and sharpens, "
              "Pixel Out goes from sharp to blocky (nice transition).",
              [label("PIXELATE  -  mosaic blocks"),
               fl("Block", "Block Size (px at 1080)", 24, 1, 120, "Size of each block.", 1),
               cb("Anim", "Animate", 0, ["Static", "Pixel In (blocky -> sharp)", "Pixel Out (sharp -> blocky)"],
                  "Animate the block size from Start Frame over Duration."),
               it("StartAt", "Start Frame", 0, 0, 300, "Frame where the animation starts.", 0),
               it("Dur", "Duration (frames)", 15, 1, 120, "Length of the animation.", 1),
               mixc()],
              [("BS", f"iif(C.Anim==1, 1+(C.Block-1)*(1-{P}), iif(C.Anim==2, 1+(C.Block-1)*{P}, C.Block))")],
              nodes, "PXCore", preview={"t": 0, "Block": 20})
EFFECTS.append(_pixelate())

# ---------------------------------------------------------------- 16 Kaleidoscope
def _kaleido():
    dx = "((x-p1x)*w)"
    dy = "((y-p1y)*h)"
    seg = "(360/n1)"
    a = f"(atan2({dy},{dx})+360-n2)"
    am = f"({a}-{seg}*floor({a}/{seg}))"
    am2 = f"({seg}*0.5-abs({am}-{seg}*0.5)+n2)"
    r = f"(sqrt({dx}*{dx}+{dy}*{dy})/n3)"
    def fold(e):
        return f"(1-abs(1-(({e})-2*floor(({e})/2))))"
    nodes = [custom("KSCore", "C", numbers={1: "max(C.Seg,2)", 2: "C.ROT", 3: "max(C.Zoom,0.05)", 4: "C.Mix"},
                    points={1: "Point(C.CX, C.CY)"},
                    inter={1: safe(fold(f"p1x+{r}*cos({am2})/w")), 2: safe(fold(f"p1y+{r}*sin({am2})/h"), "y")},
                    ch={c: mix(f"{c}1", f"get{c}1b(i1,i2)", "n4") for c in "rgba"})]
    return FX("Kaleidoscope", "KS", "Mirror",
              "kaleidoscope mirror with segments, spin and zoom",
              "Kaleidoscope - reflects a slice of the image around the centre into a symmetric pattern. "
              "Spin animates it.",
              [label("KALEIDOSCOPE  -  mirrored slices"),
               it("Seg", "Segments", 6, 2, 16, "Number of mirrored slices.", 2, 64),
               fl("Rot", "Rotation", 0, -180, 180, "Pattern rotation in degrees."),
               fl("Spin", "Spin Speed", 0.5, -5, 5, "Continuous rotation speed."),
               fl("Zoom", "Zoom", 1.0, 0.3, 4, "Zoom into the source.", 0.05),
               fl("CX", "Centre X", 0.5, 0, 1, "Centre left-right."),
               fl("CY", "Centre Y", 0.5, 0, 1, "Centre up-down."),
               mixc()],
              [("ROT", "C.Rot+time*C.Spin*3")], nodes, "KSCore", preview={"t": 0})
EFFECTS.append(_kaleido())

# ---------------------------------------------------------------- 17 GlitchSlices
def _glitch():
    row = "floor(y*n1)"
    act = clamp(f"(n4-({hsh(row + '+n7*13', 'n5')}))*50")
    sh = f"(({hsh(row + '*3.7+n7', 'n5+11.3')})-0.5)*2*n2*{act}"
    def wrap(e):
        return safe(f"(({e})-floor({e}))")
    nodes = [custom("GLCore", "C",
                    numbers={1: "max(C.Slices,1)", 2: "C.Amount*C.PUL", 3: "C.RGB", 4: "C.Prob",
                             5: "floor(time/max(C.Hold,1))", 7: "C.Seed", 8: "C.Mix"},
                    inter={1: act, 2: sh},
                    ch={"r": mix("r1", f"getr1b({wrap('x+i2+n3*0.01*i1')},y)", "n8"),
                        "g": mix("g1", f"getg1b({wrap('x+i2')},y)", "n8"),
                        "b": mix("b1", f"getb1b({wrap('x+i2-n3*0.01*i1')},y)", "n8"),
                        "a": mix("a1", f"geta1b({wrap('x+i2')},y)", "n8")})]
    return FX("GlitchSlices", "GL", "Glitch",
              "digital glitch: random horizontal slices jump sideways with RGB tearing",
              "Glitch Slices - cuts the frame into horizontal strips that randomly jump sideways with colour "
              "tearing. Use Pulse Every to glitch on the beat.",
              [label("GLITCH SLICES  -  digital tearing"),
               it("Slices", "Slices", 24, 4, 80, "Number of horizontal strips.", 1),
               fl("Amount", "Shift Amount", 0.08, 0, 0.4, "How far strips jump sideways.", 0),
               fl("Prob", "Glitchiness", 0.35, 0, 1, "Share of strips that glitch.", 0, 1),
               fl("RGB", "RGB Tear", 1.0, 0, 4, "Colour tearing inside glitched strips.", 0),
               it("Hold", "Change Every (frames)", 2, 1, 12, "Frames each glitch pattern is held.", 1),
               it("Seed", "Seed", 1, 1, 100, "Different random pattern."),
               *beat_controls(0, 6), mixc()],
              [PULSE], nodes, "GLCore", preview={"t": 4, "Prob": 0.45, "Amount": 0.12})
EFFECTS.append(_glitch())

# ---------------------------------------------------------------- 18 Wave
def _wave():
    m0, m1, m2 = sel("n5", 0), sel("n5", 1), sel("n5", 2)
    uh = f"(x+n1*{dsin('y*n2*6.283185+n3')})"
    vv = f"(y+n1*(w/h)*{dsin('x*n2*6.283185+n3')})"
    d = "max(sqrt(((x-p1x)*w/h)*((x-p1x)*w/h)+(y-p1y)*(y-p1y)),0.02)"
    s = f"n1*{dsin(f'{d}*n2*6.283185-n3')}"
    ur = f"(x+{s}*(x-p1x)/{d})"
    vr = f"(y+{s}*(y-p1y)/{d})"
    U = safe(f"{m0}*{uh}+{m1}*x+{m2}*{ur}")
    Vv = safe(f"{m0}*y+{m1}*{vv}+{m2}*{vr}", "y")
    nodes = [custom("WVCore", "C", numbers={1: "C.Amp*0.02", 2: "C.Freq", 3: "time*C.Speed*0.2", 5: "C.Mode", 6: "C.Mix"},
                    points={1: "Point(C.CX, C.CY)"}, inter={1: U, 2: Vv},
                    ch={c: mix(f"{c}1", f"get{c}1b(i1,i2)", "n6") for c in "rgba"})]
    return FX("Wave", "WV", "Distort",
              "liquid wave / wobble / water ripple distortion",
              "Wave - bends the image with moving waves: horizontal wobble, vertical wobble, or a water ripple "
              "from a centre point.",
              [label("WAVE  -  liquid wobble / ripple"),
               cb("Mode", "Style", 0, ["Horizontal Wobble", "Vertical Wobble", "Ripple (from centre)"], "Kind of wave."),
               fl("Amp", "Strength", 1.0, 0, 5, "How far the image bends.", 0),
               fl("Freq", "Waves", 3, 0.5, 20, "Number of waves across the frame.", 0.1),
               fl("Speed", "Speed", 1.0, -5, 5, "Animation speed (negative = reverse)."),
               fl("CX", "Ripple Centre X", 0.5, 0, 1, "Ripple mode only."),
               fl("CY", "Ripple Centre Y", 0.5, 0, 1, "Ripple mode only."),
               mixc()],
              [], nodes, "WVCore", preview={"t": 5, "Amp": 2.5, "Mode": 0, "Freq": 3})
EFFECTS.append(_wave())

# ---------------------------------------------------------------- 19 LightLeak
LEAKS = [("Warm Sunset", (1.00, 0.45, 0.10), (1.00, 0.15, 0.35)),
         ("Pink Dream",  (1.00, 0.35, 0.70), (1.00, 0.75, 0.50)),
         ("Golden",      (1.00, 0.75, 0.25), (1.00, 0.50, 0.10)),
         ("Cool Blue",   (0.20, 0.60, 1.00), (0.60, 0.30, 1.00)),
         ("Neon",        (1.00, 0.20, 0.45), (0.20, 0.80, 1.00))]
def _leak():
    hid = []
    for j, nm in enumerate(["AR", "AG", "AB"]):
        hid.append((nm, chain("C.Palette", [a[j] for _, a, _ in LEAKS], 1)))
    for j, nm in enumerate(["BR", "BG", "BB"]):
        hid.append((nm, chain("C.Palette", [b[j] for _, _, b in LEAKS], 1)))
    ax, ay = f"(0.12+0.18*{dsin('n2*0.9')})", f"(0.85+0.12*{dsin('n2*0.63+1')})"
    bx, by = f"(0.92+0.1*{dsin('n2*0.7+2')})", f"(0.25+0.25*{dsin('n2*0.5+0.5')})"
    def blob(cx, cy):
        d2 = f"(((x-{cx})*w/h)*((x-{cx})*w/h)+(y-{cy})*(y-{cy}))"
        q = f"(1/(1+{d2}*2/(p1x*p1x)))"
        return f"({q}*{q})"
    streak = f"({clamp('1-abs((x*w/h*0.6+y)-(0.6+0.5*' + dsin('n2*0.37') + '))*3')}*0.45)"
    def ch(c, ia, ib):
        lk = f"min((({ia})*i1+({ib})*i2+(({ia})+({ib}))*0.5*i3)*n1*1.3,1)*a1"
        return f"{c}1+{lk}-{c}1*{lk}"
    nodes = [custom("LLCore", "C",
                    numbers={1: "C.Amount", 2: "time*C.Speed*0.05+C.Phase", 3: "C.AR", 4: "C.AG", 5: "C.AB",
                             6: "C.BR", 7: "C.BG", 8: "C.BB"},
                    points={1: "Point(C.Size, 0)"},
                    inter={1: blob(ax, ay), 2: blob(bx, by), 3: streak},
                    ch={"r": ch("r", "n3", "n6"), "g": ch("g", "n4", "n7"), "b": ch("b", "n5", "n8")})]
    return FX("LightLeak", "LL", "Retro",
              "drifting film light leaks in 5 palettes",
              "Light Leak - warm glowing leaks of colour drifting over the edges of the frame, like old film. "
              "Change Phase for a different position.",
              [label("LIGHT LEAK  -  film burns"),
               cb("Palette", "Colours", 0, [n for n, _, _ in LEAKS], "Colour of the leaks."),
               fl("Amount", "Intensity", 0.8, 0, 2, "Brightness of the leaks.", 0),
               fl("Size", "Size", 0.6, 0.1, 1.5, "Size of the glowing blobs.", 0.05),
               fl("Speed", "Drift Speed", 1.0, 0, 5, "How fast the leaks move.", 0),
               fl("Phase", "Phase", 0, 0, 20, "Starting position of the leaks.")],
              hid, nodes, "LLCore", preview={"t": 0, "Amount": 1.2, "Phase": 4})
EFFECTS.append(_leak())

# ---------------------------------------------------------------- 20 KenBurns
def _kenburns():
    P = "min(1, max(0, (time-C.StartAt)/max(C.Dur,1)))"
    hid = [("PR", P),
           ("EZ", "iif(C.Ease==0, C.PR, iif(C.Ease==1, C.PR*C.PR*(3-2*C.PR), 1-(1-C.PR)*(1-C.PR)))"),
           ("Z", "C.ZS+(C.ZE-C.ZS)*C.EZ")]
    nodes = [Node("KBXf", "Transform", [
        ("Input", Src("C")),
        ("Size", E(1, "C.Z")),
        ("Center", E("{ 0.5, 0.5 }", "Point(0.5-C.PanX*(C.Z-1)/2*C.EZ, 0.5-C.PanY*(C.Z-1)/2*C.EZ)")),
        ("Angle", E(0, "C.Rot*C.EZ")),
    ], (110, 0))]
    return FX("KenBurns", "KB", "Motion",
              "slow cinematic zoom + pan with easing",
              "Ken Burns - slow push-in (or pull-out) with an optional pan and tilt, eased for a cinematic feel. "
              "Zoom End below Zoom Start = pull out.",
              [label("KEN BURNS  -  slow zoom + pan"),
               fl("ZS", "Zoom Start", 1.0, 1, 2, "Zoom at the start.", 1),
               fl("ZE", "Zoom End", 1.25, 1, 2, "Zoom at the end.", 1),
               fl("PanX", "Pan X", 0.3, -1, 1, "Drift left-right while zooming (+ = towards the right side).", -1, 1),
               fl("PanY", "Pan Y", 0.0, -1, 1, "Drift up-down while zooming (+ = towards the top).", -1, 1),
               fl("Rot", "Rotation (deg)", 0, -10, 10, "Slow rotation at the end."),
               it("StartAt", "Start Frame", 0, 0, 300, "Frame where the move starts.", 0),
               it("Dur", "Duration (frames)", 150, 1, 900, "Length of the move (150 = 5 s at 30 fps).", 1),
               cb("Ease", "Easing", 1, ["Linear", "Ease In-Out", "Ease Out"], "Speed curve of the move.")],
              hid, nodes, "KBXf", preview={"t": 40, "Dur": 40, "ZE": 1.35})
EFFECTS.append(_kenburns())

# ---------------------------------------------------------------- 21 BlurReveal
def _blurreveal():
    P = "min(1, max(0, (time-C.StartAt)/max(C.Dur,1)))"
    hid = [PULSE,
           ("P", P),
           ("K", "iif(C.Mode==0, (1-C.P)*(1-C.P), iif(C.Mode==1, C.P*C.P, C.PUL))")]
    nodes = [
        Node("BRBlur", "Blur", [("Input", Src("C")), ("XBlurSize", E(0, "C.Max*C.K"))], (110, 0)),
        Node("BRXf", "Transform", [("Input", Src("BRBlur")), ("Size", E(1, "1+C.ZoomAmt*C.K"))], (220, 0)),
    ]
    return FX("BlurReveal", "BR", "Motion",
              "focus-in / focus-out blur transition or beat blur pulse",
              "Blur Reveal - starts blurry and snaps into focus (Focus In), goes out of focus (Focus Out), or "
              "blurs on every beat (Beat Pulse). A small zoom adds energy.",
              [label("BLUR REVEAL  -  focus in / out"),
               cb("Mode", "Mode", 0, ["Focus In (blurry -> sharp)", "Focus Out (sharp -> blurry)", "Beat Pulse"],
                  "What the blur does over time."),
               fl("Max", "Max Blur", 40, 0, 150, "Blur strength at its strongest.", 0),
               fl("ZoomAmt", "Zoom With Blur", 0.08, 0, 0.5, "Extra zoom while blurred.", 0),
               it("StartAt", "Start Frame", 0, 0, 300, "Frame where the transition starts.", 0),
               it("Dur", "Duration (frames)", 18, 1, 120, "Transition length.", 1),
               *beat_controls(15, 8)],
              hid, nodes, "BRXf", preview={"t": 6})
EFFECTS.append(_blurreveal())

# ---------------------------------------------------------------- 22 TealOrange
def _tealorange():
    L = LUMA
    ws = clamp(f"1-{L}*1.6")
    wh = clamp(f"({L}-0.35)*1.6")
    def ch(c, s_, h_):
        x = f"({c}1+({s_}*i1+{h_}*i2)*n1*a1)"
        con = f"(({x}-0.5*a1)*(1+n3)+0.5*a1)"
        return f"max({L}+({con}-{L})*n2,0)"
    nodes = [custom("TOCore", "C", numbers={1: "C.Amount", 2: "C.Sat", 3: "C.Contrast"},
                    inter={1: ws, 2: wh},
                    ch={"r": ch("r", -0.10, 0.10), "g": ch("g", 0.02, 0.03), "b": ch("b", 0.08, -0.12)})]
    return FX("TealOrange", "TO", "Look",
              "blockbuster teal shadows / orange skin & highlights",
              "Teal & Orange - the cinematic blockbuster grade: teal-blue shadows, warm orange highlights and skin, "
              "extra contrast.",
              [label("TEAL & ORANGE  -  blockbuster grade"),
               fl("Amount", "Amount", 1.0, 0, 2, "Strength of the colour split.", 0),
               fl("Sat", "Saturation", 1.15, 0, 2, "1 = original saturation.", 0),
               fl("Contrast", "Contrast", 0.15, -0.5, 1, "Extra contrast.")],
              [], nodes, "TOCore", preview={"t": 0, "Amount": 1.6})
EFFECTS.append(_tealorange())

# ---------------------------------------------------------------- 23 Comic (posterize + ink edges)
def _comic():
    lx = luma_at("x+s1", "y")
    lxm = luma_at("x-s1", "y")
    ly = luma_at("x", "y+s2")
    lym = luma_at("x", "y-s2")
    edge = clamp(f"sqrt(({lx}-{lxm})*({lx}-{lxm})+({ly}-{lym})*({ly}-{lym}))*n2*4-0.1")
    def ch(c):
        boosted = f"max({LUMA}+({c}1-{LUMA})*n4,0)"
        q = f"(floor({boosted}*n1+0.5)/n1)"
        return mix(f"{c}1", f"{q}*(1-i1)*a1", "n5")
    nodes = [custom("CMCore", "C", numbers={1: "max(C.Levels,2)", 2: "C.Ink", 3: "C.Width", 4: "C.Sat", 5: "C.Mix"},
                    setup={1: "max(n3*min(w,h)/1080,1)/w", 2: "max(n3*min(w,h)/1080,1)/h"},
                    inter={1: edge},
                    ch={"r": ch("r"), "g": ch("g"), "b": ch("b")})]
    return FX("Comic", "CM", "Look",
              "cartoon / comic look: flat posterized colour + black ink outlines",
              "Comic - flattens the colours into a few bands (posterize) and draws dark ink lines on the edges, "
              "like a cartoon or comic book.",
              [label("COMIC  -  cartoon posterize + ink"),
               it("Levels", "Colour Levels", 5, 2, 12, "Fewer levels = flatter, more cartoon.", 2, 32),
               fl("Ink", "Ink Lines", 1.0, 0, 3, "Strength of the black outlines.", 0),
               fl("Width", "Line Width (px at 1080)", 2, 1, 6, "Thickness of the outlines.", 1),
               fl("Sat", "Saturation", 1.3, 0, 3, "Colour boost.", 0),
               mixc()],
              [], nodes, "CMCore", preview={"t": 0})
EFFECTS.append(_comic())

# ---------------------------------------------------------------- 24 Halftone
def _halftone():
    px, py = "(x*w)", "(y*h)"
    rx = f"({px}*n3+{py}*n4)"
    ry = f"(-{px}*n4+{py}*n3)"
    cx = "((floor(RX/s1)+0.5)*s1)".replace("RX", rx)
    cy = "((floor(RY/s1)+0.5)*s1)".replace("RY", ry)
    bx = f"(({cx})*n3-({cy})*n4)"
    by = f"(({cx})*n4+({cy})*n3)"
    BXc = f"(min(max({bx},0),w)/w)"
    BYc = f"(min(max({by},0),h)/h)"
    Ls = luma_at(BXc, BYc)
    rad = f"(s1*0.5*sqrt(max(1-{Ls},0))*1.35*n7)"
    dd = f"sqrt(({rx}-{cx})*({rx}-{cx})+({ry}-{cy})*({ry}-{cy}))"
    ink = clamp(f"{rad}-{dd}+0.5")
    m = [sel("n5", i) for i in range(4)]
    def ch(c, pop_ink, pop_paper):
        col = f"get{c}1b(i1,i2)"
        o = (f"{m[0]}*(1-i3)+{m[1]}*((1-i3)+{col}*i3)+{m[2]}*({col}*i3)"
             f"+{m[3]}*({pop_paper}*(1-i3)+{pop_ink}*i3)")
        return mix(f"{c}1", f"({o})*a1", "n6")
    nodes = [custom("HTCore", "C",
                    numbers={3: "cos(C.Angle*0.0174533)", 4: "sin(C.Angle*0.0174533)", 5: "C.Mode", 6: "C.Mix",
                             7: "C.DotScale", 1: "C.Dot"},
                    setup={1: "max(n1*min(w,h)/1080,2)"},
                    inter={1: BXc, 2: BYc, 3: ink},
                    ch={"r": ch("r", 0.95, 1.0), "g": ch("g", 0.2, 0.93), "b": ch("b", 0.55, 0.8)})]
    return FX("Halftone", "HT", "Look",
              "pop-art / newspaper halftone dots",
              "Halftone - rebuilds the image from printed dots: black on white newspaper, colour dots, or a pink "
              "pop-art print.",
              [label("HALFTONE  -  print dots"),
               cb("Mode", "Style", 1, ["Black Ink on White", "Colour Dots on White", "Colour Dots on Black", "Pop Art Pink"],
                  "Look of the print."),
               fl("Dot", "Dot Spacing (px at 1080)", 14, 4, 60, "Distance between dots.", 2),
               fl("DotScale", "Dot Size", 1.0, 0.3, 2, "Scale of the dots.", 0.05),
               fl("Angle", "Screen Angle", 45, 0, 90, "Rotation of the dot grid."),
               mixc()],
              [], nodes, "HTCore", preview={"t": 0, "Dot": 16})
EFFECTS.append(_halftone())

# ---------------------------------------------------------------- 25 Fisheye / bulge
def _fisheye():
    dx = "((x-p1x)*w/h)"
    dy = "(y-p1y)"
    r = f"sqrt({dx}*{dx}+{dy}*{dy})"
    t = clamp(f"1-{r}/max(n2,0.01)")
    f = f"(1-n1*({t})*({t})*0.7)"
    nodes = [custom("FECore", "C", numbers={1: "C.Amount*C.PUL", 2: "C.Radius", 3: "C.Mix"},
                    points={1: "Point(C.CX, C.CY)"},
                    inter={1: f},
                    ch={c: mix(f"{c}1", f"get{c}1b({safe('p1x+(x-p1x)*i1')},{safe('p1y+(y-p1y)*i1', 'y')})", "n3") for c in "rgba"})]
    return FX("Fisheye", "FE", "Distort",
              "bulge / pinch lens distortion, optional beat pulse",
              "Fisheye - bulges the centre out like a GoPro / skate fisheye (negative = pinch in). Pulse Every "
              "bumps it on the beat.",
              [label("FISHEYE  -  bulge / pinch"),
               fl("Amount", "Amount (+ bulge / - pinch)", 0.6, -1, 1.4, "Positive bulges, negative pinches."),
               fl("Radius", "Radius", 0.7, 0.1, 1.5, "Size of the affected area (frame heights).", 0.01),
               fl("CX", "Centre X", 0.5, 0, 1, "Centre left-right."),
               fl("CY", "Centre Y", 0.5, 0, 1, "Centre up-down."),
               *beat_controls(0, 8), mixc()],
              [PULSE], nodes, "FECore", preview={"t": 0, "Amount": 1.3, "Radius": 0.9})
EFFECTS.append(_fisheye())

# ---------------------------------------------------------------- 26 NeonEdges
def _neon():
    lx = luma_at("x+s1", "y")
    lxm = luma_at("x-s1", "y")
    ly = luma_at("x", "y+s2")
    lym = luma_at("x", "y-s2")
    edge = clamp(f"sqrt(({lx}-{lxm})*({lx}-{lxm})+({ly}-{lym})*({ly}-{lym}))*n1*5-0.08")
    hh = "((x+y)*0.8+n3)"
    def ch(c, off):
        neon = f"(0.5+0.5*cos(360*({hh}-{off})))*i1*(1+n5)"
        base = f"{c}1*n4"
        return f"min({base}+{neon}-{base}*min({neon},1),4)"
    nodes = [custom("NECore", "C", numbers={1: "C.Strength", 2: "C.Width", 3: "time*C.Cycle*0.01+C.Hue", 4: "C.BG", 5: "C.Boost"},
                    setup={1: "max(n2*min(w,h)/1080,1)/w", 2: "max(n2*min(w,h)/1080,1)/h"},
                    inter={1: edge},
                    ch={"r": ch("r", 0), "g": ch("g", 0.333), "b": ch("b", 0.667), "a": "max(a1*n4,i1)"})]
    return FX("NeonEdges", "NE", "Glitch",
              "glowing rainbow neon outlines over a dark frame",
              "Neon Edges - finds the outlines in the image and turns them into glowing rainbow neon lines. "
              "Background keeps some of the original video.",
              [label("NEON EDGES  -  glowing outlines"),
               fl("Strength", "Edge Strength", 1.2, 0, 4, "How many edges light up.", 0),
               fl("Width", "Line Width (px at 1080)", 2, 1, 6, "Thickness of the lines.", 1),
               fl("BG", "Background Video", 0.15, 0, 1, "0 = black background, 1 = full video under the lines.", 0, 1),
               fl("Boost", "Glow Boost", 0.4, 0, 2, "Extra brightness on the lines.", 0),
               fl("Hue", "Colour Offset", 0, 0, 1, "Shift the rainbow colours."),
               fl("Cycle", "Colour Cycle Speed", 1.0, -5, 5, "Animate the colours.")],
              [], nodes, "NECore", preview={"t": 0})
EFFECTS.append(_neon())

# ---------------------------------------------------------------- 27 Symmetry
def _symmetry():
    m = [sel("n1", i) for i in range(5)]
    uL = "(n2-abs(x-n2))"
    uR = "(n2+abs(x-n2))"
    vT = "(n3+abs(y-n3))"
    vB = "(n3-abs(y-n3))"
    U = safe(f"{m[0]}*{uL}+{m[1]}*{uR}+({m[2]}+{m[3]})*x+{m[4]}*{uL}")
    Vv = safe(f"({m[0]}+{m[1]})*y+{m[2]}*{vT}+{m[3]}*{vB}+{m[4]}*{vT}", "y")
    nodes = [custom("SYCore", "C", numbers={1: "C.Mode", 2: "C.AxisX", 3: "C.AxisY", 4: "C.Mix"},
                    inter={1: U, 2: Vv},
                    ch={c: mix(f"{c}1", f"get{c}1b(i1,i2)", "n4") for c in "rgba"})]
    return FX("Symmetry", "SY", "Mirror",
              "mirror half of the frame onto the other half (or 4-way)",
              "Symmetry - copies one half of the frame onto the other like a mirror: left, right, top, bottom or "
              "all four quarters. Move the axis to choose where the fold is.",
              [label("SYMMETRY  -  mirror halves"),
               cb("Mode", "Mirror", 0, ["Left -> Right", "Right -> Left", "Top -> Bottom", "Bottom -> Top", "4-Way (top-left)"],
                  "Which half is copied onto the other."),
               fl("AxisX", "Vertical Fold Position", 0.5, 0, 1, "Where the left/right fold is."),
               fl("AxisY", "Horizontal Fold Position", 0.5, 0, 1, "Where the top/bottom fold is."),
               mixc()],
              [], nodes, "SYCore", preview={"t": 0})
EFFECTS.append(_symmetry())

# ---------------------------------------------------------------- 28 CinemaBars
BARS = [("2.39:1 Cinemascope", 2.39), ("2.00:1 Univisium", 2.0), ("1.85:1 Film", 1.85),
        ("16:9", 16 / 9), ("4:3", 4 / 3), ("1:1 Square", 1.0), ("4:5 Portrait", 0.8), ("9:16 Vertical", 9 / 16)]
def _bars():
    P = "min(1, max(0, (time-C.StartAt)/max(C.Dur,1)))"
    hid = [("AR", chain("C.Aspect", [f"{a:.5f}" for _, a in BARS], 2.39)),
           ("PR", P),
           ("K", "iif(C.Anim==0, 1, iif(C.Anim==1, 1-(1-C.PR)*(1-C.PR), (1-C.PR)*(1-C.PR)))")]
    vh = "min(1,(w/h)/n1)"
    vw = "min(1,n1/(w/h))"
    bh = f"((1-{vh})*0.5*n2)"
    bw = f"((1-{vw})*0.5*n2)"
    inside = (f"min(min({clamp(f'(y-{bh})*h')},{clamp(f'(1-{bh}-y)*h')}),"
              f"min({clamp(f'(x-{bw})*w')},{clamp(f'(1-{bw}-x)*w')}))")
    nodes = [custom("CBCore", "C", numbers={1: "C.AR", 2: "C.K", 3: "C.Shade", 4: "C.Opacity"},
                    inter={1: inside},
                    ch={**{c: f"{c}1*i1+(1-i1)*(n3*n4+{c}1*(1-n4))" for c in "rgb"},
                        "a": "a1*i1+(1-i1)*(n4+a1*(1-n4))"})]
    return FX("CinemaBars", "CB", "Look",
              "animated letterbox / pillar bars to any aspect ratio",
              "Cinema Bars - adds black bars to crop the frame to a cinema aspect (2.39:1...) or to a square / "
              "portrait box. Animate them sliding in or out. Works best on an Adjustment Clip.",
              [label("CINEMA BARS  -  letterbox"),
               cb("Aspect", "Aspect", 0, [n for n, _ in BARS], "Shape of the visible picture."),
               cb("Anim", "Animate", 0, ["Static", "Slide In", "Slide Out"], "Bars slide in or out from Start Frame."),
               it("StartAt", "Start Frame", 0, 0, 300, "Frame where the slide starts.", 0),
               it("Dur", "Duration (frames)", 20, 1, 120, "Slide length.", 1),
               fl("Shade", "Bar Colour (black - white)", 0, 0, 1, "0 = black bars, 1 = white.", 0, 1),
               fl("Opacity", "Bar Opacity", 1, 0, 1, "0 = see-through bars.", 0, 1)],
              hid, nodes, "CBCore", preview={"t": 0})
EFFECTS.append(_bars())


# ==========================================================================
#  .setting writer
# ==========================================================================
def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def fusion_expr(e, fx, self_ref=False):
    """C.Name -> <Code>Ctrl.kName (or bare kName inside the Ctrl itself)."""
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
              'TEC_Lines = 1']
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
    T = "\t"
    o = ["{", f"{T}Tools = ordered() {{", f"{T*2}{fx.name} = MacroOperator {{",
         f"{T*3}CtrlWZoom = false,", f"{T*3}NameSet = true,",
         f"{T*3}CustomData = {{ HelpPage = {q(fx.help)}, }},",
         f"{T*3}Inputs = ordered() {{",
         f'{T*4}MainInput1 = InstanceInput {{ SourceOp = "{fx.ctrl}", Source = "Input", }},']
    n = 1
    for cid, kind, cname, d, ex, tip in fx.controls:
        if kind == "label":
            o.append(f'{T*4}Input{n} = InstanceInput {{ SourceOp = "{fx.ctrl}", Source = "k{cid}", }},')
        elif kind == "text":
            o.append(f'{T*4}Input{n} = InstanceInput {{ SourceOp = "{fx.ctrl}", Source = "k{cid}", Name = {q(cname)}, }},')
        else:
            o.append(f'{T*4}Input{n} = InstanceInput {{ SourceOp = "{fx.ctrl}", Source = "k{cid}", Name = {q(cname)}, Default = {d}, }},')
        n += 1
    for line in fx.extra_inputs:
        o.append(f"{T*4}{line},")
    o += [f"{T*3}}},", f"{T*3}Outputs = {{",
          f'{T*4}MainOutput1 = InstanceOutput {{ SourceOp = "{fx.out}", Source = "Output", }},',
          f"{T*3}}},", f"{T*3}ViewInfo = GroupInfo {{ Pos = {{ 0, 0 }}, }},", f"{T*3}Tools = ordered() {{"]

    # Ctrl
    o += [f"{T*4}{fx.ctrl} = BrightnessContrast {{", f"{T*5}CtrlWZoom = false,", f"{T*5}NameSet = true,",
          f"{T*5}Inputs = {{"]
    for cid, kind, _, d, _, _ in fx.controls:
        if kind == "label":
            continue
        if kind == "text":
            o.append(f'{T*6}k{cid} = Input {{ Value = "{d}", }},')
        else:
            o.append(f"{T*6}k{cid} = Input {{ Value = {d}, }},")
    for hid, expr in fx.hidden:
        o.append(f"{T*6}k{hid} = Input {{ Value = 0, Expression = {q(fusion_expr(expr, fx, self_ref=True))}, }},")
    o += [f"{T*5}}},", f"{T*5}ViewInfo = OperatorInfo {{ Pos = {{ 0, 0 }}, }},", f"{T*5}UserControls = ordered() {{"]
    for c in fx.controls:
        o.append(f"{T*6}" + user_control(*c))
    for hid, _ in fx.hidden:
        o.append(f"{T*6}" + hidden_control(hid))
    o += [f"{T*5}}},", f"{T*4}}},"]

    for nd in fx.nodes:
        o += [f"{T*4}{nd.name} = {nd.kind} {{", f"{T*5}CtrlWZoom = false,", f"{T*5}NameSet = true,", f"{T*5}Inputs = {{"]
        for k, v in nd.inputs:
            o.append(f"{T*6}{k} = {value_str(v, fx)},")
        o += [f"{T*5}}},", f"{T*5}ViewInfo = OperatorInfo {{ Pos = {{ {nd.pos[0]}, {nd.pos[1]} }}, }},", f"{T*4}}},"]
    o += [f"{T*3}}},", f"{T*2}}},", f"{T}}},", f'{T}ActiveTool = "{fx.name}"', "}"]
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
