#!/usr/bin/env python3
"""Zip build/Edit/... into Giniroisenkou_Title_Sliding.drfx (drag onto the Resolve window to install)."""
import os, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dst = os.path.join(ROOT, "Giniroisenkou_Title_Sliding.drfx")
src = os.path.join(ROOT, "build")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
    for d, _, fs in os.walk(os.path.join(src, "Edit")):
        for f in sorted(fs):
            if f.endswith((".setting", ".png")):
                p = os.path.join(d, f)
                z.write(p, os.path.relpath(p, src).replace(os.sep, "/"))
print(dst)
