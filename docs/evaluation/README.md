# 评估契约

每个已发布 Skill 都必须包含 `evals/evals.json`。结构校验是必需的目录门禁；
未来可以在不改变单个 Skill 数据集结构的前提下，把模型执行的路由与行为评估
加入 CI。

每个数据集必须声明 `"schema_version": 1`，且 `"skill"` 值与发布目录一致。
未知的顶层字段或单用例字段会被拒绝，避免拼写错误静默削弱断言。

## 最低数据集要求

- 至少 3 个 `skill_should_trigger: true` 用例。
- 至少 2 个 `skill_should_trigger: false` 用例。
- 至少 1 个正向用例包含行为断言。
- 用例标识必须唯一、稳定。
- prompt 应接近真实用户请求，而不是只包含关键词的探针。

支持的行为断言字段：

- `expected_behavior`
- `unexpected_behavior`
- `logs_contain`
- `files_exist`

每个断言字段都必须是由非空字符串组成的非空列表。未来执行全目录路由评估时，
其他已发布 Skill 的正向用例应作为当前 Skill 的隐式负向竞争用例。

评估结果必须区分路由证据和行为证据。路由通过不能证明脚本执行正确；强制指定
Skill 后行为通过，也不能证明自动路由会选择该 Skill。

贡献脚手架见
[`templates/skill/evals/evals.json.template`](../../templates/skill/evals/evals.json.template)。
