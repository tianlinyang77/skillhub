---
name: audit-hygon-open-source
description: Assess repository release readiness by reviewing licensing, notices, source provenance, file metadata, and commit history. Use when preparing a fixed Git revision for distribution or generating a concise Chinese remediation report.
license: Apache-2.0
---

# Audit HYGON Open Source

Run a deterministic, read-only compliance comparison and produce one developer-facing Markdown report. Treat the private repository as immutable throughout the scan.

## Inputs

Require a registered repository YAML under `<workspace>/configs/repos/<repo-id>.yaml`. The default workspace is `$HYGON_GOVERNANCE_HOME/open-source`, or `~/.hygon-governance/open-source` when the environment variable is unset.

- Classify the target as either formally HYGON-original or derivative before creating the YAML. Do not infer the mode from a `-das` suffix or repository owner.
- For a declared HYGON-original repository, require the local repository path and target branch or Commit. Resolve the target to an exact 40-character Commit, create `repository_mode: original`, and do not require or invent upstream metadata.
- For every derivative repository, require the local repository path and target branch or Commit plus the upstream repository URL, at least one non-empty `upstream.branch` or `upstream.tag`, and the exact 40-character upstream baseline Commit. The exact Commit is always mandatory. A Tag-only baseline is valid when the Tag resolves exactly to that Commit; a branch-only baseline is valid when the Commit is reachable from that branch. When both are provided, verify both relationships.
- Use default `fork` mode only when the target Commit is a complete derivative tree comparable path-for-path with the upstream tree.
- Use `repository_mode: submodule-patch` when one Gitlink pins the complete upstream baseline and committed adaptation or monkey-patch code lives outside that submodule. Require an exact target Commit and `submodule_patch.upstream_path`.
- Use `repository_mode: upstream-overlay` when the target is an independently versioned adapter or patch package, carries only its own committed overlay tree, and neither embeds nor shares history with the complete upstream. Require an exact target Commit and fixed upstream metadata.
- Use `repository_mode: original` only for a formally declared HYGON-original repository. Require an exact target Commit and `original.default_provenance: hygon-authored`; never define a fake upstream.

Read these references only when needed:

- Read [repository-config-schema.md](references/repository-config-schema.md) when onboarding or correcting a repository configuration.
- Read [policy-schema.md](references/policy-schema.md) when updating HYGON policy, license rules, platform wording, overlays, or exceptions.
- Read [finding-model.md](references/finding-model.md) when interpreting report categories or extending scanners.
- Read [history-metadata-rules.md](references/history-metadata-rules.md) when a complete reachable-history inventory or a history-rewrite pre/post check is requested.

## Workflow

1. Confirm whether the repository is original or derivative, the requested `repo-id`, target ref, and repository layout. For a derivative, stop when the upstream repository URL or exact baseline Commit is missing, or when neither an upstream branch nor Tag is provided. When onboarding, inspect the committed `.gitmodules`, Gitlink modes, and source layout before selecting the derivative mode.
2. For this standalone full-repository Skill, require the resolved policy to use `governance.execution_mode: centralized-skill`. Use `policy.overlay: centralized-skill` when no repository-specific overlay is needed. If a repository-specific overlay is necessary, include the same execution mode in that approved overlay. Do not require repository-local GitHub workflows in this mode.
3. Run the thin Skill adapter. It locates the versioned shared engine from an authorized private `HYGON-AI/open-source-governance` checkout:

```bash
python3 scripts/audit_repo.py \
  --workspace "${HYGON_GOVERNANCE_HOME:-$HOME/.hygon-governance}/open-source" \
  --repo-id <repo-id>
```

4. Add `--offline` only when the configured upstream commit is already cached.
5. Accept exit code `2` as a completed scan with compliance blockers. Treat exit code `1` as an operational failure.
6. Return the generated report path and a short blocker count. Do not copy report findings into a second report.
7. When the user requests exact complete-history counts, Commit title/body review, or history-rewrite pre/post evidence, additionally run the bundled read-only history mode:

   ```bash
   python3 scripts/history_metadata_audit.py \
     --repo <complete-repository-path> \
     --ref <40-character-commit> \
     --report-ref <human-readable-branch> \
     --block-term <approved-block-term> \
     --review-term <approved-review-term> \
     --report-dir <workspace>/reports/<repo-id>
   ```

   Reject shallow repositories. Supply policy-approved blocking and review terms explicitly; do not hardcode release-specific identifiers in the Skill package.

## Non-negotiable behavior

