"""FakeUI - writes the Fusion macros (.setting) from Giniroisenkou_FakeUI_layouts.py.

FakeUI_<Template>  (the page: Profile, News, Magazine)
    Ignores its own clip. Output = static art (picture holes transparent) with every
    changeable text as a Text+ node on top. Put it on the TOP track.
    FUICtrl holds the switches / colours; art variants are picked with Dissolve tools.

FakeUI_<Template>_Photo  (one per picture)
    MediaIn -> FUICtrl (BrightnessContrast: Saturation + all maths as hidden expression
    controls) -> FUIResize (BetterResize to cover/fit size) -> FUICrop (exact slot size,
    reframe) -> FUIMerge onto FUIBG (transparent 1080x1920). The macro builds its own
    canvas because a clip-level Fusion comp runs at the SOURCE resolution.
"""
import os

from Giniroisenkou_FakeUI_layouts import *  # noqa: F401,F403

PFX = "FakeUI"

# Text+ calibration - measured in Resolve 21.1 (see README "How it works").
# Fusion scales a font by its line height (hhea ascent + descent), so the Text+ Size for
# a wanted em size in px is  px / W * LINE_H[font] / TEXT_K,  and line spacing is relative
# to that line height too. Lines inside a block follow the anchor (left / centre / right).
TEXT_K = float(os.environ.get("FAKEUI_TEXT_K", 0.81))
LINE_H = {"Segoe UI": 1.330, "Times New Roman": 1.107, "Georgia": 1.136, "Arial": 1.117,
          "DM Serif Display": 1.371}
H_ANCHOR = {"left": -1, "center": 0, "right": 1}           # HorizontalLeftCenterRight
V_ANCHOR = {"top": -1, "center": 0}                        # VerticalTopCenterBottom


# ------------------------------------------------------------ serializer ---
def lua_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def num(v):
    return repr(round(v, 6)) if isinstance(v, float) else str(v)


def val(v):
    if isinstance(v, str):
        return lua_str(v)
    if isinstance(v, (tuple, list)):
        return "{ " + ", ".join(num(x) for x in v) + " }"
    return num(v)


def I(v=None, expr=None, src=None):
    if src:
        return f'Input {{ SourceOp = "{src}", Source = "Output", }}'
    parts = []
    if v is not None:
        parts.append(f"Value = {val(v)}")
    if expr is not None:
        parts.append(f"Expression = {lua_str(expr)}")
    return "Input { " + ", ".join(parts) + ", }"


def tool(name, regid, inputs, pos, extra=""):
    body = "".join(f"\t\t\t\t\t\t{k} = {v},\n" for k, v in inputs.items())
    return (f"\t\t\t\t{name} = {regid} {{\n\t\t\t\t\tCtrlWZoom = false,\n"
            f"\t\t\t\t\tInputs = {{\n{body}\t\t\t\t\t}},\n"
            f"\t\t\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {pos[0]}, {pos[1]} }} }},\n{extra}\t\t\t\t}},\n")


def _uc(name, fields):
    return f"\t\t\t\t\t\t{name} = {{ " + " ".join(f"{k} = {v}," for k, v in fields) + " },\n"


def uc_combo(name, label, options, default=0):
    n = len(options) - 1
    opts = " ".join(f"{{ CCS_AddString = {lua_str(o)}, }}," for o in options)
    return (f"\t\t\t\t\t\t{name} = {{ LINKS_Name = {lua_str(label)}, LINKID_DataType = \"Number\", "
            f"INPID_InputControl = \"ComboControl\", INP_Integer = true, INP_Default = {default}, "
            f"INP_MinScale = 0, INP_MaxScale = {n}, INP_MinAllowed = 0, INP_MaxAllowed = {n}, "
            f"CC_LabelPosition = \"Horizontal\", ICS_ControlPage = \"Controls\", {opts} }},\n")


def uc_check(name, label, default=0):
    return _uc(name, [("LINKS_Name", lua_str(label)), ("LINKID_DataType", '"Number"'),
                      ("INPID_InputControl", '"CheckboxControl"'), ("INP_Integer", "true"),
                      ("INP_Default", default), ("CBC_TriState", "false"), ("ICS_ControlPage", '"Controls"')])


