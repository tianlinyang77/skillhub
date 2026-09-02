# Publishing and release flow

For the step-by-step contributor path, see
[Add a skill: quick start](quickstart.md). This page records the release flow.

## Local skill (default)

1. Add the self-contained skill under `skills/<skill-name>/` in this repository.
2. Register it in `components.d/<component>.yml` with `local: true`.
3. Regenerate metadata and run all catalog checks.
4. Merge one protected pull request carrying content, registration and
   generated catalog files.
5. Verify discovery from a clean checkout before announcing release.

## Remote product skill (opt-in)

1. Merge the self-contained skill in the owning HYGON-AI product repository.
2. Add or update `components.d/<component>.yml` in this repository.
3. Preview synchronization and review the resolved repository, ref, source
   path and catalog destination.
4. Apply synchronization, regenerate metadata, and run all catalog checks.
5. Merge through a protected pull request with the product owner reviewing.
6. Verify discovery from the published repository before announcing release.

Synchronization runs on manual dispatch only. Admitting the first remote
component requires an explicit decision on whether to restore scheduled
synchronization and at what frequency.

## Catalog-owned skill

Catalog ownership is reserved for SkillHub-wide workflows. Start in
`staging/<skill-name>/SKILL.md.candidate`, use the contribution templates, and
promote to `skills/` with a real `SKILL.md` only when the same evidence required
from product skills is present. `SKILL.md` is forbidden below `staging/` so
full-depth discovery cannot publish a candidate.

## Generated content

`catalog.json`, `skills.sh.json`, README catalog sections and remote mirrors
are generated artifacts. Regenerate them from reviewed sources; do not repair
drift by hand.

The repository-level catalog supports direct skill discovery and installation.