- Never modify the private repository worktree, index, refs, remotes, or config.
- Scan only the committed target tree; never enumerate or include uncommitted content in formal findings.
- In original mode, enumerate every tracked target-tree entry as scan scope and scan every reachable Commit for mandatory identity rules.
- In original mode, use the explicit repository-level provenance assertion only when the path has no deterministic third-party, generated, vendor, or external-source evidence.
- In submodule-patch mode, verify that `.gitmodules` maps the configured upstream path to the registered public upstream and that the Gitlink exactly equals the configured upstream Commit.
- In submodule-patch mode, scan every committed patch-tree entry and compare only same-path target entries with the upstream baseline. Never report upstream-only root paths as deleted because they are carried by the fixed submodule.
- In upstream-overlay mode, scan every committed target entry, compare only same-path entries with the fixed upstream baseline, and never report upstream-only paths as deletions.
- Keep added patch sources without deterministic HYGON, upstream, generated, or third-party evidence in blocking provenance review. Do not infer authorship merely because a file lives outside the upstream submodule.
- Compare Git trees directly even when histories are non-linear.
- Exclude unchanged upstream files from header findings.
- Exclude R100 renames and exact upstream blobs from HYGON header requirements.
- Require HYGON Copyright and accurate SPDX on HYGON-authored files. For H2 substantive original modifications, Apache-2.0 requires the preserved upstream declaration plus HYGON Copyright, accurate SPDX, and the configured modification notice; MIT and BSD keep the file header unchanged and require repository-level HYGON contribution attribution instead.
- Treat parameter, configuration, identifier, literal, small expression, local branch, formatting, comment, and other mechanical changes as H3 non-substantive modifications. Apache-2.0 preserves the upstream declaration and adds only the configured modification notice. MIT and BSD preserve the upstream declaration and keep the file header unchanged.
- Determine modification scope from structural originality evidence, never from changed-line count alone. Select H2 automatically only when structural change reaches the versioned policy threshold; put unsupported languages, parse failures, mixed changes, and insufficient evidence into blocking review.
- For Python, try the current runtime AST, then the newest compatible installed Python AST, then a token-semantic fallback. Never hide parser failure behind a generic provenance message; report the failed methods and require a scanner rerun after repair.
- Recognize a partial upstream backport only when every private changed source line is covered by one unique public upstream commit outside the configured baseline. Record that commit and do not require a HYGON header. Keep partial matches and mixed upstream/HYGON changes in blocking review.
- After excluding exact upstream blobs, proven upstream backports, third-party files, and generated files, automatically classify an existing upstream file as HYGON-modified when Git attribution proves retained changes from private-only commits. For mixed public/private files, classify the private commits separately and use their modification scope. Include those commits in the evidence and do not ask developers to reconfirm the source.
- Keep only genuinely insufficient evidence in provenance review: mixed public/private line ownership, deletion-only changes without target-side attribution, missing objects, or failed Git attribution. Never infer HYGON ownership from repository name, author name, email domain, or changed-line count.
- Automatically approve only MIT, BSD-3-Clause, and Apache-2.0. Scan component LICENSE files and tree-wide SPDX markers; route every other, unknown, missing, or compound license to blocking legal/compliance review unless the versioned policy explicitly marks it forbidden. Do not instruct developers to remove code merely because automated approval is unavailable.
- Recognize configured root-license names and common `LICENSE.*`, `LICENSE-*`, `COPYING.*`, and `COPYING-*` variants, including `LICENSE-APACHE`; do not require the root file to be named literally `LICENSE`.
- Preserve original Copyright, LICENSE, and Apache NOTICE content.
- Compare `README_ORIGIN.md` with the fixed upstream `README.md` after normalizing only `CRLF`/`CR` line endings to `LF` and ignoring the presence or absence of one final end-of-file newline. Keep extra blank lines, all other characters, whitespace, line order, and content strict; do not emit `README.ORIGIN_MISMATCH` for line-ending-only differences.
- Keep unmodified third-party source files unchanged. Record their real license and provenance in `THIRD_PARTY_NOTICES.md` or approved repository metadata instead of directly inserting SPDX or HYGON headers.
- Treat Git mode `100755` as valid for a newly added executable script only when its first line contains a non-empty shebang. Preserve that mode for fixed-version third-party scripts instead of reporting it as a mandatory remediation item. Continue to report non-script source, configuration, or data files marked executable, and existing paths changed from `100644` to `100755` without separate permission-change evidence.
- Do not guess third-party provenance. Mark unresolved provenance as blocking.
- Under policy v1.3 and later, scan committed paths, committed text, and private Commit metadata for policy-defined identifiers. Keep the configured terms outside the published Skill package.
- In complete-history mode, scan every Commit reachable from the fixed target, including author, committer, email, subject, body, and trailers. Keep embedded-substring evidence such as `uidcui`; label it separately from an independent token.
- Never perform platform-specific naming or runtime wording remediation in this Skill. Route that work to the appropriate platform-specialist workflow.
- Require direct third-party sources and newly introduced dependencies to use fixed provenance or versions.
- Keep commit-log findings advisory. For a derivative repository, inspect only Commits reachable from the target but not from the fixed upstream baseline; never report an upstream Commit as a target Commit-message recommendation. For an original repository, inspect the target's reachable history. Apply `commit_log.inspect_count` as the maximum number of newest in-scope Commits.
- In `centralized-skill` mode, never emit missing repository-local workflow, PR-trigger, or PR hard-blocking findings. PR incremental admission belongs to the separate `HYGON-AI/quality-gate` project and is not a prerequisite for a valid full-repository report.
- Inspect repository-local compliance workflows only when the user explicitly requests `repository-ci` delivery-mode validation and the resolved versioned policy selects that mode.
- Generate a Chinese developer remediation report without audit commands or scanner tutorials.
- Render one centralized, license-aware header-template section with stable template IDs. Per-file must-fix and review entries must reference those IDs and must not repeat complete header blocks. If the repository license is not yet approved, show the exact MIT, BSD-3-Clause, and Apache-2.0 SPDX choices but do not select one for the developer.
- Do not run vulnerability, CVE, SAST, secret, or code-quality scanners.

