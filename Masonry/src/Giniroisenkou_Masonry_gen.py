"""Giniroisenkou_Masonry_gen.py - writes the Masonry Fusion macros for DaVinci Resolve.

Masonry is a per-clip Edit-page Effect for Pinterest / Instagram style masonry
grids: one clip per cell, each clip on its own track, all with the same Layout
and a different Cell number.

Run:  python src/Giniroisenkou_Masonry_gen.py
Out:  build/Edit/Effects/Masonry/Masonry.setting            (all layouts, dropdown)
      build/Edit/Effects/Masonry/Masonry_<Layout>.setting   (one-click, layout preset)

Why the macro builds its own canvas: a clip-level Fusion comp runs at the
SOURCE clip's resolution (e.g. 3840x2160), not the timeline's. So the clip is
resized straight to the size it is shown at in its cell (one clean downscale),
then cropped/padded onto a canvas of the chosen frame size, masked with a
rounded rectangle and merged over a transparent background of that size.

Layouts are tables of (x, y, w, h) rectangles on a DW x DH design grid with the
cells touching; gaps and corners are applied at render time, so a new layout is
one entry in LAYOUTS.
"""
import os

DW, DH = 1080, 1920          # design grid the layout tables are written in
C = "MMCtrl"                 # the pass-through node that holds every control

# key -> (label in the Layout dropdown, preset effect name, cells)
LAYOUTS = [
    ("Banner 6  (banner + 3 | 2)", "Masonry_Banner6", [
        (0, 0, 1080, 330),
        (0, 330, 540, 320), (0, 650, 540, 690), (0, 1340, 540, 580),
        (540, 330, 540, 660), (540, 990, 540, 930),
    ]),
    ("Columns 5  (3 | 2)", "Masonry_Columns5", [
        (0, 0, 540, 560), (0, 560, 540, 700), (0, 1260, 540, 660),
        (540, 0, 540, 900), (540, 900, 540, 1020),
    ]),
    ("Staggered 6  (3 | 3)", "Masonry_Staggered6", [
        (0, 0, 540, 500), (0, 500, 540, 650), (0, 1150, 540, 770),
        (540, 0, 540, 760), (540, 760, 540, 520), (540, 1280, 540, 640),
    ]),
    ("Scroll 12  (two screens tall)", "Masonry_Scroll12", [
        (0, 0, 1080, 330),
        (0, 330, 540, 320), (0, 650, 540, 690), (0, 1340, 540, 580),
        (0, 1920, 540, 640), (0, 2560, 540, 540), (0, 3100, 540, 740),
        (540, 330, 540, 660), (540, 990, 540, 930), (540, 1920, 540, 430),
        (540, 2350, 540, 650), (540, 3000, 540, 840),
    ]),
    ("Offset 4  (2 | 2)", "Masonry_Offset4", [
        (0, 0, 540, 1100), (0, 1100, 540, 820),
        (540, 0, 540, 760), (540, 760, 540, 1160),
    ]),
]

# label -> content aspect of the clip; None = same shape as the output frame
ASPECTS = [("16:9  camera / 4K / HD", 16 / 9), ("9:16  phone vertical", 9 / 16),
           ("Same as output frame", None), ("4:3", 4 / 3), ("1:1  square", 1.0),
           ("4:5", 0.8), ("3:4", 0.75)]

# Output frame presets. Index 0 = Custom -> uses Frame Width/Height controls.
FRAME_PRESETS = [
    ("Custom (Frame Width/Height below)", None),
    ("9:16  Reels / TikTok / Shorts  1080x1920", (1080, 1920)),
    ("4:5  Instagram portrait post  1080x1350", (1080, 1350)),
    ("1:1  Instagram square post  1080x1080", (1080, 1080)),
    ("9:16  UHD 4K vertical  2160x3840", (2160, 3840)),
    ("16:9  YouTube HD  1920x1080", (1920, 1080)),
    ("16:9  UHD 4K  3840x2160", (3840, 2160)),
]

MAXCELL = max(len(l[2]) for l in LAYOUTS)


def pick(combo, values):
    expr = str(values[-1])
    for i, v in reversed(list(enumerate(values[:-1]))):
        expr = f"iif({C}.{combo}=={i}, {v}, {expr})"
    return expr