def uc_slider(name, label, default, lo, hi, amin=None, amax=None, visible=True):
    f = [("LINKS_Name", lua_str(label)), ("LINKID_DataType", '"Number"'), ("INPID_InputControl", '"SliderControl"'),
         ("INP_Default", num(default)), ("INP_MinScale", num(lo)), ("INP_MaxScale", num(hi))]
    if amin is not None:
        f.append(("INP_MinAllowed", num(amin)))
    if amax is not None:
        f.append(("INP_MaxAllowed", num(amax)))
    if not visible:
        f.append(("IC_Visible", "false"))
    f.append(("ICS_ControlPage", '"Controls"'))
    return _uc(name, f)


def uc_color(prefix, label, hexv, group):
    r, g, b = rgb(hexv)
    out = ""
    for cid, (ch, v) in enumerate((("Red", r), ("Green", g), ("Blue", b))):
        f = [("LINKS_Name", lua_str(label if cid == 0 else f"{label} {ch}")), ("LINKID_DataType", '"Number"'),
             ("INPID_InputControl", '"ColorControl"'), ("INP_Default", num(round(v, 6))),
             ("INP_MinScale", "0"), ("INP_MaxScale", "1"), ("IC_ControlGroup", group), ("IC_ControlID", cid),
             ("ICS_ControlPage", '"Controls"')]
        if cid == 0:
            f.append(("CLRC_ShowWheel", "false"))
        out += _uc(prefix + ch, f)
    return out


def user_controls(ucs):
    return "\t\t\t\t\tUserControls = ordered() {\n" + "".join(ucs) + "\t\t\t\t\t},\n"


def iif_lut(var, values):
    e = num(values[-1])
    for i in range(len(values) - 2, -1, -1):
        e = f"iif({var} == {i}, {num(values[i])}, {e})"
    return e


def rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def loader(name, png, pos):
    return (f"\t\t\t\t{name} = Loader {{\n"
            "\t\t\t\t\tClips = {\n\t\t\t\t\t\tClip {\n"
            '\t\t\t\t\t\t\tID = "Clip1",\n'
            f'\t\t\t\t\t\t\tFilename = "Setting:{png}",\n'
            '\t\t\t\t\t\t\tFormatID = "PNGFormat",\n'
            "\t\t\t\t\t\t\tStartFrame = -1,\n\t\t\t\t\t\t\tLengthSetManually = true,\n"
            "\t\t\t\t\t\t\tTrimIn = 0, TrimOut = 0,\n\t\t\t\t\t\t\tExtendFirst = 0, ExtendLast = 0,\n"
            "\t\t\t\t\t\t\tLoop = 1,\n\t\t\t\t\t\t\tAspectMode = 0, Depth = 0, TimeCode = 0,\n"
            "\t\t\t\t\t\t\tGlobalStart = -2000000000, GlobalEnd = 2000000000,\n"
            "\t\t\t\t\t\t},\n\t\t\t\t\t},\n"
            "\t\t\t\t\tCtrlWZoom = false,\n"
            "\t\t\t\t\tInputs = {\n"
            "\t\t\t\t\t\tPostMultiplyByAlpha = Input { Value = 1, },\n"
            "\t\t\t\t\t\tLoop = Input { Value = 1, },\n"
            "\t\t\t\t\t},\n"
            f"\t\t\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {pos[0]}, {pos[1]} }} }},\n"
            "\t\t\t\t},\n")


def canvas_bg(name, pos):
    return tool(name, "Background", {
        "Width": I(W), "Height": I(H), "UseFrameFormatSettings": I(0),
        "TopLeftRed": I(0), "TopLeftGreen": I(0), "TopLeftBlue": I(0), "TopLeftAlpha": I(0),
    }, pos)


def dissolve(name, bg, fg, mix_expr, pos):
    return tool(name, "Dissolve", {"Background": I(src=bg), "Foreground": I(src=fg), "Mix": I(0, mix_expr)}, pos)


def merge(name, bg, fg, pos, extra=None):
    ins = {"Background": I(src=bg), "Foreground": I(src=fg), "PerformDepthMerge": I(0)}
    ins.update(extra or {})
    return tool(name, "Merge", ins, pos)


