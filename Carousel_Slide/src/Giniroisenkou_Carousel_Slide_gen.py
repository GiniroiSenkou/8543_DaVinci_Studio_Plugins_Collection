"""Giniroisenkou_Carousel_Slide_gen.py - writes build/Edit/Effects/Carousel_Slide/Carousel_Slide.setting
(DaVinci Resolve Fusion Edit effect).

"Collage slideshow" / carousel strip, per clip (same philosophy as Masonry):
every video, photo or cut-out sticker is its own clip on its own track, all
starting on the same frame. Each gets Carousel_Slide with a position on a long
strip; the strip scrolls through a rounded WINDOW (panel) and everything that
leaves the window is clipped.

Modes
  Tile      - fills its box (cover), clipped to the box and to the window.
  Pop-out   - same box/fit as a Tile (use the same position as the clip it is
              copied from) but only clipped by the window grown by Overhang:
              feed it a cut-out (Magic Mask) and the person spills over the
              tile border and over the neighbours.
  Sticker   - whole image fitted inside its box (contain), for PNG cut-outs;
              rides the strip, can sit across a seam, can rotate, clipped by
              the window grown by Overhang.

Layout
  Slot      - equal tiles: X = (Slot-1)*(Tile W + Gap) + Strip X,
              Y centred in the window + Strip Y.
  Custom    - X = Strip X, Y = Strip Y (top-left of the box inside the strip,
              px). Mix wide tiles, stacked half tiles, stickers anywhere.

A clip-level Fusion comp runs at the SOURCE resolution and counts SOURCE
frames, so the macro builds its own Frame W x H canvas and rescales time by
Timeline FPS / Clip FPS so mixed-rate clips stay locked together.
All geometry is in px of the output frame (Frame Width x Height), carried normalized.
"""

DW, DH = 1080, 1920
C = "CJCtrl"

ASPECTS = [("Auto (from clip)", "auto"), ("16:9 landscape", 16 / 9), ("4:3", 4 / 3),
           ("3:2", 3 / 2), ("1:1 square", 1.0), ("4:5", 0.8), ("3:4", 0.75),
           ("9:16 vertical", 9 / 16)]
FPS = [23.976, 24, 25, 29.97, 30, 48, 50, 59.94, 60, 100, 119.88, 120]
FPSL = [str(f) for f in FPS]
# Output frame presets. Index 0 = Custom -> uses Frame Width/Height controls.
FRAME_PRESETS = [
    ("Custom (Frame Width/Height below)", None),
    ("9:16  Reels / TikTok / Shorts  1080x1920", (1080, 1920)),
    ("4:5  Instagram portrait post  1080x1350", (1080, 1350)),
    ("1:1  Instagram square post  1080x1080", (1080, 1080)),
    ("3:4  portrait  1080x1440", (1080, 1440)),
    ("4:3  landscape  1440x1080", (1440, 1080)),
    ("16:9  YouTube HD  1920x1080", (1920, 1080)),
    ("16:9  UHD 4K  3840x2160", (3840, 2160)),
    ("9:16  UHD 4K vertical  2160x3840", (2160, 3840)),
]
DIRECTIONS = ["Right to Left", "Left to Right", "Bottom to Top", "Top to Bottom"]
# per direction: (sign of travel along the axis, horizontal?)
DIRV = [(1, 1), (-1, 1), (1, 0), (-1, 0)]


def pick(combo, values):
    expr = str(values[-1])
    for i, v in reversed(list(enumerate(values[:-1]))):
        expr = f"iif({C}.{combo}=={i}, {v}, {expr})"
    return expr


def clamp01(e):
    return f"iif({e}<0, 0, iif({e}>1, 1, {e}))"


def mn(a, b):
    return f"iif({a}<{b}, {a}, {b})"


def mx(a, b):
    return f"iif({a}>{b}, {a}, {b})"


def rad(r_px, w_n, h_n):
    """Fusion CornerRadius (0..1 of the shorter side) from a design-px radius."""
    short = mn(f"{w_n}*{C}.OutW", f"{h_n}*{C}.OutH")
    v = f"2*{r_px}/iif({short}<1, 1, {short})"
    return mn(v, "1")


