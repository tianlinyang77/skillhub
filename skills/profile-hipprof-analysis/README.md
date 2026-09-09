# profile-hipprof-analysis

> 需要分析 DCU 上模型的 hotspot/bubble/kernel 性能，不知道瓶颈在哪时...



## 什么时候用

✅ 需要分析 DCU 上模型的 hotspot/bubble/kernel 性能，不知道瓶颈在哪时

❌ 不要用于: 非 DCU 环境的 profiling

## 快速开始

在本 skill 目录下执行，将输入路径替换为实际采集的 hipprof 文件：

```bash
python scripts/analyze_hipprof_csv.py trace.hipkernel.csv --export-dir profiling-report --export-analysis-json
```

## 输入 → 输出

| 输入 | 输出 |
|------|------|
| hipprof CSV | report.md + analysis.json |

## 完整文档

→ [SKILL.md](SKILL.md)
