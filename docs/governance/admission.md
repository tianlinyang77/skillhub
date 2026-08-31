# Skill admission policy

A directory is not publishable merely because a skills CLI can discover its
`SKILL.md`. Admission requires ownership, portability, behavioral evidence,
redistribution rights, and an auditable source.

## Required decisions

Before synchronization or publication, record:

1. The HYGON-AI owning team and ongoing maintainer.
2. The source repository, source path and maintained ref or release tag.
3. Whether the content is HYGON-authored or a substantive HCU adaptation.
4. Applicable license, copyright and NOTICE obligations.
5. Intended positive prompts and nearby prompts that must not trigger it.
6. Required tools, network access, hardware and destructive side effects.
7. The validation environment and evidence available for its claims.

## Publication gates

- The skill is one flat, lowercase hyphen-case directory.
- `SKILL.md` is at most 500 lines and contains clear trigger boundaries.
- All required resources remain inside the installed skill directory.
- No nested `SKILL.md`, sibling-skill dependency, symlink or escaping path is
  present.
- `skill-card.md` identifies owner, source, license and lifecycle.
- `evals/evals.json` contains positive, negative and behavior evidence.
- Executable helpers are reviewed and tested on representative input.
- Secret, license, link, file-size and generated-catalog checks pass.
- Remote content resolves to a recorded commit in `.skillhub-lock.json`.
- Required repository checks and owning-team review pass.

## Staging and exceptions

`staging/` does not grant trust or publication status. A candidate may remain
there while its trigger boundary, licensing or behavior evidence is repaired.
Remote product skills should normally remain only in their source repository
until admitted.

`admission-exceptions.yml` records known candidates that are not currently
eligible. An exception is not a waiver and must never cause a failing skill to
appear in `skills/`.

## Removal and deprecation

Remove a published skill when its owner disappears, its source is deleted, its
license changes incompatibly, or its behavior can no longer be validated.
Record user-visible removals in release notes before deleting generated plugin
entries. Do not retain an unmaintained skill merely to preserve catalog count.
