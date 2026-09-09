# JAX XProf on DCU

Use this reference when the workload is JAX and the first-pass `hipprof` result needs framework-side attribution.

## Role split

- `hipprof`: default hardware hotspot view
  - kernels
  - HIP runtime
  - HSA runtime
  - sync / wait / launch pressure
- `xprof`: JAX/XLA-side attribution
  - step ranges
  - XLA/JAX timeline
  - profile logdir for XProf
  - capture workflow through a running profiler server

Do not replace `hipprof` with `xprof`. Pair them.

Important boundary:

- default local report stays on the `hipprof` side
- `xprof` is a supplementary attribution and UI layer
- if JAX emits a standard `xplane.pb`, this repo can summarize it with `scripts/analyze_xprof_xplane.py`
- the summary is supplementary and does not replace the default `hipprof` report

## Mode 1: xprof-logdir

Use this mode when you want deterministic, scriptable collection without a live capture step.

Typical patterns:

```python
import jax.profiler

jax.profiler.start_trace("/tmp/profile-data")
# run measured region
jax.profiler.stop_trace()
```

or:

```python
import jax.profiler

with jax.profiler.trace("/tmp/profile-data"):
    # run measured region
    ...
```

For better labeling, add:

```python
with jax.profiler.TraceAnnotation("train_step"):
    ...
```

or use `StepTraceAnnotation`.

Then open the result with:

```bash
xprof /tmp/profile-data -p 8791
```

## Mode 2: xprof-capture

Use this mode when the target program is long-running and you want on-demand capture from `xprof`.

In the JAX program:

```python
import jax.profiler

jax.profiler.start_server(9999)
```

This starts the profiler server that `xprof` can connect to.

Relevant official docs:

- `jax.profiler.start_server(port, requires_backend=True)` starts the profiler server.\
  Source: JAX docs\
  https://docs.jax.dev/en/latest/_autosummary/jax.profiler.start_server.html
- The JAX profiling guide documents both `start_trace(...)` and `start_server(...)`, and describes manual capture plus XProf usage.\
  Source: JAX docs\
  https://docs.jax.dev/en/latest/profiling.html
- OpenXLA’s XProf JAX guide shows the XProf server plus `jax.profiler.start_server(...)` flow.\
  Source: OpenXLA\
  https://openxla.org/xprof/jax_profiling

## Expected artifacts

For logdir-based collection, expect:

```text
<logdir>/plugins/profile/<timestamp>/*.xplane.pb
```

For capture mode, the exact logdir is determined by the XProf session configuration, but the end result should still be XProf-readable profile artifacts under the chosen logdir.

## Scope in this repo

- JAX is documented here so the skill can present a unified `xprof` workflow.
- This repo does not currently include a JAX fixture or automated validation.
- If the environment lacks JAX or XProf capture prerequisites, fall back to `hipprof` and say so directly.
- If a task needs a written conclusion, combine the `hipprof` report with the `xprof_summary` export and observations from the `xprof` UI.
