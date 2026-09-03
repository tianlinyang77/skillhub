# Scanner ownership

| Scanner | Ownership |
| --- | --- |
| Native Git | exact tree, paths, modes, symlinks, encoding, line endings, control characters, size, LFS pointers, confidential markers |
| Shared identity engine | case-insensitive sugon/rogon in paths, contents, and reachable Commit metadata |
| Gitleaks | current and reachable-history credentials and secrets, always redacted; deterministic templates and explicit placeholders in documentation/example contexts are ignored after read-only source verification, while uncertain values remain blocking |
| Trivy | dependency vulnerabilities only; no secret, license, or misconfiguration duplication; use the Runner's existing local database with all automatic database updates disabled; report its timestamp and stale status, and fail only when the local database is missing or unreadable |
| actionlint | GitHub Actions syntax, expressions, reusable workflows, and action metadata; embedded ShellCheck is disabled to avoid duplicate concurrent scans |
| ShellCheck | tracked shell-script files are scanned independently and sequentially |
| Semgrep | local versioned high-confidence SAST rules, network and metrics disabled |
| Ruff | Python correctness rules E9,F63,F7,F82 only |
| yamllint | YAML syntax and duplicate keys; style remains non-blocking |
| Lizard | advisory complexity only |
| Optional C/C++/CUDA | disabled until a repository supplies a supported compile-aware configuration |
| Baseline comparison | for derivative repositories, run the same complete scanner set on the fixed upstream Commit and target Commit; classify findings as introduced, regressed, inherited, or resolved |
| Repository read-only guard | verify that the private worktree, index, refs, remotes, and configuration are unchanged after the audit |
