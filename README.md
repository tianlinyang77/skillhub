# HYGON-AI Agent Skills

Portable [Agent Skills](https://agentskills.io/specification) for [HYGON-AI](https://github.com/HYGON-AI) software, infrastructure, training, and inference workflows. This repository is the organization-level catalog: product teams own their source skills, while this hub validates, mirrors, and publishes approved versions.

## Quick start

After the repository is published, browse or install skills with the standard [`skills` CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add HYGON-AI/skillhub --list
npx skills add HYGON-AI/skillhub
```

Install one skill for Codex without prompts:

```bash
npx skills add HYGON-AI/skillhub --skill skillhub-contributor --agent codex --yes
```

## Repository structure

The repository separates candidate content, product sources, published skills,
evaluation evidence, and generated metadata:

| Path | Purpose |
| --- | --- |
| [`skills/`](skills) | Flat catalog of published, independently installable skills |
| [`staging/`](staging) | Catalog-owned `SKILL.md.candidate` files that cannot be discovered |
| [`components.d/`](components.d) | One reviewed source registration per HYGON-AI product |
| [`templates/`](templates) | Non-discoverable contribution scaffolds |
| [`docs/`](docs) | Architecture, admission, evaluation and release policy |

Every direct child of `skills/` is one catalog identity. Published skills must
not contain nested `SKILL.md` files or depend on sibling skills. See the
[normative repository layout](docs/architecture/repository-layout.md) and
[admission policy](docs/governance/admission.md).

## Skill catalog

<!-- catalog:start -->

| Product | Description | Skills |
|---|---|---|
| **SkillHub** | Author, validate, onboard, and publish portable Agent Skills across HYGON-AI projects. | [`skillhub-contributor`](skills/skillhub-contributor) |

<!-- catalog:end -->

## Skills by category

<!-- categories:start -->

1 skill across 1 category.

### Developer Tools

| Skill | Product | Description |
|---|---|---|
| [`skillhub-contributor`](skills/skillhub-contributor) | SkillHub | Create, review, and onboard portable Agent Skills into Hygon SkillHub. Use when adding a new SKILL.md, registering a HYGON-AI product repository in components.d, preparing a SkillHub contribution, or diagnosing catalog validation and synchronization failures. |

<!-- categories:end -->

## How publication works

1. Product teams maintain source skills in `skills/<skill-name>/` in their own repository.
2. A small `components.d/<product>.yml` file registers source paths and catalog names.
3. Admission review checks ownership, licensing, self-containment, routing data, and behavior evidence.
4. The synchronization workflow mirrors registered content into this repository.
5. Validation checks naming, frontmatter, resources, evaluation data, secrets, and generated catalog drift.
6. Approved changes land through pull requests and become installable from this repository.

Catalog maintainers can run:

```bash
python3 scripts/validate_skills.py
python3 scripts/validate_agent_skills_spec.py
python3 scripts/generate_catalog.py --check
python3 scripts/sync_sources.py --check --component <product>
```

See [CONTRIBUTING.md](CONTRIBUTING.md) to onboard a product or skill.

Catalog-owned candidates start under `staging/`. Product-owned candidates stay
in their product repositories until admission; `staging/` is not a second
product mirror. A candidate entrypoint is named `SKILL.md.candidate` until its
reviewed promotion into `skills/`, preventing deep-discovery clients from
installing staging content.

## Trust model

The catalog publishes reviewed source content; it does not make arbitrary third-party skills trusted. Every product entry records its repository, ref, and source path in [`catalog.json`](catalog.json), and synchronized commits are recorded in [`.skillhub-lock.json`](.skillhub-lock.json). Consumers should still review executable scripts and permissions before installation.

CLI discovery proves format compatibility only. Published status additionally
requires the owner, license, source and lifecycle recorded in `skill-card.md`,
plus positive, negative and behavioral cases under `evals/evals.json`.
The catalog additionally enforces exact remote commit/digest provenance and a
pinned Agent Skills reference-validation pass; neither check alone proves that
a Skill's operational behavior is correct.

## Source attribution

Product repositories remain the source of truth for mirrored skills. The catalog preserves upstream authorship and license terms, records each source repository, ref, and path in `catalog.json`, and does not treat an unchanged third-party skill as a HYGON-AI adaptation.

## License

Repository code and catalog-owned skill content are licensed under the [Apache License 2.0](LICENSE) unless stated otherwise. Mirrored skill content remains under its source license, and imported skills must carry a license compatible with public redistribution.
