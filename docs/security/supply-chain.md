# 供应链与来源完整性

## 默认本地 Skill

本地 Skill 的唯一事实来源就是本仓库：

- component 使用 `local: true`；
- 省略的 `repo` 自动归一为 `HYGON-AI/skillhub`；
- 显式填写其他 repo 会被拒绝；
- source path 必须精确等于 `skills/<catalog_dir>`；
- 内容、注册、评估、许可证和生成目录在同一个 Pull Request 中评审。

本地 Skill 不需要远端 clone、commit lock 或目录镜像，也不会在
`.skillhub-lock.json` 中生成条目或保存远端内容 digest。它的完整性依赖 Git
提交历史、受保护分支、required checks、CODEOWNERS、DCO 和人工评审，而不是
远端 commit/digest 提供的加密来源证明。

## 显式远端 Skill

当产品团队选择在自己的 HYGON-AI 仓库维护 Skill 时，额外使用以下完整性机制：

- component 记录仓库、ref、源路径、目录名和分类；
- 同步程序将 ref 解析为具体 commit；
- `.skillhub-lock.json` 记录 commit 和源目录 SHA-256 digest；
- 发布镜像只能由同步程序生成；
- check 模式同时比较远端解析结果、lock 和发布目录。

同步前会拒绝不安全路径、符号链接、特殊文件、嵌套 Skill、缓存和超限软件包。
失败时必须保持已有目录状态不变，不允许用手工修改镜像掩盖来源漂移。

## 信任边界

来源一致性不等于内容可信。无论本地还是远端，发布前都必须独立检查：

- 维护责任和公开发布批准；
- 第三方版权、许可证和 NOTICE；
- 脚本、网络、文件写入和外部操作权限；
- 正向、负向和行为评估；
- 真实运行证据及其适用边界。

CI workflow 只有在 GitHub 分支保护或 ruleset 中配置为 required check 后才是
强制门禁；仅仅存在 workflow 文件不能阻止直接 push 或无评审合并。
