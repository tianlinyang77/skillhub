#!/usr/bin/env python3
# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
"""Publish a validated rewrite to a review branch or perform guarded cutover."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Optional

from identity_common import (
    SafetyError,
    git,
    read_json,
    require_git_version,
    run,
    validate_ref,
    write_json,
)


def remote_tip(git_bin: str, remote: str, ref: str) -> Optional[str]:
    output = run(
        [git_bin, "ls-remote", remote, ref],
    ).stdout.decode("ascii").strip()
    if not output:
        return None
    lines = output.splitlines()
    if len(lines) != 1:
        raise SafetyError(f"remote ref resolved more than once: {ref}")
    object_id, remote_ref = lines[0].split()
    if remote_ref != ref or not re.fullmatch(r"[0-9a-f]{40}", object_id):
        raise SafetyError(f"unexpected ls-remote output for {ref}: {output}")
    return object_id


def load_context(
    state_path: Path,
    rewrite_result_path: Path,
    validation_result_path: Path,
) -> tuple[dict, dict, dict]:
    state = read_json(state_path)
    rewrite = read_json(rewrite_result_path)
    validation = read_json(validation_result_path)
    if not all(isinstance(value, dict) for value in (state, rewrite, validation)):
        raise SafetyError("publication evidence files must contain JSON objects")
    if validation.get("status") != "PASS":
        raise SafetyError("strict validation has not passed")
    if state.get("old_tip") != rewrite.get("old_tip"):
        raise SafetyError("state and rewrite old tips differ")
    if validation.get("old_tip") != state.get("old_tip"):
        raise SafetyError("validation and state old tips differ")
    if validation.get("new_tip") != rewrite.get("new_tip"):
        raise SafetyError("validation and rewrite new tips differ")
    if validation.get("old_tree") != validation.get("new_tree"):
        raise SafetyError("final Git tree is not identical")
    if int(validation.get("forbidden_metadata_fields", -1)) != 0:
        raise SafetyError("forbidden metadata remains after rewrite")
    return state, rewrite, validation


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--rewrite-result", required=True, type=Path)
    parser.add_argument("--validation-result", required=True, type=Path)
    parser.add_argument("--rewrite-repo", required=True, type=Path)
    parser.add_argument("--git-bin", default="git")
    parser.add_argument("--output", required=True, type=Path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Publish only a strictly validated rewrite. This utility never uses "
            "git push --mirror."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser(
        "status", help="Read remote tips without changing remote state."
    )
    add_common_arguments(status_parser)
    status_parser.add_argument("--review-branch")

    review_parser = subparsers.add_parser(
        "push-review", help="Create a new temporary review branch."
    )
    add_common_arguments(review_parser)
    review_parser.add_argument("--review-branch", required=True)
    review_parser.add_argument("--confirm-new-tip", required=True)

    cutover_parser = subparsers.add_parser(
        "cutover", help="Force-replace the official branch with an exact lease."
    )
    add_common_arguments(cutover_parser)
    cutover_parser.add_argument("--review-branch", required=True)
    cutover_parser.add_argument("--confirm-branch", required=True)
    cutover_parser.add_argument("--confirm-old-tip", required=True)
    cutover_parser.add_argument("--confirm-new-tip", required=True)
    cutover_parser.add_argument(
        "--execute-approved-cutover",
        action="store_true",
        help="Required after a separate explicit human cutover approval.",
    )

    args = parser.parse_args()
    try:
        require_git_version(args.git_bin)
        state, rewrite, validation = load_context(
            args.state, args.rewrite_result, args.validation_result
        )
        remote = str(state["remote"])
        branch = str(state["branch"])
        target_ref = str(state["branch_ref"])
        old_tip = str(state["old_tip"])
        new_tip = str(rewrite["new_tip"])
        source_ref = str(rewrite["ref"])
        validate_ref(args.git_bin, target_ref, heads_only=True)
        validate_ref(args.git_bin, source_ref, heads_only=True)
        local_tip = git(
            args.git_bin, args.rewrite_repo, "rev-parse", source_ref
        ).decode("ascii").strip()
        if local_tip != new_tip:
            raise SafetyError("rewrite repository no longer points to validated new tip")

        review_ref = None
        if getattr(args, "review_branch", None):
            review_ref = f"refs/heads/{args.review_branch}"
            validate_ref(args.git_bin, review_ref, heads_only=True)
            if review_ref == target_ref:
                raise SafetyError("review branch must differ from the official branch")

        current_official = remote_tip(args.git_bin, remote, target_ref)
        if current_official != old_tip:
            raise SafetyError(
                "official branch changed after freeze; abort without pushing: "
                f"remote={current_official}, frozen={old_tip}"
            )

        args.output.mkdir(parents=True, exist_ok=True)
        if args.command == "status":
            review_tip = (
                remote_tip(args.git_bin, remote, review_ref)
                if review_ref is not None
                else None
            )
            result = {
                "version": 1,
                "status": "REMOTE_UNCHANGED",
                "official_ref": target_ref,
                "official_tip": current_official,
                "frozen_old_tip": old_tip,
                "validated_new_tip": new_tip,
                "review_ref": review_ref,
                "review_tip": review_tip,
            }
            write_json(args.output / "remote-status.json", result)
            print("STATUS=REMOTE_UNCHANGED")
            print(f"OFFICIAL_REF={target_ref}")
            print(f"OFFICIAL_TIP={current_official}")
            print(f"VALIDATED_NEW_TIP={new_tip}")
            if review_ref:
                print(f"REVIEW_REF={review_ref}")
                print(f"REVIEW_TIP={review_tip or ''}")
            return

        if args.command == "push-review":
            if args.confirm_new_tip != new_tip:
                raise SafetyError("--confirm-new-tip does not match validated new tip")
            assert review_ref is not None
            existing_review = remote_tip(args.git_bin, remote, review_ref)
            if existing_review is not None:
                raise SafetyError(
                    f"review branch already exists and will not be overwritten: "
                    f"{review_ref}={existing_review}"
                )
            command = [
                args.git_bin,
                "-C",
                str(args.rewrite_repo),
                "push",
                remote,
                f"{source_ref}:{review_ref}",
                f"--force-with-lease={review_ref}:",
            ]
            completed = run(command, check=False)
            if completed.returncode != 0:
                raise SafetyError(
                    "review branch push failed:\n"
                    + completed.stderr.decode("utf-8", "replace").strip()
                )
            published_tip = remote_tip(args.git_bin, remote, review_ref)
            if published_tip != new_tip:
                raise SafetyError("review branch does not point to validated new tip")
            result = {
                "version": 1,
                "status": "REVIEW_BRANCH_PUBLISHED",
                "official_ref": target_ref,
                "official_tip": current_official,
                "review_ref": review_ref,
                "review_tip": published_tip,
            }
            write_json(args.output / "review-publication.json", result)
            print("STATUS=REVIEW_BRANCH_PUBLISHED")
            print(f"REVIEW_REF={review_ref}")
            print(f"REVIEW_TIP={published_tip}")
            print("OFFICIAL_BRANCH_UNCHANGED=YES")
            print("NEXT=REVIEW_AND_RUN_REQUIRED_SCANS")
            return

        if args.command == "cutover":
            if not args.execute_approved_cutover:
                raise SafetyError(
                    "cutover requires a separate explicit human approval and "
                    "--execute-approved-cutover"
                )
            if args.confirm_branch != branch:
                raise SafetyError("--confirm-branch does not match frozen branch")
            if args.confirm_old_tip != old_tip:
                raise SafetyError("--confirm-old-tip does not match frozen old tip")
            if args.confirm_new_tip != new_tip:
                raise SafetyError("--confirm-new-tip does not match validated new tip")
            assert review_ref is not None
            reviewed_tip = remote_tip(args.git_bin, remote, review_ref)
            if reviewed_tip != new_tip:
                raise SafetyError(
                    "review branch is missing or does not point to validated new tip"
                )
            command = [
                args.git_bin,
                "-C",
                str(args.rewrite_repo),
                "push",
                remote,
                f"{source_ref}:{target_ref}",
                f"--force-with-lease={target_ref}:{old_tip}",
            ]
            completed = run(command, check=False)
            if completed.returncode != 0:
                raise SafetyError(
                    "guarded official cutover failed:\n"
                    + completed.stderr.decode("utf-8", "replace").strip()
                )
            published_tip = remote_tip(args.git_bin, remote, target_ref)
            if published_tip != new_tip:
                raise SafetyError("official branch does not point to validated new tip")
            result = {
                "version": 1,
                "status": "CUTOVER_COMPLETE",
                "official_ref": target_ref,
                "old_tip": old_tip,
                "new_tip": published_tip,
                "review_ref": review_ref,
                "review_tip": reviewed_tip,
            }
            write_json(args.output / "cutover-result.json", result)
            print("STATUS=CUTOVER_COMPLETE")
            print(f"OFFICIAL_REF={target_ref}")
            print(f"OLD_TIP={old_tip}")
            print(f"NEW_TIP={published_tip}")
            print("NEXT=QUICK_IDENTITY_AUDIT_THEN_UNFREEZE")
            return
        raise SafetyError(f"unsupported command: {args.command}")
    except SafetyError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
