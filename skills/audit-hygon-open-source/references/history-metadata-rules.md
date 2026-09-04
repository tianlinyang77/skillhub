# Git 历史元数据审计规则

本规则属于 `$audit-hygon-open-source` 的完整可达历史模式。它只读扫描，不执行历史改写；需要整改时改用受控的 `$sanitize-hygon-git-history`。

## 字段

| 字段 | Git 格式 | 报告名称 |
| --- | --- | --- |
| Author name | `%an` | 作者姓名 |
| Author email | `%ae` | 作者邮箱 |
| Committer name | `%cn` | 提交者姓名 |
| Committer email | `%ce` | 提交者邮箱 |
| Subject | `%s` | Commit 标题 |
| Body | `%b` | Commit 正文 |

正文包括普通消息、说明段落以及 `Signed-off-by`、`Co-authored-by` 等 trailer。

## 策略定义的严重级别

| 字段 | 级别 | 结论 |
| --- | --- | --- |
| 策略定义的阻断标识 | 阻断 | 对外发布前需要完成审批的整改 |
| 策略定义的复核标识 | 复核 | 需要人工确认处理方式 |

调用时必须通过 `--block-term` 和/或 `--review-term` 提供经批准的扫描词。默认使用大小写不敏感的子串匹配；嵌入单词的命中进入报告，但标记为“嵌入子串”，不得与独立 token 混为自动阻断。

## 有效性

- 只扫描目标 Commit 可达的历史。
- shallow repository 返回退出码 `1`，报告结论为“扫描无效”。
- 有阻断或复核项返回退出码 `2`。
- 无命中返回退出码 `0`。
- 报告必须记录解析到的 Commit 数；如与 `git rev-list --count` 不一致，扫描无效。

## 范围边界

- 不扫描文件路径、文件内容、二进制、工作区或未跟踪文件。
- 不检查漏洞、密钥、许可证、文件头或平台运行时输出。
- 不修改 Git 历史；历史改写必须经过独立审批和离线验证。
