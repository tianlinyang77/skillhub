#!/usr/bin/env python3
# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
"""Create independent backup and rewrite mirrors plus immutable evidence."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from identity_common import (
    SafetyError,
    ensure_bare_mirror,
    git,
    require_git_version,
    run,
    sha256_file,
    validate_ref,
    write_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze evidence for one remote branch and create two independent "
            "fresh mirror clones. This command never pushes."
        )
    )
    parser.add_argument("--remote", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--git-bin", default="git")
    args = parser.parse_args()

    try:
        git_version = require_git_version(args.git_bin)
        branch_ref = f"refs/heads/{args.branch}"
        validate_ref(args.git_bin, branch_ref, heads_only=True)
        if args.workspace.exists():
            raise SafetyError(
                f"workspace already exists; use a new empty path: {args.workspace}"
            )
        args.workspace.parent.mkdir(parents=True, exist_ok=True)

        remote_line = run(
            [args.git_bin, "ls-remote", args.remote, branch_ref]
        ).stdout.decode("ascii").strip()
        parts = remote_line.split()
        if len(parts) != 2 or parts[1] != branch_ref:
            raise SafetyError(f"remote branch does not resolve exactly: {branch_ref}")
        old_tip = parts[0]
        if not re.fullmatch(r"[0-9a-f]{40}", old_tip):
            raise SafetyError(f"unexpected remote tip: {old_tip}")

        args.workspace.mkdir()
        evidence = args.workspace / "evidence"
        evidence.mkdir()
        backup = args.workspace / "repository-backup.git"
        rewrite = args.workspace / "repository-rewrite.git"
        bundle = args.workspace / "repository-before.bundle"

        run(
            [
                args.git_bin,
                "clone",
                "--mirror",
                "--no-local",
                args.remote,
                str(backup),
            ]
        )
        ensure_bare_mirror(args.git_bin, backup)
        backup_tip = git(
            args.git_bin, backup, "rev-parse", branch_ref
        ).decode("ascii").strip()
        if backup_tip != old_tip:
            raise SafetyError(
                f"backup mirror raced with remote: {backup_tip} != {old_tip}"
            )

        refs = git(
            args.git_bin,
            backup,
            "for-each-ref",
            (
                "--format=%(refname)%09%(objectname)%09"
                "%(objecttype)%09%(*objectname)"
            ),
        )
        refs_path = evidence / "refs-before.tsv"
        refs_path.write_bytes(
            b"ref\tobject\tobject_type\tpeeled_object\n" + refs
        )

        old_tree = git(
            args.git_bin, backup, "rev-parse", f"{old_tip}^{{tree}}"
        ).decode("ascii").strip()
        commit_count = int(
            git(
                args.git_bin,
                backup,
                "rev-list",
                "--count",
                branch_ref,
            )
        )
        merge_count = int(
            git(
                args.git_bin,
                backup,
                "rev-list",
                "--count",
                "--merges",
                branch_ref,
            )
        )
        baseline_path = evidence / "baseline.env"
        baseline_path.write_text(
            "\n".join(
                (
                    f"REMOTE={args.remote}",
                    f"BRANCH={args.branch}",
                    f"BRANCH_REF={branch_ref}",
                    f"OLD_TIP={old_tip}",
                    f"OLD_TREE={old_tree}",
                    f"COMMIT_COUNT={commit_count}",
                    f"MERGE_COMMIT_COUNT={merge_count}",
                    "",
                )
            ),
            encoding="utf-8",
        )
        git(
            args.git_bin,
            backup,
            "bundle",
            "create",
            str(bundle.resolve()),
            "--all",
        )
        verification = git(
            args.git_bin,
            backup,
            "bundle",
            "verify",
            str(bundle.resolve()),
        )
        (evidence / "bundle-verify.txt").write_bytes(verification)

        run(
            [
                args.git_bin,
                "clone",
                "--mirror",
                "--no-local",
                args.remote,
                str(rewrite),
            ]
        )
        ensure_bare_mirror(args.git_bin, rewrite)
        rewrite_tip = git(
            args.git_bin, rewrite, "rev-parse", branch_ref
        ).decode("ascii").strip()
        if rewrite_tip != old_tip:
            raise SafetyError(
                f"rewrite mirror raced with remote: {rewrite_tip} != {old_tip}"
            )

        state = {
            "version": 1,
            "remote": args.remote,
            "branch": args.branch,
            "branch_ref": branch_ref,
            "old_tip": old_tip,
            "old_tree": old_tree,
            "commit_count": commit_count,
            "merge_commit_count": merge_count,
            "git_bin": os.path.abspath(args.git_bin)
            if os.path.sep in args.git_bin
            else args.git_bin,
            "git_version": git_version,
            "backup_repo": str(backup.resolve()),
            "rewrite_repo": str(rewrite.resolve()),
            "bundle": str(bundle.resolve()),
            "evidence_dir": str(evidence.resolve()),
        }
        state_path = evidence / "state.json"
        write_json(state_path, state)
        (backup / "DO_NOT_MODIFY").write_text(
            "Read-only evidence mirror. Never run history rewriting here.\n",
            encoding="utf-8",
        )
        (rewrite / "REWRITE_ONLY").write_text(
            "Dedicated rewrite mirror. Never use git push --mirror.\n",
            encoding="utf-8",
        )

        checksummed = [
            state_path,
            baseline_path,
            refs_path,
            evidence / "bundle-verify.txt",
            bundle,
        ]
        checksum_path = evidence / "SHA256SUMS"
        checksum_path.write_text(
            "".join(
                f"{sha256_file(path)}  {path.relative_to(args.workspace)}\n"
                for path in checksummed
            ),
            encoding="ascii",
        )

        print(f"STATUS=PREPARED\n")
        print(f"WORKSPACE={args.workspace.resolve()}")
        print(f"OLD_TIP={old_tip}")
        print(f"OLD_TREE={old_tree}")
        print(f"BACKUP_REPO={backup.resolve()}")
        print(f"REWRITE_REPO={rewrite.resolve()}")
        print(f"EVIDENCE_DIR={evidence.resolve()}")
        print("NEXT=AUDIT_BACKUP_REPO")
    except SafetyError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
