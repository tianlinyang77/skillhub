---
name: profile-hipprof-analysis
description: "DCU Profiler 性能分析器。使用 hipprof 作为默认硬件后端分析 DCU 上模型的性能，支持 PyTorch/TensorFlow/JAX 框架的框架层归因。产出 hotspot 报告、bubble 分析、kernel 级性能分解。适用：需要分析 DCU 上模型的 hotspot/bubble/kernel 性能。不适用：非 DCU 环境的 profiling。"
---

# 框架 Profiler 分析

使用此 skill 生成主工作流中的第一个稳定交付产物：

`report.md / analysis.json -> advisor -> executor`

其职责是：
- 从实际运行入口点找到真实测量区域
- 优先运行 `hipprof`
- 仅在路径归因缺失时添加框架归因
- 导出 `report.md`，下游需要时导出 `analysis.json`

默认模式始终是 `hipprof`。框架归因是第二层：

- PyTorch：`torch.profiler`
- TensorFlow：`xprof`
- JAX：`xprof`
- 其他框架：仅 `hipprof`

在 DCU 工作负载上不要习惯性地从框架 profiler 开始。先从 `hipprof` 开始，仅在路径归因缺失时添加框架层。

## 工作流

1. **首先找到测量区域。**
   - 如果当前工作区包含 `run.sh`，默认将其视为规范运行入口点，从那里跟随实际执行路径。
   - 否则，如果用户提供了运行命令、shell 脚本、启动器或配置，将其视为最高优先级入口点，从那里跟随实际执行路径。
   - 否则从用户提示开始（如果他们指定了文件、函数、循环或调用点）。
   - 否则检查代码，寻找**最小的稳定周期性单元**，仍能代表一个真实模型迭代。
   - 将其视为默认 profiling 边界。除非用户显式要求，不要保留额外的外层端到端包装器。
   - 当代码库不熟悉或执行路径不直接时，阅读 `references/hotpath-locating.md`。

2. **慎重选择 profiling 边界。**
   - 对于推理，优先选择围绕 `model(...)`、`generate(...)`、`predict(...)` 或内部评分/排序步骤的一个重复前向单元。
   - 对于训练，优先选择仍具有完整步骤语义的最小重复训练单元；在大多数项目中这是一个 optimizer step。
   - 优先使用最小周期性单元，而非更广泛的包装器（如整个 epoch、整个 eval 函数或整个生成会话）。
   - 排除模型构建、检查点加载和一次性设置，除非用户显式要求启动成本分析。
   - 排除数据加载器和预处理，除非用户显式要求管道分析而非模型分析。
   - 对于 `hipprof`，将预热保持在包装区域之外，仅 trace 稳定的稳态块。

3. **优先使用 `hipprof` 进行插桩。**
   - 如果已有现成的计时代码，复用它；否则在循环中打补丁。
   - 当目标文件已知且区域可用注释标记时，优先使用 `scripts/patch_hipprof_roctracer_template.py`。
   - 使用 `references/patching-template.md` 的标记契约：用 `# HIPPROF_LOOP_START/END` 包裹重复块。
   - 使用 `hipprof --trace-off` 驱动运行，然后在代码内部通过 `roctracer_start()` / `roctracer_stop()` 开始/停止 trace。
   - 将预热与测量迭代分开。
   - 优先同时收集 kernel 和 runtime trace：
     - `--hip-trace`
     - `--hsa-trace`
     - `--stats`
     - 需要符号详情时使用 `--kernel-stack`
   - 保持插桩最小化，使代码路径保持代表性。

4. **收集默认的 `hipprof` 产物。**
   - 将 `-o` 值视为产物前缀，而非保证单个 JSON 文件。
   - 默认预期以下输出：
     - `<prefix>.hipkernel.csv`
     - `<prefix>.hiptrace.csv`
     - `<prefix>.hsatrace.csv`
     - 可选的 `<prefix>.db`
   - 运行 `scripts/analyze_hipprof_csv.py` 导出：
     - `report.md` 作为默认人类可读交付物
     - 复制的 `hipprof` 产物
   - 以下情况导出 `analysis.json`：
     - 用户显式要求结构化输出，或
     - 结果将流入 advisor/executor
   - 将此 `hipprof` 报告视为所有框架的默认报告路径，除非显式生成了单独的 PyTorch `torch.profiler` 报告。

