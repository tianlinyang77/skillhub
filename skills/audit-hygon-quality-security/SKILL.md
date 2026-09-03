---
name: audit-hygon-quality-security
description: Run a whole-repository HYGON quality and security audit against an exact committed Git ref and generate one Chinese developer remediation report. Require derivative repositories to declare an immutable upstream baseline and scan both baseline and target with identical pinned tools so new or regressed HYGON lint is separated from inherited upstream debt; keep full-tree security safeguards. Use for pre-release Gitleaks, Trivy, Semgrep, forbidden identity, Git abnormal-file, Ruff, ShellCheck, actionlint, yamllint, Lizard, and optional C/C++/CUDA checks. Do not use for license/provenance or HCU/AMD wording audits.
license: LicenseRef-HYGON-Internal
---

# HYGON Quality and Security Audit

在计算节点上调用本 Skill，扫描在组织管理的受控节点执行。Skill 自动通过 SSH 把目标仓库的隔离 bundle 和扫描规则传输到受控节点，在受控节点维护的固定 Docker 镜像和离线 Trivy 数据库上完成扫描，再把结果传回计算节点渲染中文整改报告。**受控节点无需安装任何 Skill**。

## Run an audit

1. 解析请求仓库到 `<workspace>/configs/repos/<repo-id>.yaml` 下注册的 repo-id；`local_path` 指向计算节点上的本地克隆。新配置必须明确声明 `repository_mode`：

   - `fork` 或兼容名称 `derivative`：二次开发仓库。必须填写 `baseline.repository`、`baseline.branch` 和完整 40 位 `baseline.commit`；Tag 可选且只能作为说明。基线 Commit 必须存在于本地仓库；历史被压平等导致官方上游 Commit 不在本地历史时，也允许使用该官方 Commit（非目标祖先），此时引擎将其单独打包并按官方树双层对比。
   - `original`：HYGON 原创仓库。禁止伪造上游基线，执行目标版本全仓扫描。
   存量配置缺少 `repository_mode` 时仅进入兼容模式：目标树扫描仍有效，但来源标为 `unknown`，不得声称完成上游/HYGON 增量归类。存量二次开发配置仅缺少上游仓库或分支展示字段时，可继续按固定 Commit 双树扫描并在报告中提示补齐。
2. 创建或修改仓库配置时阅读 [repository-config-schema.md](references/repository-config-schema.md)。受控节点连接和扫描环境由管理员统一维护，不把执行器初始化作为每次 Skill 调用步骤。
3. 运行：

```bash
python3.12 scripts/audit_quality_security.py \
  --workspace "${HYGON_GOVERNANCE_HOME:-$HOME/.hygon-governance}/quality-security" \
  --repo-id <repo-id>
```

  计算节点没有 python3.12 时可用 python3.9+（脚本会自动使用 checkout 内的 `.venv`）。

4. 引擎自动完成：在计算节点创建包含目标 Commit 可达历史的隔离 bundle → scp 到受控节点 `runs/<run-id>/` → 在受控节点以固定镜像执行 Gitleaks、Trivy、Semgrep、Ruff、ShellCheck、actionlint、yamllint、Lizard → 结果 scp 回计算节点 → 渲染报告到 `<workspace>/reports/<repo-id>/`。

   二次开发仓库必须执行双层扫描：先验证固定上游 Commit（在本地历史中或作为独立官方基线对象存在），再以完全相同的镜像、规则、参数和离线漏洞库分别扫描目标与上游基线；基线不在本地历史时为其单独打包，并输出“新增、恶化、上游继承、相对基线已消失”四类结果。普通上游继承 lint 不计入本次 HYGON 新增质量整改；安全风险仍在全仓结论中保留。任一层扫描失败都使正式扫描无效。

   默认报告文件名必须为 `<仓库名>-<分支>-<短Commit>-质量-<YYYYMMDD-HHMMSS>.md`。分支名中的 `/`、`\\` 和空白转换为 `-`，短 Commit 固定取前 12 位。配置使用精确 Commit 作为 `target_ref` 时，应设置 `report_ref`；旧字段 `report_branch` 兼容读取并在报告中提示迁移。

   C/C++/CUDA 专项检查（cppcheck）默认关闭；仓库配置 `scanners.cpp.enabled: true` 时启用（跳过 vendored/构建目录），需要受控节点存在 `hygon-cpp-quality-tools:1.0.0` 镜像。
