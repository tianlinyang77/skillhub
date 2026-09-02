---
name: skillhub-contributor
description: Create, review, and onboard portable Agent Skills into HYGON-AI SkillHub. Use when adding or updating a SkillHub package, preparing its metadata and evaluations, or diagnosing catalog validation; use remote synchronization only when a product team explicitly owns the source skill in another HYGON-AI repository.
license: Apache-2.0
compatibility: Requires Python 3.11+ and Git; network access is needed only for optional remote synchronization and CLI reference checks.
metadata:
  author: HYGON-AI
  version: "1.2.0"
---

# Contribute to HYGON-AI SkillHub

Maintain new skills directly in SkillHub by default. Use one repository and one
pull request unless a product team explicitly chooses to keep its skill beside
the product code.

## Prerequisite

Locate a SkillHub checkout before running repository scripts. If it is absent,
stop and provide the reviewed clone or repository-location step. An installed
copy of this skill does not contain the root `scripts/*.py` tools.

## Default local workflow

1. Confirm the skill name, owning team, category, license, intended user prompts,
   nearest non-triggering cases, runtime permissions, and validation boundary.
2. Run `python3 scripts/new_skill.py <name> --local ...` from the SkillHub root.
   Omitting both `--local` and `--repo` also selects local mode. The generator
   creates `skills/<name>/`, copies license material, and updates the shared
   local component registration.
3. Complete `SKILL.md`, `skill-card.md`, and `evals/evals.json`. Replace every
   scaffold marker, set the reviewed lifecycle to `published`, and keep the
   package self-contained. Put long procedures in `references/`, deterministic
   helpers in `scripts/`, and output material in `assets/`.
4. Run catalog generation, structural validation, Agent Skills reference
   validation, generated-file checks, and pinned normal/full-depth CLI discovery.
   Local contributors do not run synchronization; CI skips local components.
5. Review the complete diff and submit one SkillHub pull request with DCO
   sign-off and the owning team as reviewer.

## Optional remote workflow

Use `--repo HYGON-AI/<product> --source-root <checkout>` only when the product
team explicitly commits to maintaining the source skill. Merge the product
repository first, then synchronize the reviewed component into SkillHub. The
sync check must prove the ref, resolved commit, source digest, lock entry, and
published tree agree. Never edit a remote mirror directly.

Read [onboarding.md](references/onboarding.md) for command examples, component
semantics, the release checklist, and common failures.

## Guardrails

- Never include credentials, internal endpoints, customer data, or unpublished product information.
- Do not copy a private or unchanged third-party skill into the public catalog.
- Do not treat staging, templates, CLI discovery, or routing-only evaluations as behavior proof.
- Do not broaden tool permissions beyond the declared workflow.
- Review executable scripts as supply-chain content and test them on representative inputs.
- Apply remote mirror rules only to explicitly remote components; local skills are maintained directly here.
