# Publishing and release flow

For the step-by-step contributor path, see
[Add a skill: quick start](quickstart.md). This page records the release flow.

## Local skill (default)

1. Import an existing package with `python3 scripts/contribute.py import <path>`.
   If no package exists yet, run `python3 scripts/contribute.py new <skill-name>`.
2. Review its Skill Card, runtime requirements, attribution and applicable license
   material. Its lifecycle already defaults to `published`; this is not approval.
3. Run `python3 scripts/contribute.py check` to regenerate metadata and run all
   catalog checks.
4. Merge one protected pull request carrying content, registration and
   generated catalog files.
5. Verify discovery from a clean checkout before announcing release.

## Remote product skill (opt-in)

1. Select a self-contained skill on a maintained ref in any GitHub repository.
2. Add or update `components.d/<component>.yml` in this repository.
3. Preview synchronization and review the resolved repository, ref, source
   path and catalog destination.
4. Apply synchronization, regenerate metadata, and run all catalog checks.
5. Pass Quality Gate, catalog checks and DCO, then merge a protected pull
   request with the catalog maintainer reviewing.
6. Verify discovery from the published repository before announcing release.

For an existing third-party package, follow [Import external skills](external-skills.md).
Synchronization runs on manual dispatch only. Admitting the first remote
component requires an explicit decision on whether to restore scheduled
synchronization and at what frequency.

## Optional catalog-owned prototype

Any directly maintained skill can use the normal local path above. For an
unfinished prototype, optionally start in `staging/<skill-name>/SKILL.md.candidate`
and promote to `skills/` when the publication contract is satisfied.
`SKILL.md` is forbidden below `staging/` so
full-depth discovery cannot publish a candidate.

## Generated content

`catalog.json`, `skills.sh.json`, README catalog sections and remote mirrors
are generated artifacts. Regenerate them from reviewed sources; do not repair
drift by hand.

The repository-level catalog supports direct skill discovery and installation.
