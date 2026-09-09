# Contribution templates

Templates are deliberately non-discoverable: every scaffold-only file uses a
`.template` suffix. Published packages reject any remaining `.template` file.

Prefer `python3 scripts/contribute.py new <skill-name>`: it prompts for normal
local metadata, writes final filenames, defaults originals to root Apache-2.0, and
builds the component registration. Use `contribute.py import <path>` for an
existing package. These templates remain the manual fallback.

For manual local creation, copy `templates/skill/` to this repository's
`skills/<skill-name>/`, rename the package files listed in
`README.md.template`, delete that scaffold README, replace every placeholder,
and validate the installed directory in isolation before requesting catalog
admission.

Generated cards default to `published`; no Validation section or eval form is
required. Preserve any existing legal notices. Remote scaffolding is an explicit
opt-in, not a prerequisite for contributing locally.
