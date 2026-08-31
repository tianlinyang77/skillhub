# Contributing

Hygon SkillHub is a publication catalog. Product teams own their source skills so documentation and product changes evolve together.

## Repository lifecycle

- Product-owned candidates remain in their HYGON-AI product repository until admission.
- Catalog-owned prototypes may use `staging/<skill-name>/`; staging content is never published or indexed.
- Only direct children of `skills/` are published catalog identities.
- Generated mirrors, catalog files, lock files and plugin bundles are never repaired by hand.

Start from [`templates/skill/`](templates/skill) and read the
[repository layout](docs/architecture/repository-layout.md),
[admission policy](docs/governance/admission.md), and
[evaluation contract](docs/evaluation/README.md). Reuse the stable categories
in the [catalog taxonomy](docs/governance/taxonomy.md).

## Publication boundary

SkillHub publishes skills whose source-of-truth repository is owned by the [`HYGON-AI` GitHub organization](https://github.com/HYGON-AI). Organization ownership alone is not sufficient: each published skill must be either HYGON-authored or substantively adapted and validated for HCU, with a HYGON team responsible for ongoing maintenance.

Do not register or mirror an unchanged third-party or upstream skill as a HYGON-AI skill. Link to the canonical upstream skill instead, then request catalog admission after the product team has added and tested the HCU-specific workflow. Preserve all applicable third-party copyright, license, and NOTICE material in an adapted skill.

## Add a product-owned skill

1. Add a portable `skills/<skill-name>/SKILL.md` directory to the product repository.
2. Add `skill-card.md`, `evals/evals.json`, required license and NOTICE material, and any self-contained resources.
3. Confirm the owning team approved public release and the source license permits redistribution.
4. Add `components.d/<product>.yml` here. Use one file per product team; do not edit another team's registry file.
5. Preview the mirror with `python3 scripts/sync_sources.py --check --component <product>`.
6. Apply the mirror, regenerate the catalog, and validate:

   ```bash
   python3 scripts/sync_sources.py --component <product>
   python3 scripts/generate_catalog.py
   python3 scripts/validate_skills.py
   python3 scripts/generate_catalog.py --check
   npx skills add . --list
   ```

7. Verify discovery from a clean checkout, then open a pull request with the owning team as reviewers.

## Add a catalog-owned skill

Use catalog ownership only for SkillHub-wide workflows. Begin under `staging/`,
complete the same admission evidence as a product skill, then promote it to
`skills/`, add `local: true` to its component definition, generate the catalog,
and validate.

## Skill requirements

- Folder and frontmatter names use lowercase hyphen-case and match exactly.
- YAML frontmatter contains only `name` and `description` until the validator adopts additional specification fields.
- The description explains capability, trigger conditions, and the nearest important exclusion.
- Keep `SKILL.md` at or below 500 lines; move details into `references/`.
- Keep the published catalog flat. Do not place another `SKILL.md` inside a skill.
- Bundle every required dependency inside the skill directory. Do not depend on sibling skills or source-repository files that an installer will not copy.
- Add `skill-card.md` with the owner, source, license, lifecycle, runtime permissions, and validation boundary.
- Add `evals/evals.json` with at least three positive triggers, two negative triggers, and one behavioral assertion.
- Use only the standard optional directories `agents/`, `references/`, `scripts/`, and `assets/` unless a documented format requires another path.
- Put repeatable deterministic operations in tested `scripts/`.
- Do not include credentials, private endpoints, personal data, generated caches, or unrelated documentation.
- Do not request broader permissions than the workflow requires.

## Pull request checklist

- [ ] The source-of-truth repository is owned by [`HYGON-AI`](https://github.com/HYGON-AI).
- [ ] The skill is HYGON-authored or documents substantive, tested HCU adaptations.
- [ ] A HYGON team owns ongoing maintenance and approved publication.
- [ ] Third-party attribution, license, and NOTICE requirements are preserved.
- [ ] The source and catalog licenses are compatible.
- [ ] The installed skill retains required LICENSE and NOTICE material.
- [ ] Scripts were reviewed and tested.
- [ ] `skill-card.md` identifies owner, source, license, lifecycle, runtime permissions, and validation boundary.
- [ ] `evals/evals.json` contains the minimum positive, negative, and behavioral evidence.
- [ ] The skill contains no nested `SKILL.md` or sibling-skill dependency.
- [ ] `python3 scripts/validate_skills.py` passes.
- [ ] `python3 scripts/generate_catalog.py --check` passes.
- [ ] `npx skills add . --list` discovers only the intended published skills.
- [ ] No mirrored files were edited only in the catalog.

Use `git commit --signoff` so the contribution records [Developer Certificate of Origin](https://developercertificate.org/) agreement.
