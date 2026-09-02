# Repository assets

README media for the catalog itself. Nothing here is skill content and nothing
here is installed by the `skills` CLI.

`banner.gif` is generated, not hand-edited. It is a profiler-style trace whose
blocks are the eleven enforced catalog categories from
[`docs/governance/taxonomy.md`](../docs/governance/taxonomy.md). Skill names are
deliberately absent so the banner does not go stale as skills are admitted.

Regenerate it after a taxonomy change:

```bash
python3 assets/build_banner.py
```

The script keeps its category list in sync with `ALLOWED_CATEGORIES` in
[`scripts/skillhub.py`](../scripts/skillhub.py). Update both together, and
record the change in `CHANGELOG.md` as the taxonomy contract requires.

The build reads system-installed fonts (Bahnschrift, Consolas) and writes
`banner.gif` plus a static `banner.png` first frame.

## Resolution

The design is authored in a 1200x384 logical space but exported at 2x
(2400x768) via `OUT_SCALE`, and the README requests `width="1200"`. GitHub's
README column is roughly 1012px, so a 1:1 export would be resampled down by a
fractional factor and small labels would smear. Exporting at 2x keeps the
source dense enough to stay legible after that downscale and on HiDPI
displays. Keep `OUT_SCALE` at 2 or higher if the type scale changes.