HIDDEN = {
    # ---- output frame: preset, or Frame Width/Height when preset = Custom ---
    "OutW": pick("FramePreset", [f"{C}.FrameW"] + [p[1][0] for p in FRAME_PRESETS[1:]]),
    "OutH": pick("FramePreset", [f"{C}.FrameH"] + [p[1][1] for p in FRAME_PRESETS[1:]]),
    # ---- panel centre = frame centre + offset --------------------------------
    "WinX": f"{C}.OutW/2 + {C}.WinOffX",
    "WinY": f"{C}.OutH/2 + {C}.WinOffY",
    # ---- time: timeline frames since the clip's first frame ----------------
    "TLfps": pick("TLFps", FPS),
    "CLfps": f"iif({C}.ClipFps==0, {C}.TLfps, " + pick("ClipFps", ["0"] + FPS) + ")",
    "T": f"(time - comp.RenderStart)*{C}.TLfps/{C}.CLfps - {C}.Delay",
    "Tp": f"iif({C}.T<0, 0, {C}.T)",
    # ---- direction ----------------------------------------------------------
    "DS": pick("Direction", [d[0] for d in DIRV]),
    "Hz": pick("Direction", [d[1] for d in DIRV]),
    # ---- box on the strip (design px, top-left, window-relative) ------------
    "BX": f"iif({C}.Layout==0, ({C}.Slot-1)*({C}.TileW+{C}.Gap)*{C}.Hz + iif({C}.Hz==1, 0, ({C}.WinW-{C}.TileW)/2) + {C}.StripX, {C}.StripX)",
    "BY": f"iif({C}.Layout==0, ({C}.Slot-1)*({C}.TileH+{C}.Gap)*(1-{C}.Hz) + iif({C}.Hz==1, ({C}.WinH-{C}.TileH)/2, 0) + {C}.StripY, {C}.StripY)",
    "Along": f"iif({C}.Hz==1, {C}.BX, {C}.BY)",
    "Size": f"iif({C}.Hz==1, {C}.TileW, {C}.TileH)",
    # step distance: Step (px) if set, otherwise one box (+ gap)
    "Pitch": f"iif({C}.StepPx>0, {C}.StepPx, {C}.Size + {C}.Gap)",
    # ---- travel -------------------------------------------------------------
    "Pc": f"{C}.Tp*{C}.Speed",
    "Cyc": f"iif({C}.Hold+{C}.Slide<1, 1, {C}.Hold+{C}.Slide)",
    "K": f"floor({C}.Tp/{C}.Cyc)",
    "U": clamp01(f"(({C}.Tp - {C}.K*{C}.Cyc) - {C}.Hold)/iif({C}.Slide<1, 1, {C}.Slide)"),
    "E": f"{C}.U*{C}.U*(3-2*{C}.U)",
    "Ps": f"{C}.Pitch*({C}.K + {C}.E)",
    "P": f"{C}.StartOffset + iif({C}.Motion==0, {C}.Pc, {C}.Ps)",
    "S0": f"{C}.Along - {C}.DS*{C}.P",
    # loop: wrap once the box has fully left the window on the exit side
    "L": f"iif({C}.Layout==0, iif({C}.Count<1, 1, {C}.Count)*({C}.Size+{C}.Gap), iif({C}.LoopLen<1, 1, {C}.LoopLen))",
    "Wrap": f"{C}.Size + {C}.Overhang*iif({C}.Mode==0, 0, 1)",
    # moving back (R->L, B->T): wrap window [-Wrap, L-Wrap)
    # moving forward:            wrap window [Win+Ovh-L, Win+Ovh)
    "Exit": f"iif({C}.DS>0, {C}.Wrap, {C}.L - iif({C}.Hz==1, {C}.WinW, {C}.WinH) - ({C}.Wrap - {C}.Size))",
    "S": f"iif({C}.Loop==1, {C}.S0 - {C}.L*floor(({C}.S0 + {C}.Exit)/{C}.L), {C}.S0)",
    # ---- screen placement (design px) --------------------------------------
    "WinL": f"{C}.WinX - {C}.WinW/2",
    "WinT": f"{C}.WinY - {C}.WinH/2",
    "TX": f"{C}.WinL + iif({C}.Hz==1, {C}.S, {C}.BX)",
    "TY": f"{C}.WinT + iif({C}.Hz==1, {C}.BY, {C}.S)",
    "NX": f"({C}.TX + {C}.TileW/2)/{C}.OutW",
    "NY": f"1 - ({C}.TY + {C}.TileH/2)/{C}.OutH",
    "CW": f"{C}.TileW/{C}.OutW",
    "CH": f"{C}.TileH/{C}.OutH",
    # tile mask only in Tile mode; otherwise a huge (no-op) rectangle
    "MW": f"iif({C}.Mode==0, {C}.CW, 4)",
    "MH": f"iif({C}.Mode==0, {C}.CH, 4)",
    "MR": f"iif({C}.Mode==0, " + rad(f"{C}.TileRadius", f"{C}.CW", f"{C}.CH") + ", 0)",
    # window mask, grown by Overhang for Pop-out / Sticker
    "Grow": f"{C}.Overhang*iif({C}.Mode==0, 0, 1)",
    "WNX": f"{C}.WinX/{C}.OutW",
    "WNY": f"1 - {C}.WinY/{C}.OutH",
    "WW": f"({C}.WinW + 2*{C}.Grow)/{C}.OutW",
    "WH": f"({C}.WinH + 2*{C}.Grow)/{C}.OutH",
    "WR": rad(f"({C}.WinRadius + {C}.Grow)", f"{C}.WW", f"{C}.WH"),
    # ---- source fit ---------------------------------------------------------
    "Ac": f"{C}.OutW/{C}.OutH",
    "As": pick("SrcAspect", [f"({C}.Input.Width/{C}.Input.Height)" if a == "auto" else round(a, 6)
                             for _, a in ASPECTS]),
    # source is contain-fitted into the OutW x OutH canvas (never cropped)
    "RW": f"iif({C}.As >= {C}.Ac, {C}.OutW, {C}.OutH*{C}.As)",
    "RH": f"iif({C}.As >= {C}.Ac, {C}.OutW/{C}.As, {C}.OutH)",
    "FW": f"{C}.RW/{C}.OutW",
    "FH": f"{C}.RH/{C}.OutH",
    "PadX": f"-({C}.OutW - {C}.RW)/2",
    "PadY": f"-({C}.OutH - {C}.RH)/2",
    # cover (Tile / Pop-out) or contain (Sticker), then user zoom
    "Sc": f"iif({C}.Mode==2, " + mn(f"{C}.CW/{C}.FW", f"{C}.CH/{C}.FH") + ", "
          + mx(f"{C}.CW/{C}.FW", f"{C}.CH/{C}.FH") + f") * {C}.Zoom",
    # reframe: within the overflow for Tile/Pop-out, half a box for Sticker
    "OX": f"{C}.PanX*iif({C}.Mode==2, {C}.CW/2, ({C}.Sc*{C}.FW - {C}.CW)/2)",
    "OY": f"{C}.PanY*iif({C}.Mode==2, {C}.CH/2, ({C}.Sc*{C}.FH - {C}.CH)/2)",
}

