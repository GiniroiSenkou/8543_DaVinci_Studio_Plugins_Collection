"""FakeUI - single source of truth for every template.

All geometry is in pixels on a 1080x1920 (9:16) design canvas, origin top-left.
The art PNGs (Giniroisenkou_FakeUI_art.py) and the Fusion macros
(Giniroisenkou_FakeUI_gen.py) are both generated from these tables, so moving a
field or a photo slot is a one-line change here.

TEXT fields
    key      internal name (Text+ node = "t" + key)
    label    name shown in the Resolve Inspector
    text     default text ("\n" = new line)
    x, y     anchor in px. y = line centre for va="center", top of the block for va="top"
    size     font size in px (cap height is ~0.7 of this)
    font     (family, style) - Windows fonts, DM Serif Display ships in fonts/
    align    left | center | right (x is the left edge / centre / right edge)
    va       center | top
    color    colour role (per template, see COLORS below)
    ls       line spacing (multi-line fields), cs = character spacing

SLOTS  (picture holes): key, label, (x, y, w, h), shape rect | circle
"""

W, H = 1080, 1920

UI = "Segoe UI"
TNR = "Times New Roman"
GEO = "Georgia"
ARIAL = "Arial"
DIDONE = "DM Serif Display"   # free OFL font, bundled in fonts/

# ==========================================================================
# SOCIAL PROFILE PAGE  (generic app look - no real brand logos or wordmarks)
# ==========================================================================
PROFILE_THEMES = {
    0: dict(name="Dark",  bg="#000000", fg="#F5F5F5", muted="#A8A8A8", btn="#262626",
            primary="#0095F6", onprimary="#FFFFFF", ring="#3A3A3A", line="#262626", link="#E0F1FF"),
    1: dict(name="Light", bg="#FFFFFF", fg="#000000", muted="#737373", btn="#EFEFEF",
            primary="#0095F6", onprimary="#FFFFFF", ring="#DBDBDB", line="#DBDBDB", link="#00376B"),
}
PROFILE_BUTTONS = {0: "Blue first button (visitor: Follow)", 1: "Grey buttons (own profile / Following)"}

HL_X = [123, 318, 513, 708, 903]
HL_Y, HL_D = 960, 144
GRID_Y0, CELL_W, CELL_H, GAP = 1202, 358, 477, 3
NAV_Y = 1770

