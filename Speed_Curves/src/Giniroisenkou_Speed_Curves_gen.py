#!/usr/bin/env python3
"""
Giniroisenkou_Speed_Curves_gen.py - builds and packages Speed_Curves.

    python src/Giniroisenkou_Speed_Curves_gen.py

1. writes the macros to build/Edit/Effects/Speed_Curves/ (main effect with
   every preset in a dropdown + one quick effect per preset)
2. draws a 320x180 Effects-panel thumbnail beside every .setting
3. draws docs/Giniroisenkou_Speed_Curves_cheatsheet.png (all icons)
4. packs Giniroisenkou_Speed_Curves.drfx in the plugin folder (drag-install file)

Needs Python 3 with Pillow. Offline check of the macro maths:
    lua src/Giniroisenkou_Speed_Curves_test.lua

How it works
------------
One Ctrl node (SCCtrl, a pass-through BrightnessContrast) carries every
user control. A TimeStretcher (SCTime) fetches source frames; its
SourceTime is a Lua expression that evaluates the chosen speed curve
F(u) -> s, where u = normalised output time (0..1 across the clip) and
s = normalised source time. A Text+ HUD (optional) shows the live speed.

To add or tweak a preset: edit PRESETS (the combo list), the matching
branch in CURVE_LUA and its Python twin curve(), and SHORT. Then re-run.
"""
import os, zipfile

NAME = "Speed_Curves"
PREFIX = "Giniroisenkou_Speed_Curves"
SPARKLINES = True   # speed graph after each preset name in the dropdown; False if Resolve shows boxes
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build", "Edit", "Effects", NAME)
DOCS = os.path.join(ROOT, "docs")

# index -> (label shown in the Inspector, one-line description for README)
PRESETS = [
    ("Normal (bypass)",              "1x, untouched"),
    ("Boomerang",                    "forward then backward; Cycles = how many back-and-forths"),
    ("Slow-Mo Hit (fast-slow-fast)", "classic velocity ramp: fast in, slow-mo on the Hit Point, fast out"),
    ("Speed Burst (slow-fast-slow)", "slow, whip to Max Speed around the Hit Point, slow again"),
    ("Velocity Pulses (beat)",       "Cycles x slow-mo hits spread evenly - line Cycles up with the beat"),
    ("Freeze Hit",                   "ramps down into a freeze frame at the Hit Point, holds, ramps out"),
    ("Slow Down Into End",           "normal speed, then eases into slow-mo from the Hit Point to the end"),
    ("Speed Up Into End",            "normal speed, then accelerates to Max Speed from the Hit Point"),
    ("Accelerate (ease in)",         "starts slow, ends fast across the whole clip"),
    ("Decelerate (ease out)",        "starts fast, ends slow across the whole clip"),
    ("Smooth In-Out",                "eases in and out, fastest in the middle"),
    ("Reverse",                      "plays backwards"),
    ("Rewind",                       "plays forward to the Hit Point then rewinds (VHS style) to the start"),
]

