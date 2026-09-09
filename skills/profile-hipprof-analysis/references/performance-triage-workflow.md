# Performance triage workflow: hipprof first, then bubble or kernel branch

Use this reference when coordinating the profiler/advisor/executor skills with DCU remote execution and Hygon HIP kernel optimization.

## One-line operating model

Always start with `$profile-hipprof-analysis` on the real workload path, using `hipprof` as the default backend. Classify the bottleneck from profiler evidence, then route to either **bubble/scheduling optimization** or **kernel/operator optimization**. Add `torch.profiler` only when kernel or runtime hotspots still cannot be tied to a concrete model/module/op path. Escalate to `$kernel-hip-baseline` + `$kernel-hip-optimize` only after the hot operator/kernel is stable, correctness constraints are known, and PyTorch/config-level fixes are insufficient.

## Skill sequence

```text
(optional) $dcu-rag-kb
  -> (optional, if target is another node/container) $dcu-remote-container-workflow
  -> $profile-hipprof-analysis
  -> $dcu-optimization-advisor
  -> $dcu-optimization-executor
  -> if kernel/operator remains dominant:
       $kernel-hip-baseline
       $kernel-hip-optimize
```

## Gate 0: make the measurement trustworthy

Before optimizing, check that the profiler window measures the intended steady-state unit.

- Prefer one full optimizer step for training or one repeated forward/generation unit for inference.
- Exclude one-time setup, checkpoint load, dataset construction, and compile warmup unless explicitly measuring them.
- Watch for measurement-boundary artifacts: a single huge CPU op, async tail, or profiler synchronization at the first/last step.
- Run `hipprof` first to establish kernel, HIP runtime, and HSA runtime hotspots.
- If the first `hipprof` report cannot tie a kernel to code, add `torch.profiler.record_function(...)` markers around suspected modules/operators and run `analyze_record_function_annotations.py`.
- Compare clean baseline vs diagnostic/ablation runs with `compare_profiler_runs.py` on the torch side when you need attribution diffs; do not judge only by one profiled run.

## Gate 1: bubble/scheduling branch

Choose this branch when GPU utilization is low or total bubble is a large part of the profiled region, especially when dispatch-exposed, sync, copy, or host-prep components dominate.

### What to inspect

Trace the delay from high level to low level:

```text
Python/API call
  -> ATen/C++ op
  -> runtime launch / memcpy / sync
  -> kernel event
```

Look for:

- explicit sync/readback: `.item()`, `.cpu()`, `.numpy()`, `torch.cuda.synchronize()`, metric logging, printing device tensors, checkpoint/eval barriers;
- host preparation inside the step: Python loops, dynamic shape/index construction, CPU-side sampling, tokenizer/dataloader work, repeated allocation or type/device conversion;
- copy/layout overhead: host-to-device or device-to-host copies, missing pinned memory/non-blocking transfer, unexpected dtype/layout/device conversions;
- launch overhead: many small ATen ops, tiny kernels, Python control flow between kernels, dynamic graph breaks;
- post-launch dependency: kernels waiting on streams/events, collectives, preceding long kernels, or forced ordering.

### Typical actions

- Move invariant CPU work out of the steady-state step.
- Remove or defer readbacks/synchronization.
- Batch/vectorize small Python-loop ops.
- Try targeted `torch.compile` placement, CUDA/HIP Graph style steady-state capture, or local operator fusion when shapes/control flow are stable.
- Use existing config knobs first; keep batch size, precision, and TF32 frozen unless the user explicitly opens them.
- Validate with profiler-off and profiler-on comparisons if profiler perturbation is suspected.

## Gate 2: kernel/operator branch

Choose this branch when GPU busy time is high, bubbles are small, and one or a few kernels/operators dominate device time.

### What to inspect

- Map the top kernel name back to its launch CPU op using `analysis.json` and, when needed, `record_function_attribution.json`.
- Identify whether the hot kernel is caused by a model-level operation, loss/sampler, optimizer, framework fallback, or custom extension.
- Inspect tensor shapes, dtype, layout, index distribution, duplication, sparsity, and whether the op appears in forward, backward, or optimizer step.
- Check whether a semantic config knob changes the hot path; any such change needs accuracy/quality validation.

### PyTorch/operator-level actions before custom kernel

- Remove redundant work, e.g. repeated normalization, repeated gather/scatter, or recomputed indices.
- Reduce scatter/gather pressure: deduplicate indices, pre-aggregate, split dense vs sparse paths, or change optimizer if sparse gradients are intended.
- Replace an inefficient op pattern with an equivalent fused or batched pattern.
- Try layout/static-shape changes only when they match code evidence.
- Consider torch source patching or custom fused op only when the hot `aten::...` op is stable and dominates across clean runs.

### Escalate to Hygon HIP kernel skills when

- the hot op/kernel remains dominant after reversible PyTorch/config experiments;
- the operator contract is clear: inputs, shapes, dtype, semantics, tolerance, and validation command;
- a Python/Torch reference can be written or extracted;
- the expected win is worth a custom HIP/CK Tile maintenance cost.

Then use:

1. `$kernel-hip-baseline` to create a correctness-checked HIP/DCU baseline and harness from Torch/CUDA/Triton/TileLang/CUTLASS/reference code;
2. `$kernel-hip-optimize` to run measured HIP/CK Tile iterations with hipprof, DTK tooling, branch selection, ablation, and ISA checks.

## Advisor/executor responsibilities

- `$dcu-optimization-advisor` owns the decision memo: classify scheduling vs kernel vs diagnostic, list code evidence, choose landing sites, and emit a structured `search_space`.
- `$dcu-optimization-executor` owns controlled experiments: unchanged baseline first, single-factor runs, then targeted combinations. It records exact env/command deltas and correctness/quality guards.
- Executor should not silently perform large manual rewrites. For risky op rewrites or custom kernels, record them as deferred/manual actions and hand off to the kernel skills.

## Output that makes the next step unambiguous

A good handoff contains:

- real entrypoint and profiled region;
- `report.md`, `analysis.json`, and optional `record_function_attribution.json`;
- dominant classification: measurement artifact / bubble-scheduling / kernel-operator / mixed;
- top bubble source or top kernel/operator with evidence;
- code landing site and reversible first experiments;
- semantic/accuracy validation command if an optimization may change training or model quality;
- decision on whether custom HIP/CK Tile kernel work is justified.
