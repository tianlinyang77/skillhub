# Contribution templates

Templates are deliberately non-discoverable: every scaffold-only file uses a
`.template` suffix. Published packages reject any remaining `.template` file.

Prefer `python3 scripts/new_skill.py --help`: it writes the final filenames,
fills deterministic identity fields, copies reviewed license material, and
builds the component registration. These templates remain the manual fallback.

For manual creation, copy `templates/skill/` to a product repository's
`skills/<skill-name>/`, rename the package files listed in
`README.md.template`, delete that scaffold README, replace every placeholder,
and validate the installed directory in isolation before requesting catalog
admission.
