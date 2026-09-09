# Automatic profiling patch template

Use the backend that matches the current need:

- default hardware backend: `scripts/patch_hipprof_roctracer_template.py`
- PyTorch attribution backend: `scripts/patch_torch_profiler_template.py`
- TensorFlow attribution backend: `xprof` with `scripts/patch_tf_xprof_template.py` as an optional helper

## 1. Default mode: `hipprof`

Use `scripts/patch_hipprof_roctracer_template.py` when you already know the file and roughly know the smallest stable periodic block to trace on DCU.

### Marker protocol

Insert these markers around the exact block to wrap:

```python
# HIPPROF_LOOP_START
for batch in dataloader:
    outputs = model(batch)
    loss = criterion(outputs)
# HIPPROF_LOOP_END
```

Notes:
- Put the start/end markers around the whole repeated block, usually the loop.
- For `hipprof`, tracing starts at region entry and stops at region exit.
- Keep warmup outside the marked block. Do not rely on the wrapper to skip startup iterations.
- `# HIPPROF_STEP` is optional and only kept for marker symmetry; it is not required for `hipprof` output.

### Script usage

Patch in place:

```bash
python scripts/patch_hipprof_roctracer_template.py path/to/file.py \
  --label train-step \
  --in-place
```

Or write to a new file:

```bash
python scripts/patch_hipprof_roctracer_template.py path/to/file.py \
  --label infer-step \
  --output path/to/file_hipprof.py
```

### Runtime environment variables

The inserted helper is runtime-controlled so the code can remain patched without always tracing.

- `HIPPROF_ENABLE=1`: enable in-code `roctracer_start/stop`; default disabled
- `HIPPROF_ROCTRACER_LIB=/opt/dtk/roctracer/lib/libroctracer64.so`: optional override when the library is not in the default DTK path

Example:

```bash
HIPPROF_ENABLE=1 \
hipprof --trace-off --hip-trace --hsa-trace --stats --kernel-stack \
  -o outputs/run/trace.json \
  python train.py
```

Then run:

```bash
python scripts/analyze_hipprof_csv.py \
  outputs/run/trace.json \
  --export-dir outputs/run/report
```

Expected default artifacts:

- `outputs/run/trace.json.hipkernel.csv`
- `outputs/run/trace.json.hiptrace.csv`
- `outputs/run/trace.json.hsatrace.csv`
- optional `outputs/run/trace.json.db`

## 2. PyTorch attribution mode: `torch.profiler`

Use `scripts/patch_torch_profiler_template.py` only when `hipprof` has already identified the hotspot class, but you still need model/module/op path attribution.

### Marker protocol

Insert these markers around the exact block to wrap:

```python
# TORCH_PROFILER_LOOP_START
for batch in dataloader:
    outputs = model(batch)
    loss = criterion(outputs)
    # TORCH_PROFILER_STEP
# TORCH_PROFILER_LOOP_END
```

Notes:
- Put the start/end markers around the whole repeated block, usually the loop.
- Put `# TORCH_PROFILER_STEP` once per logical iteration, normally after one full inference step or one optimizer step.
- Prefer the smallest repeated unit. Do not wrap a larger outer function if the inner loop is the true periodic hotpath.
- If no step marker is present inside the block, the script inserts `_torch_profiler_step(__torch_profiler)` at the end of the wrapped block.

### Script usage

Patch in place:

```bash
python scripts/patch_torch_profiler_template.py path/to/file.py \
  --label train-step \
  --in-place
```

Or write to a new file:

```bash
python scripts/patch_torch_profiler_template.py path/to/file.py \
  --label infer-step \
  --output path/to/file_profiled.py
```

### Runtime environment variables

