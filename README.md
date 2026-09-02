# HYGON-AI SkillHub

HYGON-AI SkillHub 是一个经过治理的可移植
[Agent Skills](https://agentskills.io/specification) 仓库，面向 HCU 软件、
基础设施、训练、推理、算子开发和通用工程工作流。

默认模式很简单：**Skill 直接保存在本仓库，一次 Pull Request 完成发布。**
仓库仍保留可选的产品仓同步能力，但只有产品团队明确希望 Skill 与代码同仓维护时
才启用。

## 本地查看与安装

查看仓库中可发现的 Skill：

```bash
npx --yes skills@1.5.23 add . --list
npx --yes skills@1.5.23 add . --list --full-depth
```

安装一个 Skill 到 Codex：

```bash
npx --yes skills@1.5.23 add . \
  --skill skillhub-contributor \
  --agent codex \
  --yes
```

普通发现和 full-depth 发现必须得到相同的正式发布集合；模板和 staging 候选项
不得被发现。

## 仓库目录

| 路径 | 用途 |
| --- | --- |
| [`skills/`](skills) | 已发布、可独立安装的扁平 Skill 软件包 |
| [`components.d/`](components.d) | 分类与来源注册；默认共享本仓 `local: true` component |
| [`staging/`](staging) | 不可发现的 `SKILL.md.candidate` 原型 |
| [`templates/`](templates) | 不可发现的贡献脚手架 |
| [`scripts/`](scripts) | 脚手架、校验、生成和可选同步工具 |
| [`tests/`](tests) | 校验器和脚手架回归测试 |
| [`docs/`](docs) | 架构、治理、评估、发布与安全说明 |
| [`catalog.json`](catalog.json)、[`skills.sh.json`](skills.sh.json) | 自动生成的目录元数据 |

`skills/` 的每个直接子目录都是一个独立 Skill。已发布 Skill 内禁止嵌套其他
`SKILL.md`，也不得依赖安装时不会复制的同级目录。

## Skill 目录

<!-- catalog:start -->

| Product | Description | Skills |
|---|---|---|
| **SkillHub** | Directly maintained HYGON-AI SkillHub skills. | [`skillhub-contributor`](skills/skillhub-contributor) |

<!-- catalog:end -->

## 按分类浏览

<!-- categories:start -->

1 skill across 1 category.

### Developer Tools

| Skill | Product | Description |
|---|---|---|
| [`skillhub-contributor`](skills/skillhub-contributor) | SkillHub | Create, review, and onboard portable Agent Skills into HYGON-AI SkillHub. Use when adding or updating a SkillHub package, preparing its metadata and evaluations, or diagnosing catalog validation; use remote synchronization only when a product team explicitly owns the source skill in another HYGON-AI repository. |

<!-- categories:end -->

## 添加 Skill

默认在仓库根目录运行：

```bash
python3 scripts/new_skill.py quality-gate-audit \
  --local \
  --owner "Quality Gate Team" \
  --description "Audit repositories when publication readiness must be verified." \
  --license Apache-2.0 \
  --category "Governance and Compliance" \
  --with-openai \
  --with-references
```

脚本直接创建 `skills/quality-gate-audit/`，复制根 LICENSE，并自动追加本地
component 注册。贡献者只需完成 `SKILL.md`、`skill-card.md`、
`evals/evals.json` 中的真实内容，然后运行：

```bash
python3 scripts/generate_catalog.py
python3 scripts/validate_skills.py
python3 scripts/validate_agent_skills_spec.py
python3 scripts/generate_catalog.py --check
```

完整流程和检查清单见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 发布模型

### 默认：本仓直接维护

- `components.d/skillhub.yml` 使用 `local: true`；
- `repo` 可以省略，校验器会固定归一为 `HYGON-AI/skillhub`；
- Skill 直接在 `skills/` 中修改；
- 不执行 clone、digest 或镜像更新；
- 一次 Pull Request 完成发布。

### 可选：产品仓自行维护

如果产品团队明确要求 Skill 与产品代码同仓演进，可以注册远端 HYGON-AI
component。此时产品仓是唯一事实来源，SkillHub 只接受同步生成的镜像，并使用
具体 commit、内容 digest 和 `.skillhub-lock.json` 验证来源一致性。

## 信任边界

- CLI 能发现 Skill，只能证明格式和目录兼容，不能证明行为正确。
- Schema 和 eval 数据通过，不代表脚本安全或适用于所有环境。
- 发布前仍需评审权限、可执行程序、依赖、许可证和真实验证边界。
- 未经修改的第三方 Skill 不得包装成 HYGON-AI Skill；应链接正式上游。

## 正式入口

仓库迁移到正式组织并验证分支保护后，计划使用：

```bash
npx skills add HYGON-AI/skillhub --list
npx skills add HYGON-AI/skillhub
```

迁移完成前，以当前 checkout 的本地发现和 CI 结果为准。

## 许可证

除非 Skill 目录另有声明，仓库代码和本仓自有内容使用
[Apache License 2.0](LICENSE)。每个可独立安装的 Skill 仍需携带自己的
`LICENSE`，需要署名时同时携带 `NOTICE`。
