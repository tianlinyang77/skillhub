# Benchmark evidence

Only skills that make measurable performance, accuracy, coverage, latency,
throughput or resource claims require `BENCHMARK.md`. Instruction-only skills
must not add empty benchmark files merely to satisfy a count.

A benchmark record must include:

- skill and source commit;
- hardware, software, model and dataset identity;
- exact command and parameters;
- warmup, repetitions and aggregation method;
- baseline and candidate results with units;
- correctness or acceptance gate;
- raw evidence location and digest when artifacts are external;
- limitations such as synthetic, single-operation, degraded or partial runs.

The future root benchmark index is generated from validated per-skill evidence.
Missing results, empty dataset digests and unverified claims must fail the
index build rather than appear as successful benchmarks.
