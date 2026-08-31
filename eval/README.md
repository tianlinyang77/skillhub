# Shared evaluation tooling

Per-skill datasets live in `skills/<name>/evals/evals.json`. This directory is
reserved for shared routing, behavior, grading and report-generation code.

The current repository validates dataset structure during catalog validation.
Future model-executed runners must preserve the distinction between routing
and behavior evidence described in `docs/evaluation/README.md` and must store
run outputs outside the source tree.
