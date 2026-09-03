# Policy schema

The workspace policy is authoritative. Load the base YAML, recursively merge the optional repository overlay, then apply non-expired approved exceptions.

## Base policy

Store the executable policy at `policies/base/<policy-id>.yaml` and the leadership-approved source text beside it as Markdown.

The YAML defines:

- `allowed_licenses`: exactly MIT, BSD-3-Clause, Apache-2.0.
- `source_files`: extensions, special filenames, and header scan depth.
- `copyright`: HYGON templates, substantive-modification classification, Apache change notices, and unchanged/upstream/rename exclusions.
- `provenance`: deterministic private-commit attribution and upstream-backport exclusions.
- `legal_files`: LICENSE and NOTICE filenames. Root-license discovery also accepts common `LICENSE.*`, `LICENSE-*`, `COPYING.*`, and `COPYING-*` variants such as `LICENSE-APACHE`.
- `third_party`: primary/accepted registry files and required provenance fields.
- `readme`: attribution markers.
- `platform`: legacy engine compatibility only; `$audit-hygon-platform` owns formal HCU/DCU and AMD/XGMI conclusions.
- `governance`: execution mode, compliance workflows, optional immutable-ref enforcement, and source modes. Use `centralized-skill` for the standalone full-repository audit Skill; repository-local workflows are then explicitly out of scope. Use `repository-ci` only for a separately requested validation of repository-local PR enforcement.
- `dependency_pinning`: changed dependency manifests that require fixed versions.
- `commit_log`: advisory conventional-commit rules and the maximum number of newest in-scope Commits. The in-scope set is target-minus-fixed-baseline for derivative repositories and target-reachable history for original repositories.
- `brand_identity`: mandatory forbidden-identity ruleset used by policy v1.3 and later.

## Overlay

Allow only additive repository-specific values such as excluded evidence paths, workflow paths, and platform hints. The versioned `centralized-skill` overlay selects the default standalone full-repository scan delivery mode without requiring repository-local GitHub workflows. A repository-specific overlay used by the Skill must retain that execution mode. Do not remove allowed-license, provenance, identity, or preservation requirements.

`governance.require_immutable_uses` is a Boolean compatibility control. Policy v1.4 sets it to
`false`: movable GitHub Action references such as `actions/checkout@v4` are not open-source
admission blockers. Repositories may still pin approved Actions to a full Commit SHA as a
non-blocking supply-chain hardening measure. PR-trigger and hard-finding enforcement apply only to
the configured compliance workflows, not to every ordinary test or build workflow in an original
repository.

## Exceptions

Use `policies/exceptions/approved-exceptions.yaml`:

```yaml
schema_version: 1
exceptions:
  - exception_id: APPROVAL-123
    repository: repo-id
    rule_id: RULE.ID
    paths: [path/or/glob]
    reason: approved reason
    approver: name
    approval_reference: internal-reference
    effective_date: 2026-01-01
    expires_at: 2026-12-31
```

Reject expired, incomplete, or cross-repository exceptions.

## Modification scope

For policy v1.1 and later:

- `distinguish_substantive_modifications: true` enables semantic classification.
- `substantive_classification_mode: original-implementation-v1` requires strong structural originality evidence before selecting H2.
- `substantive_originality` defines structural edit, change-ratio, and large-change thresholds; none is a changed-line threshold.
- `require_hygon_on_substantive_modified_licenses` lists the repository licenses whose H2 files require HYGON Copyright and SPDX. Policy v1.7 uses only `Apache-2.0`; MIT/BSD use repository-level attribution instead.
- `require_hygon_on_non_substantive_modified: false` prevents Copyright additions for parameter, configuration, identifier, literal, small expression, local branch, formatting, comment, and other mechanical H3 changes.
- `require_modification_notice_on_modified_licenses` lists licenses whose known HYGON modifications require a file-level notice. Policy v1.7 uses only `Apache-2.0`.
- `repository_attribution_on_substantive_modified_licenses` lists permissive licenses whose H2 contribution is recorded in root LICENSE, NOTICE, or a copyright statement while modified source headers remain unchanged.
- `require_apache_change_notice_on_modified: true` requires a prominent change notice for known HYGON modifications to Apache-2.0 files.
- `require_third_party_file_license_marker: false` preserves unmodified third-party files and records missing file-level metadata externally instead of inserting SPDX directly.
- `modification_notice_template` provides the exact notice text.

Do not use changed-line counts as the deciding threshold. Compare Python AST structure and normalized C-family code-token structure. Treat names, literals, default parameters, small expressions, local branches, formatting, comments, and other changes below the structural originality threshold as H3. Select H2 only for a sufficiently large structural implementation change. Route unsupported languages, parse failures, mixed provenance, and insufficient evidence to blocking review.

## Provenance attribution

For policy v1.2 and later:

- `auto_classify_private_modified: true` enables automatic HYGON attribution for existing upstream files.
- `require_changed_line_attribution: true` requires every target-side changed line to be attributed to an identifiable commit.
- `exclude_proven_upstream_backports: true` requires exact blobs and unique complete upstream partial backports to be handled before private attribution.
- `allow_mixed_with_private_scope: true` treats mixed public/private files as confirmed HYGON modifications only after the private commits are separately classified as substantive or non-substantive.

Treat this as deterministic evidence only for modified upstream files. Do not automatically call an
added file HYGON-authored merely because it was introduced by a private commit; copied third-party
source may lack a reliable header. Keep mixed public/private changes, deletion-only changes without
target-side lines, and failed blame attribution in blocking review.

## HCU runtime output

Do not enable platform wording from the open-source compliance Skill. Use `$audit-hygon-platform`, which owns candidate classification, coverage gaps, protected interfaces, and runtime evidence. Keep the legacy policy block only for backward-compatible engine parsing; it must not be presented as the formal platform report.

Do not use the platform rule to rename repository paths, packages, imports, APIs, environment variables, configuration keys, protocols, macros, ABI symbols, or backend identifiers. If a protected token crosses an output boundary, require compatibility-aware handling rather than a mechanical replacement.

## Brand identity

For policy v1.3 and later, load `policies/brand/forbidden-identities-v1.yaml`. Scan case-insensitively for `sugon` and `rogon` in committed paths, committed text, and private Commit metadata introduced outside the fixed upstream baseline. Commit metadata includes author and committer names and emails plus subject and body. Treat every match as blocking. Do not block `hygon` or HYGON email addresses.

This rule is mandatory and independent from the opt-in HCU runtime wording scan.
