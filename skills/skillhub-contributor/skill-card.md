---
schema_version: 1
owner: HYGON-AI SkillHub maintainers
source:
  repo: HYGON-AI/skillhub
  path: skills/skillhub-contributor
license: Apache-2.0
lifecycle: published
---

# Skill Card

## Summary

Imports, creates, reviews, registers, synchronizes, and validates portable
skills for the HYGON-AI organization catalog.

## Owner

HYGON-AI SkillHub maintainers.

## Source

- Repository: `HYGON-AI/skillhub`
- Path: `skills/skillhub-contributor`
- Lifecycle: `published`
- Ownership: catalog-owned

## License

Apache-2.0. The full license text is bundled in this installed skill directory.

## Runtime and permissions

Requires a checkout of SkillHub, Python 3.11+, Git, Node.js/npm (CI uses Node 22),
and the dependencies in `requirements-dev.txt`. Dependency setup and CLI discovery
may use the network; registered remote sources are fetched during remote checks.
Import/new writes skill files and registrations. `contribute.py check` rewrites
README/catalog files before validation; it does not stage, commit, push or open a
PR. `sync_sources.py --check` leaves catalog mirrors unchanged; apply mode writes
mirrors and the lock. Git submission requires separate user authorization.

## Validation

The catalog's unit tests, structural validation, generated catalog check, and
skills CLI discovery are the applicable evidence. They do not prove that a
newly contributed skill behaves correctly. A Validation section and separate eval
form are not required. A local skill has no lock entry or content digest. Its
review-based safeguards depend on configured branch protection and required
checks; local test success does not establish those settings or remote CI success.