PROFILE_SLOTS = [("avatar", "Avatar", (50, 230, 200, 200), "circle")]
for i, cx in enumerate(HL_X):
    PROFILE_SLOTS.append((f"hl{i+1}", f"Highlight {i+1}", (cx - HL_D // 2, HL_Y - HL_D // 2, HL_D, HL_D), "circle"))
for r in range(2):
    for c in range(3):
        n = r * 3 + c + 1
        PROFILE_SLOTS.append((f"post{n}", f"Post {n}", (c * (CELL_W + GAP), GRID_Y0 + r * (CELL_H + GAP), CELL_W, CELL_H), "rect"))

_B, _R = (UI, "Bold"), (UI, "Regular")
PROFILE_TEXT = [
    dict(key="Time",       label="Clock",           text="9:41",            x=60,  y=50,  size=34, font=_B, align="left",   va="center", color="fg"),
    dict(key="User",       label="Username",        text="yourname",        x=48,  y=142, size=46, font=_B, align="left",   va="center", color="fg"),
    dict(key="Posts",      label="Posts count",     text="128",             x=465, y=302, size=40, font=_B, align="center", va="center", color="fg"),
    dict(key="Followers",  label="Followers count", text="12.4K",           x=690, y=302, size=40, font=_B, align="center", va="center", color="fg"),
    dict(key="Following",  label="Following count", text="311",             x=915, y=302, size=40, font=_B, align="center", va="center", color="fg"),
    dict(key="LPosts",     label="Label 1",         text="posts",           x=465, y=356, size=30, font=_R, align="center", va="center", color="fg"),
    dict(key="LFollowers", label="Label 2",         text="followers",       x=690, y=356, size=30, font=_R, align="center", va="center", color="fg"),
    dict(key="LFollowing", label="Label 3",         text="following",       x=915, y=356, size=30, font=_R, align="center", va="center", color="fg"),
    dict(key="Name",       label="Display name",    text="Your Name",       x=48,  y=478, size=32, font=_B, align="left",   va="center", color="fg"),
    dict(key="Category",   label="Category",        text="Digital creator", x=48,  y=522, size=30, font=_R, align="left",   va="center", color="muted"),
    dict(key="Bio",        label="Bio (Enter = new line)",
         text="Coast, cameras and small stories\nHome → everywhere\nNew video every Friday",
         x=48, y=548, size=30, font=_R, align="left", va="top", color="fg", ls=1.3),
    dict(key="Link",       label="Link",            text="yourlink.com/yourname", x=92, y=700, size=30, font=_B, align="left", va="center", color="link"),
    dict(key="Btn1",       label="Button 1",        text="Follow",          x=264, y=798, size=30, font=_B, align="center", va="center", color="btn1"),
    dict(key="Btn2",       label="Button 2",        text="Message",         x=710, y=798, size=30, font=_B, align="center", va="center", color="fg"),
]
for i, (cx, t) in enumerate(zip(HL_X, ["Travel", "Food", "Reels", "Work", "Friends"])):
    PROFILE_TEXT.append(dict(key=f"HL{i+1}", label=f"Highlight {i+1} name", text=t,
                             x=cx, y=1068, size=26, font=_R, align="center", va="center", color="fg"))

# ==========================================================================
# ITALIAN DAILY FRONT PAGE  (in the style of a regional Italian quotidiano)
# ==========================================================================
NEWS_STYLES = {
    0: dict(name="Newsprint", paper="#F4F1EA", ink="#161616", accent="#C8102E", grain=8,  vignette=0.06),
    1: dict(name="White",     paper="#FFFFFF", ink="#111111", accent="#C8102E", grain=0,  vignette=0.0),
    2: dict(name="Vintage",   paper="#E6D8B8", ink="#2B2118", accent="#8E2A1C", grain=22, vignette=0.35),
}
M = 48
COLS = [(48, 360), (384, 696), (720, 1032)]   # three bottom columns (x0, x1)
NEWS_SLOTS = [
    ("main",  "Main photo",   (M, 812, W - 2 * M, 552), "rect"),
    ("t1",    "Teaser 1",     (M, 34, 150, 110), "rect"),
    ("t2",    "Teaser 2",     (560, 34, 150, 110), "rect"),
    ("col",   "Column photo", (720, 1446, 312, 200), "rect"),
    ("logo",  "Logo (put this clip ABOVE the page)", (M, 172, W - 2 * M, 124), "rect"),
]
LOGO_SLOTS = {"News": 4}

_A = (ARIAL, "Bold")
_AR = (ARIAL, "Regular")
_T = (TNR, "Bold")
_G = (GEO, "Regular")
_GI = (GEO, "Italic")
_ED = ("Il testo dell'editoriale va qui.\nPremi Invio per andare a capo:\nogni riga la decidi tu, come\nin una vera colonna di giornale.\nCirca trenta caratteri per riga\nfunzionano bene in questo\nspazio. Segue a pagina 3.")
NEWS_TEXT = [
    # top teasers
    dict(key="T1K", label="Teaser 1 kicker", text="SPORT",                         x=212, y=52,  size=20, font=_A,  align="left",  va="center", color="accent"),
    dict(key="T1",  label="Teaser 1 title",  text="Il derby si decide\nnel finale", x=212, y=68,  size=27, font=_T,  align="left",  va="top",    color="ink", ls=1.0),
    dict(key="T2K", label="Teaser 2 kicker", text="CULTURA",                       x=724, y=52,  size=20, font=_A,  align="left",  va="center", color="accent"),
    dict(key="T2",  label="Teaser 2 title",  text="La mostra che tutti\nvogliono vedere", x=724, y=68, size=27, font=_T, align="left", va="top", color="ink", ls=1.0),
    # masthead + folio
    dict(key="Mast", label="Masthead (newspaper name)", text="IL QUOTIDIANO", x=W // 2, y=236, size=112, font=_T, align="center", va="center", color="ink"),
    dict(key="FolL", label="Folio left",  text="QUOTIDIANO FONDATO NEL 1886",   x=M,     y=322, size=19, font=_AR, align="left",   va="center", color="ink"),
    dict(key="FolC", label="Date",        text="SABATO 26 SETTEMBRE 2026",      x=W // 2, y=322, size=21, font=_A, align="center", va="center", color="ink"),
    dict(key="FolR", label="Folio right", text="€ 1,80 · ANNO CXL · N. 228", x=W - M, y=322, size=19, font=_AR, align="right", va="center", color="ink"),
    # main story
    dict(key="Kick", label="Kicker (occhiello)", text="CITTÀ, IL CASO DEL GIORNO", x=M, y=392, size=30, font=_A, align="left", va="center", color="accent"),
    dict(key="Head", label="Headline",  text="Il titolo principale\nva scritto qui, grande\ne su tre righe", x=M, y=418, size=80, font=_T, align="left", va="top", color="ink", ls=0.98),
    dict(key="Somm", label="Summary (sommario)", text="Una o due righe che riassumono la notizia e\ninvitano a leggere l'articolo all'interno",
         x=M, y=700, size=31, font=_G, align="left", va="top", color="ink", ls=1.22),
    dict(key="Cap",    label="Photo caption", text="Didascalia della foto: chi, cosa, dove.", x=M, y=1388, size=22, font=_GI, align="left", va="center", color="ink"),
    dict(key="Credit", label="Photo credit",  text="FOTO: NOME COGNOME", x=W - M, y=1388, size=17, font=_AR, align="right", va="center", color="ink"),
    # column 1 - editorial
    dict(key="C1K", label="Column 1 kicker", text="L'EDITORIALE",  x=48, y=1446, size=21, font=_A, align="left", va="center", color="accent"),
    dict(key="C1A", label="Column 1 author", text="NOME COGNOME",  x=48, y=1474, size=19, font=_A, align="left", va="center", color="ink"),
    dict(key="C1T", label="Column 1 title",  text="Le parole che\nservono adesso", x=48, y=1494, size=31, font=_T, align="left", va="top", color="ink", ls=1.0),
    dict(key="C1B", label="Column 1 text (Enter = new line)", text=_ED, x=48, y=1574, size=21, font=_G, align="left", va="top", color="ink", ls=1.36),
    # column 2 - story
    dict(key="C2K", label="Column 2 kicker", text="CRONACA", x=384, y=1446, size=21, font=_A, align="left", va="center", color="accent"),
    dict(key="C2T", label="Column 2 title",  text="Il porto cambia\nvolto: ecco il\nnuovo progetto", x=384, y=1466, size=31, font=_T, align="left", va="top", color="ink", ls=1.0),
    dict(key="C2B", label="Column 2 text (Enter = new line)",
         text="Un secondo articolo trova\nspazio in questa colonna,\ncon il suo titolo in alto e\nil testo che scorre sotto.\nScrivi qui la notizia e\nvai a capo con Invio.\nSegue a pagina 7.",
         x=384, y=1580, size=21, font=_G, align="left", va="top", color="ink", ls=1.36),
    # column 3 - photo story
    dict(key="C3K", label="Column 3 kicker", text="SPETTACOLI", x=720, y=1668, size=21, font=_A, align="left", va="center", color="accent"),
    dict(key="C3T", label="Column 3 title",  text="Una serata da\nricordare in piazza", x=720, y=1688, size=31, font=_T, align="left", va="top", color="ink", ls=1.0),
    dict(key="C3B", label="Column 3 text (Enter = new line)", text="Poche righe per la terza\nnotizia, accanto alla foto.\nSegue a pagina 21.",
         x=720, y=1768, size=21, font=_G, align="left", va="top", color="ink", ls=1.36),
]
# static rules drawn on the paper: (x0, y0, x1, y1, colour role)
NEWS_RULES = [
    (M, 158, W - M, 160, "ink"),          # under teasers
    (538, 36, 540, 142, "ink"),           # teaser divider
    (M, 302, W - M, 306, "ink"),          # masthead rule
    (M, 340, W - M, 346, "accent"),       # red folio rule
    (M, 790, W - M, 791, "ink"),          # above photo
    (M, 1412, W - M, 1416, "ink"),        # under caption
    (371, 1432, 373, 1896, "ink"),        # column dividers
    (707, 1432, 709, 1896, "ink"),
]

# ==========================================================================
# FASHION MAGAZINE COVER  (in the style of a luxury fashion monthly)
# ==========================================================================
MAG_SLOTS = [("cover", "Cover photo", (0, 0, W, H), "rect")]
_D = (DIDONE, "Regular")
_DI = (DIDONE, "Italic")
_AB = (ARIAL, "Bold")
MAG_TEXT = [
    dict(key="Mast",  label="Masthead (magazine name)", text="MODE", x=W // 2, y=236, size=330, font=_D, align="center", va="center", color="mast", cs=1.0),
    dict(key="Issue", label="Issue line", text="ITALIA  ·  OTTOBRE 2026  ·  € 5", x=W // 2, y=428, size=22, font=_AB, align="center", va="center", color="text", cs=1.25),
    dict(key="L1",  label="Left line 1 (big)",   text="IL NUOVO\nCLASSICO",          x=60, y=640, size=64, font=_D, align="left", va="top", color="text", ls=0.95),
    dict(key="L1s", label="Left line 1 (small)", text="I capi che restano\nper sempre", x=60, y=790, size=30, font=_DI, align="left", va="top", color="text", ls=1.15),
    dict(key="L2",  label="Left line 2 (big)",   text="BEAUTY",                      x=60, y=960, size=40, font=_AB, align="left", va="top", color="accent", cs=1.2),
    dict(key="L2s", label="Left line 2 (small)", text="La luce che dura\ntutto il giorno", x=60, y=1016, size=30, font=_DI, align="left", va="top", color="text", ls=1.15),
    dict(key="R1",  label="Right line 1 (big)",  text="FASHION\nWEEK",               x=W - 60, y=640, size=64, font=_D, align="right", va="top", color="text", ls=0.95),
    dict(key="R1s", label="Right line 1 (small)", text="Milano, Parigi\ne la strada",  x=W - 60, y=790, size=30, font=_DI, align="right", va="top", color="text", ls=1.15),
    dict(key="R2",  label="Right line 2 (big)",  text="120",                         x=W - 60, y=940, size=86, font=_D, align="right", va="top", color="accent"),
    dict(key="R2s", label="Right line 2 (small)", text="look per\nl'autunno",         x=W - 60, y=1042, size=30, font=_DI, align="right", va="top", color="text", ls=1.15),
    dict(key="Name", label="Cover name",  text="GIULIA",                            x=W // 2, y=1560, size=190, font=_D, align="center", va="center", color="mast"),
    dict(key="Tag",  label="Cover line",  text="«L'amore, il lavoro e il prossimo capitolo»", x=W // 2, y=1700, size=36, font=_DI, align="center", va="center", color="text"),
]
MAG_COLORS = [  # colour pickers on the effect: (control prefix, label, default hex)
    ("Mast", "Masthead + name colour", "#FFFFFF"),
    ("Text", "Cover lines colour", "#FFFFFF"),
    ("Accent", "Accent colour", "#E4002B"),
]
BARCODE = (878, 1770, 1032, 1890)

SOURCE_ASPECTS = [("16:9", 16 / 9), ("9:16", 9 / 16), ("4:3", 4 / 3), ("3:4", 3 / 4),
                  ("1:1", 1.0), ("4:5", 4 / 5), ("3:2", 3 / 2), ("2:3", 2 / 3)]

TEMPLATES = {
    "Profile":  dict(slots=PROFILE_SLOTS, text=PROFILE_TEXT),
    "News":     dict(slots=NEWS_SLOTS, text=NEWS_TEXT),
    "Magazine": dict(slots=MAG_SLOTS, text=MAG_TEXT),
}
