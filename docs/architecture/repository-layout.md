# 仓库目录规范

## 设计原则

- 本仓库是默认的 Skill 唯一事实来源，一次 Pull Request 完成发布。
- `skills/` 保持扁平，每个直接子目录都是一个可独立安装的 Skill。
- 分类、责任人、评估和许可证证据结构化保存并由校验器强制。
- 远端同步只作为产品团队显式选择的例外能力保留。
- 模板和候选项必须不可被普通及 full-depth 发现。

## 正式目录树

```text
skillhub/
├── .github/                  # Pull Request 模板、所有权和 CI
├── components.d/             # 本地默认注册及可选远端注册
├── docs/                     # 架构、治理、评估、发布和安全说明
├── scripts/                  # 脚手架、校验、生成及可选同步工具
├── staging/                  # 不可发现的 SKILL.md.candidate
├── templates/                # 不可发现的贡献脚手架
├── tests/                    # 回归测试
├── skills/                   # 已发布的扁平 Skill 软件包
├── catalog.json              # 自动生成目录元数据
├── skills.sh.json            # 自动生成 skills CLI 元数据
└── .skillhub-lock.json       # 仅记录显式远端 component 的 commit/digest
```

## 所有权与修改方式

| 路径 | 唯一事实来源 | 是否允许直接修改 |
| --- | --- | --- |
| 本地 `skills/<name>/` | 本仓库 | 可以，必须通过 PR |
| 远端 component 对应的 `skills/<name>/` | 已注册产品仓库 | 不可以，必须同步 |
| `components.d/skillhub.yml` | 本仓库 | 脚手架自动更新，人工变更需评审 |
| 其他 `components.d/*.yml` | 对应产品团队与目录维护者 | 可以，必须通过 PR |
| `staging/` | 本仓库 | 可以，但只能使用 `SKILL.md.candidate` |
| `catalog.json`、`skills.sh.json` | 生成器输出 | 不可以手工修补 |
| `.skillhub-lock.json` | 同步程序输出 | 不可以手工修补 |

## 单个 Skill 目录

```text
skills/<skill-name>/
├── SKILL.md                  # 必需：指令和 Agent Skills 触发元数据
├── skill-card.md             # 必需：owner、source、license、lifecycle 和验证边界
├── evals/
│   └── evals.json            # 必需：路由和行为用例
├── agents/
│   └── openai.yaml           # 推荐：UI 和调用元数据
├── references/               # 可选：详细说明
├── scripts/                  # 可选：确定性且经过测试的辅助程序
├── assets/                   # 可选：模板和输出资源
├── LICENSE                   # 必需：独立安装后的许可证正文
└── NOTICE                    # 许可证要求时必需
```

统一使用 `references/`，不要创建 `docs/`、`reference/` 或嵌套 Skill 目录。
`SKILL.md` frontmatter 只允许 Agent Skills 规定的六个字段；目录分类放在
component 注册中，责任人和验证信息放在 `skill-card.md`。

发布包最多 256 个文件，单文件不超过 5 MiB，总大小不超过 20 MiB。缓存、
依赖树、虚拟环境、VCS 元数据、符号链接、特殊文件和大小写冲突路径都会被拒绝。

## 生命周期

```text
脚手架或不可发现候选
          |
          v
      内容与证据评审
          |
          v
 skills/<name>/ published
          |
          v
 自动生成 catalog 元数据
```

本地 Skill 直接在功能分支的 `skills/` 中完成即可；未经评审的长期原型可以使用
`staging/<name>/SKILL.md.candidate`。`staging/` 下任何真正的 `SKILL.md` 都会
被拒绝，防止 full-depth 客户端意外发现。

远端 Skill 仅在产品团队主动选择时采用两阶段流程：先合并产品仓，再同步到
SkillHub。同步镜像仍遵守完全相同的目录、证据和发布门禁。
