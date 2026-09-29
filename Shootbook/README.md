# Shootbook

A stick-figure storyboard kit for planning vertical videos before you shoot, and for
blocking out the edit in DaVinci Resolve before the footage exists.

It has 140 frames in 9:16, each a named shot type: shot sizes, camera angles, composition, people in
frame, camera moves, dance, hiking, events, swing dancing with a live band, and transitions.
Each frame is a 1080 × 1920 PNG, so it fills a vertical timeline exactly.

![Shootbook](docs/Giniroisenkou_Shootbook_overview.png)

## What's inside

```
Shootbook/
  frames/                                 140 PNG frames, 1080 x 1920
  Giniroisenkou_Shootbook_shot_list.csv   every shot: code, category, name, note, context, file
  Giniroisenkou_Shootbook.html            the Shot Book page: browse, filter, build and copy a shot list
  src/
    Giniroisenkou_Shootbook_render_page.html   drawing code used for export
    Giniroisenkou_Shootbook_render.js          renders frames/ and the CSV
  docs/                                   preview image
  README.md
  DESCRIPTION.txt
```

Frames are named `Giniroisenkou_Shootbook_<CODE>_<Name>.png`, for example
`Giniroisenkou_Shootbook_SW-07_Swing-out.png`. The code and name are also printed in the top-left
corner, so you can read them on the timeline.

Colours in every frame:

| Colour | Means |
|---|---|
| Black | The subject: solid stick figures with no faces |
| Blue | Background and context: ground, mountains, stage, crowd |
| Orange | Movement of the camera or the subject |

Codes:

| Code | Category | Shots |
|---|---|---|
| SZ | Shot size | 12 |
| AN | Camera angle | 10 |
| CP | Composition | 13 |
| SB | People in frame | 12 |
| MV | Camera movement | 19 |
| DA | Dance | 16 |
| HK | Hiking | 16 |
| EV | Events | 16 |
| SW | Swing and live band | 18 |
| TR | Transitions | 8 |

## Using it in Resolve

1. Open `Giniroisenkou_Shootbook.html` in a browser, filter by context (Dance, Swing, Hiking,
   Events), add shots to your list with **+ List** and press **Copy list**.
2. Copy the matching PNGs from `frames/` into a new folder. Put `01_`, `02_`, `03_` … in front of the
   file names to set the order.
3. In Resolve, set how long each still lasts under **Preferences → User → Editing → Standard still duration**.
   2–3 seconds works for a rough cut; for a dance piece use one or two bars of the song.
4. Drag the folder into the Media Pool, sort by name, select all and press **Shift+F12**
   (Append to end of timeline).
5. As you shoot, drop each real clip on the track above its drawing. Any frame still showing is a
   shot you haven't got yet.

Use a 1080 × 1920 timeline so the frames fill the screen.

## Rebuilding the frames

The drawings are generated from code, so a change to a shot is made in
`src/Giniroisenkou_Shootbook_render_page.html` (and in `Giniroisenkou_Shootbook.html` so the page matches),
then re-exported:

```
cd src
npm i playwright
node Giniroisenkou_Shootbook_render.js
```

This rewrites `frames/` and `Giniroisenkou_Shootbook_shot_list.csv`.

## How it works

Each shot is a small function that draws into a 90 × 160 SVG. `fig()` draws a stick figure from a
named pose (stand, walk, jump, kick, spin, swing-out, dip and so on) at any position and scale.
Options add a hat, skirt, backpack, trumpet, sax, double bass or vintage mic. Line weight grows with
the figure's scale, so close-ups keep their weight. Background helpers draw ground, mountains, the sea,
houses, stages, spotlights, string lights and crowds. The page and the export share the same drawing code.