def mn(a, b):
    return f"iif({a}<{b}, {a}, {b})"


def mx(a, b):
    return f"iif({a}>{b}, {a}, {b})"


def lookup(idx):
    """Nested iif over (Layout, Cell) -> component idx of the design rect."""
    expr = "0"
    for li, (_, _, cells) in reversed(list(enumerate(LAYOUTS))):
        inner = "0"
        for ci, r in reversed(list(enumerate(cells))):
            inner = f"iif({C}.Cell=={ci + 1}, {r[idx]}, {inner})"
        expr = f"iif({C}.Layout=={li}, {inner}, {expr})"
    return expr


SX = f"({C}.Spacing/{DW})"         # gap, fraction of frame width
SY = f"({C}.Spacing/{DW}*{C}.Ac)"  # same gap in px, as a fraction of frame height

# Hidden maths (all normalised to the output frame, y measured downwards)
HIDDEN = {
    "OutW": pick("FramePreset", [f"{C}.FrameW"] + [p[1][0] for p in FRAME_PRESETS[1:]]),
    "OutH": pick("FramePreset", [f"{C}.FrameH"] + [p[1][1] for p in FRAME_PRESETS[1:]]),
    "Ac": f"{C}.OutW/{C}.OutH",
    "As": pick("SrcAspect", [f"{C}.Ac" if a is None else round(a, 6) for _, a in ASPECTS]),
    "RX": lookup(0), "RY": lookup(1), "RW": lookup(2), "RH": lookup(3),
    "CX": f"{SX} + ({C}.RX/{DW})*(1-{SX})",
    "CY": f"{SY} + ({C}.RY/{DH})*(1-{SY})",
    "CW": f"iif({C}.RW>0, ({C}.RW/{DW})*(1-{SX}) - {SX}, 0)",
    "CH": f"iif({C}.RH>0, ({C}.RH/{DH})*(1-{SY}) - {SY}, 0)",
    # clip width-fitted to the frame spans the full width and Ac/As of the height
    "FH": f"{C}.Ac/{C}.As",
    # cover-fit scale (clip fills the cell, overflow cropped) times Zoom
    "Sc": mx(f"{C}.CW", f"{C}.CH/{C}.FH") + f" * {C}.Zoom",
    "Scroll": f"({C}.ScrollY + time*{C}.ScrollSpeed)/{DH}",
    "NX": f"{C}.CX + {C}.CW/2",
    "NY": f"1 - ({C}.CY + {C}.CH/2 - {C}.Scroll)",
    "OX": f"{C}.PanX*({C}.Sc - {C}.CW)/2",
    "OY": f"{C}.PanY*({C}.Sc*{C}.FH - {C}.CH)/2",
    # displayed size of the whole clip in px, and where its centre lands
    # +4 px bleed so whole-pixel rounding in Crop never leaves a hairline
    "PW": f"{mx(f'{C}.OutW*{C}.Sc + 4', '2')}",
    "PH": f"{mx(f'{C}.PW/{C}.As', '2')}",
    "XOff": f"{C}.PW/2 - ({C}.NX + {C}.OX)*{C}.OutW",
    "YOff": f"{C}.PH/2 - ({C}.NY + {C}.OY)*{C}.OutH",
    "Rad": mn(f"2*({C}.Radius*{C}.OutW/{DW})/" +
              mx(mn(f"{C}.CW*{C}.OutW", f"{C}.CH*{C}.OutH"), "1"), "1"),
}

# key, label, kind, default, min, max, extra
VISIBLE = [
    ("FramePreset", "Frame Preset", "combo", 1, None, None, [p[0] for p in FRAME_PRESETS]),
    ("FrameW", "Frame Width", "int", DW, 128, 8192, None),
    ("FrameH", "Frame Height", "int", DH, 128, 8192, None),
    ("Layout", "Layout", "combo", 0, None, None, [l[0] for l in LAYOUTS]),
    ("Cell", "Cell", "int", 1, 1, MAXCELL, None),
    ("Spacing", "Gap (px)", "slider", 30, 0, 120, None),
    ("Radius", "Corner Radius (px)", "slider", 28, 0, 150, None),
    ("SrcAspect", "Source Aspect", "combo", 0, None, None, [a[0] for a in ASPECTS]),
    ("Zoom", "Zoom", "slider", 1, 1, 3, None),
    ("PanX", "Reframe X", "slider", 0, -1, 1, None),
    ("PanY", "Reframe Y", "slider", 0, -1, 1, None),
    ("ScrollY", "Scroll Offset (px)", "slider", 0, -1920, 1920, None),
    ("ScrollSpeed", "Scroll Speed (px/frame)", "slider", 0, -20, 20, None),
]