VISIBLE = [
    # key, label, kind, default, min, max, extra
    ("Mode", "Mode", "combo", 0, None, None,
     ["Tile", "Pop-out (cut-out over the edge)", "Sticker (cut-out, fit inside)"]),
    ("Layout", "Layout", "combo", 0, None, None, ["Slot (equal tiles)", "Custom position"]),
    ("Slot", "Slot", "int", 1, 1, 60, None),
    ("StripX", "Strip X (px)", "slider", 0, -2000, 8000, None),
    ("StripY", "Strip Y (px)", "slider", 0, -1000, 2000, None),
    ("TileW", "Box Width (px)", "slider", 500, 20, 2000, None),
    ("TileH", "Box Height (px)", "slider", 750, 20, 2000, None),
    ("Gap", "Gap (px)", "slider", 0, 0, 200, None),
    ("TileRadius", "Box Corner Radius (px)", "slider", 0, 0, 200, None),
    ("Angle", "Rotation (deg)", "slider", 0, -45, 45, None),
    ("Direction", "Direction", "combo", 0, None, None, DIRECTIONS),
    ("Motion", "Motion", "combo", 0, None, None, ["Continuous scroll", "Step (hold + slide)"]),
    ("Speed", "Speed (px/frame)", "slider", 4, 0, 60, None),
    ("Hold", "Hold (frames)", "int", 36, 0, 600, None),
    ("Slide", "Slide (frames)", "int", 14, 1, 240, None),
    ("StepPx", "Step Distance (px, 0 = one box)", "slider", 0, 0, 4000, None),
    ("StartOffset", "Start Offset (px)", "slider", 0, -4000, 8000, None),
    ("Delay", "Start Delay (frames)", "int", 0, 0, 600, None),
    ("Loop", "Loop (wrap around)", "check", 0, None, None, None),
    ("Count", "Slot Count (Slot loop)", "int", 6, 1, 60, None),
    ("LoopLen", "Loop Length (px, Custom loop)", "slider", 3000, 100, 20000, None),
    ("WinOffX", "Panel Offset X (px from centre)", "slider", 0, -2000, 2000, None),
    ("WinOffY", "Panel Offset Y (px from centre)", "slider", 0, -2000, 2000, None),
    ("WinW", "Window Width (px)", "slider", 1000, 50, 3840, None),
    ("WinH", "Window Height (px)", "slider", 750, 50, 3840, None),
    ("WinRadius", "Window Corner Radius (px)", "slider", 36, 0, 300, None),
    ("Overhang", "Overhang (px, Pop-out/Sticker)", "slider", 120, 0, 1000, None),
    ("SrcAspect", "Source Aspect", "combo", 0, None, None, [a[0] for a in ASPECTS]),
    ("Zoom", "Zoom", "slider", 1, 0.2, 3, None),
    ("PanX", "Reframe X", "slider", 0, -1, 1, None),
    ("PanY", "Reframe Y", "slider", 0, -1, 1, None),
    ("TLFps", "Timeline FPS", "combo", 1, None, None, FPSL),
    ("ClipFps", "Clip FPS", "combo", 0, None, None, ["Same as timeline (and photos)"] + FPSL),
    ("FramePreset", "Frame Preset", "combo", 1, None, None, [p[0] for p in FRAME_PRESETS]),
    ("FrameW", "Frame Width (Custom)", "int", DW, 128, 8192, None),
    ("FrameH", "Frame Height (Custom)", "int", DH, 128, 8192, None),
]


