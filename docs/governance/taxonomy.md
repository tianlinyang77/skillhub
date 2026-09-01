# Catalog taxonomy

Categories are catalog metadata rather than a nested filesystem hierarchy.
Every published skill stays at `skills/<skill-name>/`; `components.d/*.yml`
assigns its category and the generator builds the index.

Every component registration must use one of these stable categories exactly:

| Category | Scope |
| --- | --- |
| Governance and Compliance | Licensing, policy, audit and admission workflows |
| Developer Tools | Repository authoring, code review and general engineering |
| HCU Platform | Device, driver, runtime and environment management |
| Operator Development | Native, Triton and fused operator implementation |
| Performance and Profiling | Trace collection, diagnosis, benchmarking and optimization |
| Training | Model training, distributed training and data workflows |
| Inference | Model serving, deployment and inference optimization |
| Distributed Systems | Communication, storage, cluster and multi-node workflows |
| CI and Release | Continuous integration, packaging and release engineering |
| Documentation | Documentation generation and maintenance workflows |

Add a category only when at least one admitted skill cannot fit an existing
one. The validator rejects unlisted values, so adding a category requires a
reviewed update to both this taxonomy and the validator allowlist. Category
spelling is stable public metadata; renames require regenerating the catalog
and documenting the change in `CHANGELOG.md`.

Skill names use one global namespace. Prefer a descriptive
`<product>-<action>` name for product-specific workflows, but treat that shape
as guidance rather than a required prefix: cross-product skills may use a
clear capability name instead. The validator rejects ambiguous bare names such
as `add-model`, `profile`, `benchmark`, `test`, `build`, and `deploy`; add enough
context to make the catalog identity durable if the product or repository is
renamed.

Do not create `skills/<category>/<skill>/`. Nested category directories make
CLI discovery, global name uniqueness, synchronization and plugin selection
ambiguous.