# ---------------------------------------------------------------------------
# The curve, as Lua. Kept free of newlines-sensitive syntax so it can be
# embedded on one line inside a Fusion ':' expression. LuaJIT/5.1 compatible.
# Globals expected: P (preset), I (intensity 0..1), H (hit 0..1), W (ramp
# width 0..0.5), HO (hold 0..0.5), M (min speed), X (max speed),
# C (cycles), FIT (1 = fit whole clip, 0 = keep 1x), EZ (boomerang ease)
# ---------------------------------------------------------------------------
CURVE_LUA = r"""
local pi, sin, abs, floor, max, min = math.pi, math.sin, math.abs, math.floor, math.max, math.min
local function cl(x, a, b) if x < a then return a elseif x > b then return b else return x end end
local function sm(x) x = cl(x, 0, 1); return x * x * (3 - 2 * x) end
local function up(x, w) return 0.5 * (x - w / pi * sin(pi * x / w)) end
local function dn(x, w) return 0.5 * (x + w / pi * sin(pi * x / w)) end
local function win(u, h, w, ho)
  w = max(w, 0.0001)
  local a1 = h - ho / 2 - w; local a2 = h - ho / 2; local a3 = h + ho / 2; local a4 = a3 + w
  return up(cl(u, a1, a2) - a1, w) + (cl(u, a2, a3) - a2) + dn(cl(u, a3, a4) - a3, w)
end
local function openwin(u, h, w)
  w = max(w, 0.0001)
  return up(cl(u, h, h + w) - h, w) + max(u - h - w, 0)
end
local function G(u)
  if P == 2 then return u + (M - 1) * win(u, H, W, HO)
  elseif P == 3 then return u + (X - 1) * win(u, H, W, HO)
  elseif P == 4 then
    local g = u; local n = max(floor(C + 0.5), 1); local w = min(W, 0.5 / n)
    for k = 0, n - 1 do g = g + (M - 1) * win(u, (k + 0.5) / n, w, 0) end
    return g
  elseif P == 5 then return u - win(u, H, W, HO)
  elseif P == 6 then return u + (M - 1) * openwin(u, H, W)
  elseif P == 7 then return u + (X - 1) * openwin(u, H, W)
  end
  return u
end
local function F(u)
  local s
  if P == 1 then
    local n = max(C, 0.5); local f = (u * n) % 1; local t = 1 - abs(2 * f - 1)
    s = t + EZ * (sm(t) - t)
  elseif P >= 2 and P <= 7 then
    if FIT > 0.5 then local g0, g1 = G(0), G(1); s = (G(u) - g0) / max(g1 - g0, 0.0001) else s = G(u) - G(0) end
  elseif P == 8 then s = u ^ X
  elseif P == 9 then s = 1 - (1 - u) ^ X
  elseif P == 10 then s = sm(u)
  elseif P == 11 then s = 1 - u
  elseif P == 12 then
    local h = cl(H, 0.05, 0.95)
    if u < h then s = u else s = h * (1 - sm((u - h) / (1 - h))) end
  else s = u end
  s = u + I * (s - u)
  return cl(s, 0, 1)
end
"""

# ---------------------------------------------------------------------------
# Python twin of CURVE_LUA (used only for icons + sparklines; the plugin
# itself runs the Lua). tests/test_setting.lua cross-checks the two.
# ---------------------------------------------------------------------------
import math
DEFAULTS = dict(I=1.0, H=0.5, W=0.12, HO=0.1, M=0.25, X=3.0, C=1.0, FIT=1, EZ=0.5)

def curve(P, u, I=1.0, H=0.5, W=0.12, HO=0.1, M=0.25, X=3.0, C=1.0, FIT=1, EZ=0.5):
    cl = lambda x, a, b: a if x < a else (b if x > b else x)
    def sm(x): x = cl(x, 0, 1); return x * x * (3 - 2 * x)
    up = lambda x, w: 0.5 * (x - w / math.pi * math.sin(math.pi * x / w))
    dn = lambda x, w: 0.5 * (x + w / math.pi * math.sin(math.pi * x / w))
    def win(u, h, w, ho):
        w = max(w, 0.0001); a1 = h - ho / 2 - w; a2 = h - ho / 2; a3 = h + ho / 2; a4 = a3 + w
        return up(cl(u, a1, a2) - a1, w) + (cl(u, a2, a3) - a2) + dn(cl(u, a3, a4) - a3, w)
    def openwin(u, h, w):
        w = max(w, 0.0001); return up(cl(u, h, h + w) - h, w) + max(u - h - w, 0)
    def G(u):
        if P == 2: return u + (M - 1) * win(u, H, W, HO)
        if P == 3: return u + (X - 1) * win(u, H, W, HO)
        if P == 4:
            n = max(math.floor(C + 0.5), 1); w = min(W, 0.5 / n); g = u
            for k in range(n): g += (M - 1) * win(u, (k + 0.5) / n, w, 0)
            return g
        if P == 5: return u - win(u, H, W, HO)
        if P == 6: return u + (M - 1) * openwin(u, H, W)
        if P == 7: return u + (X - 1) * openwin(u, H, W)
        return u
    if P == 1:
        n = max(C, 0.5); f = (u * n) % 1; t = 1 - abs(2 * f - 1); s = t + EZ * (sm(t) - t)
    elif 2 <= P <= 7:
        g0, g1 = G(0), G(1)
        s = (G(u) - g0) / max(g1 - g0, 0.0001) if FIT > 0.5 else G(u) - g0
    elif P == 8: s = u ** X
    elif P == 9: s = 1 - (1 - u) ** X
    elif P == 10: s = sm(u)
    elif P == 11: s = 1 - u
    elif P == 12:
        h = cl(H, 0.05, 0.95); s = u if u < h else h * (1 - sm((u - h) / (1 - h)))
    else: s = u
    return cl(u + I * (s - u), 0, 1)

