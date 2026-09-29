#!/usr/bin/env python3
"""Zip build/Edit/... into Giniroisenkou_MangaPanels.drfx (drag onto the Resolve window to install)."""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dst = os.path.join(ROOT, "Giniroisenkou_MangaPanels.drfx")
src = os.path.join(ROOT, "build")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
    for d, _, fs in os.walk(src):
        for f in sorted(fs):
            p = os.path.join(d, f)
            z.write(p, os.path.relpath(p, src).replace(os.sep, "/"))
print(dst)