5. **仅在需要时升级到框架归因后端。**

   当首轮 `hipprof` 报告仍无法将 hotspot 关联到具体模型路径、模块、op 家族或训练步骤时使用框架层。

   ### PyTorch 路径

   - 在以下情况下使用 `torch.profiler`：
     - 需要模型/模块路径归因
     - 需要 ATen/autograd 调用点归因
     - 需要 `record_function(...)` 范围
     - 需要 CPU op 堆栈/上下文归因
   - 在这些情况下：
     - 在可疑模块/操作符周围添加临时 `torch.profiler.record_function(...)` 标记，或
     - 使用 `scripts/patch_torch_profiler_template.py` 对循环打补丁
   - 然后运行：
     - `scripts/analyze_torch_trace.py`
     - `scripts/analyze_record_function_annotations.py`
     - `scripts/analyze_cpu_op_stacks.py`
   - 可从此路径生成独立的 PyTorch 报告。这是本仓库中唯一当前导出本地 `report.md` 的非 `hipprof` 路径。

   ### TensorFlow 路径

   - 在以下情况下使用 `xprof`：
     - 需要在自定义训练循环中进行步骤级 trace
     - 需要框架 op/图侧归因
     - 需要 TensorFlow 侧时间线以配合 `hipprof` hotspots
   - 支持两种收集模式：
     - `xprof-logdir` 模式：使用 TensorFlow profiling API 发出 XProf 兼容的 logdir，然后用 `xprof` 检查
     - `xprof-capture` 模式：启动 TensorFlow profiler server，然后让 `xprof` 从运行中的进程捕获 profile
   - 优先使用 `references/tensorflow-xprof.md` 中的手动 start/stop + `Trace(...)` 模式生成 XProf 日志，然后用 `xprof` server 检查。
   - 如果区域简单且有界，可使用 `scripts/patch_tf_xprof_template.py` 打补丁。
   - 对于真实稳态循环，优先：
     - trace 外预热
     - `tf.profiler.experimental.start(logdir)` 发出 XProf 兼容日志
     - `with tf.profiler.experimental.Trace("train", step_num=step, _r=1):`
     - `tf.profiler.experimental.stop()`
   - 对于按需捕获，参见 `references/tensorflow-xprof.md` 中的 TensorFlow profiler server 模式。
   - 此路径的验证夹具为 `fixtures/dummy-tf-xprof-runner/`（**TODO: 该 fixtures 目录尚未入库，验证时可跳过此步骤，或直接在生成的 logdir 上启动 `xprof`**），也可在生成的 logdir 上直接启动 `xprof`。
   - 当任务需要 agent 可读的本地摘要时，在发出的 logdir 或 `xplane.pb` 上运行 `scripts/analyze_xprof_xplane.py`。
   - 保持默认报告锚定在 `hipprof` 上；将 XProf 摘要视为补充归因层，而非硬件报告的替代。

   ### JAX 路径

   - 在以下情况下使用 `xprof`：
     - 需要 JAX/XLA 执行的框架侧时间线
     - 需要 `hipprof` 之外的步骤或代码区域归因
     - 需要与 TensorFlow 匹配的统一 XProf 工作流
   - 支持两种收集模式：
     - `xprof-logdir` 模式：使用 `jax.profiler.start_trace(log_dir)` / `stop_trace()` 或 `jax.profiler.trace(...)` 发出 XProf 兼容的 logdir
     - `xprof-capture` 模式：启动 `jax.profiler.start_server(port)`，然后让 `xprof` 从运行中的进程捕获
   - 需要更好的代码区域标记时使用 `jax.profiler.TraceAnnotation` 或 `StepTraceAnnotation`。
   - 本仓库目前记录了 JAX 路径但未进行夹具验证。
   - 如果 JAX 运行发出标准 XProf `xplane.pb`，可使用相同的 `scripts/analyze_xprof_xplane.py` 摘要路径。
   - 保持 XProf 摘要为补充；不要用它替代默认的 `hipprof` 报告。

   ### 其他框架

   - 如果工作负载不是 PyTorch、TensorFlow 或 JAX，默认不要发明框架归因层。
   - 仅使用 `hipprof`，然后基于 kernels、runtime API、等待和启动行为进行推理。

