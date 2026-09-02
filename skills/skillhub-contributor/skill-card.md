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

Creates, reviews, and validates local-first Agent Skills for the HYGON-AI
organization catalog, with remote synchronization available only by explicit choice.

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

Requires a checkout of SkillHub, Python 3.11 or newer, and Git. Network access
is needed for pinned reference checks and optional remote synchronization.
Repository writes occur only when the user asks to create, update, or submit a
Skill; validation and synchronization preview remain read-only.

## Validation

The catalog's unit tests, structural validation, generated catalog check, and
skills CLI discovery are the applicable evidence. They do not prove that a
newly contributed product skill behaves correctly; each product skill needs
its own routing and behavior evidence.
