---
schema_version: 1
owner: "HYGON-AI HCU performance team"
source:
  repo: HYGON-AI/skillhub
  path: skills/torch-trace-operator-profiler
license: "Apache-2.0"
lifecycle: published
---

# Skill Card

## Summary

Analyze a torch.profiler Chrome/Perfetto JSON trace to attribute time across Python scopes, ATen operators, GPU kernels, runtime API overhead and memory copies. Use when diagnosing a slow PyTorch operator, custom extension, Triton kernel or submodule from a captured trace.

## Owner

HYGON-AI HCU performance team, reachable through issues and pull requests on
`HYGON-AI/skillhub`.

## Source

- Repository: `HYGON-AI/skillhub`
- Path: `skills/torch-trace-operator-profiler`
- Lifecycle: `published`
- Ownership: catalog-owned (local component)

## License

Declared as `Apache-2.0`; see the bundled `LICENSE`. The bundled script carries
a Hygon copyright header and no third-party NOTICE obligation applies.

## Runtime and permissions

Reads a `torch.profiler` JSON trace from the local filesystem and runs
`scripts/torch_trace_scope_summary.py` with Python 3.9 or newer. The script
only reads the trace; it does not modify the traced project. No network access
and no credentials are required, and the skill writes nothing beyond the report
the user asks for.

Trace analysis does not require the target accelerator. Reproducing before and
after numbers does: without the target GPU and runtime, after numbers stay
projections.

## Validation

Exercised against Chrome/Perfetto traces captured from PyTorch workloads,
including HIP runtime traces where GPU kernels are attributed through runtime
`correlation` values rather than wall-clock overlap. The validated part is the
bundled script's parsing and summary output.

This does not prove that any optimization the skill proposes improves a given
workload. Every optimization claim in a report needs its own measured before
and after numbers from the target environment, and projections must be labelled
as projections.
