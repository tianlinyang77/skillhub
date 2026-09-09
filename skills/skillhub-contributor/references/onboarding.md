# Skill onboarding reference

## Scaffold command

From the SkillHub checkout, create a local directory and registration together:

```bash
python3 scripts/contribute.py new example-skill --with-references
```

Review with `--dry-run` when paths are uncertain. Cards default to `published`;
this does not bypass content review or authorize submission. Complete scaffold
content and review runtime requirements and permissions. For an existing package, use
`python3 scripts/contribute.py import ../existing-skill` instead of scaffolding
over it. With `--with-references`, the generated `SKILL.md` links to the new
`references/details.md` scaffold so contributors can state when detailed
material should be loaded.

Original local contributions default to root Apache-2.0, without license or
source-URL prompts. Preserve existing licenses, notices and authored attribution.
Import preserves existing runtime text unless explicitly overridden with
`--runtime-permissions`. Otherwise supply it at the prompt, or use a reference
to `SKILL.md` when that file already explains the requirements. Category selection
is explicit, not automatic inference. No Validation section or eval form is required.

## Component schema

The local helper updates the shared `components.d/skillhub.yml`; review its new
list entry without replacing existing registrations. Its schema is:

```yaml
name: skillhub
local: true
description: One sentence describing the component and its skills.
skills:
  - path: skills/example-skill
    catalog_dir: example-skill
    category: Inference
```

`repo` may be omitted and normalizes to `HYGON-AI/skillhub`; any other value is
rejected, and `path` must equal `skills/<catalog_dir>`.

A remote component in `components.d/<slug>.yml` is the explicit opt-in for a
skill maintained by an upstream repository:

```yaml
name: Product display name
repo: example-owner/product-repository
ref: main
description: One sentence describing the product and its skills.
skills:
  - path: skills/example-skill
    catalog_dir: example-skill
    category: Inference
```

Remote components are cloned from GitHub during synchronization and carry a
`.skillhub-lock.json` entry with the resolved commit and tree digest. Local
skills carry neither.

For a catalog-owned prototype, begin with
`staging/<skill-name>/SKILL.md.candidate`. Never use a real `SKILL.md` below
`staging/`; deep discovery can install it before review. During promotion, move
the candidate into `skills/<skill-name>/`, rename the entrypoint to `SKILL.md`,
add its local component registration, and include the required Skill Card and
applicable licensing material. This prototype path is optional for local skills.

Each `catalog_dir` must be unique across the catalog and equal the skill
frontmatter `name`; there is no compatibility-alias exception.

## Release checklist

- The owning team approved public release.
- `SKILL.md` uses only the six Agent Skills fields; `metadata` keys and values
  are strings and client/catalog fields do not leak into portable frontmatter.
- The description says both what the skill does and when it should trigger.
- The published directory is flat and contains no nested `SKILL.md`.
- `skill-card.md` uses schema version 1 and binds owner, component source,
  license and published lifecycle.
- Runtime requirements and permissions have nonempty text or a `SKILL.md`
  reference. Existing real validation notes are preserved, not required as a form.
- Relative Markdown links in `SKILL.md`, `skill-card.md`, and references resolve inside the skill directory.
- Scripts contain no embedded credentials. Review them and test representative
  inputs when applicable; catalog checks do not execute their workflows.
- Original local contributions use root Apache-2.0 by default; existing source
  declarations and required LICENSE/NOTICE material are preserved. A per-skill
  duplicate of the root LICENSE is not required.
- For remote components only, `repo`, `ref` and source path are correct. A branch
  or tag can move; the lock records the resolved commit and source digest.
- Local validation and catalog generation checks pass.
- PR checks finish successfully and maintainers approve. GitHub enforcement
  additionally needs configured runners and branch protection.

## Commands

```bash
python3 scripts/contribute.py check
# Remote synchronization is opt-in and separate from the local contribution flow.
python3 scripts/sync_sources.py --check --component product-slug
python3 scripts/sync_sources.py --component product-slug
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
- **Existing destination**: edit the imported copy and run `contribute.py check`;
  `import` does not overwrite or update it. Preserve local changes before retrying.
- **Empty component skill list**: inspect the registry diff and restore accidentally
  removed registrations; do not replace the shared component with an empty list.
- **Legacy card placeholders**: import removes only recognized old Validation and
  origin placeholders. Other unfinished content must be completed; real notes stay.
- **Missing Git identity**: configure your own name/email before committing.
  A failed commit leaves nothing new to push or use as a PR head.
- **Name mismatch**: make `skills/<directory>` and frontmatter `name` identical.
- **Catalog drift**: run `python3 scripts/generate_catalog.py` and commit all generated files.
- **Private clone failure**: grant the synchronization token read access to the product repository without placing the token in a URL.
- **Mirrored edit overwritten**: make the change in the source repository, merge it there, then synchronize again.
