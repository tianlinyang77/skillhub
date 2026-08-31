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
├── benchmarks/               # Benchmark evidence contract and future indexer
├── components.d/             # Product source registry; one file per product
├── docs/                     # Architecture, governance and release contracts
├── eval/                     # Shared evaluation contract and future runner
├── plugins.d/                # Reviewed plugin source definitions
├── plugins/                  # Generated installable plugin bundles
├── schemas/                  # Machine-readable repository contracts
├── scripts/                  # Validation, synchronization and generation tools
├── staging/                  # Catalog-owned candidates; never published
├── templates/                # Non-discoverable contribution scaffolds
├── tests/                    # Validator, generator and fixture tests
├── skills/                   # Published, flat, independently installable skills
├── admission-exceptions.yml  # Time-bounded rejected or deferred candidates
├── catalog.json              # Generated catalog metadata
├── skills.sh.json            # Generated skills CLI metadata
└── .skillhub-lock.json       # Resolved remote source commits
```

The combined design rationale and the boundaries inherited from AMD, NVIDIA,
Ascend, and the portable format are documented in
[`reference-model.md`](reference-model.md).

## Directory ownership

| Path | Source of truth | Hand editing |
| --- | --- | --- |
| `components.d/` | Catalog maintainers and product owners | Yes, through PR |
| `skills/<name>/` for remote components | Registered product repository | No; synchronize it |
| `skills/<name>/` for `local: true` components | This repository | Yes, through PR |
| `staging/` | This repository | Yes, but never treat it as published |
| `catalog.json`, `skills.sh.json` | Generator output | No |
| `.skillhub-lock.json` | Synchronization output | No |
| `plugins/` | Plugin build output | No, except its directory documentation |

## Per-skill layout

```text
skills/<skill-name>/
├── SKILL.md                  # Required instructions and trigger metadata
├── skill-card.md             # Required owner, source, license and lifecycle
├── evals/
│   └── evals.json            # Required routing and behavior cases
├── agents/
│   └── openai.yaml           # Recommended UI and invocation metadata
├── references/               # Optional detailed documentation
├── scripts/                  # Optional deterministic, tested helpers
├── assets/                   # Optional templates and output resources
├── LICENSE                   # Required when root licensing is not self-contained
├── NOTICE                    # Required when the source license requires it
└── BENCHMARK.md              # Required only when publishing performance claims
```

Use `references/`, not `docs/`, `reference/`, or nested skill directories, so
all published packages have one predictable shape. Templates use suffixes such
as `.template` so discovery tools do not mistake scaffolding for real skills.

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
 catalog metadata and plugin release
```

Product-owned candidates remain in their product repositories until admitted.
`staging/` is only for catalog-owned prototypes and review fixtures; it is not
a second mirror of a product repository.