HELP = {
    "FramePreset": "Pick the format of your TIMELINE (Reels 9:16, Instagram 4:5 / 1:1, 4K...). The effect outputs exactly this size. Choose Custom to type your own. SAME on every clip.",
    "FrameW": "Only used when Frame Preset = Custom: your timeline width in px.",
    "FrameH": "Only used when Frame Preset = Custom: your timeline height in px.",
    "Layout": "The grid. SAME on every clip. The layouts are drawn for 9:16 and stretch to other frame shapes.",
    "Cell": "Which box THIS clip fills. Numbers go down the left column first, then the right column (Banner = cell 1).",
    "Spacing": "Gap between boxes and around the edge, in px at 1080 wide (scales with the frame). SAME on every clip.",
    "Radius": "Rounded corners, in px at 1080 wide. 0 = square. SAME on every clip.",
    "SrcAspect": "Shape of THIS clip. MUST match it or the picture is stretched: 4K / HD camera = 16:9, phone vertical = 9:16.",
    "Zoom": "Zoom into the clip inside its box. 1 = just fills the box.",
    "PanX": "Slide the picture left / right inside its box. -1 and +1 = the clip's edges.",
    "PanY": "Slide the picture up / down inside its box. -1 and +1 = the clip's edges.",
    "ScrollY": "Moves the whole grid up (+) or down (-), in px of the 1080x1920 design. Scroll 12 is two screens tall: 1920 shows the lower half. SAME on every clip.",
    "ScrollSpeed": "Keeps the grid moving: px per frame, + = content moves up like scrolling a feed. SAME on every clip.",
}

SECTIONS = [
    ("SecStart", "1  Start here",
     ["One Masonry on EVERY clip, each clip on its own track.",
      "Same Layout on all of them, a different Cell on each.",
      "Hover any control for help."],
     ["FramePreset", "FrameW", "FrameH", "Layout", "Cell"]),
    ("SecLook", "2  Look - SAME on every clip",
     ["Copy one clip > Paste Attributes onto the others."],
     ["Spacing", "Radius"]),
    ("SecPic", "3  Picture inside the box",
     ["Source Aspect MUST match the clip (4K / HD camera = 16:9)."],
     ["SrcAspect", "Zoom", "PanX", "PanY"]),
    ("SecScroll", "4  Scroll - SAME on every clip",
     ["Moves the whole grid like a feed."],
     ["ScrollY", "ScrollSpeed"]),
]
assert sorted(k for s in SECTIONS for k in s[3]) == sorted(v[0] for v in VISIBLE)
VIS = {v[0]: v for v in VISIBLE}


def label_uc(key, text, dropdown=False, n=0):
    lines = [f'LINKS_Name = "{text}"', 'ICS_ControlPage = "Controls"', 'LINKID_DataType = "Number"',
             'INPID_InputControl = "LabelControl"', "INP_External = false", "INP_Passive = true"]
    if dropdown:
        lines += ["LBLC_DropDownButton = true", f"LBLC_NumInputs = {n}", "LBLC_NestLevel = 1"]
    return f"\t\t\t\t\t\t{key} = {{\n" + "".join(f"\t\t\t\t\t\t\t{l},\n" for l in lines) + "\t\t\t\t\t\t},\n"


def ordered_items():
    items = []
    for sid, title, desc, keys in SECTIONS:
        items.append(("hdr", sid, title, len(desc) + len(keys)))
        for i, line in enumerate(desc):
            items.append(("lbl", f"{sid}Txt{i + 1}", line, 0))
        for k in keys:
            items.append(("ctl", k, None, 0))
    return items