# preset-specific defaults that make each icon/one-click effect read best
ICON_PARAMS = {4: dict(C=3)}

BLOCKS = "▁▂▃▄▅▆▇█"
def sparkline(P, n=12):
    """Speed over the clip: blocks = speed (low=slow-mo, tall=fast, 3x+ = full),
    · = frozen, ◂ = playing backwards."""
    kw = dict(DEFAULTS); kw.update(ICON_PARAMS.get(P, {}))
    out = []
    for i in range(n):
        a, b = i / n, (i + 1) / n
        v = (curve(P, b, **kw) - curve(P, a, **kw)) / (b - a)
        if v < -0.05: out.append("◂")
        elif v < 0.05: out.append("·")
        else: out.append(BLOCKS[min(7, int(v / 3 * 7.999))])
    return "".join(out)

def lua_oneline(src):
    lines = [l.strip() for l in src.strip().splitlines() if l.strip()]
    return " ".join(lines)

# Reads controls from SCCtrl into the globals the curve expects.
# Output-time normalisation uses the comp's render range (= the clip on the
# Edit page). Length Override (frames) replaces it if > 0.
PRELUDE = (
    "local c = SCCtrl; "
    "local P, I, H, W, HO = c.Preset, c.Intensity, c.HitPoint, c.RampWidth, c.Hold; "
    "local M, X, C, FIT, EZ = c.MinSpeed, c.MaxSpeed, c.Cycles, c.Timing, c.BoomerangEase; "
    "local rs = comp.RenderStart; local re = comp.RenderEnd; "
    "if c.LengthOverride > 0 then re = rs + c.LengthOverride - 1 end; "
    "local len = math.max(re - rs, 1); "
    "local u = math.min(math.max((time - rs) / len, 0), 1); "
    "local sin_ = c.SourceIn; local sout = c.SourceOut; "
)

SOURCE_TIME_EXPR = ":" + PRELUDE + lua_oneline(CURVE_LUA) + " " + (
    "local s = F(u); "
    "return rs + (sin_ + s * (sout - sin_)) * len"
)

HUD_EXPR = ":" + PRELUDE + lua_oneline(CURVE_LUA) + " " + (
    "local e = 0.5 / len; "
    "local a = F(math.max(u - e, 0)); local b = F(math.min(u + e, 1)); "
    "local d = (math.min(u + e, 1) - math.max(u - e, 0)); "
    "local v = (b - a) / math.max(d, 1e-6) * (sout - sin_); "
    "return Text(string.format('%s  x%.2f  src %d', v < -0.01 and 'REV' or (math.abs(v) < 0.02 and 'HOLD' or 'SPD'), math.abs(v), math.floor(rs + (sin_ + F(u) * (sout - sin_)) * len + 0.5)))"
)

def lua_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

# (id, label, kind, default, min, max) - kind: combo/slider/check/label/int
CONTROLS = [
    ("Preset",         "Preset",            "combo",  2,    None, None),
    ("Intensity",      "Intensity (mix)",   "slider", 1.0,  0.0,  1.0),
    ("HitPoint",       "Hit Point",         "slider", 0.5,  0.0,  1.0),
    ("RampWidth",      "Ramp Width",        "slider", 0.12, 0.01, 0.5),
    ("Hold",           "Hold Length",       "slider", 0.1,  0.0,  0.5),
    ("MinSpeed",       "Slow Speed",        "slider", 0.25, 0.0,  1.0),
    ("MaxSpeed",       "Fast Speed",        "slider", 3.0,  1.0,  8.0),
    ("Cycles",         "Cycles / Beats",    "slider", 1.0,  0.5,  8.0),
    ("BoomerangEase",  "Boomerang Ease",    "slider", 0.5,  0.0,  1.0),
    ("Timing",         "Fit Whole Clip",    "check",  1,    None, None),
    ("LblSrc",         "Source Range",      "label",  None, None, None),
    ("SourceIn",       "Source In",         "slider", 0.0,  0.0,  1.0),
    ("SourceOut",      "Source Out",        "slider", 1.0,  0.0,  1.0),
    ("LengthOverride", "Length Override (frames, 0=auto)", "int", 0, 0, 1000),
    ("LblOut",         "Output",            "label",  None, None, None),
    ("ShowHUD",        "Show Speed HUD",    "check",  0,    None, None),
]

