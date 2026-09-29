#!/usr/bin/env python3
"""Zip build/Edit/... into Giniroisenkou_Carousel_Slide.drfx (drag onto the Resolve window to install).
The Effects-panel thumbnail docs/Giniroisenkou_Carousel_Slide_thumbnail.png is copied in as Carousel_Slide.png."""
import os, shutil, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(ROOT, "build")
fx = os.path.join(src, "Edit", "Effects", "Carousel_Slide")
shutil.copy(os.path.join(ROOT, "docs", "Giniroisenkou_Carousel_Slide_thumbnail.png"),
            os.path.join(fx, "Carousel_Slide.png"))
dst = os.path.join(ROOT, "Giniroisenkou_Carousel_Slide.drfx")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
    for d, _, fs in os.walk(os.path.join(src, "Edit")):
        for f in sorted(fs):
            if f.endswith((".setting", ".png")):
                p = os.path.join(d, f)
                z.write(p, os.path.relpath(p, src).replace(os.sep, "/"))
print(dst)