# Hover tooltip for every control (INPS_StatusText) - plain words, no jargon.
HELP = {
    "Mode": "Tile = a normal video/photo in the row. Pop-out = copy of a clip on the TOP track with the person cut out, so they step over the tile edge. Sticker = PNG / cut-out stuck on the row (like tape over a join).",
    "Layout": "Slot = equal tiles side by side, you only pick the Slot number. Custom = you type exactly where the box goes (Strip X/Y) and its size - for collages with mixed sizes and for stickers.",
    "Slot": "Order in the row: 1 = first, 2 = next to it... Only used when Layout = Slot. Every clip needs a different number.",
    "StripX": "Custom: left edge of the box on the strip, in px (0 = panel's left edge at the start). Slot: extra nudge sideways. Join between slide 1 and 2 = Box Width.",
    "StripY": "Custom: top edge of the box inside the panel, in px (0 = panel top). Slot: extra nudge up/down.",
    "TileW": "Width of this clip's box in px. For a 4:3 slide that fills the default panel use 1000.",
    "TileH": "Height of this clip's box in px. For a 4:3 slide that fills the default panel use 750.",
    "Gap": "Empty space between tiles (Slot layout). 0 = seamless collage like Crsel.",
    "TileRadius": "Rounded corners on each tile. 0 = sharp, tiles touch cleanly.",
    "Angle": "Tilt in degrees - mostly for stickers (-6 to -10 gives the 'taped on' look).",
    "Direction": "Which way the row travels. Must be the SAME on every clip.",
    "Motion": "Continuous = slow constant drift. Step = rests on a tile (Hold), then slides one tile over (Slide), like a slideshow. SAME on every clip.",
    "Speed": "Continuous scroll speed in px per frame. 3-6 = calm Crsel drift, 15+ = fast. SAME on every clip.",
    "Hold": "Step mode: frames it stays still on each tile (48 = 2 s at 24 fps).",
    "Slide": "Step mode: frames the move to the next tile takes (12 = half a second at 24 fps).",
    "StepPx": "Step mode: how far each step moves, in px. 0 = one box (+ Gap) of THIS clip - fine for equal slides. Stickers and Custom boxes MUST use the slide distance (e.g. 1000 for 1000 px slides) or they drift away from the slides.",
    "StartOffset": "Pushes the whole row along at the start, e.g. to begin with slide 2 in view. SAME on every clip unless fixing a clip that starts late.",
    "Delay": "Frames to stay still before the movement starts.",
    "Loop": "Endless carousel: tiles leaving one side come back on the other. SAME on every clip.",
    "Count": "Loop in Slot layout: how many slots there are in total (3 videos = 3).",
    "LoopLen": "Loop in Custom layout (and for stickers!): total length of the row in px. 3 slides of 1000 px = 3000. Must be at least panel width + widest box.",
    "WinOffX": "Move the panel left (-) / right (+) from the centre of the frame, in px. 0 = centred. SAME on every clip.",
    "WinOffY": "Move the panel up (-) / down (+) from the centre of the frame, in px. 0 = centred; +290 on 9:16 = lower half like Crsel. SAME on every clip.",
    "WinW": "Panel width in px. Anything outside the panel is cut off. Panel = Frame Width x Frame Height = full screen. SAME on every clip.",
    "WinH": "Panel height in px. 1000 x 750 = 4:3 panel. SAME on every clip.",
    "WinRadius": "Rounded corners of the panel.",
    "Overhang": "Pop-out / Sticker only: how far (px) they may stick out past the panel edge.",
    "SrcAspect": "Shape of the source picture. Leave on Auto - it reads it from the clip.",
    "Zoom": "Zoom the picture inside its box (1 = just fills it).",
    "PanX": "Slide the picture left/right inside its box to reframe (-1 .. 1).",
    "PanY": "Slide the picture up/down inside its box to reframe (-1 .. 1).",
    "TLFps": "Your timeline frame rate. SAME on every clip.",
    "ClipFps": "THIS clip's own frame rate. Photos and same-rate clips: 'Same as timeline'. A 30 fps clip on a 24 fps timeline MUST be set to 30, or it drifts out of sync.",
    "FramePreset": "Pick the format of your TIMELINE: Reels 9:16, Instagram 4:5 / 1:1, 4:3, YouTube 16:9, 4K... It overrides Frame Width/Height. Choose Custom to type your own size. SAME on every clip.",
    "FrameW": "Only used when Frame Preset = Custom: your timeline width in px.",
    "FrameH": "Only used when Frame Preset = Custom: your timeline height in px.",
}

