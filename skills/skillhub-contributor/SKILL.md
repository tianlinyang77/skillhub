---
name: skillhub-contributor
description: Create, review, and onboard portable Agent Skills into Hygon SkillHub. Use when adding a new SKILL.md to the catalog, registering a local or remote component in components.d, preparing a SkillHub contribution, or diagnosing catalog validation and synchronization failures.
license: Apache-2.0
compatibility: Requires a SkillHub checkout, Python 3.11+, Git, Node.js/npm (CI uses Node 22), and requirements-dev.txt dependencies. Dependency setup, CLI discovery and opt-in remote checks may require network access.
metadata:
  author: HYGON-AI
  version: "1.3.0"
---

# Contribute to Hygon SkillHub

A skill is local by default: it lives in this catalog and ships in one pull
request. Mirroring from any GitHub repository is an explicit opt-in for maintained
upstream skills; preserve their original authorship and licenses. Never hand-edit a
mirrored skill.

## Prerequisite

Locate a checkout of the HYGON-AI SkillHub repository before running catalog
commands. If the checkout is absent, stop and give the user the reviewed clone
or repository-location step. Do not assume `scripts/*.py` exists in a target
product repository or inside this installed skill.

## Choose the mode first

- **Local (default).** The skill has no owning product repository, or the team
  is content to maintain it here. Register with `local: true`; `repo` may be
  omitted and normalizes to `HYGON-AI/skillhub`. The source path must equal
  `skills/<catalog_dir>`.
- **Remote (opt-in).** A maintained skill is sourced from any GitHub
  repository. Register `repo` and `ref`, and let synchronization mirror it.

## Workflow

1. Confirm the owning team, mode, category and intended user prompts. Original local contributions default to root Apache-2.0 without a license prompt or duplicate LICENSE; preserve existing declarations and legal notices.
2. When a local skill directory already exists, run `python3 scripts/contribute.py import <path>` from the SkillHub checkout; it copies the package without changing or executing the source. Record the team maintaining the SkillHub copy when prompted for owner; preserve any different source author or owner as attribution. Only when no package exists, run `python3 scripts/contribute.py new <name>` to scaffold one. Generated cards default to `published`, which is metadata, not review approval or permission to submit. Use `scripts/new_skill.py --repo` only for ongoing remote synchronization.
3. Use lowercase letters, digits, and hyphens for the directory and frontmatter `name`, and keep the name globally descriptive.
4. Keep `SKILL.md` focused on procedures the agent cannot infer. Put detailed knowledge in `references/`, deterministic helpers in `scripts/`, and output material in `assets/`. Do not nest another `SKILL.md`.
5. Complete scaffold content and review runtime requirements and permissions. Import reuses an existing authored runtime section unless `--runtime-permissions` overrides it; otherwise it prompts or links to `SKILL.md`. No Validation section or eval dataset is required. Preserve real validation notes and attribution; cleanup removes only recognized old template placeholders.
6. Review the generated `components.d/skillhub.yml` change. The helper registers a local package under its globally unique `catalog_dir` and chosen allowlisted category; do not hand-edit generated catalog files.
7. Run `python3 scripts/contribute.py check` from the SkillHub root. It regenerates catalog files and runs unit, policy, specification, provenance and normal/full-depth discovery checks without submitting Git changes.
8. For a remote component only, apply synchronization separately after reviewing destinations, then rerun `contribute.py check`. Remote provenance must prove the ref, resolved commit, source digest, lock entry and published tree agree.
9. A catalog-owned staging entrypoint must remain `SKILL.md.candidate` until promotion.
10. Review the diff and, when the user authorizes submission, use ordinary Git to submit one signed-off pull request. A local skill lands in one PR; a synchronized remote skill also needs one SkillHub PR containing registration, mirror and lock. Require completed Quality Gate, catalog validation, DCO and maintainer review before merge; queued jobs are not passes.

Read [onboarding.md](references/onboarding.md) for the component schema, release checklist, and troubleshooting commands.

## Guardrails

- Never place credentials, internal endpoints, customer data, or unpublished product information in a public skill.
- Never copy a skill from a private repository into a public catalog until the owning team has approved its public release.
- Do not edit mirrored files under `skills/` directly. Fix them in the source repository and synchronize again.
- Do not claim remote provenance for a local skill. It has no lock entry or content digest; protected branches and required reviews/checks are effective only when administrators configure them.
- Do not treat `staging/`, templates, CLI discovery, or a routing-only evaluation as published behavior evidence.
- Do not broaden tool permissions beyond what the skill workflow actually requires.
- Treat scripts as executable supply-chain content: review them, pin dependencies where practical, and test them before publication.
