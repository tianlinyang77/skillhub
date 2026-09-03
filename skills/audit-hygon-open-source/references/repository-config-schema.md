# Repository configuration schema

Create `<workspace>/configs/repos/<repo-id>.yaml`.

Choose the input path before selecting the detailed repository mode:

- **HYGON-original**: require the local clone and target branch or Commit. Resolve the target to a full 40-character Commit, use `repository_mode: original`, and omit `upstream` entirely.
- **Derivative**: require the local clone and target branch or Commit plus the upstream repository URL, at least one upstream branch or Tag, and the full 40-character baseline Commit. The Commit is always mandatory. Confirm the upstream license from that baseline. A configured branch must contain the Commit; a configured Tag must resolve exactly to it.

Fork mode:

```yaml
schema_version: 1
repo_id: pytorch-das
local_path: /absolute/path/to/local/clone
target_ref: branch-or-commit
report_ref: release/2.12
upstream:
  project: PyTorch
  repository: https://github.com/pytorch/pytorch
  branch: release/2.12  # Optional when tag is present.
  tag: v2.12.0  # Optional when branch is present; must resolve to upstream.commit.
  commit: 0d62256a2b23365f8e1604297eb23a6545102aa8
  license: BSD-3-Clause
policy:
  base: hygon-open-source-v1.7
  overlay: centralized-skill
platform_profile: hcu
report_language: zh-CN
```

Required invariants:

- Use an absolute `local_path` to a pre-existing Git clone.
- For every derivative mode, require the upstream repository URL and 40-character Commit.
- Require at least one non-empty `upstream.branch` or `upstream.tag`. A configured branch must contain the Commit; a configured Tag must resolve exactly to it. When both are present, verify both.
- Use only `MIT`, `BSD-3-Clause`, or `Apache-2.0` for automatic admission.
- Keep credentials and tokens out of repository URLs.
- Use an overlay name only when the corresponding YAML exists.
- Resolve `target_ref` inside the private clone without checking it out.
- Record `report_ref` as the human-readable branch label whenever `target_ref` is fixed to an exact Commit for immutable evidence. It controls only the report filename and metadata label; the exact scanned object remains `target_ref`. The legacy `target_branch` field is accepted only during migration and must not conflict with `report_ref`.
- Treat `platform_profile: hcu` only as repository classification metadata. It does not enable HCU/AMD runtime wording checks; run `$audit-hygon-platform` separately for platform conclusions.

Fixed-upstream submodule plus external patch mode:

```yaml
schema_version: 1
repo_id: verl-das
repository_mode: submodule-patch
local_path: /absolute/path/to/local/clone
target_ref: 0123456789abcdef0123456789abcdef01234567
report_ref: release/v0.8.0
upstream:
  project: verl
  repository: https://github.com/verl-project/verl.git
  branch: release/v0.8.0
  tag: v0.8.0  # Optional; include only when it resolves to upstream.commit.
  commit: 7aed6b230776f963fa09509c10d9c3a767d1102c
  license: Apache-2.0
submodule_patch:
  upstream_path: third_party/verl
policy:
  base: hygon-open-source-v1.7
  overlay: centralized-skill
platform_profile: hcu
report_language: zh-CN
```

Submodule-patch invariants:

- Use this mode only when the configured path is a committed Gitlink for the complete upstream baseline and patch/adaptor code is committed outside it.
- `target_ref` must be the exact 40-character target Commit.
- `report_ref`, when recorded, is a human-readable report label and does not change `target_ref`.
- `submodule_patch.upstream_path` must be a normalized relative POSIX path.
- The `.gitmodules` URL, Gitlink object type, and Gitlink Commit must match the registered upstream repository and Commit.
- Scan the committed patch tree without initializing or modifying the submodule worktree.
- Compare same-path patch entries with upstream, but do not treat upstream-only root paths as deletions.

Standalone upstream overlay or patch-package mode:

```yaml
schema_version: 1
repo_id: lmcache-das
repository_mode: upstream-overlay
local_path: /absolute/path/to/local/clone
target_ref: 0123456789abcdef0123456789abcdef01234567
report_ref: dev
upstream:
  project: LMCache
  repository: https://github.com/LMCache/LMCache.git
  branch: dev
  tag: v0.3.13  # Optional; include only when it resolves to upstream.commit.
  commit: fc031d471a566edb6d49a86c9116cc23cfb04111
  license: Apache-2.0
policy:
  base: hygon-open-source-v1.7
  overlay: centralized-skill
platform_profile: hcu
report_language: zh-CN
```

Upstream-overlay invariants:

- Use this mode only for an independently versioned adapter or patch package that neither embeds the complete upstream in a Gitlink nor shares the complete upstream history.
- `target_ref` must be the exact 40-character target Commit.
- `report_ref`, when recorded, is a human-readable report label and does not change `target_ref`.
- Scan every committed target entry.
- Compare same-path target entries with the fixed upstream baseline.
- Do not treat upstream-only paths as deletions.
- Keep target-only source without deterministic provenance in blocking review.

Original-repository full-tree mode:

```yaml
schema_version: 1
repo_id: vllm-plugin-das
repository_mode: original
local_path: /absolute/path/to/local/clone
target_ref: 471e837a47a05f04dc5f1c56b3f9aafd67e64347
report_ref: main
original:
  project: vllm-plugin-das
  default_provenance: hygon-authored
  # license: Apache-2.0  # Add only after formal approval.
policy:
  base: hygon-open-source-v1.7
  overlay: centralized-skill
platform_profile: hcu
report_language: zh-CN
```

Original-mode invariants:

- `target_ref` must be the exact 40-character Commit being released.
- `report_ref`, when recorded, is a human-readable report label and does not change `target_ref`.
- Do not define `upstream`; original mode never accepts the target repository as a fake upstream.
- `original.default_provenance` must explicitly equal `hygon-authored`.
- The provenance assertion does not override generated markers, third-party Copyright, or `third_party`/`vendor`/`external` path evidence.
- `original.license` is optional. If it is omitted and no recognized root license exists, the scan emits a blocker and does not invent an SPDX identifier.
- Every tracked target-tree entry is in scope; mandatory brand/identity checks cover every Commit reachable from the fixed target.

Delivery-mode invariant for all four repository modes:

- Standalone full-repository Skill scans use `policy.overlay: centralized-skill` unless an approved repository-specific overlay already declares `governance.execution_mode: centralized-skill`.
- In this mode, missing `.github/workflows/*` files, PR triggers, and PR hard-blocking configuration are outside the report scope.
- Validate repository-local PR enforcement only as a separately requested `repository-ci` audit; do not mix it into the default full-repository compliance report.