def uc_block(defaults):
    out = []
    for typ, key, text, n in ordered_items():
        if typ != "ctl":
            out.append(label_uc(key, text, typ == "hdr", n))
            continue
        _, label, kind, d, lo, hi, extra = VIS[key]
        d = defaults.get(key, d)
        lines = [f'LINKS_Name = "{label}"', 'ICS_ControlPage = "Controls"',
                 'LINKID_DataType = "Number"', f"INP_Default = {d}",
                 'INPS_StatusText = "' + HELP[key].replace('"', "'") + '"']
        if kind == "combo":
            lines += ['INPID_InputControl = "ComboControl"', "INP_Integer = true",
                      'CC_LabelPosition = "Horizontal"']
            lines += [f'{{ CCS_AddString = "{s}", }}' for s in extra]
        else:
            lines += ['INPID_InputControl = "SliderControl"',
                      f"INP_MinScale = {lo}", f"INP_MaxScale = {hi}"]
            if kind == "int":
                lines += ["INP_Integer = true", f"INP_MinAllowed = {lo}", f"INP_MaxAllowed = {hi}"]
        out.append(f"\t\t\t\t\t\t{key} = {{\n" + "".join(f"\t\t\t\t\t\t\t{l},\n" for l in lines) + "\t\t\t\t\t\t},\n")
    for key in HIDDEN:
        out.append(f"\t\t\t\t\t\t{key} = {{\n\t\t\t\t\t\t\tLINKS_Name = \"{key}\",\n"
                   "\t\t\t\t\t\t\tICS_ControlPage = \"Controls\",\n\t\t\t\t\t\t\tLINKID_DataType = \"Number\",\n"
                   "\t\t\t\t\t\t\tINPID_InputControl = \"SliderControl\",\n\t\t\t\t\t\t\tIC_Visible = false,\n"
                   "\t\t\t\t\t\t\tINP_Passive = true,\n\t\t\t\t\t\t},\n")
    return "".join(out)


def inputs_block(defaults):
    out = []
    for key, _, _, d, *_ in VISIBLE:
        out.append(f"\t\t\t\t\t\t{key} = Input {{ Value = {defaults.get(key, d)}, }},\n")
    for key, e in HIDDEN.items():
        out.append(f'\t\t\t\t\t\t{key} = Input {{ Value = 0, Expression = "{e}", }},\n')
    return "".join(out)


def instance_inputs(defaults):
    out = [f'\t\t\t\tMainInput1 = InstanceInput {{ SourceOp = "{C}", Source = "Input", }},\n']
    for typ, key, _, _ in ordered_items():
        if typ != "ctl":
            out.append(f'\t\t\t\t{key} = InstanceInput {{ SourceOp = "{C}", Source = "{key}", }},\n')
            continue
        _, label, _, d, *_ = VIS[key]
        out.append(f'\t\t\t\t{key} = InstanceInput {{ SourceOp = "{C}", Source = "{key}", '
                   f'Name = "{label}", Default = {defaults.get(key, d)}, }},\n')
    return "".join(out)


def tool(name, reg, inputs, pos):
    body = "".join(f"\t\t\t\t\t\t{l},\n" for l in inputs)
    return (f"\t\t\t\t{name} = {reg} {{\n\t\t\t\t\tCtrlWZoom = false,\n\t\t\t\t\tNameSet = true,\n"
            f"\t\t\t\t\tInputs = {{\n{body}\t\t\t\t\t}},\n"
            f"\t\t\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {pos[0]}, {pos[1]} }} }},\n\t\t\t\t}},\n")