6. **每次使用相同框架进行分析。**
   - 从 `hipprof` 报告：
     - `hipkernel.csv` 中的 Top-K GPU kernel
     - `hiptrace.csv` 中的 Top HIP runtime API
     - `hsatrace.csv` 中的 Top HSA runtime API
     - 是否存在 sync/wait/allocation/runtime-launch 压力
   - 当运行主要受以下主导时明确指出：
     - kernel 计算
     - 启动/runtime 开销
     - 同步
     - HSA wait
     - allocation/setup 开销
   - 当同时使用框架 profiler 时，将其路径归因与 `hipprof` hotspot 视图结合，而不是替代 `hipprof` 结果。
   - 对于 TensorFlow/JAX `xprof`，将生成的 profile 日志和 `xprof` UI 视为补充归因产物。当任务需要 agent 可读的本地摘要时，使用 `scripts/analyze_xprof_xplane.py` 并将该摘要与 `hipprof` 报告结合，而不是假装 XProf 是主要的硬件报告。
   - 对于 PyTorch，当比较干净 baseline 与消融实验或额外计时标记运行时，使用 `scripts/compare_profiler_runs.py` 而不是手动构建表格。
   - 当任务需要一个以"瓶颈 kernel"和"空泡/拷贝/等待"为中心的简洁交付物时，使用 `scripts/build_perf_triage_report.py` 合并 `hipprof` 加可选的框架归因。

7. **用模型术语解释结果并路由下一个 skill。**
   - 将顶层 kernel 或等待关联回相邻的 runtime API、高级 op 或模型块。
   - 区分模型侧 hotspots 和测量侧产物。
   - 将交付分类为 measurement artifact / bubble-scheduling / kernel-operator / mixed。
   - 在决定下一步是 advisor/executor scheduling 工作还是海光 HIP kernel 工作时，使用 `references/performance-triage-workflow.md`。

## 主要交付物

此 skill 的默认交付物为：

1. `report.md`
   - 简洁的人类可读 profiling 报告
2. `analysis.json`
   - 供 advisor/executor 使用的结构化路由负载

然后：

- advisor 读取 `report.md / analysis.json` 并导出 `optimization_advice.md / optimization_context.json`
- executor 读取 advisor 输出并运行受控实验

## 后端策略

除非用户显式覆盖，使用此后端顺序：

1. 优先 `hipprof`
2. 仅在路径归因缺失时使用框架归因后端
3. 仅在必要时结合两者

本仓库当前的归因映射：

- `torch` → `torch.profiler`
- `tensorflow` → `xprof`
- `jax` → `xprof`（已记录，此处未夹具验证）
- `other` → 仅 `hipprof`

## 实用搜索顺序

定位计时区域时使用此顺序：

1. 当前工作区中的 `./run.sh`
2. 用户提供的运行命令 / shell 脚本 / 启动器 / 配置
3. 用户提供的文件/函数/行提示
4. 现有的 benchmark/perf/eval/test 脚本
5. 现有的计时或 profiling 钩子，如 `hipprof`、`torch.profiler.profile`、`tf.profiler.experimental`、`jax.profiler`、`torch.cuda.Event`、`time.perf_counter`
6. 推理标记：`model(`、`generate(`、`predict(`、`infer`、`evaluate`、`test_step`
7. 训练标记：`loss.backward()`、`optimizer.step()`、`train_step`、`training_step`、`GradientTape`、`apply_gradients`
8. 框架钩子，如 Lightning/HF trainer 入口点或 TensorFlow `Model.fit` 回调

## 补丁规则

- 对最小的重复块打补丁，仍能代表一个真实稳定步骤。
- 优先使用保持 `run.sh` 或用户提供启动器中实际运行路径的补丁；对其到达的代码进行插桩，而非发明并行 benchmark 入口点。
- 避免包装巨大的设置块，当只需要稳态模型性能时。
- 对于 `hipprof`，优先使用 `hipprof --trace-off` 加目标区域周围显式的代码内 start/stop。
- 对于 TensorFlow/XProf，优先使用手动 `start/Trace/stop` 而非过于复杂的自动补丁。
- 保持文件名稳定，以便下游分析脚本可复用它们。

## 资源使用

