# Carousel_Slide

A DaVinci Resolve **Edit-page effect** (Fusion macro) for the "Crsel" collage-slideshow look:
videos, photos and cut-out stickers scroll together through a rounded panel, and
stickers or people can spill over the tile edges.

![Parameters](docs/Giniroisenkou_Carousel_Slide_parameters.png)

## Install

1. Drag **`Giniroisenkou_Carousel_Slide.drfx`** onto the Resolve window, confirm, restart Resolve.
2. Edit page → **Effects → Carousel_Slide**.

## How it works

Put each video, photo or cut-out on **its own track**, all starting on the **same frame** and with the same length.
Drop Carousel_Slide on **every** clip. Each clip gets a *box* on one long strip, and the strip slides through the *panel*.
Anything that leaves the panel is cut off.

- **Same on every clip:** Frame Preset, Panel, Direction, Motion, Speed, Loop, Timeline FPS.
  Set up one clip, then right-click → Copy, and Paste Attributes onto the rest.
- **Per clip:** Mode, Layout, Slot or Strip X/Y, Box Width/Height, Clip FPS.

## Inspector

The controls are grouped in 6 collapsible sections, each with a short explanation at the top,
and every control has a hover tooltip.

| Section | What's in it |
|---|---|
| 1 Start here | **Frame Preset**, Mode, Layout, Slot |
| 2 Box | where this clip sits in the row, its size, corners, rotation |
| 3 Movement | direction, continuous or step, speed, loop (same on every clip) |
| 4 Panel | the rounded window: offset from the centre, size, corners, overhang (same on every clip) |
| 5 Picture | zoom and reframe inside the box |
| 6 Frame rate | Timeline FPS, Clip FPS |

### Frame Preset

Pick your timeline format. It overrides Frame Width/Height, which are only used with **Custom**.

| Preset | Size |
|---|---|
| 9:16 Reels / TikTok / Shorts (default) | 1080 × 1920 |
| 4:5 Instagram portrait post | 1080 × 1350 |
| 1:1 Instagram square post | 1080 × 1080 |
| 3:4 portrait | 1080 × 1440 |
| 4:3 landscape | 1440 × 1080 |
| 16:9 YouTube HD | 1920 × 1080 |
| 16:9 UHD 4K | 3840 × 2160 |
| 9:16 UHD 4K vertical | 2160 × 3840 |
| Custom | Frame Width × Frame Height |

The panel is placed **relative to the centre of the frame** (Panel Offset X/Y, 0 = centred),
so switching preset keeps it in view. All px values are px of the chosen frame.

## Layout

- **Slot (equal tiles):** Slot 1, 2, 3… side by side, each one Box Width wide, plus Gap.
- **Custom position:** Strip X / Strip Y give the top-left of the box on the strip
  (0,0 = the panel's top-left at the start). Boxes can be any size and can touch.

Example: a 4:3 slideshow with a sticker taped over the join between slide 1 and 2 (default panel 1000 × 750).

| Clip | Mode | Layout | Position | Box | Other |
|---|---|---|---|---|---|
| Video 1 | Tile | Slot | Slot 1 | 1000 × 750 | |
| Video 2 | Tile | Slot | Slot 2 | 1000 × 750 | |
| Video 3 | Tile | Slot | Slot 3 | 1000 × 750 | Loop on, Slot Count 3 |
| Sticker (top track) | Sticker | Custom | X 800, Y 125 | 400 × 500 | Rotation −8, **Loop Length 3000**, **Step Distance 1000** |

To centre a sticker on the join between slide *n* and *n+1*: Strip X = n × Box Width − sticker width / 2.

## Modes

- **Tile:** fills its box (cover-fit) and is clipped to the box and the panel.
- **Pop-out:** a copy of a clip on a track **above** everything, with the same box as the original and the person cut out.
  Only the panel (grown by Overhang) clips it, so the person steps over the tile edge.
- **Sticker:** a PNG or cut-out that fits inside its box. It can rotate, sit across a join, and ride the strip.

### Cutting a person out (Pop-out / Sticker from video)

On the Fusion page, put a **MatteControl** between `MediaIn1` and `Carousel_Slide` (MediaIn1 → Background).
Add a **Magic Mask** (or a Polygon) on the person, connect it to **Garbage Matte**, and tick **Invert**.
For photos, just use a transparent PNG.

## Things to know

- Motion starts on each clip's first frame, so all clips must start together. Fix a late clip with Start Offset.
- **Clip FPS:** Resolve counts a clip's time in its *own* frames, so a 30 fps clip on a 24 fps timeline
  scrolls faster and drifts unless Clip FPS is set to 30.
- **Stickers and Custom boxes in Step mode:** set Step Distance to the slide width.
  Also set Loop Length to the whole row (slide width × number of slides).
- 4K stacks render slowly. Use proxies or Optimized Media while editing.

## How it works

`src/Giniroisenkou_Carousel_Slide_gen.py` writes the Fusion macro. One pass-through control node
(`CJCtrl`) holds every Inspector control and all the maths as hidden expressions: frame preset,
box position on the strip, eased step / continuous travel, loop wrap, panel mask, cover/contain fit and
the Clip FPS time correction. A clip-level Fusion comp runs at the *source* resolution, so the macro
builds its own canvas (BetterResize → Crop) at the chosen frame size, moves the picture into its box
(Transform), and cuts it with two rounded RectangleMasks multiplied together (box × panel).

```
python src/Giniroisenkou_Carousel_Slide_gen.py      # build/Edit/Effects/Carousel_Slide/Carousel_Slide.setting
python src/Giniroisenkou_Carousel_Slide_package.py  # Giniroisenkou_Carousel_Slide.drfx (+ Effects-panel thumbnail)
```

Frame presets are the `FRAME_PRESETS` table at the top of the generator; add a line there for a new size.

Tested on DaVinci Resolve Studio 21.1 (Windows), 1920×1080 timeline with 4K 30 fps clips and a photo.
