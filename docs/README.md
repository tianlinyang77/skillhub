# SkillHub 文档

本目录维护 HYGON-AI SkillHub 的架构、策略、评估、发布和安全契约。根目录的
[README](../README.md) 是对外总览，[CONTRIBUTING.md](../CONTRIBUTING.md)
是实际贡献操作指南。

## 按角色选择阅读路径

| 读者 | 从这里开始 | 继续阅读 |
| --- | --- | --- |
| 第一次了解项目 | [根目录总览](../README.md) | [仓库目录规范](architecture/repository-layout.md) |
| Skill 作者 | [贡献指南](../CONTRIBUTING.md) | [分类规范](governance/taxonomy.md)和[评估契约](evaluation/README.md) |
| 目录评审者 | [准入策略](governance/admission.md) | [发布流程](publishing/README.md)和[供应链完整性](security/supply-chain.md) |
| 仓库管理员 | [仓库设置基线](governance/repository-settings.md) | [安全策略](../SECURITY.md) |

## 契约索引

| 问题 | 正式文档 |
| --- | --- |
| 仓库允许哪些路径，由谁维护？ | [仓库目录规范](architecture/repository-layout.md) |
| 哪些 Skill 可以进入公开目录？ | [准入策略](governance/admission.md) |
| Skill 应该使用哪个分类？ | [目录分类规范](governance/taxonomy.md) |
| 必须提供哪些路由和行为用例？ | [评估契约](evaluation/README.md) |
| 默认单仓和可选远端模式如何发布？ | [发布流程](publishing/README.md) |
| 如何验证本地来源及可选远端 commit/digest？ | [供应链完整性](security/supply-chain.md) |
| 哪些 GitHub 外部设置用于强制执行检查？ | [仓库设置基线](governance/repository-settings.md) |

## 状态术语

文档使用三个明确的证据等级：

- **已强制（Enforced）**：仓库内已有校验器、测试或工作流实现该规则，
  并且已经执行相应检查。
- **外部状态（External）**：要求依赖仓库或组织设置，无法仅靠提交文件证明。
- **暂缓（Deferred）**：设计已经记录，但真实生产链路或实际用例尚未提供证据。

当前默认路径是由 SkillHub 直接维护本地 Skill，一次 Pull Request 完成发布。
远端 clone、digest、lock 和 mirror 作为显式例外能力保留，但仍需第一个正式
接入的产品 Skill 证明完整链路。
计划中的 `HYGON-AI/skillhub` 入口和生产仓库设置，在完成迁移和管理员验证前
也属于外部状态。

文档只能描述已经强制执行的行为，或者明确标注为外部状态/暂缓事项。不得把
空目录、提示性检查或计划中的入口当作生产发布门禁的证据。
