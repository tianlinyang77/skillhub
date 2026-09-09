# Skill admission policy

A directory is not publishable merely because a skills CLI can discover its
`SKILL.md`. Admission requires ownership, portability, content review,
redistribution rights, and an auditable source.

## Required decisions

Before synchronization or publication, record:

1. The upstream author/owner and the catalog maintainer responsible for review.
2. Whether the skill is local (this repository, the default) or mirrored from a
   product repository. For a remote component, also record the source
   repository, source path and maintained ref or release tag.
3. Whether the content is locally authored, an unchanged third-party import,
   or an adaptation. Any GitHub organization or personal source is eligible.
4. Applicable license, copyright and NOTICE obligations.
5. Intended positive prompts and nearby prompts that must not trigger it.
6. Required tools, network access, hardware and destructive side effects.
7. Whether any claimed results are supported. This is a review concern, not a
   mandatory Validation section or evaluation form.

## Publication gates

- The skill is one flat, lowercase hyphen-case directory.
- `SKILL.md` is at most 500 lines and contains clear trigger boundaries.
- Frontmatter passes both the catalog's strict six-field/type checks and the
  pinned Agent Skills reference validator.
- All required resources remain inside the installed skill directory.
- No nested `SKILL.md`, sibling-skill dependency, symlink or escaping path is
  present.
- `skill-card.md` has schema version 1, matches the component source, and
  identifies owner, license and published lifecycle.
- The Skill Card records runtime requirements and permissions, or links to them in SKILL.md.
  A separate eval dataset is not required; optional upstream tests may remain.
- Executable helpers are reviewed and tested on representative input.
- Secret, license, link, file-size and generated-catalog checks pass.
- For a local skill, the component sets `local: true`, any `repo` equals
  `HYGON-AI/skillhub`, and the source path equals `skills/<catalog_dir>`.
- For a remote component, content resolves to a recorded commit in
  `.skillhub-lock.json`.
- For a remote component, the independently resolved remote tree, recorded
  commit, lock digest and published package are byte-consistent. A local skill
  has no lock entry or digest; its evidence is review, not provenance.
- Quality Gate, catalog validation, DCO and catalog-maintainer review pass.

## Staging and exceptions

Generated Skill Cards default to `published` to avoid a manual state change.
That field does not mean a PR was approved, checks passed, or release occurred.

`staging/` does not grant trust or publication status. A candidate may remain
there while its trigger boundary, licensing or behavior evidence is repaired.
Remote product skills should normally remain only in their source repository
until admitted.

Catalog-owned candidates use `staging/<skill-name>/SKILL.md.candidate`. A real
`SKILL.md` is forbidden anywhere below `staging/` because full-depth discovery
would make it installable before admission. Promotion must explicitly move the
candidate under `skills/`, rename the entrypoint, register its source and add
all required publication evidence.

`admission-exceptions.yml` uses schema version 1 and records known candidates
that are not currently eligible. Duplicate entries, unsafe paths, malformed
reasons, and candidates simultaneously registered for publication are rejected.
An exception is not a waiver and must never cause a failing skill to appear in
`skills/`.

## Removal and deprecation

Remove a published skill when its owner disappears, its source is deleted, its
license changes incompatibly, or its behavior can no longer be validated.
Record user-visible removals in release notes before deleting published catalog
entries. Do not retain an unmaintained skill merely to preserve catalog count.
