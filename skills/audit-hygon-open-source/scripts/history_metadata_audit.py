#!/usr/bin/env python3
# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
"""Audit every reachable Git commit's identity, subject, and body metadata."""

from __future__ import print_function

import argparse
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


FIELDS = (
    ("author_name", "作者姓名"),
    ("author_email", "作者邮箱"),
    ("committer_name", "提交者姓名"),
    ("committer_email", "提交者邮箱"),
    ("subject", "Commit 标题"),
    ("body", "Commit 正文"),
)
DEFAULT_BLOCK_TERMS = ("sugon", "rogon")
DEFAULT_REVIEW_TERMS = ("dcu",)
MAX_EVIDENCE = 300


class AuditError(Exception):
    pass


def report_component(value, fallback):
    raw = str(value).strip()
    if raw.startswith("refs/heads/"):
        raw = raw[len("refs/heads/") :]
    normalized = "".join(
        character if (character.isalnum() or character in ".-_") else "-"
        for character in raw
    )
    normalized = re.sub(r"-{2,}", "-", normalized).strip(".-")
    return normalized[:96] or fallback


def resolve_report_ref(repo, target_ref, target_commit, configured):
    if configured and configured.strip():
        return configured.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", target_ref) and target_ref != "HEAD":
        return target_ref
    current = run_git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if current.returncode == 0 and current.stdout.strip():
        return current.stdout.decode("utf-8", errors="replace").strip()
    branches = git_text(
        repo,
        "for-each-ref",
        "--format=%(refname:short)",
        "--points-at",
        target_commit,
        "refs/heads",
    ).splitlines()
    return sorted(branches)[0] if branches else "commit"


def formal_report_path(report_dir, repo, report_ref, target_commit, when):
    return report_dir / "{}-{}-{}-历史-{}.md".format(
        report_component(repo.name.removesuffix(".git"), "repository"),
        report_component(report_ref, "commit"),
        target_commit[:12],
        when.strftime("%Y%m%d-%H%M%S"),
    )


def require_output_outside_repo(repo, output):
    try:
        output.relative_to(repo)
    except ValueError:
        return
    raise AuditError("输出报告必须位于被扫描仓库之外")


