---
schema_version: 1
owner: "HYGON-AI open source governance team"
source:
  repo: HYGON-AI/skillhub
  path: skills/rewrite-hygon-git-identity
license: "Apache-2.0"
lifecycle: published
---

# Skill Card

## Summary

Audit and safely rewrite prohibited or noncompliant Git commit identity
metadata in HYGON repositories while proving that source trees, topology and
unapproved metadata remain unchanged.

## Owner

HYGON-AI open source governance team, reachable through issues and pull
requests on `HYGON-AI/skillhub`.

## Source

- Repository: `HYGON-AI/skillhub`
- Path: `skills/rewrite-hygon-git-identity`
- Lifecycle: `published`
- Ownership: catalog-owned (local component)

## License

The HYGON-authored Skill content is licensed under `Apache-2.0`; see the
bundled `LICENSE`. The bundled `git-filter-repo` v2.47.0 program remains under
its upstream MIT license. Its copyright and license texts are preserved in
`NOTICE`, `tools/COPYING.git-filter-repo`, and
`tools/COPYING.mit.git-filter-repo`.

## Runtime and permissions

Requires Linux, Python 3.9 or newer, Git 2.36 or newer, and private disk space
for two fresh mirror clones, an offline bundle, and validation evidence.
Read-only audit and preparation require network and Git read access to the
selected HYGON repository. Publishing a temporary review branch requires
separate Git write authorization. Replacing an official branch requires a new
explicit approval containing the exact branch, frozen old Tip, validated new
Tip, and permission for a guarded `force-with-lease` update.

The workflow rewrites commit metadata in a dedicated mirror; it does not edit
the checked-out source tree. It writes local evidence under the user-selected
private workspace and can write only the explicitly approved remote review or
official branch.

## Validation

The packaged manifest and every bundled file were verified by SHA-256. The
vendored `git-filter-repo` program and license files were compared with the
declared upstream v2.47.0 commit. The HYGON helper scripts were statically
reviewed and exercised on a synthetic repository through audit, deterministic
email mapping, history rewrite, strict tree/topology validation, temporary
review publication, and guarded cutover.

This evidence validates the packaged control flow and safety invariants on
representative local Git history. It does not prove that an arbitrary remote
repository is ready for rewriting, that its organization has approved a
maintenance window, or that its credentials and branch-protection settings
permit publication. Those checks and approvals remain mandatory at runtime.
