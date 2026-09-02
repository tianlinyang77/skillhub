"""Render the HYGON SkillHub README banner as an animated trace timeline.

The banner is a profiler-style timeline. Blocks are the eleven enforced catalog
categories -- the stable public surface -- and a playhead sweeps left to right
lighting each one as it is reached. Skill names are deliberately absent so the
banner does not go stale as skills are admitted.

Rendered at 2x and downsampled so text and hairlines stay crisp.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
S = 2  # supersample factor
W, H = 1200, 384

FONTS = Path("C:/Windows/Fonts")
F_DISPLAY = FONTS / "bahnschrift.ttf"
F_MONO = FONTS / "consola.ttf"
F_MONO_B = FONTS / "consolab.ttf"

INK = (7, 11, 20)
LANE_A = (11, 16, 28)
LANE_B = (9, 13, 23)
GRID = (22, 32, 58)
RULE = (34, 46, 76)
TXT = (232, 237, 247)
TXT_FAINT = (62, 76, 107)
PLAY = (87, 224, 255)
HYGON_RED = (232, 56, 79)

# The eleven enforced catalog categories, in taxonomy.md order:
#   (lane, name, cap, fill_cold, fill_hot)
# Adding a category is a reviewed governance change, so this list is stable in
# a way skill names are not. Fills stay dark and only the 3px leading cap
# carries hue, which keeps eleven colours reading as an instrument legend
# rather than a rainbow.
CATEGORIES = [
    (0, "Governance and Compliance", (150, 126, 232), (20, 18, 30), (35, 29, 58)),
    (0, "Developer Tools", (124, 142, 236), (17, 19, 31), (29, 33, 60)),
    (0, "HCU Platform", (52, 196, 190), (13, 24, 26), (13, 45, 45)),
    (1, "Operator Development", (235, 72, 92), (26, 16, 22), (53, 20, 27)),
    (1, "Performance and Profiling", (238, 166, 58), (26, 21, 13), (52, 36, 13)),
    (2, "Accuracy and Debugging", (238, 122, 84), (27, 18, 15), (53, 29, 19)),
    (2, "Training", (104, 198, 124), (15, 24, 18), (19, 45, 24)),
    (2, "Inference", (72, 190, 226), (13, 22, 28), (14, 40, 50)),
    (3, "Distributed Systems", (100, 162, 216), (15, 20, 28), (20, 36, 52)),
    (3, "CI and Release", (178, 192, 88), (22, 24, 13), (40, 45, 16)),
    (3, "Documentation", (146, 160, 186), (19, 21, 25), (35, 37, 45)),
]

N_LANES = 4
LABEL_PAD_CH = 6  # extra character-widths of breathing room per block
GAP = 8           # px between blocks

CMD = "npx skills add HYGON-AI/skillhub"
FOOT = "every skill ships a skill-card and evals"

N_FRAMES = 76
SWEEP_A, SWEEP_B = 4, 56
TYPE_A, TYPE_B = 42, 68

# Geometry in 1x space. No gutter: the lane identity now lives in the blocks.
PAD = 34
HEAD_H = 76
FOOT_H = 62
TRACK_X0 = PAD
TRACK_X1 = W - PAD
TRACK_Y0 = HEAD_H + 26
TRACK_Y1 = H - FOOT_H - 18
LANE_H = (TRACK_Y1 - TRACK_Y0) / N_LANES
SPAN = TRACK_X1 - TRACK_X0


def font(path, size):
    return ImageFont.truetype(str(path), size * S)


def display_font(size, weight="Bold"):
    """Bahnschrift is variable (Weight 300-700); pick the instance explicitly.

    Without this it renders at the Regular default, which is too light to
    anchor the wordmark against the trace below it.
    """
    f = ImageFont.truetype(str(F_DISPLAY), size * S)
    try:
        f.set_variation_by_name(weight)
    except (OSError, AttributeError):
        pass
    return f


def px(v):
    return int(round(v * S))


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def layout():
    """Place each category so every lane tiles the full span.

    Width tracks label length, so long category names always have room and no
    lane trails off into dead space on the right.
    """
    placed = []
    for li in range(N_LANES):
        row = [c for c in CATEGORIES if c[0] == li]
        weights = [len(c[1]) + LABEL_PAD_CH for c in row]
        total = float(sum(weights))
        usable = SPAN - GAP * (len(row) - 1)
        x = TRACK_X0
        for c, wt in zip(row, weights):
            w = usable * wt / total
            placed.append((li, x, x + w, c[1], c[2], c[3], c[4]))
            x += w + GAP
    return placed


PLACED = layout()


def draw_frame(i):
    im = Image.new("RGB", (W * S, H * S), INK)
    d = ImageDraw.Draw(im)

    f_title = display_font(32)
    f_tag = font(F_MONO, 12)
    f_blk = font(F_MONO_B, 13)
    f_cmd = font(F_MONO_B, 15)
    f_hint = font(F_MONO, 11)

    intro = ease(i / 9.0)

    # Header ------------------------------------------------------------
    d.text((px(PAD), px(24)), "HYGON", font=f_title, fill=mix(INK, TXT, intro))
    tw = d.textlength("HYGON", font=f_title)
    d.text((px(PAD) + tw + px(9), px(24)), "SkillHub", font=f_title,
           fill=mix(INK, HYGON_RED, intro))

    tag = "agent skills for HCU  ::  one flat catalog, governed categories"
    d.text((px(PAD), px(58)), tag, font=f_tag, fill=mix(INK, TXT_FAINT, intro))

    d.line([(px(PAD), px(HEAD_H + 8)), (px(W - PAD), px(HEAD_H + 8))],
           fill=mix(INK, RULE, intro), width=S)

    # Ruler ticks -------------------------------------------------------
    for k in range(49):
        x = TRACK_X0 + SPAN * k / 48.0
        tall = (k % 6 == 0)
        y0 = TRACK_Y0 - (10 if tall else 5)
        c = mix(INK, RULE if tall else GRID, intro)
        d.line([(px(x), px(y0)), (px(x), px(TRACK_Y0 - 1))], fill=c, width=S)

    # Lane bands --------------------------------------------------------
    for li in range(N_LANES):
        y0 = TRACK_Y0 + LANE_H * li
        y1 = y0 + LANE_H
        d.rectangle([px(TRACK_X0), px(y0), px(TRACK_X1), px(y1 - 2)],
                    fill=mix(INK, LANE_A if li % 2 == 0 else LANE_B, intro))
        d.line([(px(TRACK_X0), px(y1 - 1)), (px(TRACK_X1), px(y1 - 1))],
               fill=mix(INK, GRID, intro), width=S)

    # Playhead position -------------------------------------------------
    sweep = ease((i - SWEEP_A) / float(SWEEP_B - SWEEP_A))
    head_x = TRACK_X0 + SPAN * sweep

    # Category blocks ---------------------------------------------------
    for li, bx0, bx1, label, cap, cold, hot in PLACED:
        y0 = TRACK_Y0 + LANE_H * li + 6
        y1 = TRACK_Y0 + LANE_H * (li + 1) - 8

        lit = ease((head_x - bx0) / (SPAN * 0.05))
        body = mix(cold, hot, lit)
        if intro < 1:
            body = mix(INK, body, intro)
        d.rectangle([px(bx0), px(y0), px(bx1), px(y1)], fill=body)

        cap_c = mix(mix(cold, cap, 0.45), cap, lit)
        if intro < 1:
            cap_c = mix(INK, cap_c, intro)
        d.rectangle([px(bx0), px(y0), px(bx0 + 3), px(y1)], fill=cap_c)

        lab = mix((78, 88, 108), (243, 246, 252), lit)
        if intro < 1:
            lab = mix(INK, lab, intro)
        d.text((px(bx0 + 12), px(y0 + (y1 - y0) / 2 - 8)), label,
               font=f_blk, fill=lab)

    # Playhead ----------------------------------------------------------
    if 0 < sweep < 1:
        for w, a in ((5, 0.10), (3, 0.20), (1, 1.0)):
            d.line([(px(head_x), px(TRACK_Y0 - 12)), (px(head_x), px(TRACK_Y1))],
                   fill=mix(INK, PLAY, a), width=px(w))
        d.polygon([
            (px(head_x - 5), px(TRACK_Y0 - 18)),
            (px(head_x + 5), px(TRACK_Y0 - 18)),
            (px(head_x), px(TRACK_Y0 - 11)),
        ], fill=PLAY)

    # Command bar -------------------------------------------------------
    cy = H - FOOT_H + 6
    d.line([(px(PAD), px(cy - 12)), (px(W - PAD), px(cy - 12))],
           fill=mix(INK, RULE, intro), width=S)

    d.text((px(PAD), px(cy + 6)), "$", font=f_cmd,
           fill=mix(INK, HYGON_RED, intro))

    n = len(CMD)
    shown = int(round(n * ease((i - TYPE_A) / float(TYPE_B - TYPE_A))))
    typed = CMD[:shown]
    d.text((px(PAD + 18), px(cy + 6)), typed, font=f_cmd, fill=TXT)

    if i >= TYPE_A and (i // 5) % 2 == 0:
        cw = d.textlength(typed, font=f_cmd)
        d.rectangle([px(PAD + 20) + cw, px(cy + 5),
                     px(PAD + 27) + cw, px(cy + 21)], fill=PLAY)

    if shown >= n:
        hw = d.textlength(FOOT, font=f_hint)
        d.text((px(W - PAD) - hw, px(cy + 9)), FOOT, font=f_hint, fill=TXT_FAINT)

    return im.resize((W, H), Image.LANCZOS)


def main():
    frames = [draw_frame(i) for i in range(N_FRAMES)]

    # One shared palette off the busiest frame keeps colours stable across the
    # loop. disposal=1 leaves earlier pixels in place, which lets Pillow's
    # optimiser store only the changed rectangle per frame -- the static ruler
    # and lane bands are then paid for once.
    master = frames[N_FRAMES - 1].quantize(colors=128, method=Image.MEDIANCUT)
    pal = [f.quantize(palette=master, dither=Image.Dither.NONE) for f in frames]

    out = OUT / "banner.gif"
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=55,
                loop=0, optimize=True, disposal=1)
    frames[N_FRAMES - 1].save(OUT / "banner.png")
    print("wrote", out, out.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
