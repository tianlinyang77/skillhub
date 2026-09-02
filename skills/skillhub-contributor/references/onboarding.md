# Skill onboarding reference

## Local-first scaffold

From the SkillHub checkout:

```bash
python3 scripts/new_skill.py example-skill \
  --local \
  --owner "Owning Team" \
  --description "Describe the capability, trigger, and nearest exclusion." \
  --license Apache-2.0 \
  --category "Developer Tools" \
  --with-openai \
  --with-references
```

Use `--dry-run` when reviewing destinations. The generated card remains
`staging`; replace every scaffold marker, add real evaluation prompts and
validation evidence, then set `published`. The generator writes directly to
`skills/<name>/` and appends the shared local registration.

## Local component semantics

The shared registration may omit `repo` and `ref`:

```yaml
name: SkillHub
local: true
description: Directly maintained HYGON-AI SkillHub skills.
skills:
  - path: skills/example-skill
    catalog_dir: example-skill
    category: Developer Tools
```

Validation normalizes the source to `HYGON-AI/skillhub@main`, requires the path
to equal `skills/<catalog_dir>`, and rejects a different declared repository.
Local skills do not receive lock entries and are edited directly in SkillHub.

## Optional remote component

Create a remote component only when the product team explicitly owns the source:

```yaml
name: Product display name
repo: HYGON-AI/product-repository
ref: main
description: One sentence describing the product and its skills.
skills:
  - path: skills/example-skill
    catalog_dir: product-example-skill
    category: Inference
```

Generate it with `--repo` and `--source-root`, merge the product repository
first, and then synchronize. Remote mirrors are read-only in SkillHub.

## Release checklist

- The owning team approved public release.
- `SKILL.md` uses only Agent Skills fields and has a bounded trigger description.
- The published directory is flat and self-contained.
- `skill-card.md` records owner, exact source, license, published lifecycle,
  permissions, and validation limits.
- `evals/evals.json` has at least three positive triggers, two negative triggers,
  and one positive behavioral assertion.
- Relative Markdown links resolve inside the package.
- Executable scripts contain no credentials and were tested on representative inputs.
- Required LICENSE and NOTICE material survives isolated installation.
- Catalog validation, generated metadata, reference validation, and both CLI
  discovery modes pass.
- Remote mode additionally proves ref, commit, digest, lock, and mirror agreement.

## Commands

```bash
python3 scripts/generate_catalog.py
python3 scripts/validate_skills.py
python3 scripts/validate_agent_skills_spec.py
python3 scripts/generate_catalog.py --check
npx --yes skills@1.5.23 add . --list
npx --yes skills@1.5.23 add . --list --full-depth
```

For an explicit remote component, additionally run
`python3 scripts/sync_sources.py --check --component <component>` before and
after applying synchronization.

## Common failures

- **Unregistered local directory**: rerun the scaffold or append it to the shared local component.
- **False local source**: remove the local `repo` field or set it to `HYGON-AI/skillhub`.
- **Name mismatch**: make the directory, `catalog_dir`, frontmatter name, eval identity, and UI invocation agree.
- **Catalog drift**: run `python3 scripts/generate_catalog.py` and commit every generated file.
- **Remote clone failure**: verify the explicit product repository and narrowly scoped read token.
- **Remote mirror overwritten**: change and merge the product source, then synchronize again.
