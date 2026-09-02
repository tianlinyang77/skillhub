#!/usr/bin/env python3
# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
"""Audit forbidden HYGON predecessor identities in reachable Git commits."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple

from identity_common import (
    SafetyError,
    affected_descendants,
    b64,
    batch_commits,
    commit_fields,
    commits_for_ref,
    contains_forbidden,
    display_bytes,
    git,
    parent_map,
    require_git_version,
    signed_commits,
    supported_email_mapping,
    validate_ref,
    write_json,
)


def other_refs_with_old_history(
    git_bin: str,
    repo: Path,
    target_ref: str,
    target_commits: Set[str],
) -> List[Tuple[str, int]]:
    output = git(
        git_bin,
        repo,
        "for-each-ref",
        "--format=%(refname)",
        "refs/heads",
        "refs/tags",
    )
    result: List[Tuple[str, int]] = []
    for ref in output.decode("utf-8", "surrogateescape").splitlines():
        if ref == target_ref:
            continue
        process_output = git(
            git_bin,
            repo,
            "rev-list",
            ref,
            "--",
            check=False,
        )
        if not process_output:
            continue
        commits = set(process_output.decode("ascii", "ignore").splitlines())
        overlap = len(commits & target_commits)
        if overlap:
            result.append((ref, overlap))
    return sorted(result)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit forbidden tokens in Git commit metadata without modifying Git."
    )
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--git-bin", default="git")
    args = parser.parse_args()

    try:
        git_version = require_git_version(args.git_bin)
        validate_ref(args.git_bin, args.ref)
        args.output.mkdir(parents=True, exist_ok=True)

        ordered = commits_for_ref(args.git_bin, args.repo, args.ref)
        if not ordered:
            raise SafetyError(f"no commits are reachable from {args.ref}")
        bodies = batch_commits(args.git_bin, args.repo, ordered)
        parents = parent_map(bodies)
        signed = signed_commits(bodies)

        email_map: Dict[bytes, bytes] = {}
        email_findings: List[Dict[str, object]] = []
        blockers: Dict[Tuple[str, str], Dict[str, object]] = {}
        direct_changed: Set[str] = set()

        for commit in ordered:
            fields = commit_fields(bodies[commit])
            subject = fields["message"].splitlines()[0] if fields["message"] else b""
            for field, value in fields.items():
                if not contains_forbidden(value):
                    continue
                finding = {
                    "commit": commit,
                    "field": field,
                    "value_b64": b64(value),
                    "value_display": display_bytes(value),
                    "subject": display_bytes(subject, 120),
                }
                if field in {"author_email", "committer_email"}:
                    mapped = supported_email_mapping(value)
                    if mapped is not None:
                        previous = email_map.setdefault(value, mapped)
                        if previous != mapped:
                            raise SafetyError(
                                "one old email unexpectedly maps to multiple values"
                            )
                        direct_changed.add(commit)
                        finding["proposed_new_b64"] = b64(mapped)
                        finding["proposed_new_display"] = display_bytes(mapped)
                        email_findings.append(finding)
                        continue
                blockers[(commit, field)] = finding

        affected = affected_descendants(
            ordered,
            parents,
            direct_changed | {commit for commit, _ in blockers},
        )
        affected_signed = sorted(affected & signed)

        email_document = {
            "version": 1,
            "purpose": "exact forbidden-domain email mapping",
            "changes": [
                {
                    "old_b64": b64(old),
                    "new_b64": b64(new),
                    "old_display": display_bytes(old),
                    "new_display": display_bytes(new),
                }
                for old, new in sorted(email_map.items())
            ],
        }
        email_map_path = args.output / "proposed-email-map.json"
        email_map_sha256 = write_json(email_map_path, email_document)

        exact_template = {
            "version": 1,
            "purpose": (
                "exact per-commit replacements for forbidden values that cannot "
                "use the deterministic email-domain mapping"
            ),
            "changes": [
                {
                    "commit": commit,
                    "field": field,
                    "old_b64": finding["value_b64"],
                    "new_b64": None,
                    "old_display": finding["value_display"],
                    "subject": finding["subject"],
                }
                for (commit, field), finding in sorted(blockers.items())
            ],
        }
        exact_path = args.output / "exact-replacements.template.json"
        exact_template_sha256 = write_json(exact_path, exact_template)

        tsv_lines = ["old_email\tnew_email"]
        mailmap_lines: List[str] = []
        for old, new in sorted(email_map.items()):
            old_text = old.decode("utf-8", "backslashreplace")
            new_text = new.decode("utf-8", "backslashreplace")
            tsv_lines.append(f"{old_text}\t{new_text}")
            mailmap_lines.append(f"<{new_text}> <{old_text}>")
        (args.output / "proposed-email-map.tsv").write_text(
            "\n".join(tsv_lines) + "\n", encoding="utf-8"
        )
        (args.output / "identity.mailmap").write_text(
            "\n".join(mailmap_lines) + ("\n" if mailmap_lines else ""),
            encoding="utf-8",
        )

        offending_lines = [
            "commit\tfield\told_value\tproposed_value\tcommit_subject"
        ]
        for finding in email_findings:
            offending_lines.append(
                "\t".join(
                    (
                        str(finding["commit"]),
                        str(finding["field"]),
                        str(finding["value_display"]),
                        str(finding["proposed_new_display"]),
                        str(finding["subject"]),
                    )
                )
            )
        for (commit, field), finding in sorted(blockers.items()):
            offending_lines.append(
                "\t".join(
                    (
                        commit,
                        field,
                        str(finding["value_display"]),
                        "REQUIRES_EXACT_APPROVAL",
                        str(finding["subject"]),
                    )
                )
            )
        (args.output / "offending-commit-fields.tsv").write_text(
            "\n".join(offending_lines) + "\n", encoding="utf-8"
        )
        (args.output / "affected-commits.txt").write_text(
            "".join(f"{commit}\n" for commit in sorted(affected)),
            encoding="ascii",
        )
        (args.output / "signed-commits.txt").write_text(
            "".join(f"{commit}\n" for commit in sorted(signed)),
            encoding="ascii",
        )
        (args.output / "affected-signed-commits.txt").write_text(
            "".join(f"{commit}\n" for commit in affected_signed),
            encoding="ascii",
        )

        other_refs = other_refs_with_old_history(
            args.git_bin, args.repo, args.ref, set(ordered)
        )
        (args.output / "other-refs-with-old-history.tsv").write_text(
            "ref\toverlapping_commits\n"
            + "".join(f"{ref}\t{count}\n" for ref, count in other_refs),
            encoding="utf-8",
        )

        tip = git(args.git_bin, args.repo, "rev-parse", args.ref).decode(
            "ascii"
        ).strip()
        tree = git(
            args.git_bin, args.repo, "rev-parse", f"{tip}^{{tree}}"
        ).decode("ascii").strip()
        merge_count = int(
            git(
                args.git_bin,
                args.repo,
                "rev-list",
                "--count",
                "--merges",
                args.ref,
            )
        )
        summary = {
            "version": 1,
            "git_version": git_version,
            "repo": str(args.repo.resolve()),
            "ref": args.ref,
            "tip": tip,
            "tree": tree,
            "commit_count": len(ordered),
            "merge_commit_count": merge_count,
            "unique_automatic_email_mappings": len(email_map),
            "automatic_email_field_findings": len(email_findings),
            "exact_replacement_fields_required": len(blockers),
            "directly_changed_commits": len(
                direct_changed | {commit for commit, _ in blockers}
            ),
            "affected_commits_including_descendants": len(affected),
            "signed_commits": len(signed),
            "predicted_signature_loss": len(affected_signed),
            "other_refs_with_old_history": len(other_refs),
            "email_map_sha256": email_map_sha256,
            "exact_template_sha256": exact_template_sha256,
        }
        write_json(args.output / "audit-summary.json", summary)
        (args.output / "audit-summary.env").write_text(
            "\n".join(
                (
                    f"REF={args.ref}",
                    f"TIP={tip}",
                    f"TREE={tree}",
                    f"COMMIT_COUNT={len(ordered)}",
                    f"MERGE_COMMIT_COUNT={merge_count}",
                    f"UNIQUE_EMAIL_MAPPINGS={len(email_map)}",
                    f"EMAIL_FIELD_FINDINGS={len(email_findings)}",
                    f"EXACT_REPLACEMENTS_REQUIRED={len(blockers)}",
                    f"AFFECTED_COMMITS={len(affected)}",
                    f"SIGNED_COMMITS={len(signed)}",
                    f"PREDICTED_SIGNATURE_LOSS={len(affected_signed)}",
                    f"EMAIL_MAP_SHA256={email_map_sha256}",
                    "",
                )
            ),
            encoding="utf-8",
        )

        status = (
            "BLOCKED_PENDING_EXACT_REPLACEMENTS"
            if blockers
            else "READY_FOR_MAPPING_APPROVAL"
        )
        report_lines = [
            "# Git Commit 身份审计 / Git Commit Identity Audit",
            "",
            f"- 状态 / Status: **{status}**",
            f"- Ref: `{args.ref}`",
            f"- Tip: `{tip}`",
            f"- Commit: {len(ordered)}",
            f"- 自动邮箱映射 / Automatic email mappings: {len(email_map)}",
            f"- 邮箱字段命中 / Email field findings: {len(email_findings)}",
            f"- 需精确审批字段 / Exact replacements required: {len(blockers)}",
            f"- 预计重写 Commit / Affected commits: {len(affected)}",
            f"- 预计移除失效签名 / Predicted signature loss: {len(affected_signed)}",
            "",
            "## 安全结论 / Safety Decision",
            "",
        ]
        if blockers:
            report_lines.extend(
                (
                    "发现姓名、Commit Message 或非标准邮箱中的禁止字段。",
                    "不得进行模糊替换；填写 `exact-replacements.template.json` "
                    "中的每个 `new_b64`，经人工逐项审批后再继续。",
                )
            )
        else:
            report_lines.extend(
                (
                    "所有命中均可按确定性规则映射为相同用户名的 `@hygon.com`。",
                    "人工核对 `proposed-email-map.tsv` 及其 SHA-256 后方可重写。",
                )
            )
        if other_refs:
            report_lines.extend(
                (
                    "",
                    "## 其他引用 / Other Refs",
                    "",
                    "其他分支或 Tag 仍引用旧历史。正式发布前必须登记为非发布 "
                    "refs，或另行纳入重写；不得把它们当作远端备份。",
                )
            )
        report_lines.extend(
            (
                "",
                "## 证据 / Evidence",
                "",
                "- `offending-commit-fields.tsv`",
                "- `proposed-email-map.json`（权威映射文件）",
                "- `proposed-email-map.tsv`（人工阅读）",
                "- `exact-replacements.template.json`",
                "- `affected-signed-commits.txt`",
                "- `other-refs-with-old-history.tsv`",
                "",
            )
        )
        (args.output / "audit-report.md").write_text(
            "\n".join(report_lines), encoding="utf-8"
        )
        print((args.output / "audit-summary.env").read_text(encoding="utf-8"), end="")
        if blockers:
            raise SystemExit(2)
    except SafetyError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
