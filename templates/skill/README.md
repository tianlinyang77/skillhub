# Skill scaffold

This directory is a contribution scaffold, not an installable skill.

Required before publication:

- rename `SKILL.md.template` to `SKILL.md`;
- rename and complete `skill-card.md.template`;
- rename `evals/evals.json.template` to `evals/evals.json`;
- optionally rename `agents/openai.yaml.template` when OpenAI UI metadata is
  provided;
- add `LICENSE` and `NOTICE` when the installed directory would otherwise lose
  required attribution (`LICENSE` is mandatory for publication);
- delete this scaffold README from the final skill package.

Keep only the six Agent Skills frontmatter fields. Optional catalog-specific
values belong in `metadata` as strings or in validated repository sidecars;
never add top-level `version`, `tags`, `tools`, `permissions`, or
`when_to_use` fields.
