---
name: skillhub-contributor
description: Create, review, and onboard portable Agent Skills into Hygon SkillHub. Use when adding a new SKILL.md, registering a HYGON-AI product repository in components.d, preparing a SkillHub contribution, or diagnosing catalog validation and synchronization failures.
---

# Contribute to Hygon SkillHub

Keep each product-owned skill in the product repository. Use this catalog as the publication and discovery layer, not as a second hand-edited source of truth.

## Prerequisite

Locate a checkout of the HYGON-AI SkillHub repository before running catalog
commands. If the checkout is absent, stop and give the user the reviewed clone
or repository-location step. Do not assume `scripts/*.py` exists in the target
product repository or inside this installed skill.

## Workflow

1. Confirm the owning team, source repository, license, and intended user prompts.
2. Create the skill at `skills/<skill-name>/` in the source repository. Use lowercase letters, digits, and hyphens for the directory and frontmatter `name`.
3. Start from the SkillHub `templates/skill/` scaffold. Add `skill-card.md`, `evals/evals.json`, and required license or NOTICE material.
4. Keep `SKILL.md` focused on procedures the agent cannot infer. Put detailed knowledge in `references/`, deterministic helpers in `scripts/`, and output material in `assets/`. Do not nest another `SKILL.md`.
5. Add or update one `components.d/<product>.yml` file in SkillHub. Map every source `path` to a globally unique `catalog_dir` and choose a category.
6. Run `python3 scripts/validate_skills.py` and `python3 scripts/generate_catalog.py --check` from the SkillHub root.
7. For a remote product source, preview synchronization with `python3 scripts/sync_sources.py --check --component <component-file-stem>`. Apply it only after reviewing the reported destinations.
8. Verify `npx skills add . --list` discovers only published skills.
9. Submit the source change first, then the SkillHub registration or sync change.

Read [onboarding.md](references/onboarding.md) for the component schema, release checklist, and troubleshooting commands.

## Guardrails

- Never place credentials, internal endpoints, customer data, or unpublished product information in a public skill.
- Never copy a skill from a private repository into a public catalog until the owning team has approved its public release.
- Do not edit mirrored files under `skills/` directly. Fix them in the source repository and synchronize again.
- Do not treat `staging/`, templates, CLI discovery, or a routing-only evaluation as published behavior evidence.
- Do not broaden tool permissions beyond what the skill workflow actually requires.
- Treat scripts as executable supply-chain content: review them, pin dependencies where practical, and test them before publication.