def user_control(cid, label, kind, default, lo, hi, overrides=None):
    if overrides and cid in overrides: default = overrides[cid]
    L = [f'\t\t\t\t\t\t{cid} = {{',
         f'\t\t\t\t\t\t\tLINKS_Name = {lua_str(label)},',
         '\t\t\t\t\t\t\tLINKID_DataType = "Number",',
         '\t\t\t\t\t\t\tICS_ControlPage = "Controls",']
    if kind == "combo":
        L += ['\t\t\t\t\t\t\tINPID_InputControl = "ComboControl",',
              f'\t\t\t\t\t\t\tINP_Default = {default},', '\t\t\t\t\t\t\tINP_Integer = true,',
              '\t\t\t\t\t\t\tINP_MinScale = 0,', f'\t\t\t\t\t\t\tINP_MaxScale = {len(PRESETS)-1},']
        L += [f'\t\t\t\t\t\t\t{{ CCS_AddString = {lua_str(p[0] + ("   " + sparkline(i) if SPARKLINES else ""))} }},' for i, p in enumerate(PRESETS)]
        L += ['\t\t\t\t\t\t\tCC_LabelPosition = "Horizontal",']
    elif kind in ("slider", "int"):
        L += ['\t\t\t\t\t\t\tINPID_InputControl = "SliderControl",',
              f'\t\t\t\t\t\t\tINP_Default = {default},',
              f'\t\t\t\t\t\t\tINP_MinScale = {lo},', f'\t\t\t\t\t\t\tINP_MaxScale = {hi},',
              f'\t\t\t\t\t\t\tINP_MinAllowed = {lo},']
        if kind == "int":
            L += ['\t\t\t\t\t\t\tINP_Integer = true,']
        else:
            L += [f'\t\t\t\t\t\t\tINP_MaxAllowed = {hi if cid not in ("MaxSpeed","Cycles") else 1000},']
    elif kind == "check":
        L += ['\t\t\t\t\t\t\tINPID_InputControl = "CheckboxControl",',
              f'\t\t\t\t\t\t\tINP_Default = {default},', '\t\t\t\t\t\t\tINP_Integer = true,',
              '\t\t\t\t\t\t\tCBC_TriState = false,']
    elif kind == "label":
        L += ['\t\t\t\t\t\t\tINPID_InputControl = "LabelControl",',
              '\t\t\t\t\t\t\tLBLC_DropDownButton = false,', '\t\t\t\t\t\t\tINP_External = false,',
              '\t\t\t\t\t\t\tINP_Passive = true,']
    L += ['\t\t\t\t\t\t},']
    return "\n".join(L)

