---
name: rewrite-hygon-git-identity
description: 审计并安全重写 HYGON 仓库 Git Commit 历史中的禁止或不规范身份字段。适用于 Author Name、Author Email、Committer Name、Committer Email 或 Commit Message 包含大小写不敏感的 sugon/rogon，或者需要把旧邮箱域按相同用户名映射为 @hygon.com 的场景。执行时使用双 mirror、离线 bundle、签名影响审批、严格 Tree 与拓扑验证、临时审核分支以及受保护的 force-with-lease 正式替换。不得用于源码内容清理、许可证头、密钥、CVE、SAST 或普通 git config 修改。
license: Apache-2.0
metadata:
  author: HYGON-AI
  version: "2026.07.23"
---

# HYGON Git Commit 身份历史整改

## 目标

在不修改源码的前提下，完成可审计的 Commit 元数据清理。仅自动执行确定性的邮箱域映射；其他元数据变化必须逐项精确审批，并证明所有未获批准的 Git 数据保持不变。

## 必须阅读

任何历史重写或远程写入前，完整阅读：

- [`references/safety-contract.md`](references/safety-contract.md)：安全约束和停止条件；
- [`references/runbook.md`](references/runbook.md)：精确命令和证据路径。

重新分发本 Skill 前，还要阅读：

- [`references/third-party-notices.md`](references/third-party-notices.md)：内置第三方工具和许可证。

## 运行模式

选择满足请求的最小运行模式：

1. **仅审计**：扫描本地精确 Commit/ref 并生成结果；不修改 Git，不写远程。
2. **准备和离线 dry-run**：创建双 mirror 和证据，完成审计、映射/签名审批、本地专用 mirror 重写及严格验证；不写远程。
3. **发布临时审核分支**：离线验证通过后，必须获得单独明确授权，才能创建一个新的临时审核分支。
4. **正式分支替换**：必须再次获得一条新的明确授权，并写明目标分支、旧 Tip 和新 Tip，才能执行带精确 lease 的正式替换和远程校验。

授权不明确时，默认只执行**仅审计**。

## 不可突破的边界

- 只处理完整 40 位 Commit SHA 或已提交 ref，不处理脏工作树。
- 不在日常开发仓库中重写历史。
- 禁止使用 `git push --mirror`。
- 禁止向远端发布旧历史备份分支或 Tag。
- 禁止模糊替换 `sugon` 或 `rogon`。
- 只自动把精确禁止邮箱域映射为相同用户名的 `@hygon.com`。
- Name、Commit Message 和非标准邮箱必须按原 Commit、字段、旧值和新值逐项审批。
- 不修改源码、依赖、Workflow 或业务逻辑。
- 发生远端 Tip 竞态、映射歧义、签名数量不符、Tree/拓扑差异、意外 ref 变化或必要扫描失败时立即停止。

## 操作流程

### 1. 确认范围

确认：

- 远程仓库 URL；
- 目标分支；
- 维护窗口以及人工或技术冻结状态；
- 私有证据工作目录；
- Python 3.9+ 和 Git 2.36+ 的实际路径；
- 内置 `tools/git-filter-repo` v2.47.0 的路径和校验值。

明确说明：即使文件 Tree 不变，被重写 Commit 及其后代的 SHA 也会改变；正式替换后开发者必须重新克隆。

如果用户只要求本地审计，使用给定 repo/ref 直接进入第 3 步。

### 2. 冻结并准备证据

安全约束要求先暂停，等待用户确认目标分支已经冻结。确认后，按运行手册执行 `scripts/prepare_workspace.py`。

命令必须生成两份独立全新 mirror、离线 bundle、refs 清单、基线、状态文件和 SHA256 清单。任一 mirror 的 Tip 与冻结远端 Tip 不一致时停止。

### 3. 审计 Commit 元数据

对未修改的备份 mirror 或精确本地 ref 执行 `scripts/audit_identity.py`。

退出码解释：