def macro(name, inputs, out_op, tools):
    ins = "".join(f"\t\t\t\t{k} = {v},\n" for k, v in inputs)
    return ("{\n\tTools = ordered() {\n"
            f"\t\t{name} = MacroOperator {{\n\t\t\tCtrlWZoom = false,\n\t\t\tNameSet = true,\n"
            f"\t\t\tInputs = ordered() {{\n{ins}\t\t\t}},\n"
            f'\t\t\tOutputs = {{\n\t\t\t\tMainOutput1 = InstanceOutput {{ SourceOp = "{out_op}", Source = "Output", }},\n\t\t\t}},\n'
            "\t\t\tViewInfo = GroupInfo { Pos = { 0, 0 } },\n"
            "\t\t\tTools = ordered() {\n" + "".join(tools) +
            "\t\t\t},\n\t\t},\n\t},\n"
            f'\tActiveTool = "{name}"\n}}\n')


def inst(op, src, label=None, default=None, group=None):
    s = f'InstanceInput {{ SourceOp = "{op}", Source = "{src}"'
    if label:
        s += f", Name = {lua_str(label)}"
    if group is not None:
        s += f", ControlGroup = {group}"
    if default is not None:
        s += f", Default = {val(default)}"
    return s + ", }"


class Inputs(list):
    def next_index(self):
        return sum(1 for k, _ in self if k != "MainInput1") + 1

    def add(self, op, src, label=None, default=None, group=None):
        key = "MainInput1" if src == "Input" and op == "FUICtrl" else f"Input{self.next_index()}"
        self.append((key, inst(op, src, label, default, group)))


# ------------------------------------------------------------ page macro ---
def text_node(f, color, y):
    inputs = {
        "Width": I(W), "Height": I(H), "UseFrameFormatSettings": I(0),
        "StyledText": I(f["text"]),
        "Font": I(f["font"][0]), "Style": I(f["font"][1]),
        "Size": I(round(f["size"] / W * LINE_H[f["font"][0]] / TEXT_K, 6)),
        "Center": I((round(f["x"] / W, 6), round(1 - f["y"] / H, 6))),
        "HorizontalLeftCenterRight": I(H_ANCHOR[f["align"]]),
        "VerticalTopCenterBottom": I(V_ANCHOR[f["va"]]),
        "LineSpacing": I(round(f.get("ls", 1.0) * 1.15 / LINE_H[f["font"][0]], 4)),
        "CharacterSpacing": I(f.get("cs", 1.0)),
        "Alpha1": I(1.0),
    }
    for ch, e in zip(("Red1", "Green1", "Blue1"), color):
        inputs[ch] = I(expr=e) if isinstance(e, str) else I(e)
    return tool("t" + f["key"], "TextPlus", inputs, (660, y))


def role_color(tpl, role):
    C = "FUICtrl."
    if tpl == "Profile":
        if role == "btn1":
            on, fg0, fg1 = rgb(PROFILE_THEMES[0]["onprimary"]), rgb(PROFILE_THEMES[0]["fg"]), rgb(PROFILE_THEMES[1]["fg"])
            return [f"iif({C}Buttons == 0, {num(on[c])}, iif({C}Theme == 0, {num(fg0[c])}, {num(fg1[c])}))" for c in range(3)]
        vals = [rgb(PROFILE_THEMES[t][role]) for t in PROFILE_THEMES]
        return [iif_lut(C + "Theme", [v[c] for v in vals]) for c in range(3)]
    if tpl == "News":
        vals = [rgb(NEWS_STYLES[s][role]) for s in NEWS_STYLES]
        return [iif_lut(C + "Paper", [v[c] for v in vals]) for c in range(3)]
    prefix = {"mast": "Mast", "text": "Text", "accent": "Accent"}[role]
    return [C + prefix + ch for ch in ("Red", "Green", "Blue")]


