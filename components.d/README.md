# Component registry

Each YAML file registers one product repository. Product teams change only their own file, which avoids a shared manifest conflict. Registered repositories must be owned by [`HYGON-AI`](https://github.com/HYGON-AI); unchanged third-party or upstream skills are not eligible for publication as HYGON-AI skills.

Required fields are `name`, `repo`, `description`, and a non-empty `skills` list. Each skill needs `path`, globally unique `catalog_dir`, and `category`. `ref` defaults to `main`; `local` defaults to `false`. A repository can be registered by exactly one component, and every skill in that component is synchronized from the same ref. Multiple refs for one repository and skill-level ref overrides are not supported.

`category` groups the skill in the generated README index and in `skills.sh.json`. It must exactly match an allowlisted value in [`docs/governance/taxonomy.md`](../docs/governance/taxonomy.md); adding a category is a reviewed governance change.

Use a globally descriptive `catalog_dir`. A `<product>-<action>` name is the
default for product-specific workflows, not a universal prefix requirement.
Ambiguous bare names such as `profile`, `benchmark`, and `deploy` are rejected.

Remote entries are mirrored by `scripts/sync_sources.py`. Local entries are validated in place and are never cloned.

Registration does not by itself grant published status. Every destination
under `skills/` must also satisfy the flat per-skill layout, ownership,
licensing, self-containment, `skill-card.md`, and `evals/evals.json` contracts
described in [`docs/governance/admission.md`](../docs/governance/admission.md).

Start new component files from
[`templates/component.yml.template`](../templates/component.yml.template).
