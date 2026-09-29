# Title_Sliding

A title that **slides side to side over a black band, with a thin line separating the title
from a subtitle**, the look of anime opening credits (song title and artist on a dark strip).
The same parts build **news lower thirds**: a tag box (LIVE, BREAKING), an accent bar and a
scrolling ticker.

## Effects (Edit page → Effects → Title_Sliding)

| Effect | Look |
|---|---|
| **Title_Sliding** | Anime opening strip: semi-transparent black band, white separator line, spaced bold title, grey subtitle. Slides in from the left, drifts slowly, leaves to the right. |
| **Title_Sliding_News** | TV lower third: navy band, red LIVE tag, red accent bar and line, white ticker strip underneath. |
| **Title_Sliding_Breaking** | Full-width red *BREAKING NEWS* bar, yellow line and tag, dark ticker. Comes in from the right. |
| **Title_Sliding_Cinema** | Centred film credit on a soft band, thin lines top and bottom, serif font, slow entrance. |

All four are the same effect with different starting values, so any of them can be turned
into any other look from the Inspector.

## Install

1. Drag **`Giniroisenkou_Title_Sliding.drfx`** onto the Resolve window, confirm, restart Resolve.
2. Edit page → **Effects → Title_Sliding**.

## Use

- Put an **Adjustment Clip** on the track above your footage and drop the effect on it
  (or drop it straight on a clip). The title animates in at the start of the clip and out at
  its end, so **trim the clip to set how long the title stays**.
- Type the title and subtitle in **Inspector → Effects**.

### Controls

| Group | Controls |
|---|---|
| Text | Title / Subtitle text, font + style, size (px), letter spacing, colour |
| Layout | Band height position, thickness, start X, length, title/subtitle split, alignment (left / centre / right), text margin, show subtitle |
| Background band | Colour, **opacity** (0 = only text + line) |
| Separator line | Position (between title & subtitle / top edge / bottom edge / top & bottom / none), **colour**, thickness, opacity, inset |
| Accent bar | Width (0 = off), position (rides the leading edge / left end / right end), colour |
| Animation | Direction (left → right / right → left), exit (keep going / go back / stay), easing (smooth / snappy / linear), start delay, exit at frame (0 = clip end), slide in / out length, line lead, text delay, text slide distance, **text drift** (the slow side-to-side movement while holding) |
| News tag box | Show, text, size, width, height, box colour, text colour |
| News ticker | Show, text, size, height, speed, restart interval, strip colour, text colour |

Sizes are in pixels at 1080 (short side), so the title looks the same on 1080×1920 and
1920×1080 timelines.

### Animation

The line shoots across first (**Line Leads By**), the band wipes in behind it, then the title
slides out from behind the band's edge (**Text Delay**, **Text Slide Distance**). While it holds,
the title keeps drifting slowly (**Text Drift**, px per frame; negative = the other way, 0 = still).
At the end of the clip everything leaves the other side (or goes back, or stays).

## Tips

- Long ticker text: raise **Ticker Restarts Every** so the text finishes before it loops.
- Title wider than the band: lower the title size or letter spacing, or make the band longer.
- For a 16:9 clip on a vertical timeline, use the Adjustment Clip route: the effect then runs at
  the timeline size.

## How it works

`src/Giniroisenkou_Title_Sliding_gen.py` writes the Fusion macros. One pass-through control node
(`TSCtrl`) holds every Inspector control and all the maths as hidden expressions: frame size
(`self.Input.OriginalWidth`), clip length (`comp.RenderEnd`), eased in/out progress and the
visible start/end of band, line and text. The drawing is done by small CustomTools
(anti-aliased rectangles for band, line, accent, tag and ticker) and Text+ nodes sized to the
input, each clipped to the band so words appear from behind its edge. Colours are native
colour pickers on tiny Background tools that are not in the image chain. Output is always the
same size as the input.

```
python src/Giniroisenkou_Title_Sliding_gen.py      # build/Edit/Effects/Title_Sliding/*.setting
python src/Giniroisenkou_Title_Sliding_thumbs.py   # thumbnails + docs from Resolve stills
python src/Giniroisenkou_Title_Sliding_package.py  # Giniroisenkou_Title_Sliding.drfx
```

Presets are the `PRESETS` table at the top of the generator; add a line there for a new look.

Tested on DaVinci Resolve Studio 21.1 (Windows), 1080×1920 timeline.
