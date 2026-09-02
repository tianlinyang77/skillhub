# Skill 准入策略

进入 `skills/` 表示该软件包可以被公开发现和独立安装，不只是“有一个
`SKILL.md`”。所有本地和远端 Skill 必须满足相同质量门禁。

## 1. 所有权和来源

- 默认来源是本仓库 `HYGON-AI/skillhub`，由 `local: true` component 管理。
- 每个 Skill 必须有明确的 HYGON 维护团队和可持续联系方式。
- 只有产品团队显式承担维护责任时，才允许登记远端 HYGON-AI 仓库。
- 未经修改的第三方 Skill 不得作为 HYGON-AI Skill 发布；应链接正式上游。
- HCU 适配内容必须保留上游版权、许可证和 NOTICE。

## 2. 可移植性

- 一个直接子目录对应一个 Skill，目录名与 frontmatter `name` 完全一致。
- 安装目录必须自包含，禁止依赖同级 Skill 或仓库外文件。
- `SKILL.md` 不超过 500 行，详细内容放入 `references/`。
- 禁止嵌套 `SKILL.md`、残留 `.template`、缓存、依赖树、虚拟环境和 VCS 元数据。
- 所有 Markdown 相对链接必须留在 Skill 目录内且真实存在。

## 3. 结构化证据

每个发布包必须包含：

- `skill-card.md`：schema version、owner、source、license、published lifecycle、
  运行权限和验证边界；
- `evals/evals.json`：至少 3 个正向、2 个负向和 1 个带行为断言的正向用例；
- 非空 `LICENSE`，以及许可证要求的 `NOTICE`；
- 实际工作流所需的全部脚本、references 和 assets。

## 4. 安全与权限

- 禁止凭据、私有 endpoint、客户数据和未公开产品信息。
- 网络、写文件、执行命令、远端操作和破坏性行为必须在 Skill Card 中声明。
- 可执行脚本必须经过人工评审和与风险相称的测试。
- 校验通过只证明静态契约成立，不能代替真实运行验证。

## 5. 发布门禁

本地 Skill 必须通过：

- 仓库单元测试；
- `validate_skills.py`；
- Agent Skills 固定参考实现校验；
- 生成目录一致性检查；
- 普通和 full-depth CLI 发现检查；
- DCO 检查和代码评审。

远端 Skill 还必须通过 `sync_sources.py --check`，证明 ref、具体 commit、源目录
digest、lock 条目和发布镜像一致。

任何检查失败时不得把 staging、部分验证或静态结果描述为已发布、已通过或已在
真实环境验证。
