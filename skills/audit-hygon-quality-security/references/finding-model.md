# Finding model

Every finding has a stable rule ID, scanner, path or non-file target, Chinese title, redacted evidence, remediation, severity level, optional line/Commit, and fingerprint.

Levels:

- `blocker`: confirmed issue that must be remediated or covered by a formal, unexpired exception.
- `review`: provenance, exploitability, release suitability, or unavailable-fix decision requiring a human conclusion.
- `advisory`: non-blocking maintainability guidance.

Operational failures are scanner statuses, not findings. Any failed scanner invalidates the entire scan.

Derivative repositories require a two-layer comparison. Each target finding is classified as `introduced`, `regressed`, or `inherited`; baseline-only findings are `resolved`. Ordinary inherited lint is advisory and excluded from HYGON-added remediation counts. Inherited secrets, forbidden identities, dangerous Git objects, and security review findings remain visible under the full-tree safeguard.

File counts are mutually exclusive. A file with multiple findings is counted once at the highest level. Historical paths absent from the target tree, dependency coordinates, Commit metadata, and operational failures do not alter the target-tree file total.

Secret evidence must never contain the matched value. Use only redacted metadata and the scanner fingerprint.
