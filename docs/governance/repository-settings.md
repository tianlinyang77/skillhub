# 仓库设置基线

Workflow 文件定义了检查，但不会自动让这些检查成为强制门禁。在把 SkillHub
视为生产目录前，管理员必须在发布仓库中应用并验证以下 GitHub 设置。

## `main` 分支规则

使用 branch ruleset 或 branch protection rule 保护 `main`，并满足：

- 必须通过 Pull Request，并至少获得 1 个 approval；
- 所有权路径必须经过 CODEOWNERS 评审，旧 commit 上的 approval 自动失效；
- 最新 commit 上的 `validate (3.11)`、`validate (3.12)` 和 `dco` 必须通过；
- 合并前必须解决所有 conversation，并保证分支为最新状态；
- 禁止 force push 和删除分支；
- 同样适用于管理员和自动化，除非存在范围严格且经过审计的 bypass 记录。

在对应检查至少在发布仓库执行过一次之前，不要把其名称选为 required status
check。workflow 或 job 重命名后必须重新核对所选名称。

## 仓库安全与贡献设置

- 启用 Web commit sign-off，使浏览器创建的 commit 遵循 DCO 策略。可选远端
  同步 commit 已使用 `git commit --signoff`。
- 启用 Private Vulnerability Reporting 后，才能引导外部报告者使用
  **Security → Report a vulnerability**。
- 保持 secret scanning 和 push protection 开启。
- 启用依赖告警和安全更新，并让自动化变更走与其他贡献相同的评审路径。
- 关闭未使用的发布入口；workflow token 只授予各 workflow 声明的权限。
- 只有跨仓库访问确实需要时才保存 `SKILLHUB_SYNC_TOKEN`；其权限只允许读取
  源仓库，且绝不能暴露给 fork workflow。

## 发布前验证

正式宣布目录入口前，管理员必须记录以下证据：

1. 直接 push 到 `main` 无法绕过评审；
2. 任一 Python 校验 job 或 `dco` 失败时，Pull Request 无法合并；
3. workflow、校验器、模板、来源注册和已发布 Skill 都会请求 CODEOWNERS 评审；
4. 可以提交私密漏洞报告，而无需创建公开 issue；
5. 显式启用远端 component 后，手动同步 workflow 可以创建带 sign-off 的
   Pull Request，但不能自行合并；首次准入远端 component 时，管理员必须明确
   记录是否恢复定时同步及其频率；未启用远端来源时不安排定时同步。

仓库设置属于外部状态。应定期复核，并在仓库迁移、fork 提升、workflow 重命名
或默认分支变更后重新验证。
