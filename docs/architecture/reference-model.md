# Reference model

The HYGON-AI catalog combines useful patterns from AMD, NVIDIA, Ascend, and
the open Agent Skills format. No reference repository is treated as a complete
or authoritative implementation.

| Source | Pattern adopted | Pattern not copied |
| --- | --- | --- |
| AMD skills | `staging/`, per-skill eval datasets, positive and negative routing, behavior assertions, explicit plugin manifests | Advisory-only security gates, unsigned releases, and ambiguous published subsets |
| NVIDIA skills | Product component registry, source synchronization, generated plugin bundles, benchmark aggregation, content integrity and signature direction | Organization-scale process weight, file-presence-only benchmark claims, and empty validation metadata |
| Ascend agent-skills | Flat top-level skill catalog, accelerator-domain taxonomy, Chinese catalog index, reusable scripts/references/templates | Nested skill trees, manual index drift, missing CI validators, invalid frontmatter, and mixed directory naming |
| OpenAI Docs and Agent Skills | `SKILL.md`, progressive disclosure, clear descriptions, standard resource directories, `agents/openai.yaml`, plugin distribution | Product-specific behavior that is not part of the portable format |

## Resulting HYGON model

- `skills/` contains only published, flat, independently installable skills.
- `staging/` contains only catalog-owned `SKILL.md.candidate` entrypoints; CI
  proves that normal and full-depth discovery expose only published skills.
- `components.d/` preserves product repositories as source of truth.
- `skill-card.md`, `evals/evals.json`, and conditional `BENCHMARK.md` carry
  review evidence next to each skill.
- `catalog.json`, `skills.sh.json`, benchmark indexes, lock files and plugin
  bundles are generated rather than hand-maintained.
- Supply-chain signing is introduced only with a documented trust root,
  signature profile, revocation process, and CI verification. An unexplained
  signature file is not evidence.

## Scale rule

Adopt gates before catalog volume. A smaller catalog with verified ownership,
routing and behavior is preferable to a large collection that a CLI can only
partially parse.
