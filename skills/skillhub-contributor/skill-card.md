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

Creates, reviews, registers, synchronizes, and validates portable skills for
the HYGON-AI organization catalog.

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

Requires a checkout of SkillHub, Python 3.11 or newer, Git, network access for
remote synchronization, and repository write access only when the user asks to
apply or submit changes. Validation and synchronization preview are read-only.

## Validation

The catalog's unit tests, structural validation, generated catalog check, and
skills CLI discovery are the applicable evidence. They do not prove that a
newly contributed product skill behaves correctly; each product skill needs
its own routing and behavior evidence.
