---
schema_version: 1
owner: das-test
license: Apache-2.0
lifecycle: published
source:
  repo: HYGON-AI/skillhub
  path: skills/profile-hipprof-analysis
---
# Skill Card


## Summary

DCU Profiler 性能分析器。使用 hipprof 作为默认硬件后端分析 DCU 上模型的性能，支持 PyTorch/TensorFlow/JAX 框架的框架层归因。产出 hotspot 报告、bubble 分析、kernel 级性能分解。适用：需要分析 DCU 上模型的 hotspot/bubble/kernel 性能。不适用：非 DCU 环境的 profiling。


## Owner

das-test


## Source

Locally maintained at `HYGON-AI/skillhub`, path `skills/profile-hipprof-analysis`.


## License

Declared as `Apache-2.0`; see original source licensing and any preserved LICENSE/NOTICE material. Import does not relicense this content.


## Runtime and permissions

需要海光设备、hipprof 及被分析模型对应的框架和依赖。需要执行性能采集命令、读取性能数据、按所选流程修改采集入口并写入分析报告的权限。具体要求参见 SKILL.md 和随附脚本。


## Local catalog import

This copy is maintained in `HYGON-AI/skillhub` at `skills/profile-hipprof-analysis`, not synchronized upstream. Existing instructions, attribution and validation statements describe the imported source; review their applicability before publishing this copy. No skill code was executed by the importer.
