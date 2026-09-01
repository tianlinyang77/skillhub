# Skill onboarding reference

## Scaffold command

From the SkillHub checkout, generate the product-owned directory and component
registration together:

```bash
python3 scripts/new_skill.py example-skill \
  --source-root ../product-repository \
  --repo HYGON-AI/product-repository \
  --owner "Product Team" \
  --description "Describe the capability and when it should trigger." \
  --license Apache-2.0 \
  --category Inference \
  --with-references
```

Review with `--dry-run` when paths or repository checkouts are uncertain. The
generated card deliberately remains `staging`; complete every `TODO`, replace
the Eval prompts with real routing boundaries, and set `published` only after
the evidence is ready. Commit and merge the product repository first. The
component change remains local in SkillHub until the source ref contains the
reviewed Skill.

## Component schema

Create `components.d/<slug>.yml`:

```yaml
name: Product display name
repo: HYGON-AI/product-repository
ref: main
description: One sentence describing the product and its skills.
skills:
  - path: skills/example-skill
    catalog_dir: example-skill
    category: Inference
```

Use `local: true` only for a skill whose source of truth is the SkillHub repository itself. Remote components are cloned from GitHub during synchronization.

For a catalog-owned prototype, begin with
`staging/<skill-name>/SKILL.md.candidate`. Never use a real `SKILL.md` below
`staging/`; deep discovery can install it before review. During promotion, move
the candidate into `skills/<skill-name>/`, rename the entrypoint to `SKILL.md`,
add its local component registration, and add the same Skill Card, Eval and
license evidence required from product-owned skills.

Each `catalog_dir` must be unique across the catalog. Keep it equal to the skill frontmatter `name` unless a temporary compatibility alias is unavoidable.

## Release checklist

- The owning team approved public release.
- `SKILL.md` uses only the six Agent Skills fields; `metadata` keys and values
  are strings and client/catalog fields do not leak into portable frontmatter.
- The description says both what the skill does and when it should trigger.
- The published directory is flat and contains no nested `SKILL.md`.
- `skill-card.md` uses schema version 1 and binds owner, component source,
  license and published lifecycle.
- `evals/evals.json` uses schema version 1, names the Skill, and contains at
  least three positive triggers, two negative triggers, and one behavior assertion.
- Relative Markdown links in `SKILL.md`, `skill-card.md`, and references resolve inside the skill directory.
- Scripts contain no embedded credentials and have been executed on a representative input.
- The source repository has an explicit compatible license.
- Required LICENSE and NOTICE material remains available after isolated installation.
- The component registry points to an immutable release branch or the team's maintained default branch.
- Local validation and catalog generation checks pass.

## Commands

```bash
python3 scripts/validate_skills.py
python3 scripts/validate_agent_skills_spec.py
python3 scripts/generate_catalog.py
python3 scripts/generate_catalog.py --check
python3 scripts/sync_sources.py --check --component product-slug
python3 scripts/sync_sources.py --component product-slug
npx --yes skills@1.5.23 add . --list
npx --yes skills@1.5.23 add . --list --full-depth
```

After publication, verify discovery without installing:

```bash
npx skills add HYGON-AI/skillhub --list
```

Install one skill non-interactively:

```bash
npx skills add HYGON-AI/skillhub --skill example-skill --yes
```

## Common failures

- **Unregistered directory**: add the skill to exactly one component file or remove the orphaned catalog directory.
- **Name mismatch**: make `skills/<directory>` and frontmatter `name` identical.
- **Catalog drift**: run `python3 scripts/generate_catalog.py` and commit all generated files.
- **Private clone failure**: grant the synchronization token read access to the product repository without placing the token in a URL.
- **Mirrored edit overwritten**: make the change in the source repository, merge it there, then synchronize again.
