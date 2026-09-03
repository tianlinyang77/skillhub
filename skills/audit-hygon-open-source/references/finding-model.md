# Finding model

Use these fields internally:

```yaml
rule_id: LICENSE.MODIFIED_FILE_HEADER
severity: blocker
status: must-fix
path: path/to/file
line: 1
classification: hygon-modified
modification_scope: substantive
title: missing HYGON modification header
evidence: concise deterministic evidence
required_change: exact developer action
expected_content: optional target snippet
```

Valid statuses:

- `must-fix`: confirmed violation that blocks admission.
- `needs-provenance-review`: unresolved source or visibility; blocks admission.
- `no-change`: explicitly excluded upstream, exact-blob, or R100 item.
- `approved-exception`: valid policy exception; do not count as blocker.
- `informational`: non-blocking context.
- `advisory`: non-blocking commit-log recommendation.

Sort formal findings by status priority, path, line, and rule ID. Never convert uncertainty into a compliant result.

Aggregate the report summary by unique changed-file paths, not by finding count. Put every
changed file into exactly one top-level group: confirmed must-fix, review-only, or no blocker.
Split confirmed must-fix into fix-only and fix-plus-review. The three top-level groups must add
exactly to the Git changed-file total. Keep generic header detection and modification-scope
statistics out of the developer summary.

Report HYGON header completion as a separate additive hierarchy. Include HYGON-authored sources
and only those HYGON-modified sources for which the governing license requires file-level action.
For MIT/BSD H2 files, check repository-level attribution separately and do not count unchanged
source headers as incomplete. Exclude unresolved provenance from completed counts.

Render complete header text once in a centralized license-aware template matrix. Assign stable
template IDs for HYGON-authored, substantive-modified, non-substantive-modified, restored-original,
third-party, and generated-file handling, with separate hash and slash comment variants where
applicable. Per-file findings keep `expected_content` as machine evidence but the developer report
must suppress repeated header snippets and emit one deduplicated template reference per file.

Valid modification scopes:

- `new`: added source.
- `substantive`: structural AST or normalized code-token evidence reaches the versioned policy threshold for a substantial original implementation.
- `non-substantive`: comments/formatting only, or a parameter, configuration, identifier, literal, small expression, local branch, or other mechanical change below the H2 structural originality threshold.
- `review`: the language or mixed change cannot be determined safely.
- `legacy`: policy does not distinguish modification scope.

Valid provenance classifications also include:

- `upstream-exact`: the complete target blob exists in the isolated upstream cache.
- `upstream-partial-backport`: every private changed source line is covered by one unique public upstream commit outside the baseline.
- `upstream-submodule-pin`: the configured Gitlink path, object type, URL mapping, and Commit represent the fixed upstream baseline in submodule-patch mode.
- `hygon-<scope>-modified`: an existing upstream source has a HYGON declaration, or Git attribution proves retained changes from private-only commits after exact/partial upstream backports, third-party files, and generated files are excluded. For mixed public/private changes, `<scope>` describes the private commits rather than the aggregate upstream-to-target diff.

Do not send deterministically attributed HYGON modifications to developers for provenance
confirmation. Produce direct `must-fix` findings when required attribution is absent. Use
`needs-provenance-review` only when line ownership is mixed, target-side attribution is
unavailable, Git objects are missing, or source type/semantics cannot be determined.

For Python semantic comparison, record whether the current runtime AST, compatible external
Python AST, or token-semantic fallback produced the decision. If all methods fail, use an explicit
automatic-scanner-failure finding; do not disguise it as ordinary provenance uncertainty.
