# Staging

This directory contains catalog-owned candidate skills and review fixtures that
are not published, indexed, synchronized, or installable from the catalog.

Product-owned candidates should remain in their product repository until they
meet the admission policy. Never copy a remote product skill here as a second
source of truth.

Each candidate uses `staging/<skill-name>/SKILL.md.candidate`. Do not place a
real `SKILL.md` anywhere below `staging/`: deep-discovery clients can otherwise
mistake an unreviewed candidate for a published skill. Validation checks the
candidate by copying it to an isolated temporary directory and renaming the
entrypoint there.

Publication is a separate promotion change: rename the entrypoint to
`SKILL.md` under `skills/<skill-name>/`, add component registration and the
required evidence, then regenerate and validate the catalog.