5. 退出码解释：

   - `0`：扫描有效；无阻断或待核对发现。
   - `2`：扫描有效；存在阻断或待核对发现。
   - `1`：配置、Git 访问、扫描器、数据库、解析或只读校验失败；不存在质量结论。

6. 返回生成的 Markdown 路径和简明结论。不得暴露原始扫描 JSON、含密钥的源码片段、凭据、SSH 路径或受控节点地址以外的运行细节。

## Enforce scan integrity

- 只扫描 `target_ref` 解析出的精确 40 位 Commit；忽略脏工作树内容。
- 创建包含目标 Commit 可达历史的隔离 Git bundle；不更新私有仓库 refs。
- 外部工具在固定镜像容器中运行：源码只读挂载、无附加能力、扫描期间无网络。只使用受控节点上已有的本地 Trivy DB；审计期间绝不自动更新。
- 受控节点上 `quality-runner` 使用 `mode: ssh`；SSH 私钥只保存在计算节点的受限凭据存储中，不把主机地址、密码、私钥路径或正文、Token 或漏洞库凭据复制进 Skill 包、仓库或报告。
- Semgrep 规则保持本地和版本化；正式扫描绝不使用 `p/python` 等可变在线规则源。
- 对 Gitleaks 输出脱敏。只报告 rule、path、line、Commit 和 fingerprint；绝不报告密钥值。
- 禁止品牌身份命中 Git Commit 作者邮箱或提交者邮箱时，在报告中准确展示完整邮箱，作为历史整改和复核所需证据；明确说明它来自 Commit 元数据而非源码文件。该规则仅适用于邮箱，不得据此展开 Gitleaks 密钥、Token、密码、私钥或其他凭据原文。
- 只忽略已被提交源码和版本化策略证明的确定性变量/模板引用、显式占位符字面量或 marker-only PEM 测试断言。完整 PEM 块、不透明值、源码不可用行或不确定值保持阻断。
- 扫描器失败或 Trivy 数据库缺失/不可读视为扫描无效。当前策略允许 stale 本地数据库，但报告必须披露其时间戳、时效和有限覆盖范围。
- 当前策略下只自动阻断可修复的 CRITICAL Trivy 发现；HIGH 和无可修复方案的高危发现与运行时可达性和工具链兼容性一起评审。
- Semgrep 模式命中视为待核对项，除非版本化策略明确列出经过回归测试的阻断规则。不得仅凭扫描器严重度推断可利用性。
- 只对版本化确定语法或控制流代码阻断 Ruff；动态命名和平台条件结果保留为待核对。
- 二次开发仓库不接受无基线扫描：必须提供上游仓库地址、分支和固定完整 Commit；Commit 通常应为目标祖先，历史被压平等场景允许使用存在于本地仓库的官方上游 Commit（非祖先），此时按官方树双层对比。Tag 名不能替代 Commit。
- 双层扫描必须使用同一版本的扫描镜像、规则、参数和 Trivy 数据库，不得把历史报告与当前目标报告直接相减。
- 普通 lint 只把相对基线新增或恶化的问题计入 HYGON 整改；上游继承 lint 单列为非阻断存量。Trivy、Semgrep 等上游继承安全问题不得归入普通 lint 或静默通过，必须单列“上游继承安全风险与发布处置”，逐项记录升级、缓解、运行时可达性或批准豁免。
- 来源未知的问题不得自动降级，必须保留扫描器原始等级，直到形成可复核的来源结论。
- 密钥、禁止身份、危险软链接、异常 LFS、路径碰撞和控制字符等绝对规则始终扫描目标全仓，绝不因上游已存在而降级。
- 渲染 Markdown 报告后删除原始临时结果。
- 扫描后校验私有仓库快照，发生变化则判定失败。
