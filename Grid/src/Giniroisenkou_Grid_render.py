#!/usr/bin/env python3
"""
Offline validator + preview renderer for Grid.

It evaluates the EXACT expression strings that gridgen.py writes into the
.setting (Ctrl simple expressions + CustomTool per-pixel expressions) with
numpy, on a synthetic test clip (no personal footage), and writes:
  build/Edit/Effects/Grid/<preset>.png   320x180 Effects-panel thumbnails
  docs/*.png                                README illustrations
"""
import os, re, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import Giniroisenkou_Grid_gen as G

ROOT = G.ROOT
DOCS = os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)


# ------------------------------------------------------------ test clip ---
def test_clip(W=1600, H=900):
    """16:9 synthetic clip: sky/sea gradient, sun, hills, and a 'person' + matte."""
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    sky = np.stack(np.broadcast_arrays(0.98 - 0.35 * y + 0 * x, 0.62 - 0.1 * y + 0 * x, 0.45 + 0.4 * y + 0 * x), -1)
    sky = np.broadcast_to(sky, (H, W, 3)).copy()
    img = Image.fromarray((np.clip(sky, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.ellipse([1150, 120, 1330, 300], fill=(255, 226, 120))
    d.polygon([(0, 640), (300, 520), (600, 610), (900, 500), (1250, 620), (1600, 540), (1600, 900), (0, 900)],
              fill=(40, 90, 120))
    d.rectangle([0, 760, 1600, 900], fill=(28, 60, 88))
    for i in range(0, 1600, 80):  # texture so tiling is readable
        d.line([(i, 760), (i + 40, 900)], fill=(36, 74, 104), width=6)
    # person (centre) + matte
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    for dr in (d, dm):
        col = (235, 80, 110) if dr is d else 255
        dr.ellipse([735, 250, 865, 380], fill=col)                     # head
        dr.rounded_rectangle([690, 370, 910, 900], 70, fill=col)        # body
    rgba = np.dstack([np.asarray(img) / 255.0, np.ones((H, W))])
    matte = np.asarray(m.filter(ImageFilter.GaussianBlur(2))) / 255.0
    return rgba, matte


# ----------------------------------------------------- expression engine ---
def fusion_simple_eval(expr, env):
    py = expr.replace("iif(", "_iif(")
    return eval(py, {"_iif": lambda c, a, b: a if c else b, "min": min, "max": max,
                     "floor": math.floor, "abs": abs}, env)


def ctrl_values(vals):
    env = dict(vals)
    env.setdefault("IW", 1600); env.setdefault("IH", 900)     # input size (16:9 test clip, Stretch)
    for name, expr in G.HIDDEN:
        if name in ("IW", "IH"):
            continue
        env[name] = fusion_simple_eval(expr, env)
    return env


def resize_like_fusion(rgba, w, h):
    out = []
    for c in range(4):
        im = Image.fromarray((rgba[..., c] * 65535).astype(np.uint16).astype(np.int32), "I")
        out.append(np.asarray(im.resize((w, h), Image.LANCZOS)).astype(np.float64) / 65535)
    return np.clip(np.dstack(out), 0, 1)


def sampler(img):
    """get??b(x,y): Fusion normalized coords (y up), bilinear, black outside."""
    H, W = img.shape[:2]

    def get(ch):
        plane = img[..., ch] if img.ndim == 3 else img

        def f(u, v):
            u = np.asarray(u, float) * np.ones(1)
            v = np.asarray(v, float) * np.ones(1)
            px = u * W - 0.5
            py = (1 - v) * H - 0.5
            x0 = np.floor(px).astype(int); y0 = np.floor(py).astype(int)
            fx = px - x0; fy = py - y0
            acc = 0
            for dx, dy, wt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                               (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
                xi = x0 + dx; yi = y0 + dy
                ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
                acc = acc + wt * np.where(ok, plane[np.clip(yi, 0, H - 1), np.clip(xi, 0, W - 1)], 0.0)
            return acc
        return f
    return get


def run_custom(ctrl, src, matte, bg_rgb, bg_a, hold_center):
    W, H = int(ctrl["FW"]), int(ctrl["FH"])
    ys, xs = np.mgrid[0:H, 0:W]
    x = (xs + 0.5) / W
    y = 1 - (ys + 0.5) / H
    s2 = sampler(src)
    s3 = sampler(np.dstack([matte, matte, matte, matte])) if matte is not None else None

    def z(u, v): return np.zeros(np.broadcast(u, v).shape)
    fn = {"floor": np.floor, "min": np.minimum, "max": np.maximum, "abs": np.abs, "sqrt": np.sqrt,
          "pow": lambda a, b: np.power(float(a), np.asarray(b, float)), "exp": np.exp}
    for i, ch in enumerate("rgba"):
        fn[f"get{ch}2b"] = s2(i)
        fn[f"get{ch}3b"] = s3(i) if s3 else z
    env = dict(fn)
    env.update(x=x, y=y, w=W, h=H)
    # numbers / points from Ctrl values (same expressions, GRCtrl. prefix stripped)
    def ce(e): return fusion_simple_eval(e.replace("GRCtrl.", ""), dict(ctrl))
    for i, e in G.NUMBERS.items():
        env[f"n{i}"] = ce(e)
        assert abs(env[f"n{i}"]) <= G.NUMBER_LIMIT, f"n{i} = {env[f'n{i}']} would be clamped by Resolve"
    Point = lambda a, b: (a, b)
    for i, e in G.POINTS.items():
        px, py = eval(e.replace("GRCtrl.", "").replace("iif(", "_iif("),
                      {"Point": Point, "_iif": lambda c, a, b: a if c else b}, dict(ctrl))
        env[f"p{i}x"], env[f"p{i}y"] = px, py
    env["r1"], env["g1"], env["b1"] = [bg_rgb[i] * bg_a for i in range(3)]
    env["a1"] = bg_a
    def ev(e):
        assert "pow(" not in e and "exp(" not in e, "pow()/exp() do not work in Resolve's CustomTool"
        return eval(e.replace("^", "**"), env)          # Fusion ^ = power
    for i, e in G.SETUP.items():
        env[f"s{i}"] = ev(e)
    for i, e in G.INTER.items():
        env[f"i{i}"] = ev(e)                  # intermediates see the earlier ones (as in Fusion)
    out = [ev(G.CHANNELS[k]) for k in
           ("RedExpression", "GreenExpression", "BlueExpression", "AlphaExpression")]
    return np.dstack([np.broadcast_to(o, (H, W)) for o in out])


def render(preset_overrides, src, matte, scale=0.4, matte_on=False):
    vals = {cid: d for cid, k, _, d, _, _ in G.VISIBLE if k not in ("label", "ticks")}
    vals.update({k: v for k, v in preset_overrides.items() if k in vals})
    ctrl = ctrl_values(vals)
    # preview at reduced size: scale frame; px controls scale via UNIT automatically
    vals2 = dict(vals, FramePreset=len(G.FRAME_PRESETS) - 1,
                 FrameWidth=round(ctrl["FW"] * scale), FrameHeight=round(ctrl["FH"] * scale))
    ctrl = ctrl_values(vals2)
    dw, dh = max(int(ctrl["DW"] + .5), 1), max(int(ctrl["DH"] + .5), 1)
    rs = resize_like_fusion(src, dw, dh)
    rm = np.asarray(Image.fromarray((matte * 255).astype(np.uint8)).resize((dw, dh), Image.LANCZOS)) / 255.0
    gap = (vals["GapShade"],) * 3
    bga = vals["GapOpacity"] if vals["Mode"] == 0 else 0
    return run_custom(ctrl, rs, rm if matte_on else None, gap, bga, None)


def to_img(rgba, checker=True):
    H, W = rgba.shape[:2]
    if checker:
        yy, xx = np.mgrid[0:H, 0:W]
        c = np.where(((xx // 12) + (yy // 12)) % 2, 0.23, 0.30)[..., None] * np.ones(3)
    else:
        c = np.zeros((H, W, 3))
    rgb = rgba[..., :3] + c * (1 - rgba[..., 3:4])
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def thumb(frame_img, label, path):
    T = Image.new("RGB", (320, 180), (18, 18, 22))
    f = frame_img.copy()
    f.thumbnail((150, 170))
    T.paste(f, (12, (180 - f.height) // 2))
    d = ImageDraw.Draw(T)
    words = label.split("\n")
    yy = 40
    for i, wd in enumerate(words):
        d.text((178, yy), wd, fill=(255, 255, 255) if i == 0 else (170, 170, 180), font=font(18 if i == 0 else 13))
        yy += 28 if i == 0 else 20
    T.save(path)


def number_overlay(img, cols, rows, margin_px, gap_px):
    """draw cell numbers (doc image only)"""
    d = ImageDraw.Draw(img)
    W, H = img.size
    cw = (W - 2 * margin_px - (cols - 1) * gap_px) / cols
    ch = (H - 2 * margin_px - (rows - 1) * gap_px) / rows
    for r in range(rows):
        for c in range(cols):
            cx = margin_px + c * (cw + gap_px) + cw / 2
            cy = margin_px + r * (ch + gap_px) + ch / 2
            t = str(r * cols + c + 1)
            d.text((cx - 8, cy - 12), t, fill=(255, 255, 255), font=font(22), stroke_width=3, stroke_fill=(0, 0, 0))
    return img


def main():
    src, matte = test_clip()

    labels = {
        "Grid": "Grid\nvideo in cells\npick what shows",
        "Grid_One_Cell": "One Cell\nonly cell 5\nrest transparent",
        "Grid_Picked_Checker": "Picked Cells\ntick boxes\n(checker)",
        "Grid_Reveal_Box_By_Box": "Reveal\ncells 1 to N\nkeyframe N",
        "Grid_Tiles_Gaps": "Tiles + Gaps\nsee-through\ngaps, rounded",
        "Grid_Single_Cell_Fit": "Single Cell\nwhole video\nin one cell",
        "Grid_Tiles_White_Gaps": "Tiles 4x6\nwhite gaps,\nrounded",
        "Grid_Hidden_Black": "Hidden Black\nhidden cells +\nlines black",
    }
    for name, d in G.PRESETS.items():
        im = to_img(render(d, src, matte, scale=0.25))
        thumb(im, labels[name], os.path.join(G.OUT_DIR, name + ".png"))

    # --- docs: what the modes look like (checker = transparent, the track below shows there)
    s = 0.3
    shots = [
        ("All cells + Guide", render({"Show": 0, "Guide": 1}, src, matte, s)),
        ("One cell (5)", render({"Show": 1, "Cell": 5}, src, matte, s)),
        ("Picked cells", render(dict(G.PICK_CORNERS, Show=2), src, matte, s)),
        ("Cells 1 to 5", render({"Show": 3, "RevealN": 5}, src, matte, s)),
        ("Hidden = black", render(dict(G.PICK_CORNERS, Show=2, TileGap=6, GapFill=1, HiddenFill=1), src, matte, s)),
        ("Gaps, 4x6", render({"Show": 0, "Columns": 4, "Rows": 6, "TileGap": 12, "Margin": 12, "Radius": 14},
                             src, matte, s)),
        ("Single Cell fit", render({"Mode": 1, "Cell": 1, "TileGap": 12, "Margin": 12}, src, matte, s)),
    ]
    tiles = [to_img(r) for _, r in shots]
    tw, th = tiles[0].size
    sheet = Image.new("RGB", (len(tiles) * (tw + 16) + 16, th + 60), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    for i, (t, (lab, _)) in enumerate(zip(tiles, shots)):
        sheet.paste(t, (16 + i * (tw + 16), 46))
        d.text((16 + i * (tw + 16), 14), lab, fill=(255, 255, 255), font=font(18))
    sheet.save(os.path.join(DOCS, "Giniroisenkou_Grid_modes.png"))

    # --- docs: cell numbering
    im = to_img(render({"Show": 0, "Guide": 1}, src, matte, 0.3))
    number_overlay(im, 3, 3, 0, 0).save(os.path.join(DOCS, "Giniroisenkou_Grid_cell_numbers_3x3.png"))
    im = to_img(render({"Show": 0, "Guide": 1, "Columns": 4, "Rows": 5}, src, matte, 0.3))
    number_overlay(im, 4, 5, 0, 0).save(os.path.join(DOCS, "Giniroisenkou_Grid_cell_numbers_4x5.png"))

    # --- self-checks on the math -------------------------------------
    allc = render({"Show": 0}, src, matte, 0.25)
    H, W = allc.shape[:2]
    assert allc[..., 3].min() > 0.999, "All cells, no gap: video covers the frame, no seams"

    def cell_alpha(img, c, r, cols=3, rows=3):
        h, w = img.shape[:2]
        return img[int((r + .3) * h / rows):int((r + .7) * h / rows), int((c + .3) * w / cols):int((c + .7) * w / cols), 3]

    one = render({"Show": 1, "Cell": 5}, src, matte, 0.25)
    assert cell_alpha(one, 1, 1).min() > 0.99 and cell_alpha(one, 0, 0).max() < 0.01, "one cell"
    assert np.allclose(one[..., :3][one[..., 3] > 0.99], allc[..., :3][one[..., 3] > 0.99]), "cell shows video in place"
    pk = render(dict(G.PICK_CORNERS, Show=2), src, matte, 0.25)
    for k in range(9):
        a = cell_alpha(pk, k % 3, k // 3)
        want = 0 if (k + 1) in (2, 4, 6, 8) else 1
        assert (a.min() > 0.99) if want else (a.max() < 0.01), f"picked cell {k+1}"
    big = {f"T{k}": 0 for k in range(1, 82)}; big.update(T47=1, T81=1)     # bits in the 2nd number
    pb = render(dict(big, Show=2, Columns=9, Rows=9), src, matte, 0.25)
    assert cell_alpha(pb, 1, 5, 9, 9).min() > 0.99 and cell_alpha(pb, 8, 8, 9, 9).min() > 0.99, "ticks 47, 81"
    assert cell_alpha(pb, 0, 5, 9, 9).max() < 0.01 and cell_alpha(pb, 0, 0, 9, 9).max() < 0.01, "unticked"
    rv = render({"Show": 3, "RevealN": 4}, src, matte, 0.25)
    assert cell_alpha(rv, 0, 1).min() > 0.99 and cell_alpha(rv, 1, 1).max() < 0.01, "reveal 1..4"
    gd = render({"Show": 1, "Cell": 1, "Guide": 1}, src, matte, 0.25)
    assert 0.2 < cell_alpha(gd, 2, 2).mean() < 0.4, "guide dims hidden cells"
    cell = render({"Mode": 1, "Cell": 9, "TileGap": 12, "Margin": 12}, src, matte, 0.25)
    assert cell[: H // 2, : W // 2, 3].max() < 0.01 and cell[int(H*0.8):int(H*0.95), int(W*0.75):int(W*0.95), 3].min() > 0.99, "cell 9 bottom-right"
    gp = render({"Show": 0, "TileGap": 20}, src, matte, 0.25)
    assert (gp[..., 3] < 0.01).mean() > 0.02, "gaps are see-through"
    hb = render(dict(G.PICK_CORNERS, Show=2, TileGap=8, GapFill=1, HiddenFill=1), src, matte, 0.25)
    a = cell_alpha(hb, 1, 0)                                   # hidden cell 2 -> solid black
    assert a.min() > 0.99 and hb[int(.1*H):int(.2*H), int(.45*W):int(.55*W), :3].max() < 0.01, "hidden = black"
    gl = hb[int(.1*H):int(.2*H), :, 3].min()                   # black lines between cells are solid
    assert gl > 0.99, "filled gaps are opaque"
    ht = render(dict(G.PICK_CORNERS, Show=2, TileGap=8, GapFill=1, HiddenFill=0), src, matte, 0.25)
    assert cell_alpha(ht, 1, 0).max() < 0.01, "hidden transparent while gaps filled"
    wg = render({"Show": 0, "TileGap": 20, "GapFill": 1, "GapShade": 1}, src, matte, 0.25)
    assert wg[..., :3][wg[..., 3] > 0.99].max() > 0.99, "white gaps"
    print("self-checks OK")


if __name__ == "__main__":
    main()