def page_macro(tpl):
    name = f"{PFX}_{tpl}"
    tools, ins = [], Inputs()
    ins.add("FUICtrl", "Input")
    ucs = []
    if tpl == "Profile":
        ucs += [uc_combo("Theme", "Theme", [t["name"] for t in PROFILE_THEMES.values()]),
                uc_combo("Buttons", "Buttons", list(PROFILE_BUTTONS.values()))]
        ins.add("FUICtrl", "Theme", "Theme", 0)
        ins.add("FUICtrl", "Buttons", "Buttons", 0)
    elif tpl == "News":
        ucs.append(uc_combo("Paper", "Paper", [s["name"] for s in NEWS_STYLES.values()]))
        ins.add("FUICtrl", "Paper", "Paper", 0)
    else:
        ucs.append(uc_slider("Shade", "Dark shade top / bottom", 0.6, 0, 1, amin=0, amax=1))
        ucs.append(uc_check("Barcode", "Show barcode", 1))
        ins.add("FUICtrl", "Shade", "Dark shade top / bottom", 0.6)
        ins.add("FUICtrl", "Barcode", "Show barcode", 1)
        for g, (pfx, label, hexv) in enumerate(MAG_COLORS, start=1):
            ucs.append(uc_color(pfx, label, hexv, g))
            grp = ins.next_index()
            for ch, v in zip(("Red", "Green", "Blue"), rgb(hexv)):
                ins.add("FUICtrl", pfx + ch, label if ch == "Red" else None, round(v, 6), group=grp)
    ucs.append(uc_check("ShowSlots", "Show slot numbers", 0))
    ins.add("FUICtrl", "ShowSlots", "Show slot numbers", 0)
    tools.append(tool("FUICtrl", "BrightnessContrast", {}, (0, 0), user_controls(ucs)))

    # art
    tools.append(canvas_bg("FUIBG", (440, 100)))
    if tpl == "Profile":
        arts = [f"{PFX}_Profile_{t}{b}.png" for t in PROFILE_THEMES for b in PROFILE_BUTTONS]
        for i, png in enumerate(arts):
            tools.append(loader(f"FUIArt{i}", png, (110 * i, 100)))
        tools += [dissolve("FUIMixD", "FUIArt0", "FUIArt1", "FUICtrl.Buttons", (55, 170)),
                  dissolve("FUIMixL", "FUIArt2", "FUIArt3", "FUICtrl.Buttons", (275, 170)),
                  dissolve("FUIArt", "FUIMixD", "FUIMixL", "FUICtrl.Theme", (165, 240))]
    elif tpl == "News":
        for i in NEWS_STYLES:
            tools.append(loader(f"FUIArt{i}", f"{PFX}_News_{i}.png", (110 * i, 100)))
        tools += [dissolve("FUIMix1", "FUIArt0", "FUIArt1", "iif(FUICtrl.Paper == 1, 1, 0)", (55, 170)),
                  dissolve("FUIArt", "FUIMix1", "FUIArt2", "iif(FUICtrl.Paper == 2, 1, 0)", (165, 240))]
    else:
        tools += [loader("FUIShadeL", f"{PFX}_Magazine_shade.png", (0, 100)),
                  loader("FUIBarL", f"{PFX}_Magazine_barcode.png", (110, 100)),
                  dissolve("FUIShade", "FUIBG", "FUIShadeL", "FUICtrl.Shade", (0, 170)),
                  dissolve("FUIBar", "FUIBG", "FUIBarL", "FUICtrl.Barcode", (110, 170)),
                  merge("FUIArt", "FUIShade", "FUIBar", (55, 240))]
    tools += [loader("FUISlotsL", f"{PFX}_{tpl}_slots.png", (550, 100)),
              dissolve("FUISlots", "FUIBG", "FUISlotsL", "FUICtrl.ShowSlots", (495, 170)),
              merge("FUIBase", "FUISlots", "FUIArt", (330, 300))]

    prev = "FUIBase"
    for k, f in enumerate(TEMPLATES[tpl]["text"]):
        y = 380 + k * 60
        tools.append(text_node(f, role_color(tpl, f["color"]), y))
        tools.append(merge("m" + f["key"], prev, "t" + f["key"], (330, y)))
        prev = "m" + f["key"]
        ins.add("t" + f["key"], "StyledText", f["label"])
    if tpl in ("News", "Magazine"):
        for src, lab in (("Font", "Masthead font"), ("Style", "Masthead style"), ("Size", "Masthead size")):
            ins.add("tMast", src, lab)
        big = "tHead" if tpl == "News" else "tName"
        ins.add(big, "Size", "Headline size" if tpl == "News" else "Cover name size")
    return name, macro(name, ins, prev, tools)