def build_setting(name=NAME, overrides=None):
    ov = overrides or {}
    ctrls = [(c[0], c[1], c[2], ov.get(c[0], c[3]), c[4], c[5]) for c in CONTROLS]
    ins = []
    n = 1
    for cid, label, kind, default, *_ in ctrls:
        extra = f", Default = {default}" if default is not None else ""
        ins.append(f'\t\t\t\tInput{n} = InstanceInput {{ SourceOp = "SCCtrl", Source = "{cid}", Name = {lua_str(label)}{extra}, }},')
        n += 1
    # frame-blend options straight from the TimeStretcher
    ins.append(f'\t\t\t\tInput{n} = InstanceInput {{ SourceOp = "SCTime", Source = "InterpolateBetweenFrames", Name = "Frame Blend", Default = 1, }},'); n += 1
    ins.append(f'\t\t\t\tInput{n} = InstanceInput {{ SourceOp = "SCTime", Source = "SampleSpread", Name = "Blend Spread", }},'); n += 1
    ins.append('\t\t\t\tMainInput1 = InstanceInput { SourceOp = "SCCtrl", Source = "Input", },')

    uc = "\n".join(user_control(*c) for c in ctrls)

    return f'''{{
	Tools = ordered() {{
		{name} = MacroOperator {{
			CtrlWZoom = false,
			NameSet = true,
			Inputs = ordered() {{
{chr(10).join(ins)}
			}},
			Outputs = {{
				MainOutput1 = InstanceOutput {{ SourceOp = "SCMerge", Source = "Output", }},
			}},
			ViewInfo = GroupInfo {{ Pos = {{ 0, 0 }} }},
			Tools = ordered() {{
				SCCtrl = BrightnessContrast {{
					CtrlWZoom = false,
					NameSet = true,
					Inputs = {{
{chr(10).join(f"						{c[0]} = Input {{ Value = {c[3]}, }}," for c in ctrls if c[3] is not None)}
					}},
					ViewInfo = OperatorInfo {{ Pos = {{ 0, 0 }} }},
					UserControls = ordered() {{
{uc}
					}},
				}},
				SCTime = TimeStretcher {{
					CtrlWZoom = false,
					NameSet = true,
					Inputs = {{
						SourceTime = Input {{
							Value = 0,
							Expression = {lua_str(SOURCE_TIME_EXPR)},
						}},
						InterpolateBetweenFrames = Input {{ Value = 1, }},
						Input = Input {{ SourceOp = "SCCtrl", Source = "Output", }},
					}},
					ViewInfo = OperatorInfo {{ Pos = {{ 110, 0 }} }},
				}},
				SCHud = TextPlus {{
					CtrlWZoom = false,
					NameSet = true,
					Inputs = {{
						UseFrameFormatSettings = Input {{ Value = 1, }},
						Center = Input {{ Value = {{ 0.5, 0.08 }}, }},
						Size = Input {{ Value = 0.06, }},
						Font = Input {{ Value = "Open Sans", }},
						Style = Input {{ Value = "Bold", }},
						StyledText = Input {{
							Value = "SPD",
							Expression = {lua_str(HUD_EXPR)},
						}},
						Red1 = Input {{ Value = 1, }},
						Green1 = Input {{ Value = 0.85, }},
						Blue1 = Input {{ Value = 0.1, }},
					}},
					ViewInfo = OperatorInfo {{ Pos = {{ 110, 60 }} }},
				}},
				SCMerge = Merge {{
					CtrlWZoom = false,
					NameSet = true,
					Inputs = {{
						Background = Input {{ SourceOp = "SCTime", Source = "Output", }},
						Foreground = Input {{ SourceOp = "SCHud", Source = "Output", }},
						Blend = Input {{ Value = 0, Expression = "SCCtrl.ShowHUD", }},
						PerformDepthMerge = Input {{ Value = 0, }},
					}},
					ViewInfo = OperatorInfo {{ Pos = {{ 220, 0 }} }},
				}},
			}},
		}},
	}},
	ActiveTool = "{name}",
}}
'''


# ---------------------------------------------------------------------------
# Icons (PIL). 320x180 like Resolve thumbnails. Line = source position over
# the clip (like Resolve's Retime Curve); colour = speed:
#   blue = slow-mo, white = ~1x, orange = fast, magenta = reverse, grey = frozen
# ---------------------------------------------------------------------------
ICON_W, ICON_H, SS = 320, 180, 4

def speed_colour(v):
    if v < -0.02: return (230, 70, 200)
    a = abs(v)
    if a < 0.03: return (150, 150, 160)
    if a < 1:   t = (a - 0.03) / 0.97; return tuple(int(x + (y - x) * t) for x, y in zip((60, 140, 255), (245, 245, 245)))
    t = min((a - 1) / 2, 1); return tuple(int(x + (y - x) * t) for x, y in zip((245, 245, 245), (255, 140, 30)))