# Collapsible Inspector sections: (id, title, description lines, control keys)
SECTIONS = [
    ("SecClip", "1  Start here - this clip",
     ["One Carousel_Slide on EVERY clip, each on its own track,",
      "all starting on the same frame. Hover any control for help.",
      "Frame Preset = your timeline format (Reels, 4:5, 1:1, 16:9...)."],
     ["FramePreset", "FrameW", "FrameH", "Mode", "Layout", "Slot"]),
    ("SecBox", "2  Box - where it sits and how big",
     ["Position/size of THIS clip in the row, in px of your frame.",
      "Sticker over the join of slide 1|2: Strip X = Box Width - sticker W/2."],
     ["StripX", "StripY", "TileW", "TileH", "Gap", "TileRadius", "Angle"]),
    ("SecMove", "3  Movement - SAME on every clip",
     ["Copy one clip > Paste Attributes onto the others.",
      "Loop: Slot layout uses Slot Count, Custom/Sticker uses Loop Length.",
      "Stickers: type Step Distance = slide width, Loop Length = total row."],
     ["Direction", "Motion", "Speed", "Hold", "Slide", "StepPx", "StartOffset", "Delay",
      "Loop", "Count", "LoopLen"]),
    ("SecWin", "4  Panel - SAME on every clip",
     ["The rounded window the row scrolls through.",
      "Default 1000 x 750 = 4:3. Everything outside is cut off."],
     ["WinOffX", "WinOffY", "WinW", "WinH", "WinRadius", "Overhang"]),
    ("SecPic", "5  Picture inside the box",
     ["Zoom / reframe the footage inside its own box."],
     ["SrcAspect", "Zoom", "PanX", "PanY"]),
    ("SecSync", "6  Frame rate",
     ["Set Clip FPS on clips whose rate differs from the timeline."],
     ["TLFps", "ClipFps"]),
]
assert sorted(k for sec in SECTIONS for k in sec[3]) == sorted(v[0] for v in VISIBLE), "section keys mismatch"
VIS = {v[0]: v for v in VISIBLE}


def label_uc(key, text, dropdown=False, n=0):
    lines = [f'LINKS_Name = "{text}"', 'ICS_ControlPage = "Controls"', 'LINKID_DataType = "Number"',
             'INPID_InputControl = "LabelControl"', "INP_External = false", "INP_Passive = true"]
    if dropdown:
        lines += ["LBLC_DropDownButton = true", f"LBLC_NumInputs = {n}", "LBLC_NestLevel = 1"]
    return f"\t\t\t\t\t\t{key} = {{\n" + "".join(f"\t\t\t\t\t\t\t{l},\n" for l in lines) + "\t\t\t\t\t\t},\n"


