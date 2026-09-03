---
schema_version: 1
owner: "HYGON-AI Open Source Governance"
source:
  repo: HYGON-AI/skillhub
  path: skills/audit-hygon-quality-security
license: Apache-2.0
lifecycle: published
---

# Skill Card

## Summary

Run a whole-repository HYGON quality and security audit at an exact committed Git ref and render a Chinese remediation report.

## Owner

HYGON-AI Open Source Governance. File maintenance or release issues through the
owning HYGON-AI governance team.

## Source

- Repository: `HYGON-AI/skillhub`
- Path: `skills/audit-hygon-quality-security`
- Lifecycle: `published`
- Origin: imported from the HYGON-AI Open Source Governance project with
  release authorization confirmed by the submitting owner on 2026-09-03.

## License

Apache-2.0. The full license text and the project NOTICE are bundled in this
installed skill directory.

## Runtime and permissions

Requires a Linux-capable HYGON governance checkout, Python 3.9 or newer, Git,
and an administrator-provisioned controlled scanning runner. The adapter reads
the registered committed Git ref, creates an isolated bundle, and writes the
rendered report to the configured governance workspace. It needs approved SSH
connectivity to the controlled runner; host details and credentials are external
configuration and are never bundled with the Skill.

## Validation

The bundled adapter passed syntax compilation. Structural catalog validation,
generated catalog checks, and CLI discovery are applicable package checks. Full
quality and security scans require the separately maintained governance engine,
approved runner, fixed images, and offline vulnerability database; they are not
executed by this package validation.
