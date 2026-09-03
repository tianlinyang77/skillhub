# Repository and executor configuration

Repository configuration lives only in the runtime workspace. Always declare whether the repository is derivative or HYGON-original.

## Derivative repository

```yaml
schema_version: 1
repo_id: tilelang-das
repository_mode: fork  # 也接受兼容名称 derivative，语义完全相同
local_path: /absolute/path/to/tilelang-das
target_ref: release/0.1.12
# Optional report filename label. Required when target_ref is an exact Commit.
report_ref: release/0.1.12
policy: hygon-quality-security-v1.2
executor: quality-runner
report_language: zh-CN
baseline:
  mode: fixed-upstream-commit
  repository: https://github.com/tile-ai/tilelang.git
  branch: main
  tag: v0.1.12  # Optional; record only when it resolves to baseline.commit.
  commit: 0123456789abcdef0123456789abcdef01234567
scanners:
  cpp:
    enabled: false
```

Required invariants:

- `baseline.repository`, `baseline.branch`, and the full 40-character `baseline.commit` are mandatory.
- The baseline Commit must exist in the local clone. It is normally an ancestor of the target Commit; when the local history was squashed and the official upstream Commit is not reachable, the official Commit may be used as a non-ancestor baseline (fetch it into the local clone and keep a ref such as `refs/quality-baselines/<repo>-upstream` to protect it from GC). Non-ancestor baselines are packed separately and compared at the official-tree level. Never use a floating branch or Tag as the machine baseline.
- A Tag is optional evidence only. When present, confirm it resolves to the configured Commit.
- Scan baseline and target with the same pinned images, rules, arguments, and offline Trivy database.
- Report ordinary inherited lint separately; count only new or regressed lint as HYGON quality remediation.
- Never suppress inherited secrets, forbidden identities, dangerous Git objects, or inherited security review findings. List inherited security findings in a separate release-disposition section; keep unknown-origin findings at their original level until reviewed.

## HYGON-original repository

```yaml
schema_version: 1
repo_id: vllm-plugin-das
repository_mode: original
local_path: /absolute/path/to/vllm-plugin-das
target_ref: main
report_ref: main
policy: hygon-quality-security-v1.2
executor: quality-runner
report_language: zh-CN
scanners:
  cpp:
    enabled: false
```

Original repositories must omit `baseline`. Every target finding belongs to the original repository's full-tree result.

## Report filename

The default filename is:

```text
<仓库名>-<分支>-<短Commit>-质量-<YYYYMMDD-HHMMSS>.md
```

The repository name is the final `local_path` component. The branch label prefers `report_ref`, otherwise `target_ref`. The legacy `report_branch` field is accepted only for migration and must not conflict with `report_ref`. Replace `/`, `\\`, and whitespace in the label with `-`; use the first 12 Commit characters.

## Executor

Executor configuration must use the suffix `.local.yaml`, remain outside Git, and contain no password:

```yaml
schema_version: 1
executor_id: quality-runner
host: <runner-host>
user: <runner-user>
identity_file: /absolute/path/to/dedicated/private/key
remote_root: /home/<runner-user>/.hygon-governance/quality-runner
uid: <runner-uid>
gid: <runner-gid>
```

Store it at `<workspace>/configs/executors/quality-runner.local.yaml`. Create it with `hygon-governance setup-quality-runner`. The setup command prepares work and cache directories but never downloads a vulnerability database or stores credentials. Never copy executor addresses, key paths, credentials, or remote work directories into a developer report.
