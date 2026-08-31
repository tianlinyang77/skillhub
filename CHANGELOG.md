# Changelog

All notable catalog, policy, validation and distribution changes are recorded
here. Generated skill synchronization updates may be grouped by release.

## Unreleased

### Added

- Layered repository foundation for published skills, staging, evaluation,
  product federation, benchmark evidence, and future plugin distribution.
- Normative repository layout, admission, evaluation, publishing, and
  supply-chain documentation.
- Non-discoverable contribution templates.

### Changed

- Published skills require a skill card and a minimum routing/behavior dataset.
- Nested `SKILL.md` dependencies are rejected in the flat catalog.
- Relative Markdown links are validated recursively across each skill package.
- Remote lock entries carry and verify the source-tree SHA-256 digest.
- Synchronization rejects symlinks and special files before copying source content.
