# 端到端操作手册

必须先完整阅读 `safety-contract.md`，再使用本手册。

## 1. 定义路径

```bash
SKILL_DIR=/absolute/path/to/rewrite-hygon-git-identity
PYTHON=/usr/bin/python3.9
GIT_BIN=/absolute/path/to/git
FILTER_REPO="$SKILL_DIR/tools/git-filter-repo"
REMOTE=git@github.com:HYGON-AI/example.git
BRANCH=main
WORKSPACE=/absolute/private/path/git-history-rewrite/example-YYYYMMDD
```

要求：

- Python 3.9 或更高版本；
- Git 2.36 或更高版本；
- 内置固定 `git-filter-repo v2.47.0`，SHA256：
  `67447413e273fc76809289111748870b6f6072f08b17efe94863a92d810b7d94`。

不要替换系统 Git，通过 `GIT_BIN` 选择批准的 Git 可执行文件。不要替换内置 `git-filter-repo`，重写脚本会拒绝校验值不同的文件。

## 2. 创建双 mirror 和证据

确认分支冻结后执行：

```bash
"$PYTHON" -B "$SKILL_DIR/scripts/prepare_workspace.py" \
  --remote "$REMOTE" \
  --branch "$BRANCH" \
  --workspace "$WORKSPACE" \
  --git-bin "$GIT_BIN"
```

该步骤对远端只读，并生成：

```text
repository-backup.git
repository-rewrite.git
repository-before.bundle
evidence/
  baseline.env
  refs-before.tsv
  state.json
  SHA256SUMS
```

禁止在 `repository-backup.git` 中执行重写命令。

## 3. 审计所有可达 Commit 元数据

```bash
"$PYTHON" -B "$SKILL_DIR/scripts/audit_identity.py" \
  --repo "$WORKSPACE/repository-backup.git" \
  --ref "refs/heads/$BRANCH" \
  --output "$WORKSPACE/evidence/audit" \
  --git-bin "$GIT_BIN"
```

退出码：

- `0`：全部问题都可使用确定性禁止邮箱域映射；
- `2`：Name、Message 或非标准邮箱需要精确替换；
- 其他非零值：扫描或环境无效。

人工检查：

```text
audit-report.md
offending-commit-fields.tsv
proposed-email-map.tsv
proposed-email-map.json
exact-replacements.template.json
affected-signed-commits.txt
other-refs-with-old-history.tsv
```

`proposed-email-map.json` 是权威输入，TSV 只用于人工阅读。

## 4. 处理精确值问题

如果 `EXACT_REPLACEMENTS_REQUIRED` 非零，复制模板：

```bash
cp \
  "$WORKSPACE/evidence/audit/exact-replacements.template.json" \
  "$WORKSPACE/evidence/audit/approved-exact-replacements.json"
```

每一项都必须保留 `commit`、`field` 和 `old_b64`，然后把完整新字段值的 Base64 写入 `new_b64`。

允许字段：

- `author_name`
- `author_email`
- `committer_name`
- `committer_email`
- `message`

Commit Message 必须编码包含末尾换行的完整消息。新值不得包含大小写不敏感的 `sugon` 或 `rogon`。

编码示例：

```bash
printf 'approved replacement\n' | base64 -w0
```

不要添加无关的干净字段。重写脚本要求获批 Key 与审计阻断项完全一致。

## 5. 记录审批哈希

```bash
EMAIL_MAP="$WORKSPACE/evidence/audit/proposed-email-map.json"
EMAIL_MAP_SHA256=$(sha256sum "$EMAIL_MAP" | awk '{print $1}')

EXACT_CHANGES="$WORKSPACE/evidence/audit/approved-exact-replacements.json"
EXACT_CHANGES_SHA256=$(sha256sum "$EXACT_CHANGES" | awk '{print $1}')
```

向审批人展示映射、精确变化、哈希和 `PREDICTED_SIGNATURE_LOSS`。暂停，只有审批人明确批准上述精确值后才能继续。

## 6. 重写专用 mirror

没有精确替换时：

```bash
"$PYTHON" -B "$SKILL_DIR/scripts/rewrite_identity.py" \
  --repo "$WORKSPACE/repository-rewrite.git" \
  --ref "refs/heads/$BRANCH" \
  --audit-dir "$WORKSPACE/evidence/audit" \
  --email-map "$EMAIL_MAP" \
  --email-map-sha256 "$EMAIL_MAP_SHA256" \
  --approved-signature-loss <APPROVED_COUNT> \
  --filter-repo "$FILTER_REPO" \
  --output "$WORKSPACE/evidence/rewrite" \
  --git-bin "$GIT_BIN"
```

有精确替换时，追加：

