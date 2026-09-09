# Delivery Checklist

Use this checklist before handing profiler results to a teammate, downstream
skill, or the next optimization stage.

This is intentionally lightweight. It does not replace the profiler workflow.
It only checks that the current profiling package is complete enough to keep
moving without re-reading the whole run from scratch.

## A. Environment

- [ ] project path is known
- [ ] real `run.sh` / launch command is recorded
- [ ] device selection env is known when applicable
- [ ] short-run control is known (`ITERATIONS`, `STEPS`, `EPOCHS`, or equivalent)
- [ ] log/output path is known
- [ ] source mutation policy is explicit (`env_only_first`, `allow_local_patch`, or project-defined)
- [ ] `profile_metadata.json` exists
- [ ] `observed_arch` is recorded
- [ ] DTK/ROCm version or DTK path is recorded
- [ ] profiler backend is recorded
- [ ] framework attribution backend is recorded when used

## A2. Acceptance Contract

- [ ] primary performance metric is declared
- [ ] quality/accuracy metric is declared when optimization may affect semantics
- [ ] `semantic_contract` is declared: output/training/algorithm semantics are preserved by default
- [ ] `benchmark_contract` is declared: metric and measurement scope are preserved by default
- [ ] allowed quality regression is declared or explicitly deferred
- [ ] minimum validation length is declared
- [ ] long-run validation need is declared
- [ ] accuracy / metric validation command is recorded, or missing validation is treated as a risk
- [ ] faster-but-different candidates are marked `opt_in`, not default accepted

## A3. Baseline Provenance

- [ ] baseline loaded libraries or equivalent project command are recorded
- [ ] relevant library / extension / script hashes are recorded
- [ ] source status or diff is recorded when source changes are possible
- [ ] benchmark command and env are enough to reproduce the baseline measurement

## B. Core Triage Result

- [ ] `report.md` exists
- [ ] `analysis.json` exists
- [ ] top kernel is clearly identified
- [ ] `classification` is present
- [ ] `recommended_route` is present
- [ ] `recommended_route_reason` is present
- [ ] `recommended_route_action` is present

## C. Bubble / Copy / Wait Evidence

- [ ] the report states whether bubble / wait / copy is a major issue
- [ ] `overlap_opportunities.json` exists
- [ ] overlap opportunities contain at least one concrete signal or explicitly remain empty
- [ ] copy/sync/wait signals are visible either in the report or sidecar JSON

## D. Kernel / Fusion Sidecars

- [ ] `kernel_table.json` exists
- [ ] kernel table rows are machine-readable and non-empty when kernels were observed
- [ ] `fuse_opportunities.json` exists
- [ ] fusion opportunities are either populated or explicitly empty

## E. Downstream Handoff Readiness

- [ ] source artifact paths are recorded
- [ ] current result is sufficient for one of:
  - bubble optimization
  - framework/operator rewrite
  - kernel optimization
  - more attribution
- [ ] the next stage can start without reopening the raw trace first

## F. Delivery Package

- [ ] `OPTIMIZATION_RECORD.md` exists or is planned
- [ ] `OPTIMIZATION_USAGE.md` exists or is planned
- [ ] `OPTIMIZATION.patch` exists or is planned
- [ ] one master switch env is documented, such as `PROJECT_DCU_OPT=1`
- [ ] accepted / opt-in / rejected candidates are listed separately

## Exit Rule

The profiling package is ready to hand off only when:

1. environment is recorded;
2. top kernel and bottleneck class are clear;
3. next-step route is explicit;
4. downstream-readable JSON sidecars exist;
5. semantic and benchmark contracts are explicit;
6. default delivery contains record, usage, patch, and one master switch.