def build(name="Masonry", defaults=None):
    defaults = defaults or {}
    tools = [
        # one clean resize of the whole clip to the size it is shown at
        tool("MMResize", "BetterResize", [
            f'Input = Input {{ SourceOp = "{C}", Source = "Output", }}',
            f'Width = Input {{ Value = {DW}, Expression = "{C}.PW", }}',
            f'Height = Input {{ Value = {DH}, Expression = "{C}.PH", }}',
            'PixelAspect = Input { Value = { 1, 1 }, }'], (110, 0)),
        # crop / pad onto the output frame so the clip's centre sits on the cell
        tool("MMPlace", "Crop", [
            'Input = Input { SourceOp = "MMResize", Source = "Output", }',
            f'XOffset = Input {{ Value = 0, Expression = "{C}.XOff", }}',
            f'YOffset = Input {{ Value = 0, Expression = "{C}.YOff", }}',
            f'XSize = Input {{ Value = {DW}, Expression = "{C}.OutW", }}',
            f'YSize = Input {{ Value = {DH}, Expression = "{C}.OutH", }}'], (220, 0)),
        tool("MMBG", "Background", [
            'UseFrameFormatSettings = Input { Value = 0, }',
            f'Width = Input {{ Value = {DW}, Expression = "{C}.OutW", }}',
            f'Height = Input {{ Value = {DH}, Expression = "{C}.OutH", }}',
            'PixelAspect = Input { Value = { 1, 1 }, }',
            'TopLeftRed = Input { Value = 0, }', 'TopLeftGreen = Input { Value = 0, }',
            'TopLeftBlue = Input { Value = 0, }', 'TopLeftAlpha = Input { Value = 0, }'], (220, -60)),
        tool("MMMask", "RectangleMask", [
            'SoftEdge = Input { Value = 0.0006, }',
            f'MaskWidth = Input {{ Value = {DW}, Expression = "{C}.OutW", }}',
            f'MaskHeight = Input {{ Value = {DH}, Expression = "{C}.OutH", }}',
            'PixelAspect = Input { Value = { 1, 1 }, }',
            'ClippingMode = Input { Value = FuID { "None" }, }',
            f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point({C}.NX, {C}.NY)", }}',
            f'Width = Input {{ Value = 0.5, Expression = "{C}.CW", }}',
            f'Height = Input {{ Value = 0.5, Expression = "{C}.CH", }}',
            f'CornerRadius = Input {{ Value = 0, Expression = "{C}.Rad", }}'], (330, 60)),
        tool("MMMerge", "Merge", [
            'Background = Input { SourceOp = "MMBG", Source = "Output", }',
            'Foreground = Input { SourceOp = "MMPlace", Source = "Output", }',
            'EffectMask = Input { SourceOp = "MMMask", Source = "Mask", }',
            'PerformDepthMerge = Input { Value = 0, }'], (330, 0)),
    ]
    return f"""{{
\tTools = ordered() {{
\t\t{name} = MacroOperator {{
\t\t\tCtrlWZoom = false,
\t\t\tNameSet = true,
\t\t\tInputs = ordered() {{
{instance_inputs(defaults)}\t\t\t}},
\t\t\tOutputs = {{
\t\t\t\tMainOutput1 = InstanceOutput {{ SourceOp = "MMMerge", Source = "Output", }},
\t\t\t}},
\t\t\tViewInfo = GroupInfo {{ Pos = {{ 0, 0 }} }},
\t\t\tTools = ordered() {{
\t\t\t\t{C} = BrightnessContrast {{
\t\t\t\t\tCtrlWZoom = false,
\t\t\t\t\tNameSet = true,
\t\t\t\t\tInputs = {{
{inputs_block(defaults)}\t\t\t\t\t}},
\t\t\t\t\tViewInfo = OperatorInfo {{ Pos = {{ 0, 0 }} }},
\t\t\t\t\tUserControls = ordered() {{
{uc_block(defaults)}\t\t\t\t\t}},
\t\t\t\t}},
{"".join(tools)}\t\t\t}},
\t\t}},
\t}},
\tActiveTool = "{name}"
}}
"""


def effects():
    """(effect name, defaults) for the master and every one-click layout preset."""
    out = [("Masonry", {})]
    for i, (_, preset, _) in enumerate(LAYOUTS):
        out.append((preset, {"Layout": i}))
    return out


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dst = os.path.join(root, "build", "Edit", "Effects", "Masonry")
    os.makedirs(dst, exist_ok=True)
    for name, d in effects():
        with open(os.path.join(dst, name + ".setting"), "w", encoding="utf-8", newline="\n") as f:
            f.write(build(name, d))
    print(f"wrote {len(effects())} effects to {dst}; {len(VISIBLE)} controls, {len(HIDDEN)} hidden")
