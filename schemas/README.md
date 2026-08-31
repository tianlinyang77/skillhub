# Repository schemas

This directory is the home for machine-readable schemas for component
registration, lock files, evaluation datasets, catalog metadata and plugin
definitions.

Do not add an unenforced schema. A schema becomes normative only when a test or
validator loads it and rejects invalid input. Until then, the Python validators
and the contracts under `docs/` are authoritative.
