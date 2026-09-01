# Contributing

Hygon SkillHub is a publication catalog. Product teams own their source skills so documentation and product changes evolve together.

## Repository lifecycle

- Product-owned candidates remain in their HYGON-AI product repository until admission.
- Catalog-owned prototypes may use `staging/<skill-name>/SKILL.md.candidate`;
  a real `SKILL.md` is forbidden anywhere below `staging/` so deep discovery
  cannot expose candidates.
- Only direct children of `skills/` are published catalog identities.
- Generated mirrors, catalog files and lock files are never repaired by hand.

Use [`scripts/new_skill.py`](scripts/new_skill.py) for the mechanical scaffold
or fall back to [`templates/skill/`](templates/skill). Read the
[repository layout](docs/architecture/repository-layout.md),
[admission policy](docs/governance/admission.md), and
[evaluation contract](docs/evaluation/README.md). Reuse the stable categories
in the [catalog taxonomy](docs/governance/taxonomy.md).

Workflow files are not enforcement by themselves. Before production release,
administrators must apply and verify the
[repository settings baseline](docs/governance/repository-settings.md).

## Publication boundary

SkillHub publishes skills whose source-of-truth repository is owned by the [`HYGON-AI` GitHub organization](https://github.com/HYGON-AI). Organization ownership alone is not sufficient: each published skill must be either HYGON-authored or substantively adapted and validated for HCU, with a HYGON team responsible for ongoing maintenance.

Do not register or mirror an unchanged third-party or upstream skill as a HYGON-AI skill. Link to the canonical upstream skill instead, then request catalog admission after the product team has added and tested the HCU-specific workflow. Preserve all applicable third-party copyright, license, and NOTICE material in an adapted skill.

## Generate a product-owned scaffold

Run the generator from a SkillHub checkout and point it at the local product
repository. It creates the final filenames, fills identity fields, copies the
product license and any root NOTICE, and creates or appends the component
registration without reformatting an existing file:

```bash
python3 scripts/new_skill.py quality-gate-audit \
  --source-root ../quality-gate \
  --repo HYGON-AI/quality-gate \
  --ref main \
  --owner "Quality Gate Team" \
  --description "Audit a repository when publication readiness must be verified." \
  --license Apache-2.0 \
  --category "Governance and Compliance" \
  --product-name "Quality Gate" \
  --product-description "Repository publication and compliance gates." \
  --with-openai \
  --with-references
```

Use `--dry-run` to review destinations first. The generator refuses to
overwrite an existing skill, rejects unapproved repositories, categories and
generic names, and requires a non-empty source `LICENSE` unless
`--license-file` names another reviewed license text. It copies a root
`NOTICE`, `NOTICE.txt` or `NOTICE.md` automatically; use `--notice-file` for a
different required notice. The script does not infer legal terms: reviewers
must confirm that `--license` matches the copied text and that all NOTICE
obligations are satisfied.

The generated Skill Card remains `staging` and its author-owned sections and
Eval prompts contain `TODO` markers. Replace them with real workflow,
permission and evaluation evidence, then change the lifecycle to `published`.
The command makes local changes in both repositories for convenience, but the
Git history remains two-stage: merge the product source first, then synchronize
and submit the SkillHub component change.

## Add a product-owned skill

1. Generate or add a portable `skills/<skill-name>/SKILL.md` directory to the product repository.
2. Add `skill-card.md`, `evals/evals.json`, required license and NOTICE material, and any self-contained resources.
3. Confirm the owning team approved public release and the source license permits redistribution.
4. Add `components.d/<product>.yml` here. Use one file per product team; do not edit another team's registry file.
5. Preview the mirror with `python3 scripts/sync_sources.py --check --component <product>`.
6. Apply the mirror, regenerate the catalog, and validate:

   ```bash
   python3 scripts/sync_sources.py --component <product>
   python3 scripts/generate_catalog.py
   python3 scripts/validate_skills.py
   python3 scripts/validate_agent_skills_spec.py
   python3 scripts/generate_catalog.py --check
   npx --yes skills@1.5.23 add . --list
   npx --yes skills@1.5.23 add . --list --full-depth
   ```

7. Verify discovery from a clean checkout, then open a pull request with the owning team as reviewers.

## Add a catalog-owned skill

Use catalog ownership only for SkillHub-wide workflows. Begin under `staging/`,
write the entrypoint as `SKILL.md.candidate`, and complete the same admission
evidence as a product skill. Promotion is a reviewed change that moves the
candidate to `skills/`, renames the entrypoint to `SKILL.md`, adds `local: true`
to its component definition, generates the catalog, and validates both normal
and full-depth discovery.

## Skill requirements

- Folder and frontmatter names use lowercase hyphen-case and match exactly.
- Use a globally descriptive name. Prefer `<product>-<action>` for
  product-specific workflows, while cross-product skills may use another clear
  capability name. Bare generic names such as `add-model`, `profile`,
  `benchmark`, `test`, `build`, and `deploy` are rejected.
- YAML frontmatter uses only Agent Skills fields: required `name` and
  `description`, plus optional `license`, `compatibility`, `metadata`, and
  experimental `allowed-tools`. Put vendor fields such as version, author and
  tags inside `metadata`, whose keys and values must all be strings.
- The description explains capability, trigger conditions, and the nearest important exclusion.
- Keep `SKILL.md` at or below 500 lines; move details into `references/`.
- Keep the published catalog flat. Do not place another `SKILL.md` inside a skill.
- Remove scaffold placeholders and every `.template` file before publication.
- Bundle every required dependency inside the skill directory. Do not depend on sibling skills or source-repository files that an installer will not copy.
- Add a schema-versioned `skill-card.md` with machine-readable owner, source,
  license and lifecycle frontmatter plus the required human-readable sections.
- Add schema-versioned `evals/evals.json` with the matching skill identity, at
  least three positive triggers, two negative triggers, and one behavioral
  assertion.
- Use only the standard optional directories `agents/`, `references/`, `scripts/`, and `assets/` unless a documented format requires another path.
- Put repeatable deterministic operations in tested `scripts/`.
- Do not include credentials, private endpoints, personal data, generated caches, or unrelated documentation.
- Do not request broader permissions than the workflow requires.
- Keep packages at or below 256 files, 5 MiB per file and 20 MiB total. Do not
  publish VCS metadata, virtual environments, dependency trees, caches or
  case-colliding paths.

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
- [ ] `python3 scripts/validate_agent_skills_spec.py` passes against the pinned reference implementation.
- [ ] `python3 scripts/generate_catalog.py --check` passes.
- [ ] `python3 scripts/sync_sources.py --check` proves every remote ref, commit, digest, lock entry and mirror agree.
- [ ] `npx --yes skills@1.5.23 add . --list` discovers only the intended published skills.
- [ ] `npx --yes skills@1.5.23 add . --list --full-depth` also discovers only the intended published skills.
- [ ] No mirrored files were edited only in the catalog.

Use `git commit --signoff` so the contribution records [Developer Certificate of Origin](https://developercertificate.org/) agreement.
