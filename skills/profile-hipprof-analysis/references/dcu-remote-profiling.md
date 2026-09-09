# DCU Remote Profiling Workflow

Use this reference when profiling a workload on a Hygon DCU / DTK machine through SSH and a remote container.

This document is intentionally multi-framework:

- default hardware backend: `hipprof`
- PyTorch attribution backend: `torch.profiler`
- TensorFlow attribution backend: `xprof`
- JAX attribution backend: `xprof`
- other frameworks: `hipprof` only unless the user provides another framework-native profiler explicitly

## Goals

- Optimize the remote model with evidence from profiler traces, logs, and controlled experiments.
- Improve these profiler skills while optimizing: when a repeated gap appears in DCU usage, trace parsing, metric extraction, or experiment automation, patch the skill repo and verify the patch on the same workload.

## Terminology

- Prefer user-facing wording such as GPU/DCU/DTK unless quoting a framework API or trace category.
- Some frameworks still expose GPU APIs under names such as `torch.cuda.*`; treat those as framework API names, not as proof of NVIDIA CUDA.
- Trace categories may still contain names such as `cuda_runtime`; preserve raw category names in analysis, but explain them as runtime API events in the DTK backend.

## Remote Preconditions

Use `$dcu-remote-container-workflow` first to verify:

- SSH login works.
- Target container exists and is running.
- `source /opt/dtk/env.sh` or `source /opt/dtk-26.04/env.sh` works inside the container.
- `hy-smi` sees idle DCU devices.
- The workload workdir and run script exist inside the container.
- The target framework imports successfully inside the container:
  - PyTorch: `import torch`
  - TensorFlow: `import tensorflow as tf`
  - JAX: `import jax`

Never store SSH passwords, private keys, tokens, or host-specific secrets in skill files.

## Target Mapping Policy

Do not write host-specific node/container mappings into this reference.

Use target profiles from `$dcu-remote-container-workflow` instead, for example:

- SSH alias / host profile
- remote user
- container name
- container workdir
- DTK env path
- launcher script or command
- device pinning such as `HIP_VISIBLE_DEVICES`

If there is case-specific profiling history, keep it under `references/cases/` rather than in the generic workflow doc.

## Profiling Strategy

Do not profile the full training job first.

1. Inspect `run.sh`, `main.py`, config, and the real training or inference loop.
   - Preserve environment setup from `run.sh` in short profiling runs, including `source /opt/dtk/env.sh`, `HIP_VISIBLE_DEVICES`, `LD_PRELOAD`, allocator settings, and library paths. Do not retype only the Python command if `run.sh` carries required runtime fixes.
2. Identify the smallest stable repeated unit:
   - one training step if optimizing training
   - one forward/eval step if optimizing inference
3. Add profiler instrumentation around that repeated unit with environment-controlled output.
4. Reduce the first profiling run to a short job, for example one epoch or a small fixed number of steps.
5. Keep warmup separate from measured iterations.
6. Default backend: `hipprof`.
7. Add framework attribution only when model/module/op/path attribution is still missing.

## Default `hipprof` Pipeline

Use `hipprof` first on all DCU workloads, regardless of framework.

Suggested command shape:

```bash
export PROF_OUT=/path/to/outputs/<timestamp>
mkdir -p "$PROF_OUT"

HIPPROF_ENABLE=1 \
hipprof --trace-off --hip-trace --hsa-trace --stats --kernel-stack \
  -o "$PROF_OUT/trace.json" \
  bash -lc 'source /opt/dtk/env.sh && ./run.sh'
```

Expected artifacts:

- `$PROF_OUT/trace.json.hipkernel.csv`
- `$PROF_OUT/trace.json.hiptrace.csv`
- `$PROF_OUT/trace.json.hsatrace.csv`
- optional `$PROF_OUT/trace.json.db`

After the run:

```bash
python scripts/analyze_hipprof_csv.py \
  "$PROF_OUT/trace.json" \
  --export-dir "$PROF_OUT/analysis"
```

What `hipprof` is good at:

- kernel hotspot ranking
- HIP runtime hotspot ranking
- HSA wait/allocation/runtime behavior
- sync or launch-heavy signatures

What `hipprof` does not solve by itself:

- exact model/module path attribution
- framework op / graph / autograd / XLA callsite mapping

In this repo, `hipprof` is also the default remote report path. Treat its exported `report.md` / `analysis.json` as the canonical local artifact unless you explicitly run the standalone PyTorch `torch.profiler` report path.

## Supplementary PyTorch Pipeline

Only add this layer when the `hipprof` result is not enough to locate the exact PyTorch code path.

Typical reasons:

- a top kernel name is generic or template-heavy
- you need to know which module launched `aten::index_select`
- you need autograd or parent stack attribution

Then:

1. add temporary `torch.profiler.record_function(...)` around suspected model subpaths, or
2. patch the loop with `scripts/patch_torch_profiler_template.py`

After the run, use:

```bash
python scripts/analyze_torch_trace.py profiler_trace.json \
  --profile-json profiler_raw.json \
  --export-dir analysis
```

Optional deeper attribution:

```bash
python scripts/analyze_record_function_annotations.py profiler_trace.json \
  --annotation-prefix codex_hstu/ \
  --export-md record_function_attribution.md \
  --export-json record_function_attribution.json

python scripts/analyze_cpu_op_stacks.py profiler_trace.json \
  --op aten::index_add_ \
  --op aten::index_select \
  --export-md cpu_op_stacks.md \
  --export-json cpu_op_stacks.json
```

This path may produce a standalone PyTorch local report. That is a PyTorch-specific supplement, not the default cross-framework report path.

