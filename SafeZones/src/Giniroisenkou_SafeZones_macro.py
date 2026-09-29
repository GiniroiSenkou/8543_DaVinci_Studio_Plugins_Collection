#!/usr/bin/env python3
"""
Giniroisenkou_SafeZones_macro.py - writes the SafeZones Fusion macro(s) from build/slots.json.

Graph (all names prefixed SZ):
  MainInput -> SZCtrl (BrightnessContrast, identity; holds every control + hidden maths)
            -> SZResize (BetterResize, keeps source aspect)  -> SZCanvas (Crop, pads to the phone frame)
            -> SZPlace (Transform: scales the video into the slot of the chosen state)
  SZBlack (Background, opaque)  + SZPlace          -> SZVideo (Merge)
  Loaders -> SZGuiSwitch (Switch)   -> SZGuiSize (BetterResize to frame)   -> SZGui (Merge, blend = GUI opacity)
  Loaders -> SZGuideSwitch (Switch) -> SZGuideSize (BetterResize to frame) -> SZGuides (Merge, blend = guides)
  -> MainOutput

Overlay PNGs are referenced as "Setting:<file>" so they must sit beside the .setting (the .drfx does that).
One master effect plus one quick effect per platform (same macro, Platform preset).
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "..", "build")
DW, DH = 1080, 1920
PREFIX = "SZCtrl"

QUICK = [  # file stem, platform index
    ("SafeZones_InstagramReel", 0), ("SafeZones_InstagramStory", 1), ("SafeZones_TikTok", 2),
    ("SafeZones_YouTubeShorts", 3), ("SafeZones_FacebookReel", 4), ("SafeZones_FacebookStory", 5),
    ("SafeZones_LinkedIn", 6), ("SafeZones_Insta360", 7),
]


def lua_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def iif_chain(var, values, fmt="{:.6f}"):
    """values indexed 0..n-1 -> iif(var==0, v0, iif(var==1, v1, ... v_last))"""
    e = fmt.format(values[-1])
    for i in range(len(values) - 2, -1, -1):
        e = f"iif({var}=={i}, {fmt.format(values[i])}, {e})"
    return e


def build(table, name, platform_default, pathmap="Setting:"):
    states = table["states"]
    P, V = len(table["platforms"]), len(table["views"])
    C = PREFIX
    key = f"({C}.Platform*{V}+{C}.View)"
    # --- slot LUTs (normalised to the design frame, y from top)
    sx = [s["slot"][0] / DW for s in states]
    sy = [s["slot"][1] / DH for s in states]
    sw = [s["slot"][2] / DW for s in states]
    sh = [s["slot"][3] / DH for s in states]
    fd = [{"fill": 0, "fit": 1, "width": 2}[s["fit"]] for s in states]

    # --- unique GUI files + switch mapping  (index = Platform*V*2 + View*2 + Theme)
    gui_files, gui_map = [], []
    for s in states:
        for theme in ("dark", "light"):
            f = s["gui"].get(theme) or s["gui"]["dark"]
            if f not in gui_files:
                gui_files.append(f)
            gui_map.append(gui_files.index(f))
    guide_files = [s["guide"] for s in states]

    controls = []   # (id, dict of UserControl fields, default, published_name)

    def label(cid, text, section=False, n=0):
        d = dict(LINKS_Name=text, ICS_ControlPage="Controls", LINKID_DataType="Number",
                 INPID_InputControl="LabelControl", INP_External=False, INP_Passive=True)
        if section:
            d.update(LBLC_DropDownButton=True, LBLC_NumInputs=n, LBLC_NestLevel=1)
        controls.append((cid, d, None, None))

    def combo(cid, name, opts, default, tip):
        d = dict(LINKS_Name=name, ICS_ControlPage="Controls", LINKID_DataType="Number", INP_Default=default,
                 INPS_StatusText=tip, INPID_InputControl="ComboControl", INP_Integer=True,
                 CC_LabelPosition="Horizontal", _opts=opts)
        controls.append((cid, d, default, name))

    def slider(cid, name, default, lo, hi, tip, integer=False, amin=None, amax=None):
        d = dict(LINKS_Name=name, ICS_ControlPage="Controls", LINKID_DataType="Number", INP_Default=default,
                 INPS_StatusText=tip, INPID_InputControl="SliderControl", INP_MinScale=lo, INP_MaxScale=hi,
                 INP_Integer=integer)
        if amin is not None:
            d["INP_MinAllowed"] = amin
        if amax is not None:
            d["INP_MaxAllowed"] = amax
        controls.append((cid, d, default, name))

    def check(cid, name, default, tip):
        d = dict(LINKS_Name=name, ICS_ControlPage="Controls", LINKID_DataType="Number", INP_Default=default,
                 INPS_StatusText=tip, INPID_InputControl="CheckboxControl", INP_Integer=True,
                 CBC_TriState=False)
        controls.append((cid, d, default, name))

    # ---------------- Inspector layout
    label("SecStart", "1  Start here", True, 7)
    label("SecStartTxt1", "Put SafeZones on an ADJUSTMENT CLIP above your edit.")
    label("SecStartTxt2", "The frame = a phone screen. Turn it OFF before you render.")
    combo("Platform", "Platform", table["platforms"], platform_default,
          "Which app to mirror. Each one draws that app's real screen: icons, name, caption, bars.")
    combo("View", "View", [
        "1st view - Full-screen (tapped)", "3rd view - Feed scroll", "Comments open", "Profile grid"], 0,
        "1st view: your video fills the phone and the app's buttons float on top - see what gets covered. "
        "3rd view: the phone shows the app feed and your video sits in the post, cropped like the app does. "
        "Comments open: the sheet slides up and the video shrinks above it. Profile grid: your video as a "
        "profile thumbnail.")
    combo("Theme", "App theme", ["Dark mode", "Light mode"], 0,
          "Light or dark app screens (feed, comments, grid). Full-screen views look the same in both.")
    combo("Timeline", "Timeline", ["1080 x 1920  vertical HD", "2160 x 3840  vertical 4K", "720 x 1280  vertical",
                                   "1920 x 1080  horizontal HD", "3840 x 2160  horizontal 4K"], 0,
          "Your timeline format. Vertical: the whole monitor is the phone. Horizontal: the phone is drawn in "
          "the middle of the frame, on black.")
    combo("Upload", "Upload shape", ["Same as timeline", "9:16 vertical", "4:5 portrait", "1:1 square",
                                     "3:4 portrait", "16:9 horizontal"], 0,
          "The shape of the file you will post. Everything outside that shape is cut away (never squeezed), "
          "exactly what gets uploaded, then shown the way the app shows it.")

    label("SecLook", "2  Overlay look", True, 4)
    slider("GuiOpacity", "GUI opacity", 1.0, 0, 1, "How strong the app interface is drawn. 0 hides it.",
           amin=0, amax=1)
    check("ShowGuides", "Show safe-zone guides", 0,
          "Red = covered by the app. Green dashed box = safe for text and faces. Yellow lines = where the "
          "feed (4:5) and grid (3:4) crops cut the frame. In feed/grid views: cyan = where your video sits.")
    slider("GuideOpacity", "Guide opacity", 0.9, 0, 1, "Strength of the guides.", amin=0, amax=1)
    check("HideVideo", "Show GUI only (no video)", 0, "Checks the overlay alone over black.")

    label("SecPic", "3  Your video inside the app", True, 5)
    label("SecPicTxt1", "How the app fits your upload into the post, sheet or thumbnail.")
    combo("Picture", "Picture", ["Like the app (default)", "Fill the slot (crop)", "Show whole video (fit)"], 0,
          "Like the app = what the platform really does (full-screen and comments show it whole, feed posts "
          "match the width and crop the height, thumbnails and cards crop to fill). Fill = always crop to the slot. "
          "Fit = shrink so the whole video shows.")
    slider("Zoom", "Zoom", 1.0, 0.5, 2.0, "Extra zoom inside the slot.", amin=0.1, amax=10)
    slider("PanX", "Reframe X", 0.0, -1, 1, "Slide the crop left/right when the video is bigger than the slot "
           "(like choosing the cover crop in the app).", amin=-1, amax=1)
    slider("PanY", "Reframe Y", 0.0, -1, 1, "Slide the crop up/down when the video is bigger than the slot.",
           amin=-1, amax=1)

    # ---------------- hidden maths on SZCtrl
    hidden = {
        "IW": f"iif({C}.Timeline==1, 2160, iif({C}.Timeline==2, 720, iif({C}.Timeline==3, 1920, "
              f"iif({C}.Timeline==4, 3840, 1080))))",
        "IH": f"iif({C}.Timeline==1, 3840, iif({C}.Timeline==2, 1280, iif({C}.Timeline==3, 1080, "
              f"iif({C}.Timeline==4, 2160, 1920))))",
        "PW": f"iif({C}.Timeline==1, 2160, iif({C}.Timeline==4, 2160, iif({C}.Timeline==2, 720, 1080)))",
        "PH": f"{C}.PW*16/9",
        "IA": f"{C}.IW/{C}.IH",
        "CA": f"iif({C}.Upload==1, 9/16, iif({C}.Upload==2, 0.8, iif({C}.Upload==3, 1, iif({C}.Upload==4, 0.75, "
              f"iif({C}.Upload==5, 16/9, {C}.IA)))))",
        # upload shape = centre cut of the timeline frame (nothing squeezed)
        "CW": f"floor(iif({C}.CA < {C}.IA, {C}.IH*{C}.CA, {C}.IW)+0.5)",
        "CH": f"floor(iif({C}.CA < {C}.IA, {C}.IH, {C}.IW/{C}.CA)+0.5)",
        "CutX": f"floor(({C}.IW-{C}.CW)/2)",
        "CutY": f"floor(({C}.IH-{C}.CH)/2)",
        # the uploaded file shown whole inside the phone frame
        "RW": f"floor(iif({C}.CA >= 9/16, {C}.PW, {C}.PH*{C}.CA)+0.5)",
        "RH": f"floor(iif({C}.CA >= 9/16, {C}.PW/{C}.CA, {C}.PH)+0.5)",
        "PadX": f"-floor(({C}.PW - {C}.RW)/2)",
        "PadY": f"-floor(({C}.PH - {C}.RH)/2)",
        "UW": f"{C}.RW/{C}.PW",
        "UH": f"{C}.RH/{C}.PH",
        # phone composite placed in the timeline frame (centred on black when horizontal)
        "FW": f"iif({C}.Timeline>=3, floor({C}.IH*9/16+0.5), {C}.IW)",
        "OutPadX": f"-floor(({C}.IW-{C}.FW)/2)",
        "Key": key,
        "SX": iif_chain(f"{C}.Key", sx), "SY": iif_chain(f"{C}.Key", sy),
        "SW": iif_chain(f"{C}.Key", sw), "SH": iif_chain(f"{C}.Key", sh),
        "FitDef": iif_chain(f"{C}.Key", fd, "{:d}"),
        "FitOn": f"iif({C}.Picture==0, {C}.FitDef, {C}.Picture-1)",
        "A": f"{C}.SW/{C}.UW",
        "B": f"{C}.SH/{C}.UH",
        # 0 fill (cover the slot)  1 fit (whole video)  2 width (match the slot width, crop the height)
        "Sc": f"{C}.Zoom*iif({C}.FitOn==2, {C}.A, iif({C}.FitOn==1, iif({C}.A<{C}.B, {C}.A, {C}.B), "
              f"iif({C}.A>{C}.B, {C}.A, {C}.B)))",
        "OvX": f"iif({C}.Sc*{C}.UW>{C}.SW, ({C}.Sc*{C}.UW-{C}.SW)/2, 0)",
        "OvY": f"iif({C}.Sc*{C}.UH>{C}.SH, ({C}.Sc*{C}.UH-{C}.SH)/2, 0)",
        "NX": f"{C}.SX + {C}.SW/2 + {C}.PanX*{C}.OvX",
        "NY": f"1 - ({C}.SY + {C}.SH/2) + {C}.PanY*{C}.OvY",
        "GuideBlend": f"{C}.ShowGuides*{C}.GuideOpacity",
    }

    L = []
    w = L.append
    w("{")
    w("\tTools = ordered() {")
    w(f"\t\t{name} = MacroOperator {{")
    w("\t\t\tCtrlWZoom = false,")
    w("\t\t\tNameSet = true,")
    w("\t\t\tCustomData = { HelpPage = \"https://github.com/\", },")
    w("\t\t\tInputs = ordered() {")
    w(f'\t\t\t\tMainInput1 = InstanceInput {{ SourceOp = "{C}", Source = "Input", }},')
    for cid, d, default, pub in controls:
        extra = f', Name = {lua_str(pub)}, Default = {default}' if pub else ""
        w(f'\t\t\t\t{cid} = InstanceInput {{ SourceOp = "{C}", Source = "{cid}"{extra}, }},')
    w("\t\t\t},")
    w("\t\t\tOutputs = ordered() {")
    w('\t\t\t\tMainOutput1 = InstanceOutput { SourceOp = "SZOut", Source = "Output", },')
    w("\t\t\t},")
    w("\t\t\tViewInfo = GroupInfo { Pos = { 0, 0 } },")
    w("\t\t\tTools = ordered() {")
    # ---- control node
    w(f"\t\t\t\t{C} = BrightnessContrast {{")
    w("\t\t\t\t\tCtrlWZoom = false,")
    w("\t\t\t\t\tNameSet = true,")
    w("\t\t\t\t\tInputs = {")
    for cid, d, default, pub in controls:
        if pub:
            w(f"\t\t\t\t\t\t{cid} = Input {{ Value = {default}, }},")
    for hid, ex in hidden.items():
        w(f"\t\t\t\t\t\t{hid} = Input {{ Value = 0, Expression = {lua_str(ex)}, }},")
    w("\t\t\t\t\t},")
    w("\t\t\t\t\tViewInfo = OperatorInfo { Pos = { 0, 0 } },")
    w("\t\t\t\t\tUserControls = ordered() {")
    for cid, d, default, pub in controls:
        w(f"\t\t\t\t\t\t{cid} = {{")
        for k, v in d.items():
            if k == "_opts":
                continue
            if isinstance(v, bool):
                v = "true" if v else "false"
            elif isinstance(v, str):
                v = lua_str(v)
            w(f"\t\t\t\t\t\t\t{k} = {v},")
        for o in d.get("_opts", []):
            w(f"\t\t\t\t\t\t\t{{ CCS_AddString = {lua_str(o)}, }},")
        w("\t\t\t\t\t\t},")
    for hid in hidden:
        w(f'\t\t\t\t\t\t{hid} = {{ LINKS_Name = "{hid}", LINKID_DataType = "Number", '
          f'INPID_InputControl = "SliderControl", IC_Visible = false, INP_External = false, }},')
    w("\t\t\t\t\t},")
    w("\t\t\t\t},")

    def tool(tname, ttype, inputs, pos):
        w(f"\t\t\t\t{tname} = {ttype} {{")
        w("\t\t\t\t\tCtrlWZoom = false,")
        w("\t\t\t\t\tNameSet = true,")
        w("\t\t\t\t\tInputs = {")
        for k, v in inputs:
            w(f"\t\t\t\t\t\t{k} = {v},")
        w("\t\t\t\t\t},")
        w(f"\t\t\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {pos[0]}, {pos[1]} }} }},")
        w("\t\t\t\t},")

    def conn(op, src="Output"):
        return f'Input {{ SourceOp = "{op}", Source = "{src}", }}'

    def ex(e, v=0):
        return f"Input {{ Value = {v}, Expression = {lua_str(e)}, }}"

    rs = lambda wv, hv: [("Width", ex(wv, DW)), ("Height", ex(hv, DH)), ("PixelAspect", "Input { Value = { 1, 1 }, }")]
    tool("SZIn", "BetterResize", [("Input", conn(C))] + rs(f"{C}.IW", f"{C}.IH"), (110, 0))
    tool("SZCut", "Crop", [("Input", conn("SZIn")), ("XOffset", ex(f"{C}.CutX")), ("YOffset", ex(f"{C}.CutY")),
                           ("XSize", ex(f"{C}.CW", DW)), ("YSize", ex(f"{C}.CH", DH))], (165, 0))
    tool("SZResize", "BetterResize", [("Input", conn("SZCut"))] + rs(f"{C}.RW", f"{C}.RH"), (220, 0))
    tool("SZCanvas", "Crop", [("Input", conn("SZResize")), ("XOffset", ex(f"{C}.PadX")),
                              ("YOffset", ex(f"{C}.PadY")), ("XSize", ex(f"{C}.PW", DW)),
                              ("YSize", ex(f"{C}.PH", DH))], (275, 0))
    tool("SZPlace", "Transform", [("Input", conn("SZCanvas")), ("Edges", "Input { Value = 0, }"),
                                  ("Size", ex(f"{C}.Sc", 1)),
                                  ("Center", f"Input {{ Value = {{ 0.5, 0.5 }}, Expression = "
                                             f"{lua_str(f'Point({C}.NX, {C}.NY)')}, }}")], (330, 0))
    bg_inputs = [("UseFrameFormatSettings", "Input { Value = 0, }"), ("Width", ex(f"{C}.PW", DW)),
                 ("Height", ex(f"{C}.PH", DH)), ("PixelAspect", "Input { Value = { 1, 1 }, }"),
                 ("TopLeftRed", "Input { Value = 0, }"), ("TopLeftGreen", "Input { Value = 0, }"),
                 ("TopLeftBlue", "Input { Value = 0, }"), ("TopLeftAlpha", "Input { Value = 1, }")]
    tool("SZBlack", "Background", bg_inputs, (330, -60))
    tool("SZVideo", "Merge", [("Background", conn("SZBlack")), ("Foreground", conn("SZPlace")),
                              ("Blend", ex(f"1-{C}.HideVideo", 1)), ("PerformDepthMerge", "Input { Value = 0, }")],
         (440, 0))

    def loader(tname, fname, pos):
        w(f"\t\t\t\t{tname} = Loader {{")
        w(f'\t\t\t\t\tClips = {{ Clip {{ ID = "Clip1", Filename = {lua_str(pathmap + fname)}, FormatID = "PNGFormat", '
          'StartFrame = -1, LengthSetManually = true, TrimIn = 0, TrimOut = 0, ExtendFirst = 0, ExtendLast = 0, '
          'Loop = 0, AspectMode = 0, Depth = 0, TimeCode = 0, GlobalStart = 0, GlobalEnd = 0 } },')
        w("\t\t\t\t\tCtrlWZoom = false,")
        w("\t\t\t\t\tCtrlWShown = false,")
        w("\t\t\t\t\tNameSet = true,")
        w('\t\t\t\t\tInputs = { ["Gamut.SLogVersion"] = Input { Value = FuID { "SLog2" }, }, '
          '["Clip1.PNGFormat.PostMultiply"] = Input { Value = 1, }, '
          'HoldFirstFrame = Input { Value = 0, }, HoldLastFrame = Input { Value = 1000000, }, },')
        w(f"\t\t\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {pos[0]}, {pos[1]} }} }},")
        w("\t\t\t\t},")

    for i, f in enumerate(gui_files):
        loader(f"SZGuiL{i}", f, (550, 200 + i * 20))
    for i, f in enumerate(guide_files):
        loader(f"SZGuideL{i}", f, (770, 200 + i * 20))

    # Switch inputs follow the key*2+theme order; each points at its (shared) loader
    sw_in = [("NumberOfInputs", f"Input {{ Value = {len(gui_map)}, }}"), ("Source", ex(f"{C}.Key*2+{C}.Theme"))]
    for k, gi in enumerate(gui_map):
        sw_in.append((f"Input{k}", conn(f"SZGuiL{gi}")))
    tool("SZGuiSwitch", "Switch", sw_in, (550, 100))
    gd_in = [("NumberOfInputs", f"Input {{ Value = {len(guide_files)}, }}"), ("Source", ex(f"{C}.Key"))]
    for k in range(len(guide_files)):
        gd_in.append((f"Input{k}", conn(f"SZGuideL{k}")))
    tool("SZGuideSwitch", "Switch", gd_in, (770, 100))
    for nm, src, pos in (("SZGuiSize", "SZGuiSwitch", (550, 50)), ("SZGuideSize", "SZGuideSwitch", (770, 50))):
        tool(nm, "BetterResize", [("Input", conn(src))] + rs(f"{C}.PW", f"{C}.PH"), pos)
    tool("SZGui", "Merge", [("Background", conn("SZVideo")), ("Foreground", conn("SZGuiSize")),
                            ("Blend", ex(f"{C}.GuiOpacity", 1)), ("PerformDepthMerge", "Input { Value = 0, }")],
         (550, 0))
    tool("SZGuides", "Merge", [("Background", conn("SZGui")), ("Foreground", conn("SZGuideSize")),
                               ("Blend", ex(f"{C}.GuideBlend", 0)), ("PerformDepthMerge", "Input { Value = 0, }")],
         (770, 0))
    # phone composite -> timeline frame (identity on vertical timelines, centred on black on horizontal ones)
    tool("SZOutFit", "BetterResize", [("Input", conn("SZGuides"))] + rs(f"{C}.FW", f"{C}.IH"), (880, 0))
    tool("SZOutPad", "Crop", [("Input", conn("SZOutFit")), ("XOffset", ex(f"{C}.OutPadX")),
                              ("YOffset", "Input { Value = 0, }"), ("XSize", ex(f"{C}.IW", DW)),
                              ("YSize", ex(f"{C}.IH", DH))], (990, 0))
    out_bg = [("UseFrameFormatSettings", "Input { Value = 0, }"), ("Width", ex(f"{C}.IW", DW)),
              ("Height", ex(f"{C}.IH", DH)), ("PixelAspect", "Input { Value = { 1, 1 }, }"),
              ("TopLeftRed", "Input { Value = 0, }"), ("TopLeftGreen", "Input { Value = 0, }"),
              ("TopLeftBlue", "Input { Value = 0, }"), ("TopLeftAlpha", "Input { Value = 1, }")]
    tool("SZOutBG", "Background", out_bg, (990, -60))
    tool("SZOut", "Merge", [("Background", conn("SZOutBG")), ("Foreground", conn("SZOutPad")),
                            ("PerformDepthMerge", "Input { Value = 0, }")], (1100, 0))
    w("\t\t\t},")
    w("\t\t},")
    w("\t},")
    w(f'\tActiveTool = "{name}"')
    w("}")
    return "\n".join(L) + "\n"


def write_all(build_dir=BUILD, pathmap="Setting:"):
    table = json.load(open(os.path.join(build_dir, "slots.json")))
    out = {}
    out["SafeZones"] = build(table, "SafeZones", 0, pathmap)
    for stem, p in QUICK:
        out[stem] = build(table, stem, p, pathmap)
    for stem, txt in out.items():
        with open(os.path.join(build_dir, stem + ".setting"), "w", encoding="utf-8") as f:
            f.write(txt)
    return out


if __name__ == "__main__":
    o = write_all()
    print({k: len(v) for k, v in o.items()})
