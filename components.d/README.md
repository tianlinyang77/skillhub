# Component registry

Each YAML file registers one component: either skills owned by this repository
(the default) or skills mirrored from one HYGON-AI product repository. One file
per team avoids a shared manifest conflict.

Required fields are `name`, `description`, and a non-empty `skills` list. Each
skill needs `path`, a globally unique `catalog_dir`, and `category`.

## Local component (default)

Set `local: true`. `repo` may be omitted and normalizes to
`HYGON-AI/skillhub`; any other value is rejected. Each skill's `path` must
equal `skills/<catalog_dir>` exactly:

```yaml
name: SkillHub
local: true
description: Author, validate, onboard, and publish portable Agent Skills across HYGON-AI projects.
skills:
  - path: skills/skillhub-contributor
    catalog_dir: skillhub-contributor
    category: Developer Tools
```

Local entries are validated in place, are never cloned, and have no
`.skillhub-lock.json` entry or content digest.

## Remote component (explicit opt-in)

Omit `local` (or set it to `false`) and provide `repo`, which must be owned by
[`HYGON-AI`](https://github.com/HYGON-AI). `ref` defaults to `main`. A remote
repository can be registered by exactly one component, and every skill in that
component is synchronized from the same ref; multiple refs for one repository
and skill-level ref overrides are not supported.

Remote entries are mirrored by `scripts/sync_sources.py`. Unchanged
third-party or upstream skills are not eligible for publication as HYGON-AI
skills. Start from
[`templates/component.yml.template`](../templates/component.yml.template),
which is the optional remote form.

## Naming and categories

`category` groups the skill in the generated README index and in
`skills.sh.json`. It must exactly match an allowlisted value in
[`docs/governance/taxonomy.md`](../docs/governance/taxonomy.md); adding a
category is a reviewed governance change.

Use a globally descriptive `catalog_dir`. A `<product>-<action>` name is the
default for product-specific workflows, not a universal prefix requirement.
Ambiguous bare names such as `profile`, `benchmark`, and `deploy` are rejected.

Registration does not by itself grant published status. Every destination
under `skills/` must also satisfy the flat per-skill layout, ownership,
licensing, self-containment, `skill-card.md`, and `evals/evals.json` contracts
described in [`docs/governance/admission.md`](../docs/governance/admission.md).