# ----------------------------------------------------------- photo macro ---
def photo_macro(tpl):
    name = f"{PFX}_{tpl}_Photo"
    slots = TEMPLATES[tpl]["slots"]
    logo = LOGO_SLOTS.get(tpl)
    xs, ys, ws, hs = zip(*[sl[2] for sl in slots])
    C = "FUICtrl."
    ucs = [
        uc_combo("Slot", "Slot", [sl[1] for sl in slots]),
        uc_combo("Fit", "Fit", ["Auto", "Fill (crop)", "Fit (whole picture)"]),
        uc_combo("SrcAspect", "Source aspect", [a for a, _ in SOURCE_ASPECTS]),
        uc_slider("Zoom", "Zoom", 1.0, 0.5, 3.0, amin=0.05),
        uc_slider("ReframeX", "Reframe X", 0.0, -1.0, 1.0),
        uc_slider("ReframeY", "Reframe Y", 0.0, -1.0, 1.0),
    ]
    hidden = {
        "hA": iif_lut(C + "SrcAspect", [round(v, 6) for _, v in SOURCE_ASPECTS]),
        "hSX": iif_lut(C + "Slot", list(xs)),
        "hSY": iif_lut(C + "Slot", list(ys)),
        "hSW": iif_lut(C + "Slot", list(ws)),
        "hSH": iif_lut(C + "Slot", list(hs)),
        "hFM": (f"iif({C}Fit == 0, iif({C}Slot == {logo}, 1, 0), {C}Fit - 1)" if logo is not None
                else f"iif({C}Fit == 0, 0, {C}Fit - 1)"),
        "hCW": (f"iif({C}hFM == 0, iif({C}hSW > {C}hSH * {C}hA, {C}hSW, {C}hSH * {C}hA), "
                f"iif({C}hSW < {C}hSH * {C}hA, {C}hSW, {C}hSH * {C}hA)) * {C}Zoom"),
        "hCH": f"{C}hCW / {C}hA",
        "hXO": f"({C}hCW - {C}hSW) / 2 * (1 + {C}ReframeX)",
        "hYO": f"({C}hCH - {C}hSH) / 2 * (1 + {C}ReframeY)",
        "hPX": f"({C}hSX + {C}hSW / 2) / {W}",
        "hPY": f"1 - ({C}hSY + {C}hSH / 2) / {H}",
    }
    for k in hidden:
        ucs.append(uc_slider(k, k, 0, -5000, 5000, visible=False))
    tools = [
        tool("FUICtrl", "BrightnessContrast", {k: I(0, e) for k, e in hidden.items()}, (0, 0), user_controls(ucs)),
        tool("FUIResize", "BetterResize", {"Input": I(src="FUICtrl"), "Width": I(1080, C + "hCW"), "Height": I(1920, C + "hCH"),
                                           "KeepAspect": I(0), "HiQOnly": I(0)}, (110, 0)),
        tool("FUICrop", "Crop", {"Input": I(src="FUIResize"), "XOffset": I(0, C + "hXO"), "YOffset": I(0, C + "hYO"),
                                 "XSize": I(1080, C + "hSW"), "YSize": I(1920, C + "hSH"),
                                 "KeepAspect": I(0), "KeepCentered": I(0)}, (220, 0)),
        canvas_bg("FUIBG", (330, -60)),
        merge("FUIMerge", "FUIBG", "FUICrop", (330, 0), {"Center": I((0.5, 0.5), f"Point({C}hPX, {C}hPY)")}),
    ]
    ins = Inputs()
    ins.add("FUICtrl", "Input")
    ins.add("FUICtrl", "Slot", "Slot", 0)
    ins.add("FUICtrl", "Fit", "Fit", 0)
    ins.add("FUICtrl", "SrcAspect", "Source aspect (match the clip)", 0)
    ins.add("FUICtrl", "Zoom", "Zoom", 1.0)
    ins.add("FUICtrl", "ReframeX", "Reframe X", 0.0)
    ins.add("FUICtrl", "ReframeY", "Reframe Y", 0.0)
    ins.add("FUICtrl", "Saturation", "Saturation (0 = B&W)", 1.0)
    return name, macro(name, ins, "FUIMerge", tools)


def write_all(build):
    names = []
    for tpl in TEMPLATES:
        for fn in (page_macro, photo_macro):
            name, text = fn(tpl)
            with open(os.path.join(build, name + ".setting"), "w", encoding="utf-8") as fh:
                fh.write(text)
            names.append(name)
    return names