- `0`：全部问题都能使用确定性邮箱映射处理；
- `2`：仍需审批 Name、Message 或非标准邮箱的精确替换；这是待核对状态，不是扫描器崩溃；
- 其他非零值：扫描无效，立即停止。

向用户展示：

- 去重后的邮箱映射及映射文件 SHA256；
- 按元数据字段统计的问题；
- 受影响 Commit 和后代数量；
- 签名 Commit 数量及预计签名丢失数；
- 仍引用旧历史的其他分支和 Tag。

Commit 身份是必要证据，但不要在对话中复制超过整改所需的个人信息。

### 4. 获取精确变更审批

需要精确替换时，填写 `exact-replacements.template.json` 的副本。保留原始 Commit SHA、字段和旧值，用完整的新字段值替换，禁止子串替换。

向审批人展示：

- 可读邮箱映射；
- 权威邮箱映射文件 SHA256；
- 精确替换文件 SHA256（如有）；
- 预计签名丢失数量。

暂停并获取对上述精确值的明确审批。如果证据已经变化，不得沿用旧审批。

### 5. 重写专用 mirror

使用获批哈希、签名丢失数量和内置 `tools/git-filter-repo` 路径执行 `scripts/rewrite_identity.py`。脚本会校验固定工具 SHA256、审计 Tip、映射完整性、精确旧值以及是否仍有未解决禁止字段。

执行失败时，废弃 rewrite mirror 并从新的工作目录重新开始；禁止追加 `--force` 重试。

### 6. 证明重写正确

执行 `scripts/validate_rewrite.py`，只接受 `STATUS=PASS`。

验证器检查：

- 最终 Tree SHA 相同；
- Commit 和 Merge Commit 数量相同；
- 父子拓扑映射一致；
- 只有获批元数据发生变化；
- 未受影响 Commit 对象逐字节相同；
- 签名丢失与获批数量完全一致；
- 禁止身份字段为零；
- 非目标分支和 Tag 未变化。

验证失败时禁止发布任何内容。

### 7. 执行仓库要求的扫描

使用临时审核 Tip 执行仓库要求的全量扫描。组织提供 `$audit-hygon-open-source` 和 `$audit-hygon-quality-security` 时，分别对精确新 Tip 调用。

本 Skill 只负责证明 Commit 身份历史整改正确，不替代全仓合规及质量安全扫描。重写不得新增合规、质量、安全或测试问题。

### 8. 发布临时审核分支

先执行 `scripts/publish_rewrite.py status` 进行只读检查，确认正式远端 Tip 仍等于冻结旧 Tip。

明确告知用户：创建临时审核分支属于外部写入。暂停并取得单独授权后，才执行 `push-review`。此阶段不得修改正式分支。

### 9. 正式替换

人工审核及必要扫描全部通过后再次暂停。要求新的明确授权，且必须写明：

- 目标分支；
- 冻结旧 Tip；
- 验证通过的新 Tip；
- 允许强制替换正式分支。

只有此时才能带 `--execute-approved-cutover` 执行 `publish_rewrite.py cutover`。脚本必须重新读取远端并使用精确 `--force-with-lease`。

### 10. 关闭维护窗口

正式替换后：

1. 验证远端 Tip 等于已验证新 Tip；
2. 再次执行 `audit_identity.py` 并要求零问题；
3. 离线保留 bundle 和校验材料；
4. 解除人工冻结并恢复正常 PR；
5. 提供运行手册中的重新克隆及本地身份配置命令；
6. 未合并工作只允许经过审核的 `cherry-pick`；
7. 对外发布前盘点仍含旧历史的分支、Tag 和 PR。

## 输出要求

简洁报告：

- 审计状态、精确目标 ref 和 Tip；
- 各字段问题数量；
- 获批映射和精确替换哈希；
- 受影响 Commit 和签名数量；
- 旧/新 Tip 及相同 Tree SHA；
- 严格验证结果；
- 临时审核分支状态；
- 正式替换状态；
- 其他旧历史 refs 或开发者后续操作。

只要仍有强制审批、验证、必要扫描、远端校验或开发者交接未完成，就不得宣称任务已经完成。
