# 变更记录

这里记录所有重要的目录、策略、校验和分发变更。可选远端 Skill 的自动生成更新
可以按 release 合并记录。

## 未发布

### 新增

- 为已发布 Skill、staging、评估、产品仓联邦和生成目录元数据建立分层仓库基础。
- 正式的目录结构、准入、评估、发布和供应链文档。
- 生产仓库设置基线，覆盖受保护评审、required checks、DCO、私密漏洞报告和同步权限。
- 不可被发现的贡献模板。
- 产品 Skill 生成器，支持确定性命名、占位符替换、LICENSE/NOTICE 复制和 component 注册。
- 可选 reference 脚手架，并从生成的 `SKILL.md` 条件链接。
- 本地优先贡献模式：Skill 直接由本仓库维护，一次 Pull Request 完成发布。

### 变更

- 按读者路径、发布职责、当前证据和明确暂缓边界重组对外 README 与文档索引。
- 目录分类采用强制 allowlist、主要产物判定规则和明确的包含/排除边界；精度与正确性调试使用独立分类。
- 发布前拒绝含义模糊的裸目录名、残留 `.template` 文件和未解决脚手架占位符。
- Pull Request 在 Python 3.11/3.12 上校验；DCO 和可选同步使用声明的最低 Python 3.11。
- `new_skill.py` 默认本地生成，支持显式 `--local`，并保留 `--repo` 远端模式。
- `local: true` component 允许省略 `repo`，但校验后来源必须严格归一为
  `HYGON-AI/skillhub`，本地路径必须等于 `skills/<catalog_dir>`。
- 远端同步默认仅允许手动触发；首次准入远端 component 时必须明确记录是否恢复
  定时同步及其频率。
- Skill 生成器对明显的标准许可证声明冲突给出 warning，但不替代人工 LICENSE/NOTICE 评审。
- 已发布 Skill 必须包含 Skill Card 和最低路由/行为数据集。
- 扁平目录拒绝嵌套 `SKILL.md` 依赖。
- 对每个 Skill 软件包递归校验相对 Markdown 链接。
- 远端 lock 条目记录并验证源目录 SHA-256 digest。
- 同步程序复制源内容前拒绝符号链接和特殊文件。
- Agent Skills frontmatter 支持并校验全部六个规范字段，同时拒绝供应方专用顶层字段。
- Skill Card 和 Eval 数据集携带 schema version 与来源/身份绑定，并在发布前校验。
- 远端检查绑定 ref、commit、源 digest、lock 条目和发布目录；发布包同时限制文件数量、大小、缓存和跨平台路径冲突。
- 准入例外使用经过校验的 schema，且不能同时指向已注册发布来源。
- Staging 候选项使用 `SKILL.md.candidate`；拒绝 `staging/` 下真正的 `SKILL.md`，并在 CI 验证 full-depth 发现。
- CI 固定外部 Action 和 CLI 版本，运行固定 Agent Skills 参考校验器，验证 CLI 发现并强制 DCO sign-off。

### 暂缓

- 远端 clone、sparse-checkout、digest 和 lock 链路仍需首个正式准入产品 Skill
  验证；仅本地校验不能建立该证据。首次准入同时决定是否启用定时同步。
