# 发布流程

## 默认本地流程

1. 运行 `scripts/new_skill.py --local`，直接在 `skills/<name>/` 生成软件包。
2. 完成 `SKILL.md`、`skill-card.md`、`evals/evals.json` 和许可证材料。
3. 把 Skill Card lifecycle 改为 `published`，清除所有脚手架占位符。
4. 生成 README、`catalog.json` 和 `skills.sh.json`。
5. 执行结构校验、Agent Skills 参考校验和普通/full-depth CLI 发现。
6. 通过一个经过评审且带 DCO sign-off 的 Pull Request 合并。
7. 从干净 checkout 验证发布仓库中的发现和安装结果。

本地 component 可以省略 `repo`，但校验后公开来源始终固定为
`HYGON-AI/skillhub`。本地 Skill 不需要 clone、digest 或 lock 条目。

## 可选远端流程

远端模式只适用于明确由产品仓维护的 Skill：

1. 在对应 HYGON-AI 产品仓中完成自包含软件包并合并。
2. 添加或更新该产品的远端 component 注册。
3. 以 check 模式确认仓库、ref、解析 commit、源路径和目录目标。
4. 应用同步，生成镜像、内容 digest 和 lock 条目。
5. 执行与本地 Skill 相同的全部发布门禁。
6. 通过 SkillHub Pull Request 合并镜像与目录元数据。

产品仓是远端 Skill 的唯一事实来源。同步失败时保持 SkillHub 状态不变，修复
产品源或 component 定义后重新执行；不得直接修改目录镜像。

## 生成内容

`catalog.json`、`skills.sh.json` 和 README 标记区块由生成器维护。
`.skillhub-lock.json` 只记录远端 component。不要手工修补这些文件。

## 发布前最低证据

- 责任团队批准公开发布；
- 许可证和 NOTICE 义务已核对；
- 软件包自包含且权限边界明确；
- 3 个正向触发、2 个负向触发和至少 1 个行为断言；
- 代表性环境的真实验证及其限制；
- 目录、官方参考实现和 CLI 发现检查通过；
- 远端模式额外通过 commit/digest/lock 一致性检查。
