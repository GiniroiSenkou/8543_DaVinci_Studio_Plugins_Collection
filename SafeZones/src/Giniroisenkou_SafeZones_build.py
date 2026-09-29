#!/usr/bin/env python3
"""
Giniroisenkou_SafeZones_build.py - one command: overlays -> macros -> thumbnails -> previews -> .drfx

    python src/Giniroisenkou_SafeZones_fetch_tools.py    (once: icons, font, SVG renderer into _tools/)
    python src/Giniroisenkou_SafeZones_build.py

Writes Giniroisenkou_SafeZones.drfx next to this folder's README. Inside it, Edit/Effects/SafeZones/ holds
the master effect, one quick effect per platform, their Effects-panel thumbnails and every overlay PNG
(referenced as Setting:<file>).
"""
import glob, json, os, shutil, sys, zipfile
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import Giniroisenkou_SafeZones_gen as G
import Giniroisenkou_SafeZones_macro as M
import Giniroisenkou_SafeZones_preview as PV
import Giniroisenkou_SafeZones_thumbs as T

PFX = "Giniroisenkou_SafeZones"


def upload_sheet(build, table, frame, out):
    """IG Reel full-screen + feed for each upload shape: the cut, never a squeeze."""
    shapes = [("Same as timeline (9:16)", None), ("4:5 portrait", .8), ("1:1 square", 1.0), ("16:9 horizontal", 16 / 9)]
    st = {s["view"]: s for s in table["states"] if s["platform"] == 0}
    tw_, th, pad = 270, 480, 16
    im = Image.new("RGB", (pad + 8 * (tw_ + pad), 110 + th + pad), (18, 18, 20))
    d = ImageDraw.Draw(im)
    d.text((pad, 24), "Upload shape - everything outside the shape is cut, then shown the way the app shows it",
           font=PV.F(30, True), fill=(240, 240, 240))
    for i, (lab, asp) in enumerate(shapes):
        for j, v in enumerate((0, 1)):
            x = pad + (i * 2 + j) * (tw_ + pad)
            d.text((x, 76), lab if j == 0 else "  in the feed", font=PV.F(19, True), fill=(190, 190, 195))
            c = PV.compose(build, st[v], "dark", frame, upload=asp).convert("RGB")
            im.paste(c.resize((tw_, th), Image.LANCZOS), (x, 110))
    im.save(out, optimize=True)


def main():
    build = os.path.join(ROOT, "build")
    docs = os.path.join(ROOT, "docs")
    shutil.rmtree(build, ignore_errors=True)
    os.makedirs(docs, exist_ok=True)
    G.build_all(build)
    M.write_all(build)
    T.write_thumbs(build)
    table = json.load(open(os.path.join(build, "slots.json")))
    frame = PV.test_frame()
    PV.contact(build, table, frame, "dark", False, os.path.join(docs, PFX + "_all_dark.png"))
    PV.contact(build, table, frame, "light", False, os.path.join(docs, PFX + "_all_light.png"))
    PV.contact(build, table, frame, "dark", True, os.path.join(docs, PFX + "_all_guides.png"))
    upload_sheet(build, table, frame, os.path.join(docs, PFX + "_upload_shapes.png"))
    T.strips(build, docs)
    T.thumb_sheet(build, os.path.join(docs, PFX + "_thumbnails.png"))
    drfx = os.path.join(ROOT, PFX + ".drfx")
    with zipfile.ZipFile(drfx, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(build, "*.setting")) + glob.glob(os.path.join(build, "*.png"))):
            z.write(f, "Edit/Effects/SafeZones/" + os.path.basename(f))
    print("built", drfx, os.path.getsize(drfx) // 1024, "KB")
    return drfx


if __name__ == "__main__":
    main()
