---
schema_version: 1
owner: "HYGON-AI Open Source Governance"
source:
  repo: HYGON-AI/skillhub
  path: skills/audit-hygon-open-source
license: "LicenseRef-HYGON-Internal"
lifecycle: published
---

# Skill Card

## Summary

Audit complete Git repository provenance, licensing, headers, notices, and reachable history metadata for HYGON open-source release readiness.

## Owner

HYGON-AI Open Source Governance. File maintenance or release issues through the
owning HYGON-AI governance team.

## Source

- Repository: `HYGON-AI/skillhub`
- Path: `skills/audit-hygon-open-source`
- Lifecycle: `published`
- Origin: imported from the HYGON-AI Open Source Governance project with
  release authorization confirmed by the submitting owner on 2026-09-03.

## License

Declared as `LicenseRef-HYGON-Internal`; the source `LICENSE` and `NOTICE` are
bundled unchanged. Public release authorization was confirmed by the submitting
owner; do not relicense, remove attribution, or redistribute it under a
different license without the owner's approval.

## Runtime and permissions

Requires a Linux-capable HYGON governance checkout, Python 3.9 or newer, and
Git. The bundled history helper reads Git objects and writes reports only outside
the repository under audit. The full compliance adapter requires the separately
maintained governance engine and its approved repository configuration. Network
access is needed only to retrieve an uncached declared upstream baseline; use
`--offline` only when that baseline is already cached.

## Validation

The bundled Python scripts passed syntax compilation and the history helper's
argument parser was exercised locally. Structural catalog validation, generated
catalog checks, and CLI discovery are applicable package checks. This evidence
does not validate the separately maintained governance engine or any release
decision for a production repository.
