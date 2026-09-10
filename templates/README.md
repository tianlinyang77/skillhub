# Contribution templates

Templates are deliberately non-discoverable: every scaffold-only file uses a
`.template` suffix. Published packages reject any remaining `.template` file.

Prefer `python3 scripts/contribute.py import <path>` when a skill package already
exists; it retains the package's portable resources and builds the local
registration. Use `contribute.py new <skill-name>` only when starting from
scratch: it prompts for local metadata, writes final filenames, and defaults
originals to root Apache-2.0. These templates remain the manual fallback.

For manual local creation, copy `templates/skill/` to this repository's
`skills/<skill-name>/`, rename the package files listed in
`README.md.template`, delete that scaffold README, replace every placeholder,
and validate the installed directory in isolation before requesting catalog
admission.

Generated cards default to `published`; no Validation section or eval form is
required. Preserve any existing legal notices. Remote scaffolding is an explicit
opt-in, not a prerequisite for contributing locally.
