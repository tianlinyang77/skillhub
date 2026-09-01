# Contribution templates

Templates are deliberately non-discoverable: every scaffold-only file uses a
`.template` suffix. Published packages reject any remaining `.template` file.

Copy `templates/skill/` to a product repository's `skills/<skill-name>/`,
rename the package files listed in `README.md.template`, delete that scaffold
README, replace every placeholder, and validate the installed directory in
isolation before requesting catalog admission.
