---
name: torch-trace-operator-profiler
description: "Analyze a torch.profiler Chrome/Perfetto JSON trace to attribute time across Python scopes, ATen operators, GPU kernels, runtime API overhead and memory copies. Use when diagnosing a slow PyTorch operator, custom extension, Triton kernel or submodule from a captured trace."
license: "Apache-2.0"
compatibility: "Requires Python 3.9+ to run the bundled summary script. Reproducing before/after numbers requires the target GPU and runtime; trace analysis alone does not."
metadata:
  author: "HYGON-AI HCU performance team"
  version: "1.0.0"
---

# Torch Trace Operator Profiler

## Overview

Use this skill to turn a `torch.profiler` JSON trace into an evidence-based operator performance analysis. The goal is to separate Python scope time, CPU/ATen time, GPU kernel time, runtime API overhead, memory copies, and source-level causes before proposing optimizations.

## Workflow

1. State the scope and assumptions.
   - Identify the trace file, target operator names or source-line scopes, and whether the current machine can rerun benchmarks.
   - If the machine lacks the target GPU/runtime, mark before numbers as measured from trace and after numbers as targets or estimates until the user reruns on the real environment.

2. Extract a trace summary.
   - Prefer the bundled script:

```bash
python scripts/torch_trace_scope_summary.py trace.json \
  --target label="substring or exact profiler scope" \
  --target other_label="another scope" \
  --top 25
```

   - Use exact source-line scope names when the user provides them, for example `spconv/pytorch/ops.py(450): get_indice_pairs`.
   - Attribute GPU kernels through HIP/CUDA runtime `correlation` values, not only wall-clock overlap. Use `External id` mainly to group nested CPU/ATen events.

3. Inspect source code for the hot scopes.
   - Follow Python wrapper -> C++ extension binding -> CUDA/HIP/Triton kernel -> allocator/workspace path.
   - Map profiler events to exact source lines: allocations, dtype conversions, sync points, host-device copies, sort/unique calls, gather/scatter calls, GEMM launches, and fallback branches.
   - Keep facts, assumptions, and inferences separate.

4. Decide the bottleneck class.
   - Host/runtime: many `cudaMalloc`/`hipMalloc`, `cudaFree`/`hipFree`, launch overhead, syncs.
   - Memory movement: H2D/D2H/D2D copies, memset, dtype conversion kernels, gather/scatter.
   - Algorithmic: sort/unique, hash-table collision behavior, repeated small GEMMs, unfused gather-GEMM-scatter.
   - Compute/ISA: a small number of dominant custom kernels after overheads are removed.
   - Fallback/configuration: unexpected Python fallback, disabled implicit path, missing extension, dtype/device mismatch.

5. Build the optimization plan in priority order.
   - Start with high-confidence fixes from measured overheads.
   - For fused operators, propose the minimal fusion boundary and required backward/autograd path.
   - For Triton/TorchInductor, trace back from generated kernel to FX graph semantics and consider a narrow graph pass or custom op only when it reduces real measured work.
   - For CUDA/HIP assembly, ask for architecture details only after the trace shows custom kernels, not host/runtime or library calls, dominate.

6. Produce a report.
   - Include: methodology, before baseline table, per-scope kernel/runtime breakdown, source mapping, optimization plan, before/after comparison table, verification commands, and unverified risks.
   - Never present projected after numbers as measured results.

## Useful Script

`scripts/torch_trace_scope_summary.py` parses Chrome trace JSON and prints:

- event category counts
- per-target call count, total, avg, p50/p90/p99/max
- nested CPU/ATen event breakdown
- HIP/CUDA runtime correlation count
- attributed GPU kernel, memcpy/memset, and runtime API summaries

If a trace is too large for local memory, fall back to `rg`/`jq` sampling or open it in Perfetto to inspect the same scopes visually.

## Report Checklist

- The target scope names and trace file are named.
- Before numbers are trace-derived and reproducible.
- GPU kernel attribution uses runtime correlation when available.
- Source-code claims cite exact files and lines.
- Optimizations are ranked by measured impact and implementation risk.
- After numbers are either measured on the target GPU or clearly labeled as expected targets.
- The final handoff includes commands to rerun benchmarks and regenerate the summary.
