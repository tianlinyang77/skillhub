# Staging 候选区

本目录存放需要长期保留但尚未准入的候选 Skill 和评审 fixture。普通贡献可以
直接在功能分支的 `skills/` 中完成，不要求先经过 staging。这里的内容不会发布、
索引、同步，也不能从目录安装。

显式采用远端 component 的产品候选仍应保留在产品仓库，禁止复制到这里形成
第二事实来源。

每个候选项使用 `staging/<skill-name>/SKILL.md.candidate`。`staging/` 下禁止
真正的 `SKILL.md`，否则 deep-discovery 客户端可能把未经评审的候选项误认为
已发布 Skill。校验时会把候选项复制到隔离临时目录，并仅在那里重命名入口。

发布必须作为独立提升变更：移动到 `skills/<skill-name>/` 并把入口重命名为
`SKILL.md`，添加本地 component 注册和所需证据，再重新生成并校验目录。
