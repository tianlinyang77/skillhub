#!/usr/bin/env python3
# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
"""Strictly prove that only explicitly approved Git metadata changed."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple

from identity_common import (
    SafetyError,
    IdentityValue,
    batch_commits,
    commit_fields,
    contains_forbidden,
    exact_change_map,
    git,
    header_values,
    load_commit_map,
    load_email_map,
    load_exact_changes,
    parse_commit,
    parse_identity,
    read_json,
    render_identity,
    require_git_version,
    signed_commits,
    validate_ref,
    write_json,
)


def ref_map(git_bin: str, repo: Path) -> Dict[str, str]:
    output = git(
        git_bin,
        repo,
        "for-each-ref",
        "--format=%(refname)%09%(objectname)",
        "refs/heads",
        "refs/tags",
    )
    result: Dict[str, str] = {}
    for line in output.decode("ascii").splitlines():
        ref, object_id = line.split("\t", 1)
        result[ref] = object_id
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare old and rewritten histories commit-by-commit. Validation "
            "fails if any unapproved field, tree, topology, message, or ref changes."
        )
    )
    parser.add_argument("--old-repo", required=True, type=Path)
    parser.add_argument("--new-repo", required=True, type=Path)
    parser.add_argument("--old-ref", required=True)
    parser.add_argument("--new-ref", required=True)
    parser.add_argument("--rewrite-output", required=True, type=Path)
    parser.add_argument("--email-map", required=True, type=Path)
    parser.add_argument("--exact-changes", type=Path)
    parser.add_argument("--expected-signature-loss", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--git-bin", default="git")
    args = parser.parse_args()

    try:
        require_git_version(args.git_bin)
        validate_ref(args.git_bin, args.old_ref, heads_only=True)
        validate_ref(args.git_bin, args.new_ref, heads_only=True)
        args.output.mkdir(parents=True, exist_ok=True)
        errors: List[str] = []

        rewrite_result = read_json(args.rewrite_output / "rewrite-result.json")
        if not isinstance(rewrite_result, dict) or rewrite_result.get("version") != 1:
            raise SafetyError("rewrite-result.json is missing or incompatible")
        mapping = load_commit_map(args.rewrite_output / "commit-map.txt")
        affected = set(
            (args.rewrite_output / "affected-commits-approved.txt")
            .read_text(encoding="ascii")
            .splitlines()
        )
        email_map = load_email_map(args.email_map)
        exact_changes = exact_change_map(load_exact_changes(args.exact_changes))

        if set(mapping) != affected:
            errors.append(
                "commit-map differs from approved affected set: "
                f"missing={len(affected - set(mapping))}, "
                f"extra={len(set(mapping) - affected)}"
            )

        old_tip = git(
            args.git_bin, args.old_repo, "rev-parse", args.old_ref
        ).decode("ascii").strip()
        new_tip = git(
            args.git_bin, args.new_repo, "rev-parse", args.new_ref
        ).decode("ascii").strip()
        if old_tip != rewrite_result.get("old_tip"):
            errors.append("old repository tip differs from rewrite evidence")
        if new_tip != rewrite_result.get("new_tip"):
            errors.append("new repository tip differs from rewrite evidence")

        old_tree = git(
            args.git_bin, args.old_repo, "rev-parse", f"{old_tip}^{{tree}}"
        ).decode("ascii").strip()
        new_tree = git(
            args.git_bin, args.new_repo, "rev-parse", f"{new_tip}^{{tree}}"
        ).decode("ascii").strip()
        if old_tree != new_tree:
            errors.append(f"final tree differs: {old_tree} != {new_tree}")

        old_commits = set(
            git(args.git_bin, args.old_repo, "rev-list", args.old_ref)
            .decode("ascii")
            .splitlines()
        )
        new_commits = set(
            git(args.git_bin, args.new_repo, "rev-list", args.new_ref)
            .decode("ascii")
            .splitlines()
        )
        old_bodies = batch_commits(args.git_bin, args.old_repo, old_commits)
        new_bodies = batch_commits(args.git_bin, args.new_repo, new_commits)
        expected_new_commits = (old_commits - affected) | set(mapping.values())
        if new_commits != expected_new_commits:
            errors.append(
                "reachable commit set differs from expected mapping: "
                f"missing={len(expected_new_commits - new_commits)}, "
                f"extra={len(new_commits - expected_new_commits)}"
            )

        old_merges = int(
            git(
                args.git_bin,
                args.old_repo,
                "rev-list",
                "--count",
                "--merges",
                args.old_ref,
            )
        )
        new_merges = int(
            git(
                args.git_bin,
                args.new_repo,
                "rev-list",
                "--count",
                "--merges",
                args.new_ref,
            )
        )
        if old_merges != new_merges:
            errors.append(f"merge count differs: {old_merges} != {new_merges}")

        for commit in sorted(old_commits - affected):
            if commit not in new_bodies:
                errors.append(f"{commit}: unaffected commit is no longer reachable")
            elif old_bodies[commit] != new_bodies[commit]:
                errors.append(f"{commit}: unaffected commit object bytes changed")

        rewritten_old_signed: Set[str] = set()
        for old in sorted(affected):
            new = mapping.get(old)
            if new is None or new not in new_bodies:
                continue
            old_headers, old_message = parse_commit(old_bodies[old])
            new_headers, new_message = parse_commit(new_bodies[new])
            old_fields = commit_fields(old_bodies[old])

            expected_fields = dict(old_fields)
            for field in ("author_email", "committer_email"):
                expected_fields[field] = email_map.get(
                    expected_fields[field], expected_fields[field]
                )
            for field in old_fields:
                change = exact_changes.get((old, field))
                if change is not None:
                    if old_fields[field] != change.old:
                        errors.append(f"{old}:{field}: approved old value mismatch")
                    expected_fields[field] = change.new

            if new_message != expected_fields["message"]:
                errors.append(f"{old}: commit message changed beyond approval")

            old_trees = header_values(old_headers, b"tree")
            new_trees = header_values(new_headers, b"tree")
            if old_trees != new_trees:
                errors.append(f"{old}: tree header changed")

            old_parents = [
                value.decode("ascii")
                for value in header_values(old_headers, b"parent")
            ]
            new_parents = [
                value.decode("ascii")
                for value in header_values(new_headers, b"parent")
            ]
            expected_parents = [mapping.get(parent, parent) for parent in old_parents]
            if new_parents != expected_parents:
                errors.append(f"{old}: parent topology changed unexpectedly")

            old_author_values = header_values(old_headers, b"author")
            new_author_values = header_values(new_headers, b"author")
            old_committer_values = header_values(old_headers, b"committer")
            new_committer_values = header_values(new_headers, b"committer")
            if (
                len(old_author_values) != 1
                or len(new_author_values) != 1
                or len(old_committer_values) != 1
                or len(new_committer_values) != 1
            ):
                errors.append(f"{old}: malformed author or committer headers")
            else:
                old_author = parse_identity(old_author_values[0])
                old_committer = parse_identity(old_committer_values[0])
                expected_author = render_identity(
                    IdentityValue(
                        expected_fields["author_name"],
                        expected_fields["author_email"],
                        old_author.timestamp,
                    )
                )
                expected_committer = render_identity(
                    IdentityValue(
                        expected_fields["committer_name"],
                        expected_fields["committer_email"],
                        old_committer.timestamp,
                    )
                )
                if new_author_values[0] != expected_author:
                    errors.append(
                        f"{old}: author name, email, or timestamp changed "
                        "beyond approval"
                    )
                if new_committer_values[0] != expected_committer:
                    errors.append(
                        f"{old}: committer name, email, or timestamp changed "
                        "beyond approval"
                    )

            old_signed = any(
                key.startswith(b"gpgsig") for key, _ in old_headers
            )
            new_signed = any(
                key.startswith(b"gpgsig") for key, _ in new_headers
            )
            if old_signed:
                rewritten_old_signed.add(old)
            if new_signed:
                errors.append(f"{old}: invalid old signature was retained or replaced")

            old_other = [
                (key, value)
                for key, value in old_headers
                if key not in {b"tree", b"parent", b"author", b"committer"}
                and not key.startswith(b"gpgsig")
            ]
            new_other = [
                (key, value)
                for key, value in new_headers
                if key not in {b"tree", b"parent", b"author", b"committer"}
                and not key.startswith(b"gpgsig")
            ]
            if old_other != new_other:
                errors.append(f"{old}: non-signature extended headers changed")

        old_signed_all = signed_commits(old_bodies)
        new_signed_all = signed_commits(new_bodies)
        expected_new_signed = old_signed_all - rewritten_old_signed
        if new_signed_all != expected_new_signed:
            errors.append(
                "unaffected signature set changed: "
                f"missing={len(expected_new_signed - new_signed_all)}, "
                f"extra={len(new_signed_all - expected_new_signed)}"
            )
        signature_loss = len(old_signed_all) - len(new_signed_all)
        if signature_loss != args.expected_signature_loss:
            errors.append(
                f"signature loss is {signature_loss}, expected "
                f"{args.expected_signature_loss}"
            )
        if len(rewritten_old_signed) != args.expected_signature_loss:
            errors.append(
                f"rewritten signed commits are {len(rewritten_old_signed)}, "
                f"expected {args.expected_signature_loss}"
            )

        forbidden_fields = 0
        for commit in new_commits:
            for field, value in commit_fields(new_bodies[commit]).items():
                if contains_forbidden(value):
                    forbidden_fields += 1
                    errors.append(f"{commit}:{field}: forbidden token remains")
                    if forbidden_fields >= 50:
                        break
            if forbidden_fields >= 50:
                errors.append("forbidden-token error list truncated at 50 fields")
                break

        old_refs = ref_map(args.git_bin, args.old_repo)
        new_refs = ref_map(args.git_bin, args.new_repo)
        for ref, object_id in old_refs.items():
            if ref == args.old_ref:
                continue
            if new_refs.get(ref) != object_id:
                errors.append(f"{ref}: non-target ref changed or disappeared")
        for ref in new_refs:
            if ref != args.new_ref and ref not in old_refs:
                errors.append(f"{ref}: unexpected non-target ref was created")

        status = "FAIL" if errors else "PASS"
        result = {
            "version": 1,
            "status": status,
            "old_tip": old_tip,
            "new_tip": new_tip,
            "old_tree": old_tree,
            "new_tree": new_tree,
            "old_commit_count": len(old_commits),
            "new_commit_count": len(new_commits),
            "old_merge_count": old_merges,
            "new_merge_count": new_merges,
            "rewritten_commits": len(mapping),
            "old_signed_commits": len(old_signed_all),
            "new_signed_commits": len(new_signed_all),
            "signatures_removed": signature_loss,
            "forbidden_metadata_fields": forbidden_fields,
            "error_count": len(errors),
            "errors": errors,
        }
        write_json(args.output / "validation-result.json", result)
        env_lines = [
            f"STATUS={status}",
            f"OLD_TIP={old_tip}",
            f"NEW_TIP={new_tip}",
            f"OLD_TREE={old_tree}",
            f"NEW_TREE={new_tree}",
            f"OLD_COMMIT_COUNT={len(old_commits)}",
            f"NEW_COMMIT_COUNT={len(new_commits)}",
            f"OLD_MERGE_COUNT={old_merges}",
            f"NEW_MERGE_COUNT={new_merges}",
            f"REWRITTEN_COMMITS={len(mapping)}",
            f"SIGNATURES_REMOVED={signature_loss}",
            f"FORBIDDEN_METADATA_FIELDS={forbidden_fields}",
            f"ERROR_COUNT={len(errors)}",
            *(f"ERROR={error}" for error in errors),
            "",
        ]
        (args.output / "validation-result.env").write_text(
            "\n".join(env_lines), encoding="utf-8"
        )
        report = [
            "# Git 历史重写验证 / Git History Rewrite Validation",
            "",
            f"- Status: **{status}**",
            f"- Old Tip: `{old_tip}`",
            f"- New Tip: `{new_tip}`",
            f"- Tree unchanged: **{'YES' if old_tree == new_tree else 'NO'}**",
            f"- Rewritten commits: {len(mapping)}",
            f"- Signatures removed: {signature_loss}",
            f"- Forbidden metadata fields: {forbidden_fields}",
            f"- Validation errors: {len(errors)}",
            "",
        ]
        if errors:
            report.extend(
                ["## Errors", "", *(f"- {error}" for error in errors), ""]
            )
        else:
            report.extend(
                (
                    "## Decision",
                    "",
                    "严格验证通过：除已批准的 Commit 元数据和因此失效的签名外，"
                    "代码 Tree、拓扑、消息、时间及其他 refs 均未改变。",
                    "",
                )
            )
        (args.output / "validation-report.md").write_text(
            "\n".join(report), encoding="utf-8"
        )
        print("\n".join(env_lines), end="")
        if errors:
            raise SystemExit(1)
    except SafetyError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