## Onboard a repository

Create one YAML in `configs/repos`. Keep secrets out of it. Point `local_path` to a pre-existing local clone or a symlink under the workspace `repositories` directory. Resolve the target branch to an exact Commit before writing the configuration, and record the human-readable branch in `report_ref` so the report filename remains clear. The legacy `target_branch` field remains readable during migration but must not conflict with `report_ref`. For an original repository, write `repository_mode: original` without an `upstream` block. For a derivative, refuse onboarding until the upstream URL, exact 40-character Commit, and at least one upstream branch or Tag are known; choose fork, submodule-patch, or upstream-overlay from the committed layout. Record only selectors actually used to establish the baseline: a configured Tag must resolve exactly to the Commit, while a configured branch must contain the Commit. For the default standalone full-repository scan, select `policy.overlay: centralized-skill`; repository-local GitHub workflows are not required and must not appear as blockers. In fork, submodule-patch, and upstream-overlay modes, set the upstream license to exactly `MIT`, `BSD-3-Clause`, or `Apache-2.0` for automatic approval. In submodule-patch mode, use the committed Gitlink path rather than an initialized submodule worktree path. In original mode, omit `original.license` until the repository has an approved license; the scan then blocks on the missing root license instead of inventing one. Keep any platform-specific profile and wording rules in the private policy overlay.

Use a repository overlay only for delivery mode, additive path exclusions, workflow paths, or platform visibility rules. A repository-specific overlay used by this Skill must retain `governance.execution_mode: centralized-skill`. Do not weaken a blocker without a non-expired approved exception.

## 报告位置（固定约定）

**合规扫描报告统一输出到 `~/.hygon-governance/open-source/reports/<仓库名>/`**（即 `${HYGON_GOVERNANCE_HOME:-$HOME/.hygon-governance}/open-source/reports/<repo-id>/`）。

## Report contract

Write exactly one formal artifact to:

```text
<workspace>/reports/<repo-id>/<repository-name>-<report-ref>-<short-commit>-合规-<YYYYMMDD-HHMMSS>.md
```

Keep the 12-character Commit and second-level timestamp so scans of different target revisions or reruns do not overwrite evidence. Replace `/`, `\\`, spaces, and other filename-unsafe characters in repository and ref names with `-`. When `target_ref` is a fixed Commit, prefer the registered `report_ref`; otherwise use a local branch that points exactly to the target Commit. Use `detached-<short-commit>` only when no branch can be established.

Include the scan mode, fixed target Commit, applicable upstream baseline or explicit no-upstream statement, deterministic diff/full-tree/patch-tree counts, license-admission blockers, per-file required changes, provenance review list, advisory commit findings, and a developer delivery checklist. State that execution uses the centralized Skill and that repository-local GitHub workflows are not applicable; never list missing workflows as remediation items in this mode. In fork mode retain exact and partial upstream backport lists. In submodule-patch mode report the verified upstream path and Gitlink, count only committed patch-tree entries, and explicitly state that upstream-only paths are not deletions. In upstream-overlay mode count every committed target entry, compare only same-path upstream entries, and explicitly state that upstream-only paths are not deletions. In original mode state that upstream exclusions do not apply. Summarize the relevant file scope as a strict hierarchy: confirmed must-fix, review-only, and no blocker; split confirmed must-fix into fix-only and fix-plus-review. Require the top-level groups to add exactly to the total file count. Separately report the header completion hierarchy for confirmed authored and modified sources: completed versus incomplete, with completed split by source type. Do not treat generic header detection as compliance completion, and do not count unresolved provenance as completed. Surface scanner recognition failures with the exact failed parsing method instead of presenting them as ordinary source uncertainty. Keep platform-specific wording outside this report and in the applicable private policy overlay. Use [developer-remediation-report.md](assets/developer-remediation-report.md) as the section contract.

Place the complete license-aware H1-H6 matrix once before the per-file remediation list, with Apache-2.0 first, then MIT and BSD-3-Clause. Explain `#` versus `//` once, show only the `#` example, and tell developers to replace the comment prefix for slash-comment files. Use the confirmed repository license in SPDX examples. If no license has been approved, keep an explicit placeholder and the three-license matrix instead of guessing. In every later per-file entry, emit only a deduplicated template reference such as `H1-HASH`, `H2-SLASH`, or `H2-REPOSITORY`.