def ordered_items():
    """Inspector order: header, description lines, controls - per section."""
    items = []
    for sid, title, desc, keys in SECTIONS:
        items.append(("hdr", sid, title, len(desc) + len(keys)))
        for i, line in enumerate(desc):
            items.append(("lbl", f"{sid}Txt{i + 1}", line, 0))
        for k in keys:
            items.append(("ctl", k, None, 0))
    return items


def uc_block():
    out = []
    for typ, key, text, n in ordered_items():
        if typ == "hdr":
            out.append(label_uc(key, text, True, n))
            continue
        if typ == "lbl":
            out.append(label_uc(key, text))
            continue
        key, label, kind, d, lo, hi, extra = VIS[key]
        lines = [f'LINKS_Name = "{label}"', 'ICS_ControlPage = "Controls"',
                 'LINKID_DataType = "Number"', f"INP_Default = {d}",
                 'INPS_StatusText = "' + HELP[key].replace('"', "'") + '"']
        if kind == "combo":
            lines += ['INPID_InputControl = "ComboControl"', "INP_Integer = true",
                      'CC_LabelPosition = "Horizontal"']
            lines += [f'{{ CCS_AddString = "{s}", }}' for s in extra]
        elif kind == "check":
            lines += ['INPID_InputControl = "CheckboxControl"', "INP_Integer = true",
                      "INP_MinScale = 0", "INP_MaxScale = 1"]
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


def inputs_block():
    out = []
    for key, _, _, d, *_ in VISIBLE:
        out.append(f"\t\t\t\t\t\t{key} = Input {{ Value = {d}, }},\n")
    for key, e in HIDDEN.items():
        out.append(f'\t\t\t\t\t\t{key} = Input {{ Value = 0, Expression = "{e}", }},\n')
    return "".join(out)


def instance_inputs():
    out = [f'\t\t\t\tMainInput1 = InstanceInput {{ SourceOp = "{C}", Source = "Input", }},\n']
    for typ, key, text, _ in ordered_items():
        if typ != "ctl":
            out.append(f'\t\t\t\t{key} = InstanceInput {{ SourceOp = "{C}", Source = "{key}", }},\n')
            continue
        _, label, _, d, *_ = VIS[key]
        out.append(f'\t\t\t\t{key} = InstanceInput {{ SourceOp = "{C}", Source = "{key}", Name = "{label}", Default = {d}, }},\n')
    return "".join(out)


def tool(name, reg, inputs, pos):
    body = "".join(f"\t\t\t\t\t\t{l},\n" for l in inputs)
    return (f"\t\t\t\t{name} = {reg} {{\n\t\t\t\t\tCtrlWZoom = false,\n\t\t\t\t\tNameSet = true,\n"
            f"\t\t\t\t\tInputs = {{\n{body}\t\t\t\t\t}},\n"
            f"\t\t\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {pos[0]}, {pos[1]} }} }},\n\t\t\t\t}},\n")


