#!/usr/bin/env python3
"""
Giniroisenkou_FakeUI_build.py - one command: art -> macros -> thumbnails -> previews -> .drfx

    python src/Giniroisenkou_FakeUI_build.py

Writes Giniroisenkou_FakeUI.drfx next to this folder's README. Inside it, Edit/Effects/FakeUI/
holds the six effects, their Effects-panel thumbnails and every art PNG (referenced as
Setting:<file>). Needs Python 3 with Pillow and NumPy.
"""
import glob
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import Giniroisenkou_FakeUI_art as A  # noqa: E402
import Giniroisenkou_FakeUI_gen as G  # noqa: E402

PFX = "Giniroisenkou_FakeUI"


def main():
    build = os.path.join(ROOT, "build")
    docs = os.path.join(ROOT, "docs")
    shutil.rmtree(build, ignore_errors=True)
    os.makedirs(build)
    os.makedirs(docs, exist_ok=True)
    A.build_art(build)
    G.write_all(build)
    A.build_docs_and_thumbs(build, docs)
    drfx = os.path.join(ROOT, PFX + ".drfx")
    with zipfile.ZipFile(drfx, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(build, "*.setting")) + glob.glob(os.path.join(build, "*.png"))):
            z.write(f, "Edit/Effects/FakeUI/" + os.path.basename(f))
    print("built", drfx, os.path.getsize(drfx) // 1024, "KB")
    return drfx


if __name__ == "__main__":
    main()
