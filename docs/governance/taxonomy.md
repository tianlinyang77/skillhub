# Catalog taxonomy

Categories are catalog metadata rather than a nested filesystem hierarchy.
Every published skill stays at `skills/<skill-name>/`; `components.d/*.yml`
assigns its category and the generator builds the index.

Every component registration must use one of these stable categories exactly:

| Category | Includes | Excludes |
| --- | --- | --- |
| Governance and Compliance | Licensing, policy, audit and admission workflows | General documentation and ordinary project reporting |
| Developer Tools | Repository authoring, code review and general engineering tools | Domain workflows that fit a platform, workload or operator category |
| HCU Platform | Device, driver, runtime and environment management | Model workflows, operator implementation and generic remote development |
| Operator Development | Native, Triton and fused operators, plus graph rewrites whose primary output is production code | Measurement-only profiling and reports |
| Performance and Profiling | Trace collection, benchmarking, diagnosis and performance reports | Work whose primary output is an implemented or modified operator |
| Accuracy and Debugging | Numerical comparison, correctness regression isolation and precision diagnosis | Generic test execution and performance profiling |
| Training | Model training, training data and workload-level distributed training | Communication-library implementation and inference serving |
| Inference | Model serving, deployment and workload-level inference optimization | Operator-only implementation and generic cluster infrastructure |
| Distributed Systems | Communication libraries, collectives, storage and cluster scheduling | Agent orchestration and workload-specific multi-node procedures |
| CI and Release | Continuous integration, packaging and release engineering | Runtime model deployment and general repository authoring |
| Documentation | Documentation generation and maintenance as the primary deliverable | Reports incidental to profiling, governance or implementation work |

Add a category only when at least one admitted skill cannot fit an existing
one. The validator rejects unlisted values, so adding a category requires a
reviewed update to both this taxonomy and the validator allowlist. Category
spelling is stable public metadata; renames require regenerating the catalog
and documenting the change in `CHANGELOG.md`.

Choose the category from the skill's primary output or the artifact it changes,
not merely from the goal it serves. Code that implements or modifies an
operator belongs in `Operator Development` even when the goal is performance;
a workflow whose primary output is a trace, measurement, diagnosis or report
belongs in `Performance and Profiling`. Multi-node use alone does not imply
`Distributed Systems`: reserve that category for the underlying communication,
storage or scheduling infrastructure.

Categories are the single shelf used by the generated README and
`skills.sh.json`. Cross-cutting tags are not yet accepted in component files.
Adding them requires a reviewed vocabulary, validation limits and an explicit
`catalog.json` schema contract; do not introduce ad hoc tag spellings in the
meantime.

Skill names use one global namespace. Prefer a descriptive
`<product>-<action>` name for product-specific workflows, but treat that shape
as guidance rather than a required prefix: cross-product skills may use a
clear capability name instead. The validator rejects ambiguous bare names such
as `add-model`, `profile`, `benchmark`, `test`, `build`, and `deploy`; add enough
context to make the catalog identity durable if the product or repository is
renamed.

Do not create `skills/<category>/<skill>/`. Nested category directories make
CLI discovery, global name uniqueness, synchronization and catalog generation
ambiguous.