- `TORCH_PROFILER_ENABLE=1`: enable profiling; default disabled
- `TORCH_PROFILER_TRACE=/path/to/trace.json`: export Chrome/Perfetto trace
- `TORCH_PROFILER_JSON=/path/to/profile.json`: export structured Top-K profile summary
- `TORCH_PROFILER_TOPK=40`: Top-K operator rows to keep
- `TORCH_PROFILER_SYNC_EACH_STEP=0|1`: whether to synchronize before each `prof.step()`
- `TORCH_PROFILER_RECORD_SHAPES=0|1`
- `TORCH_PROFILER_PROFILE_MEMORY=0|1`
- `TORCH_PROFILER_WITH_STACK=0|1`

Example:

```bash
TORCH_PROFILER_ENABLE=1 \
TORCH_PROFILER_TRACE=outputs/run/profiler_trace.json \
TORCH_PROFILER_JSON=outputs/run/profiler_raw.json \
python train.py
```

Then run:

```bash
python scripts/analyze_torch_trace.py \
  outputs/run/profiler_trace.json \
  --profile-json outputs/run/profiler_raw.json \
  --export-dir outputs/run/report
```

## 3. TensorFlow attribution mode: `XProf`

Use `scripts/patch_tf_xprof_template.py` only for simple bounded regions. For real steady-state loops, prefer the manual pattern in `references/tensorflow-xprof.md` and `fixtures/dummy-tf-xprof-runner/`.

### Bounded-region marker protocol

Insert these markers around the exact bounded block to wrap:

```python
# TF_XPROF_REGION_START
outputs = model(batch, training=True)
loss = loss_fn(labels, outputs)
# TF_XPROF_REGION_END
```

Notes:
- This script wraps the selected region with `tf.profiler.experimental.start/stop` to generate a logdir for `xprof`.
- It is suitable for smoke tests and simple bounded regions.
- It is **not** the preferred way to profile a long training loop.
- For a real loop, use manual warmup plus per-step `Trace(...)`:

```python
tf.profiler.experimental.start(logdir)
for step in range(steps):
    with tf.profiler.experimental.Trace("train", step_num=step, _r=1):
        train_step(...)
tf.profiler.experimental.stop()
```

### Script usage

Patch in place:

```bash
python scripts/patch_tf_xprof_template.py path/to/file.py \
  --label train-step \
  --in-place
```

Or write to a new file:

```bash
python scripts/patch_tf_xprof_template.py path/to/file.py \
  --label infer-step \
  --output path/to/file_xprof.py
```

### Runtime environment variables

- `TF_XPROF_ENABLE=1`: enable XProf instrumentation; default disabled
- `TF_XPROF_LOGDIR=/path/to/logdir`: TensorFlow profiler output directory
- `TF_XPROF_TRACE_NAME=train`: trace label override

Example:

```bash
TF_XPROF_ENABLE=1 \
TF_XPROF_LOGDIR=outputs/run/tf_xprof \
python train.py
```

Expected default artifacts:

- `outputs/run/tf_xprof/plugins/profile/<timestamp>/*.xplane.pb`

The generated logdir is intended to be opened with `xprof`, and it can also be summarized locally:

```bash
python scripts/analyze_xprof_xplane.py \
  outputs/run/tf_xprof \
  --export-dir outputs/run/tf_xprof_summary \
  --export-analysis-json
```

If a matching `hipprof` report already exists, add:

```bash
  --hipprof-analysis-json outputs/run/hipprof_report/analysis.json
```

Typical view command:

```bash
xprof outputs/run/tf_xprof -p 8791
```

## When to prefer manual patching instead

Do not use the template scripts if:

- the target region is split across multiple files or callbacks
- the real step boundary is not representable by a single repeated block
- the loop body contains control flow that makes marker wrapping misleading
- the TensorFlow workload needs per-step `Trace(...)` around a real steady-state loop

In those cases, patch manually but keep the same backend-specific artifact contract:

- `hipprof`: `*.hipkernel.csv` + `*.hiptrace.csv` + `*.hsatrace.csv`
- `torch.profiler`: trace JSON + profile JSON + exported report package
- `tensorflow/xprof`: logdir with `plugins/profile/<timestamp>/*.xplane.pb`