def build():
    tools = [
        tool("CJResize", "BetterResize", [
            f'Input = Input {{ SourceOp = "{C}", Source = "Output", }}',
            f'Width = Input {{ Value = {DW}, Expression = "{C}.RW", }}',
            f'Height = Input {{ Value = {DH}, Expression = "{C}.RH", }}',
            'PixelAspect = Input { Value = { 1, 1 }, }'], (110, 0)),
        tool("CJCanvas", "Crop", [
            'Input = Input { SourceOp = "CJResize", Source = "Output", }',
            f'XOffset = Input {{ Value = 0, Expression = "{C}.PadX", }}',
            f'YOffset = Input {{ Value = 0, Expression = "{C}.PadY", }}',
            f'XSize = Input {{ Value = {DW}, Expression = "{C}.OutW", }}',
            f'YSize = Input {{ Value = {DH}, Expression = "{C}.OutH", }}'], (220, 0)),
        tool("CJBG", "Background", [
            'UseFrameFormatSettings = Input { Value = 0, }',
            f'Width = Input {{ Value = {DW}, Expression = "{C}.OutW", }}',
            f'Height = Input {{ Value = {DH}, Expression = "{C}.OutH", }}',
            'PixelAspect = Input { Value = { 1, 1 }, }',
            'TopLeftRed = Input { Value = 0, }', 'TopLeftGreen = Input { Value = 0, }',
            'TopLeftBlue = Input { Value = 0, }', 'TopLeftAlpha = Input { Value = 0, }'], (220, -60)),
        tool("CJMove", "Transform", [
            'Input = Input { SourceOp = "CJCanvas", Source = "Output", }',
            'Edges = Input { Value = 0, }',
            f'Size = Input {{ Value = 1, Expression = "{C}.Sc", }}',
            f'Angle = Input {{ Value = 0, Expression = "{C}.Angle", }}',
            f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point({C}.NX + {C}.OX, {C}.NY + {C}.OY)", }}'],
            (330, 0)),
        tool("CJWinMask", "RectangleMask", [
            'SoftEdge = Input { Value = 0.0006, }',
            f'MaskWidth = Input {{ Value = {DW}, Expression = "{C}.OutW", }}',
            f'MaskHeight = Input {{ Value = {DH}, Expression = "{C}.OutH", }}',
            'PixelAspect = Input { Value = { 1, 1 }, }',
            'ClippingMode = Input { Value = FuID { "None" }, }',
            f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point({C}.WNX, {C}.WNY)", }}',
            f'Width = Input {{ Value = 0.9, Expression = "{C}.WW", }}',
            f'Height = Input {{ Value = 0.4, Expression = "{C}.WH", }}',
            f'CornerRadius = Input {{ Value = 0, Expression = "{C}.WR", }}'], (330, 120)),
        tool("CJTileMask", "RectangleMask", [
            'SoftEdge = Input { Value = 0.0006, }',
            'PaintMode = Input { Value = FuID { "Multiply" }, }',
            f'MaskWidth = Input {{ Value = {DW}, Expression = "{C}.OutW", }}',
            f'MaskHeight = Input {{ Value = {DH}, Expression = "{C}.OutH", }}',
            'PixelAspect = Input { Value = { 1, 1 }, }',
            'ClippingMode = Input { Value = FuID { "None" }, }',
            f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point({C}.NX, {C}.NY)", }}',
            f'Width = Input {{ Value = 0.5, Expression = "{C}.MW", }}',
            f'Height = Input {{ Value = 0.5, Expression = "{C}.MH", }}',
            f'CornerRadius = Input {{ Value = 0, Expression = "{C}.MR", }}',
            'EffectMask = Input { SourceOp = "CJWinMask", Source = "Mask", }'], (330, 60)),
        tool("CJMerge", "Merge", [
            'Background = Input { SourceOp = "CJBG", Source = "Output", }',
            'Foreground = Input { SourceOp = "CJMove", Source = "Output", }',
            'EffectMask = Input { SourceOp = "CJTileMask", Source = "Mask", }',
            'PerformDepthMerge = Input { Value = 0, }'], (440, 0)),
    ]
    return f"""{{
\tTools = ordered() {{
\t\tCarousel_Slide = MacroOperator {{
\t\t\tCtrlWZoom = false,
\t\t\tNameSet = true,
\t\t\tInputs = ordered() {{
{instance_inputs()}\t\t\t}},
\t\t\tOutputs = {{
\t\t\t\tMainOutput1 = InstanceOutput {{ SourceOp = "CJMerge", Source = "Output", }},
\t\t\t}},
\t\t\tViewInfo = GroupInfo {{ Pos = {{ 0, 0 }} }},
\t\t\tTools = ordered() {{
\t\t\t\t{C} = BrightnessContrast {{
\t\t\t\t\tCtrlWZoom = false,
\t\t\t\t\tNameSet = true,
\t\t\t\t\tInputs = {{
{inputs_block()}\t\t\t\t\t}},
\t\t\t\t\tViewInfo = OperatorInfo {{ Pos = {{ 0, 0 }} }},
\t\t\t\t\tUserControls = ordered() {{
{uc_block()}\t\t\t\t\t}},
\t\t\t\t}},
{"".join(tools)}\t\t\t}},
\t\t}},
\t}},
\tActiveTool = "Carousel_Slide"
}}
"""


if __name__ == "__main__":
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(root, "build", "Edit", "Effects", "Carousel_Slide")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "Carousel_Slide.setting")
    open(out, "w", encoding="utf-8").write(build())
    print("wrote", out, "-", len(VISIBLE), "controls,", len(HIDDEN), "hidden")
