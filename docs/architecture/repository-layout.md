# Repository layout

## Design goals

HYGON-AI SkillHub separates product-owned source, admission review, published
content, generated metadata, evaluation evidence, and distribution packaging.
The separation prevents a catalog mirror from becoming a second hand-edited
source of truth.

The published catalog is deliberately flat. Every direct child of `skills/`
is one independently installable skill, and a published skill must not contain
another `SKILL.md`. Orchestration belongs in the parent instructions while
supporting material belongs in `references/` with ordinary Markdown names.

## Normative tree

```text
skills/
├── .github/                  # Pull-request templates, ownership and CI
├── components.d/             # Product source registry; one file per product
├── docs/                     # Architecture, governance and release contracts
├── scripts/                  # Validation, synchronization and generation tools
├── staging/                  # Catalog-owned SKILL.md.candidate files
├── templates/                # Non-discoverable contribution scaffolds
├── tests/                    # Validator, generator and fixture tests
├── skills/                   # Published, flat, independently installable skills
├── admission-exceptions.yml  # Time-bounded rejected or deferred candidates
├── catalog.json              # Generated catalog metadata
├── skills.sh.json            # Generated skills CLI metadata
└── .skillhub-lock.json       # Resolved remote source commits
```

## Directory ownership

| Path | Source of truth | Hand editing |
| --- | --- | --- |
| `components.d/` | Catalog maintainers and product owners | Yes, through PR |
| `skills/<name>/` for remote components | Registered product repository | No; synchronize it |
| `skills/<name>/` for `local: true` components | This repository | Yes, through PR |
| `staging/` | This repository | Yes; only `SKILL.md.candidate`, never `SKILL.md` |
| `catalog.json`, `skills.sh.json` | Generator output | No |
| `.skillhub-lock.json` | Synchronization output | No |

## Per-skill layout

```text
skills/<skill-name>/
├── SKILL.md                  # Required instructions and trigger metadata
├── skill-card.md             # Required structured owner, source, license and lifecycle
├── evals/
│   └── evals.json            # Required routing and behavior cases
├── agents/
│   └── openai.yaml           # Recommended UI and invocation metadata
├── references/               # Optional detailed documentation
├── scripts/                  # Optional deterministic, tested helpers
├── assets/                   # Optional templates and output resources
├── LICENSE                   # Required; installations do not inherit the repository root license
└── NOTICE                    # Required when the source license requires it
```

Use `references/`, not `docs/`, `reference/`, or nested skill directories, so
all published packages have one predictable shape. Templates use suffixes such
as `.template` so discovery tools do not mistake scaffolding for real skills.

`SKILL.md` frontmatter follows the six-field Agent Skills contract. Required
fields are `name` and `description`; optional fields are `license`,
`compatibility`, `metadata`, and experimental `allowed-tools`. Additional
catalog metadata belongs in component registration, the structured Skill Card,
or another validated sidecar, not in portable frontmatter.

Published packages are bounded to 256 files, 5 MiB per file and 20 MiB total.
Generated caches, dependency trees, virtual environments, VCS metadata,
symlinks, special files and case-colliding paths are rejected.

## Lifecycle

```text
product source or catalog prototype
              |
              v
      admission review / staging
              |
              v
    synchronized published skill
              |
              v
        catalog metadata
```

Product-owned candidates remain in their product repositories until admitted.
`staging/` is only for catalog-owned prototypes and review fixtures; it is not
a second mirror of a product repository. Candidate entrypoints are named
`SKILL.md.candidate`; validation renames them only inside an isolated temporary
directory. A real `SKILL.md` anywhere below `staging/` is rejected so CLI
full-depth discovery cannot expose an unreviewed candidate.
