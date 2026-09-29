#!/usr/bin/env python3
"""Zip build/Edit/... into Giniroisenkou_Grid.drfx (drag onto Resolve to install)."""
import os, zipfile, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
date = datetime.date.today().isoformat()
out = ROOT
dst = os.path.join(out, "Giniroisenkou_Grid.drfx")
src = os.path.join(ROOT, "build")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
    for d, _, fs in os.walk(src):
        for f in sorted(fs):
            p = os.path.join(d, f)
            z.write(p, os.path.relpath(p, src).replace(os.sep, "/"))
print(dst)