```bash
  --exact-changes "$EXACT_CHANGES" \
  --exact-changes-sha256 "$EXACT_CHANGES_SHA256"
```

命令失败时，废弃 `repository-rewrite.git` 并从新的工作目录重新开始，禁止追加 `--force`。

## 7. 严格验证

没有精确替换时：

```bash
"$PYTHON" -B "$SKILL_DIR/scripts/validate_rewrite.py" \
  --old-repo "$WORKSPACE/repository-backup.git" \
  --new-repo "$WORKSPACE/repository-rewrite.git" \
  --old-ref "refs/heads/$BRANCH" \
  --new-ref "refs/heads/$BRANCH" \
  --rewrite-output "$WORKSPACE/evidence/rewrite" \
  --email-map "$EMAIL_MAP" \
  --expected-signature-loss <APPROVED_COUNT> \
  --output "$WORKSPACE/evidence/validation" \
  --git-bin "$GIT_BIN"
```

有精确替换时，追加：

```bash
  --exact-changes "$EXACT_CHANGES"
```

只有 `validation-result.json` 报告 `PASS` 才能继续。

## 8. 只读远端竞态检查

```bash
"$PYTHON" -B "$SKILL_DIR/scripts/publish_rewrite.py" status \
  --state "$WORKSPACE/evidence/state.json" \
  --rewrite-result "$WORKSPACE/evidence/rewrite/rewrite-result.json" \
  --validation-result "$WORKSPACE/evidence/validation/validation-result.json" \
  --rewrite-repo "$WORKSPACE/repository-rewrite.git" \
  --review-branch "rewrite/$BRANCH-hygon-identity" \
  --git-bin "$GIT_BIN" \
  --output "$WORKSPACE/evidence/publication"
```

正式分支 Tip 不一致时立即停止。

## 9. 发布临时审核分支

先读取验证后的新 Tip：

```bash
NEW_TIP=$(
  "$GIT_BIN" -C "$WORKSPACE/repository-rewrite.git" \
  rev-parse "refs/heads/$BRANCH"
)
```

获得单独的审核分支发布授权后执行：

```bash
"$PYTHON" -B "$SKILL_DIR/scripts/publish_rewrite.py" push-review \
  --state "$WORKSPACE/evidence/state.json" \
  --rewrite-result "$WORKSPACE/evidence/rewrite/rewrite-result.json" \
  --validation-result "$WORKSPACE/evidence/validation/validation-result.json" \
  --rewrite-repo "$WORKSPACE/repository-rewrite.git" \
  --review-branch "rewrite/$BRANCH-hygon-identity" \
  --confirm-new-tip "$NEW_TIP" \
  --git-bin "$GIT_BIN" \
  --output "$WORKSPACE/evidence/publication"
```

对临时审核 Tip 执行仓库要求的全量合规及质量安全扫描并保存报告。正式分支仍保持不变。

## 10. 受保护正式替换

读取冻结旧 Tip：

```bash
OLD_TIP=$(
  "$GIT_BIN" -C "$WORKSPACE/repository-backup.git" \
  rev-parse "refs/heads/$BRANCH"
)
```

再次暂停，取得明确写明 `BRANCH`、`OLD_TIP` 和 `NEW_TIP` 的正式替换授权。随后由管理员执行：

```bash
"$PYTHON" -B "$SKILL_DIR/scripts/publish_rewrite.py" cutover \
  --state "$WORKSPACE/evidence/state.json" \
  --rewrite-result "$WORKSPACE/evidence/rewrite/rewrite-result.json" \
  --validation-result "$WORKSPACE/evidence/validation/validation-result.json" \
  --rewrite-repo "$WORKSPACE/repository-rewrite.git" \
  --review-branch "rewrite/$BRANCH-hygon-identity" \
  --confirm-branch "$BRANCH" \
  --confirm-old-tip "$OLD_TIP" \
  --confirm-new-tip "$NEW_TIP" \
  --execute-approved-cutover \
  --git-bin "$GIT_BIN" \
  --output "$WORKSPACE/evidence/publication"
```

命令会再次校验远端旧 Tip，并使用精确 force-with-lease。

## 11. 正式替换后

对全新 mirror 或全新拉取的正式 ref 再次执行 `audit_identity.py`，必须得到零禁止字段。

随后解除冻结并向开发者发送：

```bash
git clone --branch "$BRANCH" "$REMOTE" <new-directory>
cd <new-directory>
git config --local user.name "Zhang San"
git config --local user.email "zhangsan@hygon.com"
git config --local user.useConfigOnly true
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
```

有未合并工作的开发者必须从重写后的正式分支创建新分支，再 `cherry-pick` 经过审核的 Commit。禁止把旧本地或旧远端分支 Merge 回新历史。
