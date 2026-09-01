# Publishing and release flow

## Product-owned skill

1. Merge the self-contained skill in the owning HYGON-AI product repository.
2. Add or update `components.d/<product>.yml` in this repository.
3. Preview synchronization and review the resolved repository, ref, source
   path and catalog destination.
4. Apply synchronization, regenerate metadata, and run all catalog checks.
5. Merge through a protected pull request with the product owner reviewing.
6. Verify discovery from the published repository before announcing release.

## Catalog-owned skill

Catalog ownership is reserved for SkillHub-wide workflows. Start in
`staging/<skill-name>/SKILL.md.candidate`, use the contribution templates, and
promote to `skills/` with a real `SKILL.md` only when the same evidence required
from product skills is present. `SKILL.md` is forbidden below `staging/` so
full-depth discovery cannot publish a candidate.

## Generated content

`catalog.json`, `skills.sh.json`, README catalog sections, remote mirrors and
plugin bundles are generated artifacts. Regenerate them from reviewed sources;
do not repair drift by hand.

## Distribution layers

The repository-level catalog supports direct skill discovery and installation.
Plugin bundles are a separate distribution layer for grouped skills and tool
dependencies. A plugin manifest must select an explicit published subset; it
must not silently include every directory under `skills/`.
