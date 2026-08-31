# Contribution templates

Templates are deliberately non-discoverable: files that would otherwise be
named `SKILL.md`, `openai.yaml` or `evals.json` use a `.template` suffix.

Copy `templates/skill/` to a product repository's `skills/<skill-name>/`,
remove the `.template` suffixes, replace every placeholder, and validate the
installed directory in isolation before requesting catalog admission.