def _font(size):
    from PIL import ImageFont
    for f in ("arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try: return ImageFont.truetype(f, size)
        except OSError: pass
    return ImageFont.load_default()

def draw_icon(P, label, path, params=None):
    from PIL import Image, ImageDraw
    kw = dict(DEFAULTS); kw.update(ICON_PARAMS.get(P, {})); kw.update(params or {})
    W_, H_ = ICON_W * SS, ICON_H * SS
    im = Image.new("RGB", (W_, H_), (24, 26, 31)); d = ImageDraw.Draw(im)
    x0, x1, y0, y1 = 22 * SS, (ICON_W - 22) * SS, 14 * SS, (ICON_H - 60) * SS
    d.rectangle([x0, y0, x1, y1], outline=(55, 58, 66), width=SS)
    for k in (1, 2, 3):
        gx = x0 + (x1 - x0) * k // 4; d.line([gx, y0, gx, y1], fill=(40, 43, 50), width=SS)
        gy = y0 + (y1 - y0) * k // 4; d.line([x0, gy, x1, gy], fill=(40, 43, 50), width=SS)
    # 1x reference diagonal (dashed)
    for k in range(0, 20, 2):
        a, b = k / 20, (k + 1) / 20
        d.line([x0 + (x1 - x0) * a, y1 - (y1 - y0) * a, x0 + (x1 - x0) * b, y1 - (y1 - y0) * b], fill=(70, 74, 84), width=SS)
    N = 240
    pts = [(i / N, curve(P, i / N, **kw)) for i in range(N + 1)]
    for (u0, s0), (u1, s1) in zip(pts, pts[1:]):
        v = (s1 - s0) / (u1 - u0)
        d.line([x0 + (x1 - x0) * u0, y1 - (y1 - y0) * s0, x0 + (x1 - x0) * u1, y1 - (y1 - y0) * s1],
               fill=speed_colour(v), width=6 * SS)
    # speed ribbon
    ry0, ry1 = y1 + 8 * SS, y1 + 18 * SS
    for (u0, s0), (u1, s1) in zip(pts, pts[1:]):
        d.rectangle([x0 + (x1 - x0) * u0, ry0, x0 + (x1 - x0) * u1 + SS, ry1], fill=speed_colour((s1 - s0) / (u1 - u0)))
    # hit point marker for presets that use it
    if P in (2, 3, 5, 6, 7, 12):
        hx = x0 + (x1 - x0) * kw["H"]
        d.polygon([(hx - 7 * SS, y0 - 1 * SS), (hx + 7 * SS, y0 - 1 * SS), (hx, y0 + 10 * SS)], fill=(255, 210, 40))
        d.line([hx, y0, hx, y1], fill=(120, 105, 40), width=SS)
    f = _font(20 * SS)
    tw = d.textlength(label, font=f)
    d.text(((W_ - tw) / 2, (ICON_H - 32) * SS), label, font=f, fill=(235, 235, 240))
    im.resize((ICON_W, ICON_H), Image.LANCZOS).save(path)

def cheat_sheet(paths, out):
    from PIL import Image
    cols = 4; rows = (len(paths) + cols - 1) // cols; pad = 8
    sheet = Image.new("RGB", (cols * (ICON_W + pad) + pad, rows * (ICON_H + pad) + pad), (12, 13, 16))
    for i, pth in enumerate(paths):
        sheet.paste(Image.open(pth), (pad + (i % cols) * (ICON_W + pad), pad + (i // cols) * (ICON_H + pad)))
    sheet.save(out)

SHORT = ["Normal", "Boomerang", "Slow-Mo Hit", "Speed Burst", "Velocity Pulses", "Freeze Hit",
         "Slow Down End", "Speed Up End", "Accelerate", "Decelerate", "Smooth In-Out", "Reverse", "Rewind"]
PARAM_TO_CTRL = dict(C="Cycles", H="HitPoint", W="RampWidth", HO="Hold", M="MinSpeed", X="MaxSpeed", EZ="BoomerangEase")

def main():
    os.makedirs(BUILD, exist_ok=True); os.makedirs(DOCS, exist_ok=True)
    files = []  # (path inside .drfx, local path)

    def emit(fname, preset, label, overrides=None):
        sp = os.path.join(BUILD, fname + ".setting")
        with open(sp, "w", encoding="utf-8", newline="\n") as f:
            f.write(build_setting(name=fname, overrides=overrides))
        pp = os.path.join(BUILD, fname + ".png")
        draw_icon(preset, label, pp)
        files.extend([(f"Edit/Effects/{NAME}/{fname}.setting", sp), (f"Edit/Effects/{NAME}/{fname}.png", pp)])
        return pp

    # main effect: every preset in the dropdown
    emit(NAME, 2, "Speed Curves (all)")
    # one quick effect per preset, preset already selected
    icon_paths = []
    for i, short in enumerate(SHORT):
        if i == 0:
            p0 = os.path.join(BUILD, "_normal_icon.png"); draw_icon(0, short, p0); icon_paths.append(p0); continue
        ov = {"Preset": i}
        for k, v in ICON_PARAMS.get(i, {}).items(): ov[PARAM_TO_CTRL[k]] = v
        icon_paths.append(emit(f"{NAME}_{short.replace(' ', '').replace('-', '')}", i, short, ov))

    cheat_sheet(icon_paths, os.path.join(DOCS, f"{PREFIX}_cheatsheet.png"))
    with open(os.path.join(ROOT, "build", "curve.lua"), "w", encoding="utf-8") as f: f.write(CURVE_LUA)

    dp = os.path.join(ROOT, f"{PREFIX}.drfx")
    with zipfile.ZipFile(dp, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, loc in files: z.write(loc, arc)
    print("wrote", dp, "with", len(files), "files")
    for i, p in enumerate(PRESETS): print(f"  {i:2d} {p[0]:30s} {sparkline(i)}")


if __name__ == "__main__":
    main()
