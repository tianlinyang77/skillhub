# Catalog taxonomy

Ascend's domain-oriented index is useful for accelerator developers, but the
category must remain metadata rather than a nested filesystem hierarchy. Every
published skill stays at `skills/<skill-name>/`; `components.d/*.yml` assigns
its category and the generator builds the index.

Prefer one of these initial categories when it fits:

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
one. Category spelling is stable public metadata; renames require regenerating
the catalog and documenting the change in `CHANGELOG.md`.

Do not create `skills/<category>/<skill>/`. Nested category directories make
CLI discovery, global name uniqueness, synchronization and plugin selection
ambiguous.