def run_git(repo, *args, **kwargs):
    check = kwargs.pop("check", True)
    if kwargs:
        raise TypeError("unexpected keyword arguments: {}".format(sorted(kwargs)))
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=str(repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise AuditError("无法执行 Git：{}".format(exc))
    if check and result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise AuditError("Git 命令失败（{}）：{}".format(" ".join(args), stderr))
    return result


def git_text(repo, *args, **kwargs):
    return run_git(repo, *args, **kwargs).stdout.decode("utf-8", errors="replace")


def resolve_commit(repo, target_ref):
    value = git_text(repo, "rev-parse", "--verify", "{}^{{commit}}".format(target_ref)).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise AuditError("目标 ref 未解析为完整 Commit：{}".format(value))
    return value


def is_shallow_repository(repo):
    result = run_git(repo, "rev-parse", "--is-shallow-repository", check=False)
    if result.returncode == 0:
        return result.stdout.decode("ascii", errors="replace").strip() == "true"
    shallow_path = git_text(repo, "rev-parse", "--git-path", "shallow").strip()
    path = Path(shallow_path)
    if not path.is_absolute():
        path = repo / path
    return path.is_file() and path.stat().st_size > 0


def collect_commits(repo, target_commit):
    expected_count = int(git_text(repo, "rev-list", "--count", target_commit).strip())
    output = git_text(
        repo,
        "log",
        "--topo-order",
        "--format=%x1e%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%s%x1f%b",
        target_commit,
    )
    commits = []
    for raw_record in output.split("\x1e"):
        if not raw_record.strip():
            continue
        record = raw_record.strip("\n")
        parts = record.split("\x1f", 6)
        if len(parts) != 7:
            raise AuditError("Commit 元数据分隔解析失败，不能形成完整历史结论")
        commits.append(
            {
                "commit": parts[0],
                "author_name": parts[1],
                "author_email": parts[2],
                "committer_name": parts[3],
                "committer_email": parts[4],
                "subject": parts[5],
                "body": parts[6].strip(),
            }
        )
    if len(commits) != expected_count:
        raise AuditError(
            "解析 Commit 数 {} 与 rev-list 计数 {} 不一致".format(
                len(commits), expected_count
            )
        )
    return commits


def normalize_terms(values, defaults):
    terms = list(values) if values else list(defaults)
    normalized = []
    seen = set()
    for value in terms:
        term = value.strip()
        if not term:
            raise AuditError("扫描词不能为空")
        key = term.casefold()
        if key not in seen:
            seen.add(key)
            normalized.append(term)
    return normalized


def compile_terms(terms, case_sensitive):
    flags = 0 if case_sensitive else re.IGNORECASE
    return [(term, re.compile(re.escape(term), flags)) for term in terms]


def match_kind(value, start, end):
    before = value[start - 1] if start else ""
    after = value[end] if end < len(value) else ""
    embedded = (
        bool(before) and (before.isalnum() or before == "_")
    ) or (
        bool(after) and (after.isalnum() or after == "_")
    )
    return "嵌入子串" if embedded else "独立 token"


def evidence(value):
    text = " ".join(value.strip().split())
    if len(text) > MAX_EVIDENCE:
        return text[: MAX_EVIDENCE - 3] + "..."
    return text


def scan_commits(commits, block_terms, review_terms, case_sensitive):
    compiled = (
        [
            ("阻断", term, pattern)
            for term, pattern in compile_terms(block_terms, case_sensitive)
        ]
        + [
            ("复核", term, pattern)
            for term, pattern in compile_terms(review_terms, case_sensitive)
        ]
    )
    findings = []
    for commit in commits:
        for field, label in FIELDS:
            value = commit[field]
            for severity, term, pattern in compiled:
                matches = list(pattern.finditer(value))
                if not matches:
                    continue
                kinds = {match_kind(value, item.start(), item.end()) for item in matches}
                findings.append(
                    {
                        "severity": severity,
                        "term": term,
                        "commit": commit["commit"],
                        "field": field,
                        "field_label": label,
                        "occurrences": len(matches),
                        "match_kind": "、".join(sorted(kinds)),
                        "evidence": evidence(value),
                    }
                )
    return findings


def escape_table(value):
    return str(value).replace("|", "\\|").replace("`", "\\`")


def result_summary(findings):
    block = [item for item in findings if item["severity"] == "阻断"]
    review = [item for item in findings if item["severity"] == "复核"]
    return {
        "block_rows": len(block),
        "review_rows": len(review),
        "block_commits": len({item["commit"] for item in block}),
        "review_commits": len({item["commit"] for item in review}),
        "block_occurrences": sum(item["occurrences"] for item in block),
        "review_occurrences": sum(item["occurrences"] for item in review),
    }


def render_report(
    output,
    repo,
    target_ref,
    target_commit,
    target_tree,
    commits,
    merge_count,
    block_terms,
    review_terms,
    findings,
    case_sensitive,
):
    summary = result_summary(findings)
    if summary["block_rows"]:
        conclusion = "**结论：扫描有效，发现发布阻断身份字段，需完成历史脱敏。**"
        result = "blocked"
    elif summary["review_rows"]:
        conclusion = "**结论：扫描有效，未发现阻断身份字段，但存在 DCU 历史迁移复核项。**"
        result = "review"
    else:
        conclusion = "**结论：扫描通过，未发现配置的历史元数据字段。**"
        result = "passed"

    lines = [
        "# Git 历史元数据敏感字段审计报告",
        "",
        "## 1. 扫描结论",
        "",
        conclusion,
        "",
        "| 项目 | 内容 |",
        "| --- | --- |",
        "| 仓库 | `{}` |".format(escape_table(repo)),
        "| 目标 ref | `{}` |".format(escape_table(target_ref)),
        "| 固定 Commit | `{}` |".format(target_commit),
        "| Tip Tree | `{}` |".format(target_tree),
        "| 浅克隆 | 否 |",
        "| 可达 Commit | {} |".format(len(commits)),
        "| Merge Commit | {} |".format(merge_count),
        "| 阻断字段 | `{}` |".format("`, `".join(block_terms)),
        "| 复核字段 | `{}` |".format("`, `".join(review_terms)),
        "| 匹配方式 | {} |".format("大小写敏感" if case_sensitive else "大小写不敏感子串"),
        "| 扫描时间 | `{}` |".format(datetime.now().astimezone().isoformat(timespec="seconds")),
        "",
        "## 2. 数量汇总",
        "",
        "| 类型 | 命中 Commit | 字段行 | 出现次数 |",
        "| --- | ---: | ---: | ---: |",
        "| 阻断 | {} | {} | {} |".format(
            summary["block_commits"],
            summary["block_rows"],
            summary["block_occurrences"],
        ),
        "| 复核 | {} | {} | {} |".format(
            summary["review_commits"],
            summary["review_rows"],
            summary["review_occurrences"],
        ),
        "",
    ]

    term_rows = defaultdict(lambda: {"commits": set(), "rows": 0, "occurrences": 0, "severity": ""})
    field_rows = Counter()
    for item in findings:
        key = item["term"].casefold()
        term_rows[key]["severity"] = item["severity"]
        term_rows[key]["commits"].add(item["commit"])
        term_rows[key]["rows"] += 1
        term_rows[key]["occurrences"] += item["occurrences"]
        field_rows[(item["severity"], item["field_label"])] += 1

    lines.extend(
        [
            "### 按字段统计",
            "",
            "| 级别 | 字段 | 命中行 |",
            "| --- | --- | ---: |",
        ]
    )
    if field_rows:
        for (severity, label), count in sorted(field_rows.items()):
            lines.append("| {} | {} | {} |".format(severity, label, count))
    else:
        lines.append("| - | - | 0 |")

    lines.extend(
        [
            "",
            "### 按扫描词统计",
            "",
            "| 级别 | 扫描词 | 命中 Commit | 字段行 | 出现次数 |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    if term_rows:
        for key in sorted(term_rows):
            item = term_rows[key]
            lines.append(
                "| {} | `{}` | {} | {} | {} |".format(
                    item["severity"],
                    escape_table(key),
                    len(item["commits"]),
                    item["rows"],
                    item["occurrences"],
                )
            )
    else:
        lines.append("| - | - | 0 | 0 | 0 |")

    for severity, title in (("阻断", "## 3. 发布阻断项"), ("复核", "## 4. DCU 迁移复核项")):
        selected = [item for item in findings if item["severity"] == severity]
        lines.extend(
            [
                "",
                title,
                "",
                "| Commit | 字段 | 扫描词 | 匹配类型 | 次数 | 证据 |",
                "| --- | --- | --- | --- | ---: | --- |",
            ]
        )
        if selected:
            for item in selected:
                lines.append(
                    "| `{}` | {} | `{}` | {} | {} | `{}` |".format(
                        item["commit"][:12],
                        item["field_label"],
                        escape_table(item["term"]),
                        item["match_kind"],
                        item["occurrences"],
                        escape_table(item["evidence"]),
                    )
                )
        else:
            lines.append("| - | - | - | - | 0 | 无 |")

    lines.extend(
        [
            "",
            "## 5. 范围说明",
            "",
            "- 本报告只检查固定 Commit 的完整可达 Commit 元数据。",
            "- 未扫描文件路径、文件内容、工作区、未跟踪文件或其他不可达 refs。",
            "- `sugon/rogon` 命中是发布阻断；`dcu` 命中只进入迁移复核，不自动认定违规。",
            "- 本次未修改 Git 历史、refs、remote、index 或 worktree。",
            "",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return result, summary


def render_invalid_report(output, repo, target_ref, message):
    lines = [
        "# Git 历史元数据敏感字段审计报告",
        "",
        "## 扫描结论",
        "",
        "**结论：扫描无效，不得据此声明完整历史通过或存在多少命中。**",
        "",
        "| 项目 | 内容 |",
        "| --- | --- |",
        "| 仓库 | `{}` |".format(escape_table(repo)),
        "| 目标 ref | `{}` |".format(escape_table(target_ref)),
        "| 失败原因 | {} |".format(escape_table(message)),
        "| 扫描时间 | `{}` |".format(datetime.now().astimezone().isoformat(timespec="seconds")),
        "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def audit(args):
    repo = Path(args.repo).resolve()
    output = Path(args.output).resolve() if args.output else None
    if output is not None:
        require_output_outside_repo(repo, output)
    block_terms = normalize_terms(args.block_term, DEFAULT_BLOCK_TERMS)
    review_terms = normalize_terms(args.review_term, DEFAULT_REVIEW_TERMS)
    overlap = {item.casefold() for item in block_terms} & {
        item.casefold() for item in review_terms
    }
    if overlap:
        raise AuditError("同一扫描词不能同时是阻断和复核项：{}".format(", ".join(sorted(overlap))))
    git_text(repo, "rev-parse", "--git-dir")
    if is_shallow_repository(repo):
        raise AuditError("仓库是浅克隆，无法形成完整可达历史结论")
    target_commit = resolve_commit(repo, args.ref)
    if output is None:
        report_ref = resolve_report_ref(
            repo, args.ref, target_commit, args.report_ref
        )
        output = formal_report_path(
            Path(args.report_dir).resolve(),
            repo,
            report_ref,
            target_commit,
            datetime.now().astimezone(),
        )
        require_output_outside_repo(repo, output)
    target_tree = git_text(repo, "rev-parse", "{}^{{tree}}".format(target_commit)).strip()
    commits = collect_commits(repo, target_commit)
    merge_count = int(
        git_text(repo, "rev-list", "--merges", "--count", target_commit).strip()
    )
    findings = scan_commits(
        commits,
        block_terms,
        review_terms,
        args.case_sensitive,
    )
    result, summary = render_report(
        output,
        repo,
        args.ref,
        target_commit,
        target_tree,
        commits,
        merge_count,
        block_terms,
        review_terms,
        findings,
        args.case_sensitive,
    )
    print("REPORT={}".format(output))
    print("RESULT={}".format(result))
    print("TARGET_COMMIT={}".format(target_commit))
    print("REACHABLE_COMMITS={}".format(len(commits)))
    print("BLOCK_COMMITS={}".format(summary["block_commits"]))
    print("REVIEW_COMMITS={}".format(summary["review_commits"]))
    return 2 if findings else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="待扫描的完整 Git 仓库")
    parser.add_argument("--ref", default="HEAD", help="目标分支、Tag 或 Commit")
    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument("--output", help="兼容旧调用：显式输出 Markdown 报告")
    output_group.add_argument(
        "--report-dir", help="正式报告目录；自动生成统一格式的历史报告名"
    )
    parser.add_argument("--report-ref", help="报告文件名使用的人类可读分支标签")
    parser.add_argument(
        "--block-term",
        action="append",
        help="阻断扫描词，可重复；默认 sugon、rogon",
    )
    parser.add_argument(
        "--review-term",
        action="append",
        help="复核扫描词，可重复；默认 dcu",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="启用大小写敏感匹配；默认大小写不敏感",
    )
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    output = (
        Path(args.output).resolve()
        if args.output
        else Path(args.report_dir).resolve() / "invalid-history-metadata.md"
    )
    try:
        require_output_outside_repo(repo, output)
        return audit(args)
    except (AuditError, OSError, ValueError) as exc:
        try:
            require_output_outside_repo(repo, output)
            render_invalid_report(
                output,
                repo,
                args.ref,
                str(exc),
            )
            print("REPORT={}".format(output))
        except (AuditError, OSError) as report_exc:
            print("无法写入无效扫描报告：{}".format(report_exc), file=sys.stderr)
        print("RESULT=invalid", file=sys.stderr)
        print("ERROR={}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