## Supplementary TensorFlow Pipeline

Only add this layer when the `hipprof` result is not enough to locate the exact TensorFlow code path.

Use `xprof`, with two supported modes:

### Mode 1: `xprof-logdir`

Use TensorFlow profiling APIs to emit an XProf-readable logdir:

```python
tf.profiler.experimental.start(logdir)
for step in range(steps):
    with tf.profiler.experimental.Trace("train", step_num=step, _r=1):
        train_step(...)
tf.profiler.experimental.stop()
```

Then view it remotely or locally with:

```bash
xprof "$LOGDIR" -p 8791
```

### Mode 2: `xprof-capture`

Start a TensorFlow profiler server in the running process:

```python
tf.profiler.experimental.server.start(9999)
```

Then let `xprof` capture from the running process.

Use this mode when the job is long-running and you want on-demand collection rather than a manually bounded local logdir.

For TensorFlow, keep `xprof` as a supplementary attribution/UI layer. Do not promise a local `report.md` / `analysis.json` exporter from `xprof`.

## Supplementary JAX Pipeline

Only add this layer when the `hipprof` result is not enough to locate the exact JAX/XLA code path.

Use `xprof`, with two supported modes:

### Mode 1: `xprof-logdir`

Use JAX profiling APIs to emit an XProf-readable logdir:

```python
jax.profiler.start_trace(logdir)
# measured region
jax.profiler.stop_trace()
```

or:

```python
with jax.profiler.trace(logdir):
    ...
```

Add `jax.profiler.TraceAnnotation(...)` or `StepTraceAnnotation(...)` when you need better code-region labels.

Then view it with:

```bash
xprof "$LOGDIR" -p 8791
```

### Mode 2: `xprof-capture`

Start a JAX profiler server in the running process:

```python
jax.profiler.start_server(9999)
```

Then let `xprof` capture from the running process.

This repo currently documents the JAX path but does not fixture-validate it.
For JAX, keep `xprof` as a supplementary attribution/UI layer. Do not promise a local `report.md` / `analysis.json` exporter from `xprof`.

## Other Frameworks

If the workload is not PyTorch, TensorFlow, or JAX:

- use `hipprof` only by default
- do not invent a fake framework attribution layer
- reason from kernels, runtime APIs, waits, and launch behavior
- only add another framework-native profiler if the user explicitly asks for it or the codebase already depends on it

## Measurement Cleanups

For training workloads, make the first trace a clean steady-state trace before drawing model conclusions.

- Avoid batch-0 eval pollution.
- Turn off anomaly detection or expensive debug checks for performance runs unless debugging correctness.
- Disable or reduce hot-loop tensor logging during profiler windows.
- Keep profiler overhead low after the first exploratory run.
- Treat flow/correlation caveats as trace-quality warnings, not direct model conclusions.

## Artifact Layout

Use a timestamped output directory so each iteration is reproducible:

```bash
export PROF_OUT=/path/to/outputs/<timestamp>
mkdir -p "$PROF_OUT"
```

Default human-readable deliverable:

- `report.md` from `hipprof` by default

Structured output only when needed:

- `analysis.json` from supported local analyzers such as `hipprof` or standalone PyTorch `torch.profiler`

Keep copied raw artifacts next to the analysis export so the run is reviewable.

Framework-specific extra artifacts:

- PyTorch: `profiler_trace.json`, `profiler_raw.json`
- TensorFlow/JAX xprof-logdir: `plugins/profile/<timestamp>/*.xplane.pb`
- xprof-capture: the captured session output under the selected XProf logdir

## Recommended Pipeline

1. Remote preflight through `$dcu-remote-container-workflow`.
2. `$profile-hipprof-analysis`:
   - find the real hot loop
   - patch or reuse `hipprof` instrumentation
   - run a short remote profiling job
   - produce the default `hipprof` `report.md`
   - produce `analysis.json` only when needed and only from supported local analyzers
3. If hotspot attribution is still incomplete:
   - PyTorch: add `torch.profiler`
   - TensorFlow: add `xprof`
   - JAX: add `xprof`
   - other frameworks: stay on `hipprof` unless the user explicitly asks for a framework-native profiler
4. `$dcu-optimization-advisor`:
   - consume the profiling outputs
   - inspect `run.sh`, configs, and hot loop
   - produce optimization direction and search space
5. `$dcu-optimization-executor`:
   - run baseline first
   - run controlled single-factor experiments
   - preserve accuracy or loss guards

## Applying It To Remote-Only Code

If the model code exists only inside the remote container:

- Prefer copying the relevant files or a small source snapshot into the local workspace for code inspection and skill development.
- If a remote-only patch is necessary, create timestamped backups before editing.
- Keep profiler patches environment-controlled so they can remain in code without always profiling.
- Pull back the generated artifacts or at least `report.md`, `analysis.json` when present, stdout, stderr, and the patched file diff.
- For TensorFlow/JAX `xprof`, also pull back the logdir or capture output, because that is the actual attribution artifact.

## Skill Improvement Loop

After every profiling or optimization iteration, check whether the skill itself needs an update:

- trace parser fails on DTK-specific event names
- report wording says CUDA where DCU/DTK is clearer
- advisor suggests NVIDIA-only actions without DCU caveats
- executor cannot parse this workload's latency, throughput, loss, accuracy, or step-time logs
- remote workflow needs a repeatable target-profile template
- a manual action repeats and should become scripted

Patch the skill repo in small increments, then verify with at least:

```bash
python -m py_compile <changed-python-files>
python <changed-script> --help
```

For workflow-only changes, verify that `SKILL.md` still points to the right reference files and remains concise.
