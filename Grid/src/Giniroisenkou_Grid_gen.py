#!/usr/bin/env python3
"""
Grid generator -- emits the Fusion macro(s) for DaVinci Resolve's Edit page.

One per-clip Effect:

  Mode 0  Cells        the video stays where it is, divided into Columns x Rows
                       cells. Show: all cells / one cell / picked cells (tick
                       boxes 1-81) / cells 1..N (keyframe N = reveal box by box).
                       Hidden cells and gaps are TRANSPARENT: the track below shows.
  Mode 1  Single Cell  the whole video shrunk into one cell (stack clips on tracks).

Everything runs in ONE CustomTool (per-pixel math):
  Image1 = the effect's own input  -> output is ALWAYS the same size as the input
           (a per-clip Edit effect that returns a different size crashed Resolve 21.1)
  Image2 = the input, pre-resized to its displayed size (clean downscale)
On the Edit page the effect receives the clip already placed in the timeline frame
(after the clip's Inspector Zoom / Position), so with Source Aspect = Auto the video
stays exactly as framed and the cells sit on the timeline frame. Hidden cells are
transparent and show the track below.
Single Cell with a clean 16:9 picture: set the clip's Scaling to Stretch and Source
Aspect to 16:9 (the effect then undoes the stretch inside the cell).

Resolve limits found by probing a CustomTool in Resolve 21.1 (see comments below):
NumberIn values are clamped to +-1,000,000, pow() returns 0 (use ^), intermediates
may use earlier intermediates, Point inputs are not clamped.

Usage:  python Giniroisenkou_Grid_gen.py  -> writes build/Edit/Effects/Grid/*.setting
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "build", "Edit", "Effects", "Grid")

# --------------------------------------------------------------------------
# option tables (edit here to add presets / aspects)
# --------------------------------------------------------------------------
MODES = ["Cells (video divided into cells)",
         "Single Cell (whole video fitted in one cell)"]

SHOWS = ["All cells",
         "One cell (Cell)",
         "Picked cells (tick boxes below)",
         "Cells 1 to N (reveal box by box)"]
NTICK = 81          # tick boxes for cells 1..81 (up to 9x9)

FRAME_PRESETS = [  # label, w, h   (last = custom)
    ("Reels / TikTok / Shorts 9:16  1080x1920", 1080, 1920),
    ("Instagram Portrait 4:5  1080x1350", 1080, 1350),
    ("Square 1:1  1080x1080", 1080, 1080),
    ("YouTube 16:9  1920x1080", 1920, 1080),
    ("4K UHD 16:9  3840x2160", 3840, 2160),
    ("4K Vertical 9:16  2160x3840", 2160, 3840),
    ("Custom (Frame Width / Height)", None, None),
]

ASPECTS = [  # label, w/h   (first = timeline aspect, last = custom)
    ("Auto (the clip's own shape)", None),
    ("16:9  (landscape camera, 4K/HD)", 16 / 9),
    ("9:16  (vertical phone)", 9 / 16),
    ("4:3", 4 / 3),
    ("3:4", 3 / 4),
    ("1:1", 1.0),
    ("4:5", 4 / 5),
    ("3:2  (photo)", 3 / 2),
    ("2.39:1  (cinema)", 2.39),
    ("Custom (Aspect W / H)", None),
]


def chain(sel, values, last):
    """iif(sel==0, v0, iif(sel==1, v1, ... last))"""
    e = str(last)
    for i in range(len(values) - 1, -1, -1):
        e = f"iif({sel}=={i}, {values[i]}, {e})"
    return e


# --------------------------------------------------------------------------
# Ctrl node: hidden math as simple expressions (evaluated in dependency order)
# Unit rule: Gap / Margin / Radius are "px at 1080" and scale with the frame.
# --------------------------------------------------------------------------
fp = [p for p in FRAME_PRESETS[:-1]]
asp = [a for a in ASPECTS[1:-1]]

HIDDEN = [  # name, expression  (order matters for the python validator only)
    ("IW", "self.Input.Width"),      # the effect's input size (probed: works in Resolve 21.1)
    ("IH", "self.Input.Height"),
    ("FW", chain("FramePreset", [w for _, w, _ in fp], "FrameWidth")),
    ("FH", chain("FramePreset", [h for _, _, h in fp], "FrameHeight")),
    ("UNIT", "min(FW, FH)/1080"),
    ("GPX", "TileGap*UNIT"),
    ("MPX", "Margin*UNIT"),
    ("RPX", "Radius*UNIT"),
    ("AS", "iif(SourceAspect==0, max(IW,1)/max(IH,1), " + chain("(SourceAspect-1)", [f"{a:.6f}" for _, a in asp], "AspectW/max(AspectH, 0.001)") + ")"),
    ("CW", "max((FW - 2*MPX - (Columns-1)*GPX)/Columns, 1)"),
    ("CH", "max((FH - 2*MPX - (Rows-1)*GPX)/Rows, 1)"),
    ("CELLC", "min(max(Cell, 1), Columns*Rows)"),
    ("CCOL", "(CELLC-1) - Columns*floor((CELLC-1)/Columns)"),
    ("CROW", "floor((CELLC-1)/Columns)"),
    ("BX", "iif(Mode==1, MPX + CCOL*(CW+GPX), 0)"),
    ("BY", "iif(Mode==1, MPX + CROW*(CH+GPX), 0)"),
    ("BW", "iif(Mode==1, CW, FW)"),
    ("BH", "iif(Mode==1, CH, FH)"),
    ("DW", "iif(FitMode==0, iif(AS > BW/BH, BH*Zoom*AS, BW*Zoom), iif(AS > BW/BH, BW*Zoom, BH*Zoom*AS))"),
    ("DH", "DW/AS"),
    ("CX", "BX + BW/2 - ReframeX*(DW-BW)/2 + OffsetX*UNIT"),
    ("CY", "BY + BH/2 + ReframeY*(DH-BH)/2 - OffsetY*UNIT"),
    ("KU", "FW/DW"),
    ("OU", "0.5 - CX/DW"),
    ("KV", "FH/DH"),
    ("OV", "0.5 + (CY - FH)/DH"),
] + [
    (f"TK{c+1}", " + ".join(f"T{k+1}*{2**(k-18*c)}" for k in range(18*c, min(18*c+18, NTICK))))
    for c in range(5)
] + [
]

# visible controls on the Ctrl node --------------------------------------
# (id, kind, name, default, extra dict, tooltip)
def combo(options):
    return {"combo": options}

VISIBLE = [
    ("LblLayout", "label", "GRID  -  divide the video into cells", None, {}, ""),
    ("Mode", "combo", "Mode", 0, combo(MODES),
     "Cells = the video stays in place, divided into Columns x Rows cells; choose which cells show below. "
     "Single Cell = the whole video shrunk into one cell."),
    ("Columns", "int", "Columns", 3, {"min": 1, "max": 12, "amin": 1, "amax": 32},
     "Number of columns. More columns = smaller cells."),
    ("Rows", "int", "Rows", 3, {"min": 1, "max": 12, "amin": 1, "amax": 32},
     "Number of rows. More rows = smaller cells."),

    ("LblShow", "label", "SHOW  -  which cells are visible (hidden = transparent)", None, {}, ""),
    ("Show", "combo", "Show", 2, combo(SHOWS),
     "All = every cell. One = only the cell number in Cell. Picked = the ticked boxes below (cells 1-81). "
     "1 to N = cells 1..N in reading order: keyframe N to reveal the video box by box."),
    ("Cell", "int", "Cell", 5, {"min": 1, "max": 36, "amin": 1, "amax": 1024},
     "Cell number for 'One cell' and for Single Cell mode. Numbered left->right, top->bottom "
     "(3x3: 1 2 3 / 4 5 6 / 7 8 9)."),
    ("RevealN", "int", "Cells 1 to N", 9, {"min": 0, "max": 36, "amin": 0, "amax": 1024},
     "For 'Cells 1 to N': how many cells are visible. Keyframe it (0 -> 9 on a 3x3) to reveal box by box."),
    ("Guide", "combo", "Guide (setup only)", 0, combo(["Off", "On - white lines, hidden cells dimmed (turn Off to render)"]),
     "Set-up helper only: draws white cell borders and shows hidden cells at 30% so you can see what you are "
     "toggling. It changes the picture, so turn it Off to see / render the real result."),
    ("LblTicks", "ticks", "Picked cells  -  ticked = visible (numbered left->right, top->bottom)", None, {}, ""),
    ("T1", "check", "1", 1, {}, "Cell 1: ticked = visible (Show = Picked cells)."),
    ("T2", "check", "2", 1, {}, "Cell 2: ticked = visible (Show = Picked cells)."),
    ("T3", "check", "3", 1, {}, "Cell 3: ticked = visible (Show = Picked cells)."),
    ("T4", "check", "4", 1, {}, "Cell 4: ticked = visible (Show = Picked cells)."),
    ("T5", "check", "5", 1, {}, "Cell 5: ticked = visible (Show = Picked cells)."),
    ("T6", "check", "6", 1, {}, "Cell 6: ticked = visible (Show = Picked cells)."),
    ("T7", "check", "7", 1, {}, "Cell 7: ticked = visible (Show = Picked cells)."),
    ("T8", "check", "8", 1, {}, "Cell 8: ticked = visible (Show = Picked cells)."),
    ("T9", "check", "9", 1, {}, "Cell 9: ticked = visible (Show = Picked cells)."),
    ("T10", "check", "10", 1, {}, "Cell 10: ticked = visible (Show = Picked cells)."),
    ("T11", "check", "11", 1, {}, "Cell 11: ticked = visible (Show = Picked cells)."),
    ("T12", "check", "12", 1, {}, "Cell 12: ticked = visible (Show = Picked cells)."),
    ("T13", "check", "13", 1, {}, "Cell 13: ticked = visible (Show = Picked cells)."),
    ("T14", "check", "14", 1, {}, "Cell 14: ticked = visible (Show = Picked cells)."),
    ("T15", "check", "15", 1, {}, "Cell 15: ticked = visible (Show = Picked cells)."),
    ("T16", "check", "16", 1, {}, "Cell 16: ticked = visible (Show = Picked cells)."),
    ("T17", "check", "17", 1, {}, "Cell 17: ticked = visible (Show = Picked cells)."),
    ("T18", "check", "18", 1, {}, "Cell 18: ticked = visible (Show = Picked cells)."),
    ("T19", "check", "19", 1, {}, "Cell 19: ticked = visible (Show = Picked cells)."),
    ("T20", "check", "20", 1, {}, "Cell 20: ticked = visible (Show = Picked cells)."),
    ("T21", "check", "21", 1, {}, "Cell 21: ticked = visible (Show = Picked cells)."),
    ("T22", "check", "22", 1, {}, "Cell 22: ticked = visible (Show = Picked cells)."),
    ("T23", "check", "23", 1, {}, "Cell 23: ticked = visible (Show = Picked cells)."),
    ("T24", "check", "24", 1, {}, "Cell 24: ticked = visible (Show = Picked cells)."),
    ("T25", "check", "25", 1, {}, "Cell 25: ticked = visible (Show = Picked cells)."),
    ("T26", "check", "26", 1, {}, "Cell 26: ticked = visible (Show = Picked cells)."),
    ("T27", "check", "27", 1, {}, "Cell 27: ticked = visible (Show = Picked cells)."),
    ("T28", "check", "28", 1, {}, "Cell 28: ticked = visible (Show = Picked cells)."),
    ("T29", "check", "29", 1, {}, "Cell 29: ticked = visible (Show = Picked cells)."),
    ("T30", "check", "30", 1, {}, "Cell 30: ticked = visible (Show = Picked cells)."),
    ("T31", "check", "31", 1, {}, "Cell 31: ticked = visible (Show = Picked cells)."),
    ("T32", "check", "32", 1, {}, "Cell 32: ticked = visible (Show = Picked cells)."),
    ("T33", "check", "33", 1, {}, "Cell 33: ticked = visible (Show = Picked cells)."),
    ("T34", "check", "34", 1, {}, "Cell 34: ticked = visible (Show = Picked cells)."),
    ("T35", "check", "35", 1, {}, "Cell 35: ticked = visible (Show = Picked cells)."),
    ("T36", "check", "36", 1, {}, "Cell 36: ticked = visible (Show = Picked cells)."),
    ("T37", "check", "37", 1, {}, "Cell 37: ticked = visible (Show = Picked cells)."),
    ("T38", "check", "38", 1, {}, "Cell 38: ticked = visible (Show = Picked cells)."),
    ("T39", "check", "39", 1, {}, "Cell 39: ticked = visible (Show = Picked cells)."),
    ("T40", "check", "40", 1, {}, "Cell 40: ticked = visible (Show = Picked cells)."),
    ("T41", "check", "41", 1, {}, "Cell 41: ticked = visible (Show = Picked cells)."),
    ("T42", "check", "42", 1, {}, "Cell 42: ticked = visible (Show = Picked cells)."),
    ("T43", "check", "43", 1, {}, "Cell 43: ticked = visible (Show = Picked cells)."),
    ("T44", "check", "44", 1, {}, "Cell 44: ticked = visible (Show = Picked cells)."),
    ("T45", "check", "45", 1, {}, "Cell 45: ticked = visible (Show = Picked cells)."),
    ("T46", "check", "46", 1, {}, "Cell 46: ticked = visible (Show = Picked cells)."),
    ("T47", "check", "47", 1, {}, "Cell 47: ticked = visible (Show = Picked cells)."),
    ("T48", "check", "48", 1, {}, "Cell 48: ticked = visible (Show = Picked cells)."),
    ("T49", "check", "49", 1, {}, "Cell 49: ticked = visible (Show = Picked cells)."),
    ("T50", "check", "50", 1, {}, "Cell 50: ticked = visible (Show = Picked cells)."),
    ("T51", "check", "51", 1, {}, "Cell 51: ticked = visible (Show = Picked cells)."),
    ("T52", "check", "52", 1, {}, "Cell 52: ticked = visible (Show = Picked cells)."),
    ("T53", "check", "53", 1, {}, "Cell 53: ticked = visible (Show = Picked cells)."),
    ("T54", "check", "54", 1, {}, "Cell 54: ticked = visible (Show = Picked cells)."),
    ("T55", "check", "55", 1, {}, "Cell 55: ticked = visible (Show = Picked cells)."),
    ("T56", "check", "56", 1, {}, "Cell 56: ticked = visible (Show = Picked cells)."),
    ("T57", "check", "57", 1, {}, "Cell 57: ticked = visible (Show = Picked cells)."),
    ("T58", "check", "58", 1, {}, "Cell 58: ticked = visible (Show = Picked cells)."),
    ("T59", "check", "59", 1, {}, "Cell 59: ticked = visible (Show = Picked cells)."),
    ("T60", "check", "60", 1, {}, "Cell 60: ticked = visible (Show = Picked cells)."),
    ("T61", "check", "61", 1, {}, "Cell 61: ticked = visible (Show = Picked cells)."),
    ("T62", "check", "62", 1, {}, "Cell 62: ticked = visible (Show = Picked cells)."),
    ("T63", "check", "63", 1, {}, "Cell 63: ticked = visible (Show = Picked cells)."),
    ("T64", "check", "64", 1, {}, "Cell 64: ticked = visible (Show = Picked cells)."),
    ("T65", "check", "65", 1, {}, "Cell 65: ticked = visible (Show = Picked cells)."),
    ("T66", "check", "66", 1, {}, "Cell 66: ticked = visible (Show = Picked cells)."),
    ("T67", "check", "67", 1, {}, "Cell 67: ticked = visible (Show = Picked cells)."),
    ("T68", "check", "68", 1, {}, "Cell 68: ticked = visible (Show = Picked cells)."),
    ("T69", "check", "69", 1, {}, "Cell 69: ticked = visible (Show = Picked cells)."),
    ("T70", "check", "70", 1, {}, "Cell 70: ticked = visible (Show = Picked cells)."),
    ("T71", "check", "71", 1, {}, "Cell 71: ticked = visible (Show = Picked cells)."),
    ("T72", "check", "72", 1, {}, "Cell 72: ticked = visible (Show = Picked cells)."),
    ("T73", "check", "73", 1, {}, "Cell 73: ticked = visible (Show = Picked cells)."),
    ("T74", "check", "74", 1, {}, "Cell 74: ticked = visible (Show = Picked cells)."),
    ("T75", "check", "75", 1, {}, "Cell 75: ticked = visible (Show = Picked cells)."),
    ("T76", "check", "76", 1, {}, "Cell 76: ticked = visible (Show = Picked cells)."),
    ("T77", "check", "77", 1, {}, "Cell 77: ticked = visible (Show = Picked cells)."),
    ("T78", "check", "78", 1, {}, "Cell 78: ticked = visible (Show = Picked cells)."),
    ("T79", "check", "79", 1, {}, "Cell 79: ticked = visible (Show = Picked cells)."),
    ("T80", "check", "80", 1, {}, "Cell 80: ticked = visible (Show = Picked cells)."),
    ("T81", "check", "81", 1, {}, "Cell 81: ticked = visible (Show = Picked cells)."),

    ("LblLook", "label", "LOOK  -  gaps, margins, corners (px at 1080)", None, {}, ""),
    ("TileGap", "float", "Gap", 0, {"min": 0, "max": 60, "amin": 0},
     "Space between boxes, in px at 1080 (scales with the frame)."),
    ("Margin", "float", "Outer Margin", 0, {"min": 0, "max": 150, "amin": 0},
     "Space around the whole grid, in px at 1080."),
    ("Radius", "float", "Corner Radius", 0, {"min": 0, "max": 80, "amin": 0},
     "Rounded corners on every box, in px at 1080."),
    ("GapFill", "combo", "Gaps", 0, combo(["Transparent (track below shows)", "Filled with Colour"]),
     "What shows in the gaps between cells (set Gap above 0 to get lines). "
     "Transparent = the track below; Filled = the Colour below."),
    ("HiddenFill", "combo", "Hidden Cells", 0, combo(["Transparent (track below shows)", "Filled with Colour"]),
     "What shows in the cells you hide. Transparent = the track below; Filled = the Colour below (e.g. black)."),
    ("GapShade", "float", "Colour (black - white)", 0, {"min": 0, "max": 1, "amin": 0, "amax": 1},
     "Fill colour for Gaps / Hidden Cells set to 'Filled': 0 = black, 1 = white, in between = grey."),
    ("GapOpacity", "float", "Colour Opacity", 1, {"min": 0, "max": 1, "amin": 0, "amax": 1},
     "Opacity of the fill colour (1 = solid)."),

    ("LblFrame", "label", "FRAMING  -  how the video fills its box", None, {}, ""),
    ("SourceAspect", "combo", "Source Aspect", 0, combo([a for a, _ in ASPECTS]),
     "Auto = keep the video exactly as framed in the timeline (use this for Cells). "
     "For Single Cell with a clean 16:9 picture: set the clip's Scaling to Stretch and pick 16:9 here."),
    ("AspectW", "float", "Aspect W (Custom)", 16, {"min": 1, "max": 32, "amin": 0.01}, "Used when Source Aspect = Custom."),
    ("AspectH", "float", "Aspect H (Custom)", 9, {"min": 1, "max": 32, "amin": 0.01}, "Used when Source Aspect = Custom."),
    ("FitMode", "combo", "Fit", 0, combo(["Fill (crop to cover the box)", "Fit (whole video, letterbox)"]),
     "Fill covers the box (crops edges). Fit shows the whole video inside the box."),
    ("Zoom", "float", "Zoom", 1, {"min": 0.25, "max": 3, "amin": 0.01}, "Extra zoom on the video."),
    ("ReframeX", "float", "Reframe X", 0, {"min": -1, "max": 1},
     "Slide the video inside the box: -1 = show left edge, +1 = show right edge."),
    ("ReframeY", "float", "Reframe Y", 0, {"min": -1, "max": 1},
     "Slide the video inside the box: +1 = show top, -1 = show bottom."),
    ("OffsetX", "float", "Nudge X", 0, {"min": -200, "max": 200}, "Fine move in px at 1080."),
    ("OffsetY", "float", "Nudge Y", 0, {"min": -200, "max": 200}, "Fine move in px at 1080 (+ = up)."),

    ("LblOut", "label", "OUTPUT FRAME  -  match your timeline", None, {}, ""),
    ("FramePreset", "combo", "Frame", 0, combo([p[0] for p in FRAME_PRESETS]),
     "Output size. Must match the timeline resolution."),
    ("FrameWidth", "int", "Frame Width (Custom)", 1080, {"min": 16, "max": 4096, "amin": 16, "amax": 16384}, ""),
    ("FrameHeight", "int", "Frame Height (Custom)", 1920, {"min": 16, "max": 4096, "amin": 16, "amax": 16384}, ""),
]

# --------------------------------------------------------------------------
# CustomTool per-pixel math.  Only + - * / min max abs floor sqrt and the
# get??b() samplers -> no reliance on if()/comparison syntax.
# --------------------------------------------------------------------------
# Slots (a CustomTool has only NumberIn1-8, PointIn1-4, Setup1-4, Intermediate1-4).
# Resolve clamps every NumberIn to +-1,000,000 (also when set by expression) and
# pow() returns 0 there, so: every packed value stays < 262144 and powers use ^.
# Point inputs are not clamped.
#   n1 = Columns + 64*Rows + 4096*(Mode + 2*Show + 8*Guide)
#   n2 = cellIndex + 1024*N          n3 / n4 / n5 = gap / margin / radius (fraction of width)
#   n6 = gapShade*100 + 101*gapOpacity*100          n7 = tick boxes 1-18 (bits)
#   n8 = frame height / frame width
#   p1, p2 = source scale / offset     p3x p3y p4x p4y = tick boxes 19-36, 37-54, 55-72, 73-81
C = "(n1-64*floor(n1/64))"
R = "(floor(n1/64)-64*floor(n1/4096))"
FLAGS = "floor(n1/4096)"
GP = "(n3*w)"
MP = "(n4*w)"
RP = "(n5*w)"
HGT = "(w*n8)"
CW_ = f"((w-2*{MP}-({C}-1)*{GP})/{C})"
CH_ = f"(({HGT}-2*{MP}-({R}-1)*{GP})/{R})"

SETUP = {
    1: CW_,                                            # s1 cell width px
    2: CH_,                                            # s2 cell height px
    3: f"max(min({RP}, min({CW_}, {CH_})/2), 0)",      # s3 corner radius px
    4: FLAGS,                                          # s4 flags = Mode + 2*Show + 8*Guide
}
MODE = "(s4-2*floor(s4/2))"
SHOW = "(floor(s4/2)-4*floor(s4/8))"
GUIDE = "floor(s4/8)"
CI = "(n2-1024*floor(n2/1024))"                                    # chosen cell, 0-based
NN = "floor(n2/1024)"                                              # reveal count

U = "(x*p1x+p2x)"
V = "(y*p1y+p2y)"
COL = f"min(max(floor((x*w-{MP})/(s1+{GP})),0),{C}-1)"
ROW = f"min(max(floor(((1-y)*{HGT}-{MP})/(s2+{GP})),0),{R}-1)"
FX = f"(x*w-{MP}-{COL}*(s1+{GP}))"
FY = f"((1-y)*{HGT}-{MP}-{ROW}*(s2+{GP}))"
QX = f"(abs({FX}-s1/2)-(s1/2-s3))"
QY = f"(abs({FY}-s2/2)-(s2/2-s3))"
SDF = f"(sqrt(max({QX},0)*max({QX},0)+max({QY},0)*max({QY},0))+min(max({QX},{QY}),0)-s3)"
# Gap 0 and radius 0 -> cells are seamless (no half-transparent border pixel between cells)
SEAMLESS = f"(max(0,1-{GP}*1000000)*max(0,1-{RP}*1000000))"
TILE = f"min(max(0.5-{SDF},0)+{SEAMLESS},1)"
IDX = "i1"                                                         # this pixel's cell (Intermediate1)
M0, M1 = f"max(0,1-abs({MODE}))", f"max(0,1-abs({MODE}-1))"
SEL = f"max(0,1-abs({IDX}-{CI}))"

# tick box bit for this cell: chunk = floor(idx/18), bit = idx - 18*chunk
CHK = f"floor({IDX}/18)"
KB = f"({IDX}-18*{CHK})"
CHUNK = (f"(n7*max(0,1-abs({CHK}))+p3x*max(0,1-abs({CHK}-1))+p3y*max(0,1-abs({CHK}-2))"
         f"+p4x*max(0,1-abs({CHK}-3))+p4y*max(0,1-abs({CHK}-4)))")
PICK = (f"(min(max(81-{IDX},0),1)*(floor(({CHUNK}+0.5)/(2^{KB}))"
        f"-2*floor(({CHUNK}+0.5)/(2^({KB}+1)))))")
FIRST = f"min(max({NN}-{IDX},0),1)"
VIS = (f"(max(0,1-abs({SHOW}))+max(0,1-abs({SHOW}-1))*{SEL}"
       f"+max(0,1-abs({SHOW}-2))*{PICK}+max(0,1-abs({SHOW}-3))*{FIRST})")
VISM = f"({M0}*{VIS}+{M1}*{SEL})"                                   # this cell is shown

# n6 = shade*100 + 101*opacity*100 + 10201*(gapsFilled + 2*hiddenFilled)
N6L = "(n6-10201*floor(n6/10201))"
GS = f"(({N6L}-101*floor({N6L}/101))/100)"
GO = f"(floor({N6L}/101)/100)"
GFL = "(floor(n6/10201)-2*floor(n6/20402))"
HFL = "floor(n6/20402)"
# guide lines on the cell borders (about 2 px at 1080)
EX = f"min(abs({FX}),abs({FX}-s1))"
EY = f"min(abs({FY}),abs({FY}-s2))"
LINE = f"({GUIDE}*0.8*max(0,1-min({EX},{EY})/max(w/540,1)))"

INTER = {
    1: f"({COL}+{ROW}*{C})",                                  # i1 this pixel's cell index
    2: VISM,                                                  # i2 1 = this cell is shown
    3: TILE,                                                  # i3 cell shape (0 in gaps / margin)
    4: LINE,                                                  # i4 guide line coverage
}
COVER = f"(i3*(i2+(1-i2)*0.3*{GUIDE}))"                               # video coverage
# fill layer under the video: gap colour in gaps AND under shown cells (so cell edges stay
# solid against filled gaps), hidden colour in hidden cells
FILLA = f"(((1-i3)*{GFL}+i3*(i2*{GFL}+(1-i2)*{HFL}))*{GO})"


def _ch(c):
    fill = FILLA if c == "a" else f"({GS}*{FILLA})"
    base = f"(get{c}2b({U},{V})*{COVER}+{fill}*(1-geta2b({U},{V})*{COVER}))"
    return f"(i4+{base}*(1-i4))"          # white guide line on top (premultiplied: rgb = a = i4)
CHANNELS = {
    "RedExpression":   _ch("r"),
    "GreenExpression": _ch("g"),
    "BlueExpression":  _ch("b"),
    "AlphaExpression": _ch("a"),
}

# Output = Image1 = the effect's own input, so the output is always the same size as
# the input (Resolve crashed when a per-clip effect returned a different size).
NUMBERS = {
    1: "GRCtrl.Columns + 64*GRCtrl.Rows + 4096*(GRCtrl.Mode + 2*GRCtrl.Show + 8*GRCtrl.Guide)",
    2: "(GRCtrl.CELLC-1) + 1024*min(max(GRCtrl.RevealN,0),960)",
    3: "GRCtrl.GPX/GRCtrl.FW",
    4: "GRCtrl.MPX/GRCtrl.FW",
    5: "GRCtrl.RPX/GRCtrl.FW",
    6: "floor(GRCtrl.GapShade*100+0.5) + 101*floor(GRCtrl.GapOpacity*100+0.5) + 10201*(GRCtrl.GapFill + 2*GRCtrl.HiddenFill)",
    7: "GRCtrl.TK1",
    8: "GRCtrl.FH/GRCtrl.FW",
}
POINTS = {
    1: "Point(GRCtrl.KU, GRCtrl.KV)",
    2: "Point(GRCtrl.OU, GRCtrl.OV)",
    3: "Point(GRCtrl.TK2, GRCtrl.TK3)",
    4: "Point(GRCtrl.TK4, GRCtrl.TK5)",
}
NUMBER_LIMIT = 1000000       # Resolve clamps NumberIn to this (checked by the validator)

# --------------------------------------------------------------------------
# .setting writer
# --------------------------------------------------------------------------
def q(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def user_control(cid, kind, name, default, ex, tip):
    L = []
    if kind == "ticks":
        L += [f'LINKS_Name = {q(name)}', 'LINKID_DataType = "Number"', 'INPID_InputControl = "LabelControl"',
              'INP_External = false', 'INP_Passive = true', 'LBLC_DropDownButton = true',
              f'LBLC_NumInputs = {NTICK}', 'LBLC_NestLevel = 1', 'INP_Default = 1']
    elif kind == "check":
        L += [f'LINKS_Name = {q(name)}', 'LINKID_DataType = "Number"', 'INPID_InputControl = "CheckboxControl"',
              'INP_Integer = true', f'INP_Default = {default}', 'ICD_Width = 0.333',
              'INP_MinScale = 0', 'INP_MaxScale = 1', 'INP_MinAllowed = 0', 'INP_MaxAllowed = 1']
    elif kind == "label":
        L += [f'LINKS_Name = {q(name)}', 'LINKID_DataType = "Number"', 'INPID_InputControl = "LabelControl"',
              'INP_External = false', 'INP_Passive = true']
    elif kind == "combo":
        for opt in ex["combo"]:
            L.append(f'{{ CCS_AddString = {q(opt)}, }}')
        L += [f'LINKS_Name = {q(name)}', 'LINKID_DataType = "Number"', 'INPID_InputControl = "ComboControl"',
              'INP_Integer = true', 'CC_LabelPosition = "Horizontal"', f'INP_Default = {default}',
              'INP_MinScale = 0', f'INP_MaxScale = {len(ex["combo"])-1}',
              'INP_MinAllowed = 0', f'INP_MaxAllowed = {len(ex["combo"])-1}']
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
    return f"\t\t\t\t\t\t{cid} = {{ " + ", ".join(L) + " },"


def hidden_control(cid):
    return (f'\t\t\t\t\t\t{cid} = {{ LINKS_Name = "{cid}", LINKID_DataType = "Number", '
            f'INPID_InputControl = "SliderControl", IC_Visible = false, INP_Passive = true, '
            f'ICS_ControlPage = "Controls" }},')


def build_setting(name, defaults, help_text):
    """defaults: overrides {control_id: value} for this preset."""
    vals = {cid: d for cid, k, _, d, _, _ in VISIBLE if k not in ("label", "ticks")}
    vals.update({k: v for k, v in defaults.items() if k in vals})

    T = "\t"
    out = []
    out.append("{")
    out.append(f"{T}Tools = ordered() {{")
    out.append(f"{T*2}{name} = MacroOperator {{")
    out.append(f"{T*3}CtrlWZoom = false,")
    out.append(f"{T*3}NameSet = true,")
    out.append(f"{T*3}CustomData = {{ HelpPage = {q(help_text)}, }},")
    out.append(f"{T*3}Inputs = ordered() {{")
    out.append(f'{T*4}MainInput1 = InstanceInput {{ SourceOp = "GRCtrl", Source = "Input", }},')
    n = 1
    for cid, kind, cname, d, ex, tip in VISIBLE:
        if kind in ("label", "ticks"):
            line = f'{T*4}Input{n} = InstanceInput {{ SourceOp = "GRCtrl", Source = "{cid}"'
        else:
            line = f'{T*4}Input{n} = InstanceInput {{ SourceOp = "GRCtrl", Source = "{cid}", Name = {q(cname)}, Default = {vals[cid]}'

        out.append(line + ", },")
        n += 1
    out.append(f"{T*3}}},")
    out.append(f"{T*3}Outputs = {{")
    out.append(f'{T*4}MainOutput1 = InstanceOutput {{ SourceOp = "GRCore", Source = "Output", }},')
    out.append(f"{T*3}}},")
    out.append(f"{T*3}ViewInfo = GroupInfo {{ Pos = {{ 0, 0 }}, }},")
    out.append(f"{T*3}Tools = ordered() {{")

    # ---- Ctrl ----
    out.append(f"{T*4}GRCtrl = BrightnessContrast {{")
    out.append(f"{T*5}CtrlWZoom = false,")
    out.append(f"{T*5}NameSet = true,")
    out.append(f"{T*5}Inputs = {{")
    for cid, kind, _, d, _, _ in VISIBLE:
        if kind not in ("label", "ticks"):
            out.append(f"{T*6}{cid} = Input {{ Value = {vals[cid]}, }},")
    for hid, expr in HIDDEN:
        out.append(f"{T*6}{hid} = Input {{ Value = 0, Expression = {q(expr)}, }},")
    out.append(f"{T*5}}},")
    out.append(f"{T*5}ViewInfo = OperatorInfo {{ Pos = {{ -220, 0 }}, }},")
    out.append(f"{T*5}UserControls = ordered() {{")
    for c in VISIBLE:
        out.append(user_control(*c))
    for hid, _ in HIDDEN:
        out.append(hidden_control(hid))
    out.append(f"{T*5}}},")
    out.append(f"{T*4}}},")

    # ---- Resize (clean downscale to displayed size) ----
    out.append(f"{T*4}GRResize = BetterResize {{")
    out.append(f"{T*5}CtrlWZoom = false,")
    out.append(f"{T*5}NameSet = true,")
    out.append(f"{T*5}Inputs = {{")
    out.append(f'{T*6}Width = Input {{ Value = 1080, Expression = "max(floor(min(GRCtrl.DW, 8192)+0.5), 1)", }},')
    out.append(f'{T*6}Height = Input {{ Value = 1920, Expression = "max(floor(min(GRCtrl.DH, 8192)+0.5), 1)", }},')
    out.append(f"{T*6}KeepAspect = Input {{ Value = 0, }},")
    out.append(f'{T*6}Input = Input {{ SourceOp = "GRCtrl", Source = "Output", }},')
    out.append(f"{T*5}}},")
    out.append(f"{T*5}ViewInfo = OperatorInfo {{ Pos = {{ -110, 0 }}, }},")
    out.append(f"{T*4}}},")

    # ---- CustomTool core ----
    out.append(f"{T*4}GRCore = Custom {{")
    out.append(f"{T*5}CtrlWZoom = false,")
    out.append(f"{T*5}NameSet = true,")
    out.append(f"{T*5}Inputs = {{")
    for i, e in NUMBERS.items():
        out.append(f"{T*6}NumberIn{i} = Input {{ Value = 0, Expression = {q(e)}, }},")
    for i, e in POINTS.items():
        out.append(f"{T*6}PointIn{i} = Input {{ Value = {{ 0.5, 0.5 }}, Expression = {q(e)}, }},")
    for i, e in SETUP.items():
        out.append(f"{T*6}Setup{i} = Input {{ Value = {q(e)}, }},")
    for i, e in INTER.items():
        out.append(f"{T*6}Intermediate{i} = Input {{ Value = {q(e)}, }},")
    for k, e in CHANNELS.items():
        out.append(f"{T*6}{k} = Input {{ Value = {q(e)}, }},")
    out.append(f'{T*6}Image1 = Input {{ SourceOp = "GRCtrl", Source = "Output", }},')
    out.append(f'{T*6}Image2 = Input {{ SourceOp = "GRResize", Source = "Output", }},')
    out.append(f"{T*5}}},")
    out.append(f"{T*5}ViewInfo = OperatorInfo {{ Pos = {{ 0, 0 }}, }},")
    out.append(f"{T*4}}},")

    out.append(f"{T*3}}},")
    out.append(f"{T*2}}},")
    out.append(f"{T}}},")
    out.append(f'{T}ActiveTool = "{name}"')
    out.append("}")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# presets = one-click effects (each also gets a thumbnail from render_docs.py)
# --------------------------------------------------------------------------
HELP = ("Grid - the video stays in place, divided into Columns x Rows cells. Show all cells, one cell, "
        "picked cells (tick boxes) or cells 1..N (keyframe N to reveal box by box). Hidden cells and gaps "
        "are transparent, so the track below shows through. Single Cell mode fits the whole video into one cell.")

PICK_CORNERS = {f"T{k}": 0 for k in (2, 4, 6, 8)}   # 3x3 checkerboard: corners + centre

PRESETS = {
    "Grid":                    {},
    "Grid_One_Cell":           {"Show": 1, "Cell": 5, "Guide": 0},
    "Grid_Picked_Checker":     dict(PICK_CORNERS, Show=2),
    "Grid_Reveal_Box_By_Box":  {"Show": 3, "RevealN": 5},
    "Grid_Tiles_Gaps":         {"Show": 0, "TileGap": 12, "Margin": 12, "Radius": 10},
    "Grid_Single_Cell_Fit":    {"Mode": 1, "Cell": 1, "TileGap": 12, "Margin": 12},
    "Grid_Tiles_White_Gaps":   {"Show": 0, "Columns": 4, "Rows": 6, "TileGap": 10, "Margin": 20, "Radius": 18,
                                "GapFill": 1, "GapShade": 1},
    "Grid_Hidden_Black":       dict(PICK_CORNERS, Show=2, TileGap=6, GapFill=1, HiddenFill=1),
}


def main():
    import shutil
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, d in PRESETS.items():
        with open(os.path.join(OUT_DIR, name + ".setting"), "w", encoding="utf-8", newline="\n") as f:
            f.write(build_setting(name, d, HELP))
    print("wrote", len(PRESETS), "settings to", OUT_DIR)


if __name__ == "__main__":
    main()
