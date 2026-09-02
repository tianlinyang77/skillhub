# 目录分类规范

分类是目录元数据，不是嵌套文件系统层级。每个已发布 Skill 都保留在
`skills/<skill-name>/`；`components.d/*.yml` 负责指定分类，生成器据此构建索引。

每个 component 注册必须严格使用以下稳定分类之一：

| 分类值 | 包含 | 不包含 |
| --- | --- | --- |
| Governance and Compliance | 许可证、策略、审计和准入工作流 | 通用文档和普通项目汇报 |
| Developer Tools | 仓库开发、代码评审和通用工程工具 | 明确属于平台、工作负载或算子分类的领域工作流 |
| HCU Platform | 设备、驱动、运行时和环境管理 | 模型工作流、算子实现和通用远程开发 |
| Operator Development | Native、Triton、融合算子，以及主要产物为生产代码的图重写 | 只产生测量结果的 profiling 和报告 |
| Performance and Profiling | Trace 采集、benchmark、诊断和性能报告 | 主要产物是新增或修改算子的工作 |
| Accuracy and Debugging | 数值对比、正确性回归隔离和精度诊断 | 通用测试执行和性能 profiling |
| Training | 模型训练、训练数据和工作负载级分布式训练 | 通信库实现和推理服务 |
| Inference | 模型服务、部署和工作负载级推理优化 | 纯算子实现和通用集群基础设施 |
| Distributed Systems | 通信库、集合通信、存储和集群调度 | Agent 编排和工作负载专用多机流程 |
| CI and Release | 持续集成、打包和发布工程 | 运行时模型部署和通用仓库开发 |
| Documentation | 以文档生成和维护为主要交付物 | profiling、治理或实现过程中附带产生的报告 |

只有至少一个已经准入的 Skill 无法归入现有分类时，才新增分类。校验器会拒绝
列表外的值，因此新增分类必须同时评审本规范和校验器 allowlist。分类拼写属于
稳定的公开元数据；重命名必须重新生成目录，并在 `CHANGELOG.md` 中记录。

分类依据 Skill 的主要产物或它实际修改的制品，而不是它服务的最终目标。实现或
修改算子的代码，即使目标是性能，也归入 `Operator Development`；主要产物是
trace、测量、诊断或报告的工作流归入 `Performance and Profiling`。仅仅使用
多机不代表属于 `Distributed Systems`；该分类只用于底层通信、存储或调度基础设施。

分类是生成 README 和 `skills.sh.json` 使用的唯一货架。component 文件暂不
接受横切 tags。引入 tags 前必须先评审词汇表、校验限制和明确的 `catalog.json`
schema 契约；在此之前禁止自行创造 tag 拼写。

Skill 名称使用全局命名空间。产品专用工作流优先采用描述清晰的
`<product>-<action>`，但这只是指导，不是强制前缀；跨产品 Skill 可以直接使用
清晰的能力名称。校验器拒绝 `add-model`、`profile`、`benchmark`、`test`、
`build`、`deploy` 等含义模糊的裸名称。名称应包含足够上下文，即使产品或仓库
重命名，目录身份仍然清晰稳定。

禁止创建 `skills/<category>/<skill>/`。嵌套分类目录会使 CLI 发现、全局名称
唯一性、同步和目录生成产生歧义。
