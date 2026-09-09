# Hotpath locating guide for Torch codebases

Use this reference only when the timing region is not obvious from the initial user hint or run entrypoint.

## Goal

Find the **smallest stable periodic unit** that represents one real model iteration.

Default rule:
- prefer the smallest repeated unit first
- do not keep an additional outer end-to-end region unless the user explicitly asks for broader timing
- if `run.sh` exists in the current workspace, use it before any other static search
- if the user provides a run command/script, follow that real execution path before doing static code guesses

## Highest-priority input from the user

If available, ask for or use these inputs in this order:

1. `./run.sh` in the current workspace
2. actual run command
3. shell script / launcher script
4. config file path
5. suspected hotspot file/function

Why:
- it gives the real execution path
- it makes the profiler run reproducible
- it reduces the risk of profiling a codepath that is not actually used

## Follow the real execution chain

When the user provides a run entrypoint:
- inspect the shell script, python entrypoint, launcher, and config chain first
- identify the real train/eval/infer function reached by that command
- only then choose the smallest stable periodic unit inside that path
- prefer instrumenting code on the actual execution path over creating a synthetic benchmark path

If `run.sh` exists:
- read it first
- treat it as the default entrypoint unless the user explicitly says to override it
- trace from `run.sh` into the actual python/launcher/config chain

## Search heuristics

### Inference-oriented code

Look for:
- `with torch.no_grad()`
- `with torch.inference_mode()`
- `model(...)`
- `module(...)`
- `generate(...)`
- `predict(...)`
- functions named `infer`, `predict`, `evaluate`, `benchmark`, `run_eval`

Prefer the inner repeated loop over samples/batches, not the outer evaluation wrapper.

### Training-oriented code

Look for:
- `loss.backward()`
- `optimizer.step()`
- `optimizer.zero_grad()` / `zero_grad(set_to_none=True)`
- `scheduler.step()` when it is part of the real training step
- functions named `train_step`, `training_step`, `run_step`, `step`

Prefer one logical optimizer step, not epoch-level code.
If the project uses a smaller repeated micro-step that is the real hotpath, profile that micro-step instead.

### Framework-specific cues

#### PyTorch Lightning
- `training_step`
- `validation_step`
- `predict_step`
- trainer invocation sites

#### Hugging Face Trainer / Accelerate
- custom `compute_loss`
- `prediction_step`
- overridden training loops
- benchmark wrappers around `trainer.train()` / `trainer.predict()`

#### Custom engines
- runner/engine methods that eventually call forward/backward/step
- benchmark or perf scripts that already isolate the model loop

## Boundary rules

### Prefer including
- repeated model forward
- repeated backward/optimizer work when analyzing training
- steady-state synchronization already required by the benchmark

### Prefer excluding
- model init
- checkpoint load
- tokenizer/dataset build
- first-call compilation or graph capture unless explicitly requested
- dataloader work unless the task is pipeline analysis rather than model analysis
- extra outer wrappers such as full eval runs, full epochs, or full request lifecycles when a smaller periodic unit exists

## Existing timing code

If the code already has timing logic:
- start from that region
- verify it really surrounds the model hotpath
- shrink it to the smallest stable periodic unit when possible
- replace or augment it with profiler instrumentation instead of duplicating unrelated timers

## Entry discovery hints

Common run-entry clues:
- `bash run.sh`
- `bash train.sh`, `bash infer.sh`
- `python train.py ...`
- `torchrun ... train.py ...`
- `accelerate launch ...`
- `deepspeed ...`
- config files passed by `--config`, `--cfg`, `-c`, yaml/json paths

When reading shell or launcher scripts, trace:
- environment variables
- selected config files
- python module / script target
- framework launcher wrapper

## Recommended artifact set

- trace JSON for Perfetto / Chrome
- structured profile JSON with run metadata and Top-K ops
- markdown report from `scripts/analyze_torch_trace.py`
- optional `analysis.json` when downstream programmatic consumption is needed