- 使用 `references/hotpath-locating.md` 获取搜索启发式和边界决策。
- 使用 `references/patching-template.md` 获取 `hipprof`、`torch.profiler` 和 TensorFlow/XProf 补丁协议。
- 当目标工作负载运行在海光 DCU/DTK 远程容器上时使用 `references/dcu-remote-profiling.md`。
- 当协调 profiler 输出与 advisor/executor 决策或决定是否升级到海光 HIP kernel skill 时，使用 `references/performance-triage-workflow.md`。
- 使用 `references/tensorflow-xprof.md` 获取 TensorFlow/XProf 模式、`xprof` server 使用和产物预期。
- 使用 `references/jax-xprof.md` 获取 JAX/XProf 模式、`jax.profiler.start_server(...)` 和 trace/logdir 选项。
- 使用 `scripts/patch_hipprof_roctracer_template.py` 将可复用的 `hipprof` 包装器插入 Python 文件。
- 使用 `scripts/analyze_hipprof_csv.py` 分析 `hipprof` CSV 输出并导出最终报告包。
- 仅在需要 PyTorch 归因时使用 `scripts/patch_torch_profiler_template.py`。
- 使用 `scripts/analyze_torch_trace.py` 分析生成的 torch trace 并导出最终报告包。
- 添加本地 `record_function` 标记后，使用 `scripts/analyze_record_function_annotations.py` 生成标注级归因报告。
- 当热 CPU op 需要从 PyTorch trace 获取具体堆栈/调用点归因时，使用 `scripts/analyze_cpu_op_stacks.py`。
- 当需要比较多个 torch.profiler 导出时，使用 `scripts/compare_profiler_runs.py`。
- 仅对简单有界 TensorFlow 区域使用 `scripts/patch_tf_xprof_template.py`；对于真实循环，优先使用参考文档和夹具中的手动模式。
- 使用 `scripts/analyze_xprof_xplane.py` 将 XProf `xplane.pb` 产物摘要为步骤范围、框架热区域、等待/拷贝信号、GPU 间隙和可选的 hipprof 对齐。
- 当最终交付物应为一个统一性能分诊报告而非分开的硬件/框架报告时，使用 `scripts/build_perf_triage_report.py`。
- 在将 profiling 结果交付给团队成员或下游优化 skill 前，使用 `references/delivery-checklist.md`。
- 使用 `fixtures/dummy-tf-xprof-runner/`（**TODO: 该 fixtures 目录尚未入库，端到端验证可暂跳过**）端到端验证 TensorFlow/XProf 路径。
- 除非确实运行过，不要声称 JAX 路径已通过夹具验证。

## 输出检查清单

尽可能返回以下全部内容：

- 是否使用 `run.sh` 作为规范运行入口点
- 用户提供的运行入口点或发现的入口点
- 检测到的框架
- 精确的被 profile 代码区域
- 使用的硬件 profiling 后端：`hipprof` 或 none
- 使用的框架归因后端：none / `torch.profiler` / `xprof`
- 使用的精确 profiler 命令或入口点
- Top-K 纯 GPU kernel
- Top HIP runtime API
- Top HSA runtime API
- 是否存在 sync/wait/allocation/launch 压力
- 使用框架 profiler 时的框架归因产物路径
- 默认来自 `hipprof` 的 `report.md`，或显式运行独立 PyTorch 报告路径时来自 `torch.profiler`
- 仅在显式请求或下游需要时，来自支持的本地分析器（如 `hipprof`、`torch.profiler` 或 `xprof_summary`）的 `analysis.json`
- 请求 TensorFlow/JAX 归因时的 XProf 摘要输出：步骤范围、顶层框架区域、主机/设备阶段、hipprof 对齐和等待/间隙发现
- 请求时的统一 `性能分诊报告`：一份仅清晰回答三个问题的报告：
  - 哪个 kernel 最值得继续打
  - 当前空泡/等待/拷贝是否已成为主矛盾
  - 下一步该走 kernel 优化还是消空泡路径
- 请求时来自统一分诊导出的辅助产物：
  - `profile_metadata.json`
  - `kernel_table.json`
  - `overlap_opportunities.json`
  - `fuse_opportunities.json`
- 来自统一分诊导出的稳定路由字段：
  - `analysis.json.summary.recommended_route`
  - `analysis.json.summary.recommended_route_reason`
  - `analysis.json.summary.recommended_route_action`
- 下一步分类：measurement artifact / bubble-scheduling / kernel-operator / mixed
- 比较 baseline/消融/诊断运行时的多次运行对比报告
- 导出的产物目录
