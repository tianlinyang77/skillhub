# TensorFlow XProf on DCU

Use this reference when the workload is TensorFlow and the first-pass `hipprof` result needs framework-side attribution.

The unifying backend name is `xprof`.

- `tf.profiler.experimental.*` is the common way to produce the profile logdir
- `xprof` is the server/UI entrypoint that reads that logdir

## Role split

- `hipprof`: default hardware hotspot view
  - kernels
  - HIP runtime
  - HSA runtime
  - sync / wait / launch pressure
- `xprof`: TensorFlow-side attribution
  - step ranges
  - framework op / graph timeline
  - TensorFlow profiler logs for TensorBoard/XProf tooling

Do not replace `hipprof` with `xprof`. Pair them.

Important boundary:

- default local report stays on the `hipprof` side
- `xprof` is a supplementary attribution and UI layer
- this repo now provides a lightweight `xprof_summary` exporter through `scripts/analyze_xprof_xplane.py`
- the summary is not a replacement for `hipprof`; it is a framework-side companion view

## Mode 1: xprof-logdir

Use this mode when you want deterministic, scriptable collection without a live capture step.

For a custom training loop, keep warmup outside the measured window and use `Trace(...)` on each measured step:

```python
import tensorflow as tf

warmup_steps = 2
measured_steps = 10
logdir = "outputs/tf_xprof"

for _ in range(warmup_steps):
    train_step(...)

tf.profiler.experimental.start(logdir)
for step in range(measured_steps):
    with tf.profiler.experimental.Trace("train", step_num=step, _r=1):
        train_step(...)
tf.profiler.experimental.stop()
```

Why this pattern:

- warmup is excluded
- measured steps are explicit
- step numbers are preserved
- resulting profile logs map cleanly to the steady-state region

## Mode 2: xprof-capture

Use this mode when the target process is long-running and you want on-demand capture from `xprof`.

TensorFlow-side pattern:

```python
import tensorflow as tf

tf.profiler.experimental.server.start(9999)
```

After the profiler server is up and the model is running, capture from `xprof`.

OpenXLA’s TensorFlow XProf guide documents sampling mode through `tf.profiler.experimental.server.start` and capture from XProf.\
Source: OpenXLA\
https://openxla.org/xprof/tensorflow_profiling

## Expected artifacts

TensorFlow profiler outputs go under:

```text
<logdir>/plugins/profile/<timestamp>/*.xplane.pb
```

The important success condition is that at least one `*.xplane.pb` exists.

Then open it with `xprof`:

```bash
xprof <logdir> -p 8791
```

Example check:

```bash
find outputs/tf_xprof/plugins/profile -name '*.xplane.pb' -print
```

## Viewing with `xprof`

Typical local launch:

```bash
xprof /tmp/tf-xprof-fixture -p 8791
```

The current environment already has `/usr/local/bin/xprof`, and starting it on a generated logdir works.

## Summary boundary

For this repo, do not treat `xprof` as the default hardware report generator.

- If you need the default local report, keep using `hipprof` and `analyze_hipprof_csv.py`
- If you need TensorFlow-side attribution, open the `xprof` logdir in the UI
- If you need an agent-readable local summary, run:

```bash
python skills/profile-hipprof-analysis/scripts/analyze_xprof_xplane.py \
  /tmp/tf-xprof-fixture \
  --hipprof-analysis-json /tmp/tf-hipprof-report/analysis.json \
  --export-dir /tmp/tf-xprof-summary \
  --export-analysis-json
```

This summary is intended to provide:

- step ranges
- top framework op / region
- top host/device regions
- wait / copy signals
- GPU gaps
- optional alignment with `hipprof` top kernels

## When to use the patch helper

`scripts/patch_tf_xprof_template.py` is intentionally conservative.

Use it only when:

- the region is simple and bounded
- you want a fast smoke test
- you are not trying to add per-step loop semantics automatically

For long training loops, patch manually.

## Minimal validation fixture

This repo includes:

```text
fixtures/dummy-tf-xprof-runner/
```

It verifies:

- TensorFlow imports correctly
- `tf.profiler.experimental.start/stop` works
- `Trace("train", step_num=...)` works
- `*.xplane.pb` is emitted on the current DTK/DCU environment
- `xprof <logdir>` can be launched on the emitted logdir

This fixture validates `xprof-logdir` mode. It does not validate live capture mode.
It also validates that the emitted `xplane.pb` can be consumed by the local `xprof_summary` exporter.

Typical run:

```bash
cd fixtures/dummy-tf-xprof-runner
TF_XPROF_ENABLE=1 TF_XPROF_LOGDIR=/tmp/tf-xprof-fixture bash run.sh
find /tmp/tf-xprof-fixture/plugins/profile -name '*.xplane.pb' -print
xprof /tmp/tf-xprof-fixture -p 8791
```

Optional local summary export:

```bash
python ../../skills/profile-hipprof-analysis/scripts/analyze_xprof_xplane.py \
  /tmp/tf-xprof-fixture \
  --export-dir /tmp/tf-xprof-summary \
  --export-analysis-json
```
