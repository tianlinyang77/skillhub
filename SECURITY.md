# 安全策略

不要在公开 issue 中报告漏洞或敏感复现。生产发布前，维护者必须按照
[仓库设置基线](docs/governance/repository-settings.md)启用 Private
Vulnerability Reporting。启用后请使用 **Security → Report a vulnerability**。
在此之前，本预览仓库不声明已经验证的公开接收地址；分享细节前，请通过经过
批准的 HYGON-AI 私密渠道联系仓库维护者。

报告应包含受影响 Skill、源仓及目录 commit、影响范围和最小复现，并移除 secret
和客户数据。

Skill 可能包含可执行脚本和操作指令。安装前必须检查来源所有权、所需权限、
依赖和脚本。发现凭据泄露后应立即撤销；仅从 Git 历史中删除并不足够。

安全修复以当前 `main` 分支为准。已发布 Skill 如存在尚未解决的可利用指令、依赖
或脚本，应从生成索引中移除，直到责任团队提供经过评审的修复。
