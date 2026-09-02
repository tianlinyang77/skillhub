# Component 注册

Component 只负责把 Skill 映射到目录分类和责任域。新增 Skill 时优先运行
`scripts/new_skill.py --local`，不要手工维护注册内容。

## 默认：本地 component

`components.d/skillhub.yml` 是默认入口：

```yaml
name: SkillHub
local: true
description: Directly maintained HYGON-AI SkillHub skills.
skills:
  - path: skills/example-skill
    catalog_dir: example-skill
    category: Developer Tools
```

本地 component 可以省略 `repo` 和 `ref`。校验器会把它们固定归一为
`HYGON-AI/skillhub` 和 `main`，并拒绝把 `local: true` 伪装成其他来源仓库。
本地 `path` 必须精确等于 `skills/<catalog_dir>`。

## 例外：远端 component

只有产品团队明确在自己的仓库维护 Skill 时才创建独立 component：

```yaml
name: Quality Gate
repo: HYGON-AI/quality-gate
ref: main
description: Repository publication and compliance gates.
skills:
  - path: skills/quality-gate-audit
    catalog_dir: quality-gate-audit
    category: Governance and Compliance
```

远端仓库必须属于 `HYGON-AI`。一个远端仓库只能由一个 component 注册，其中
所有 Skill 使用同一 ref；暂不支持单仓多 ref 或 Skill 级 ref override。

`category` 必须来自[目录分类规范](../docs/governance/taxonomy.md)白名单。
名称应全局可辨识，裸通用名称会被校验器拒绝。远端模板见
[`templates/component.yml.template`](../templates/component.yml.template)。
