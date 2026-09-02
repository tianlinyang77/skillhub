# 贡献指南

SkillHub 默认采用单仓维护：正式 Skill 直接保存在本仓库的 `skills/` 下，一次
Pull Request 完成内容评审、目录更新和发布。只有产品团队明确希望 Skill 与产品
代码同仓演进时，才启用远端 component 和同步机制。

## 默认流程：直接向 SkillHub 添加 Skill

### 1. 生成脚手架

在仓库根目录运行：

```bash
python3 scripts/new_skill.py quality-gate-audit \
  --local \
  --owner "Quality Gate Team" \
  --description "Audit a repository when publication readiness must be verified." \
  --license Apache-2.0 \
  --category "Governance and Compliance" \
  --with-openai \
  --with-references
```

`--local` 是推荐写法；省略 `--local` 且未传 `--repo` 时也会进入本地模式。
建议先加 `--dry-run` 查看目标路径。

脚本会自动：

- 在 `skills/<skill-name>/` 生成最终文件名；
- 填写名称、描述、责任团队、目录来源和许可证字段；
- 从仓库根目录复制 `LICENSE`，并在存在时复制 `NOTICE`；
- 生成 `skill-card.md` 和 `evals/evals.json`；
- 按需生成 `agents/openai.yaml` 和已链接的 `references/details.md`；
- 将 Skill 追加到共享的 `components.d/skillhub.yml`。

贡献者不需要手工填写 `repo`、`ref`、`local: true` 或 lock。校验器会把省略的
本地 `repo` 归一为 `HYGON-AI/skillhub`，并拒绝伪造其他来源仓库。

### 2. 完成内容与证据

至少完成以下三个文件：

1. `SKILL.md`：说明触发条件、输入、输出、工作流、边界和安全约束。
2. `skill-card.md`：填写维护联系方式、运行权限和真实验证边界，并把
   `lifecycle: staging` 改为 `published`。
3. `evals/evals.json`：至少 3 个正向触发、2 个负向触发，以及 1 个可观察的
   行为断言。

删除所有 `TODO` 和脚手架占位符。`SKILL.md` 不得超过 500 行；长流程和领域资料
放到 `references/`。脚本、资源、依赖和许可证材料必须包含在 Skill 自身目录中，
保证独立安装后仍可使用。

### 3. 生成目录并校验

```bash
python3 scripts/generate_catalog.py
python3 scripts/validate_skills.py
python3 scripts/validate_agent_skills_spec.py
python3 scripts/generate_catalog.py --check
npx --yes skills@1.5.23 add . --list
npx --yes skills@1.5.23 add . --list --full-depth
```

本地贡献者不需要运行同步命令。CI 中保留的来源检查会自动跳过本地 component；
只有显式采用远端模式时才需要手工执行 `sync_sources.py`。

### 4. 提交一个 Pull Request

```bash
git add skills components.d catalog.json skills.sh.json README.md
git commit --signoff -m "feat(skills): add quality gate audit"
git push
```

默认本地流程只有一个仓库、一个提交序列和一个 Pull Request。

## 例外流程：产品仓自行维护

只有同时满足以下条件时才使用远端模式：

- 产品团队明确承诺在自己的 HYGON-AI 仓库持续维护 Skill；
- Skill 必须与对应代码版本一起演进；
- 团队接受“先合产品仓、再同步 SkillHub”的双 PR 流程。

远端脚手架示例：

```bash
python3 scripts/new_skill.py quality-gate-audit \
  --repo HYGON-AI/quality-gate \
  --source-root ../quality-gate \
  --ref main \
  --owner "Quality Gate Team" \
  --description "Audit a repository when publication readiness must be verified." \
  --license Apache-2.0 \
  --category "Governance and Compliance"
```

远端模式下，先合并产品仓内容，再执行：

```bash
python3 scripts/sync_sources.py --check --component quality-gate
python3 scripts/sync_sources.py --component quality-gate
python3 scripts/generate_catalog.py
python3 scripts/validate_skills.py
```

远端镜像只能由同步脚本更新，不得在 SkillHub 的 `skills/` 中直接修补。

## Skill 发布要求

- 目录名与 `SKILL.md` frontmatter `name` 必须使用小写连字符并完全一致。
- 名称应全局可辨识。产品专用工作流优先采用 `<product>-<action>`；
  `profile`、`benchmark`、`test`、`build`、`deploy` 等裸通用名称会被拒绝。
- `SKILL.md` frontmatter 只使用 Agent Skills 允许的字段：`name`、
  `description`、`license`、`compatibility`、`metadata`、`allowed-tools`。
- description 必须说明能力、触发条件和最近的排除场景。
- 发布目录保持扁平，禁止嵌套其他 `SKILL.md` 或依赖同级 Skill。
- 每个 Skill 必须包含非空 `LICENSE`；需要署名时同时包含 `NOTICE`。
- 禁止发布凭据、私有 endpoint、客户数据、生成缓存、虚拟环境、依赖树和 VCS 元数据。
- 每个包最多 256 个文件；单文件不超过 5 MiB，总大小不超过 20 MiB。
- 任何脚本和外部操作必须声明权限边界，并经过与风险相称的测试。

## Pull Request 检查清单

- [ ] Skill 由 HYGON 编写，或包含经过实质验证的 HCU 适配。
- [ ] 明确的 HYGON 团队负责维护并批准公开发布。
- [ ] 第三方版权、许可证和 NOTICE 义务均已保留。
- [ ] `skill-card.md` 记录 owner、source、license、lifecycle、权限和验证边界。
- [ ] `evals/evals.json` 满足最低路由和行为证据要求。
- [ ] Skill 自包含，不依赖同级 Skill 或仓库外文件。
- [ ] `validate_skills.py`、Agent Skills 参考校验和生成目录检查通过。
- [ ] 普通和 full-depth CLI 只发现预期的已发布 Skill。
- [ ] 若使用远端 component，`sync_sources.py --check` 证明 ref、commit、digest、lock 和镜像一致。
- [ ] commit 使用 `git commit --signoff` 记录 DCO 确认。

目录结构详见[仓库目录规范](docs/architecture/repository-layout.md)，分类选择详见
[目录分类规范](docs/governance/taxonomy.md)，评估要求详见
[评估契约](docs/evaluation/README.md)。
