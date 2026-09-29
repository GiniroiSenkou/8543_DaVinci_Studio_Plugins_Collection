#!/usr/bin/env python3
"""
Giniroisenkou_TitleCards_package.py - zips build/Edit/Effects/TitleCards/*.setting
(and any .png thumbnails sitting alongside them) into Giniroisenkou_TitleCards.drfx,
next to this folder's README. Drag the .drfx onto DaVinci Resolve to install.
"""
import glob, os, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC_DIR = os.path.join(ROOT, "build", "Edit", "Effects", "TitleCards")
OUT = os.path.join(ROOT, "Giniroisenkou_TitleCards.drfx")


def main():
    files = sorted(glob.glob(os.path.join(SRC_DIR, "*.setting")) + glob.glob(os.path.join(SRC_DIR, "*.png")))
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, "Edit/Effects/TitleCards/" + os.path.basename(f))
    print("built", OUT, os.path.getsize(OUT) // 1024, "KB,", len(files), "files")


if __name__ == "__main__":
    main()
