#!/usr/bin/env python3
"""
Makes the neutral test clip used for the Trends previews (no personal footage):
the CC0 "chelsea" cat photo from scikit-image, a slow push-in / pan, and a pink
light that moves across the frame so trails, stutter and echo are visible.

Needs: scikit-image, Pillow, numpy, ffmpeg on PATH.
Usage: python Giniroisenkou_Trends_sampleclip.py  -> sample_clip.mp4 (1280x720, 60 frames, 30 fps)
"""
import math, os, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from skimage import data

W, H, N = 1280, 720, 60
cat = Image.fromarray(data.chelsea())          # 451x300, CC0
tmp = tempfile.mkdtemp()
for f in range(N):
    t = f / (N - 1)
    z = 1.0 + 0.12 * t
    cw, ch = 451 / z, 451 / z * 9 / 16
    cx = 225.5 + (451 - cw) / 2 * 0.9 * t
    cy = 150 - (300 - ch) / 2 * 0.3 * t
    fr = cat.resize((W, H), Image.LANCZOS, box=(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)).convert("RGB")
    orb = Image.new("RGB", (W, H)); d = ImageDraw.Draw(orb)
    ox, oy = int(120 + 1040 * t), int(560 - 300 * math.sin(math.pi * t))
    for r, c in [(70, (255, 60, 160)), (40, (255, 140, 220)), (18, (255, 255, 255))]:
        d.ellipse((ox - r, oy - r, ox + r, oy + r), fill=c)
    orb = orb.filter(ImageFilter.GaussianBlur(10))
    a, o = np.asarray(fr, float), np.asarray(orb, float)
    Image.fromarray((255 - (255 - a) * (255 - o) / 255).clip(0, 255).astype(np.uint8)).save(os.path.join(tmp, f"f{f:03d}.png"))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", os.path.join(tmp, "f%03d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "14", "sample_clip.mp4"], check=True)
print("sample_clip.mp4")
