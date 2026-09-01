# Changelog

All notable catalog, policy, validation and distribution changes are recorded
here. Generated skill synchronization updates may be grouped by release.

## Unreleased

### Added

- Layered repository foundation for published skills, staging, evaluation,
  product federation, and generated catalog metadata.
- Normative repository layout, admission, evaluation, publishing, and
  supply-chain documentation.
- Production repository-settings baseline for protected reviews, required
  checks, DCO, private vulnerability reporting, and synchronization authority.
- Non-discoverable contribution templates.

### Changed

- Catalog categories now use an enforced allowlist, primary-output
  classification rules and explicit inclusion/exclusion boundaries; accuracy
  and correctness debugging have a dedicated category.
- Ambiguous bare catalog names, residual `.template` files and unresolved
  scaffold placeholders are rejected before publication.
- Pull-request validation runs on Python 3.11 and 3.12, while DCO and scheduled
  synchronization use the declared minimum Python 3.11 runtime.
- Published skills require a skill card and a minimum routing/behavior dataset.
- Nested `SKILL.md` dependencies are rejected in the flat catalog.
- Relative Markdown links are validated recursively across each skill package.
- Remote lock entries carry and verify the source-tree SHA-256 digest.
- Synchronization rejects symlinks and special files before copying source content.
- Agent Skills frontmatter now supports and type-checks all six specification
  fields while rejecting vendor-specific top-level fields.
- Skill Cards and Eval datasets now carry schema version and source/identity
  bindings that are validated before publication.
- Remote checks now bind the resolved ref, commit, source digest, lock entry
  and published tree; published packages also have file-count, size, cache and
  cross-platform path-collision limits.
- Admission exceptions now use a validated schema and cannot simultaneously
  identify a registered published source.
- Staging candidates now use `SKILL.md.candidate`; real `SKILL.md` files below
  `staging/` are rejected and full-depth CLI discovery is verified in CI.
- CI now pins external Actions and CLI versions, runs the pinned Agent Skills
  reference validator, verifies CLI discovery, and enforces DCO sign-offs.

### Deferred

- Restricting `local: true` components to the official catalog repository is
  deferred until `HYGON-AI/skillhub` exists and this repository is migrated.
- The remote clone, sparse-checkout, digest and lock path remains to be proven
  with the first admitted product-owned skill; local-only validation does not
  establish that evidence.
