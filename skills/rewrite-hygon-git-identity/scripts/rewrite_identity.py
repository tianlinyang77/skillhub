#!/usr/bin/env python3
# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
"""Apply an explicitly approved, branch-scoped Git metadata rewrite."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

from identity_common import (
    FILTER_REPO_SHA256,
    FILTER_REPO_VERSION,
    SafetyError,
    affected_descendants,
    batch_commits,
    commit_fields,
    commits_for_ref,
    contains_forbidden,
    ensure_bare_mirror,
    exact_change_map,
    git,
    load_email_map,
    load_exact_changes,
    parent_map,
    read_json,
    require_git_version,
    require_hash,
    run,
    sha256_file,
    signed_commits,
    supported_email_mapping,
    unb64,
    validate_ref,
    write_json,
)


def callback_source(
    email_map: Dict[bytes, bytes],
    exact_changes: Dict[Tuple[str, str], object],
) -> str:
    email_literal = repr(email_map)
    rules: Dict[bytes, Dict[str, Tuple[bytes, bytes]]] = {}
    for (commit, field), raw_change in exact_changes.items():
        change = raw_change
        rules.setdefault(commit.encode("ascii"), {})[field] = (
            change.old,
            change.new,
        )
    rules_literal = repr(rules)
    return f"""
email_map = {email_literal}
rules = {rules_literal}
if commit.author_email in email_map:
    commit.author_email = email_map[commit.author_email]
if commit.committer_email in email_map:
    commit.committer_email = email_map[commit.committer_email]
rule = rules.get(commit.original_id, {{}})
for field, values in rule.items():
    old, new = values
    attribute = {{
        "author_name": "author_name",
        "author_email": "author_email",
        "committer_name": "committer_name",
        "committer_email": "committer_email",
        "message": "message",
    }}[field]
    current = getattr(commit, attribute)
    if current != old:
        raise RuntimeError(
            "approved old value mismatch for %s:%s" %
            (commit.original_id.decode("ascii"), field)
        )
    setattr(commit, attribute, new)
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite one branch in a dedicated fresh mirror. The mapping hash and "
            "signature loss must have been explicitly approved."
        )
    )
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--audit-dir", required=True, type=Path)
    parser.add_argument("--email-map", required=True, type=Path)
    parser.add_argument("--email-map-sha256", required=True)
    parser.add_argument("--exact-changes", type=Path)
    parser.add_argument("--exact-changes-sha256")
    parser.add_argument("--approved-signature-loss", required=True, type=int)
    parser.add_argument("--filter-repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--git-bin", default="git")
    args = parser.parse_args()

    try:
        require_git_version(args.git_bin)
        validate_ref(args.git_bin, args.ref, heads_only=True)
        ensure_bare_mirror(args.git_bin, args.repo)
        if not args.filter_repo.is_file():
            raise SafetyError(f"git-filter-repo not found: {args.filter_repo}")
        filter_hash = sha256_file(args.filter_repo)
        if filter_hash != FILTER_REPO_SHA256:
            raise SafetyError(
                f"git-filter-repo must be exact {FILTER_REPO_VERSION}; "
                f"expected SHA-256 {FILTER_REPO_SHA256}, got {filter_hash}"
            )
        if args.output.exists() and any(args.output.iterdir()):
            raise SafetyError(f"output directory is not empty: {args.output}")
        args.output.mkdir(parents=True, exist_ok=True)

        audit_summary = read_json(args.audit_dir / "audit-summary.json")
        if not isinstance(audit_summary, dict) or audit_summary.get("version") != 1:
            raise SafetyError("audit summary is missing or incompatible")
        current_tip = git(
            args.git_bin, args.repo, "rev-parse", args.ref
        ).decode("ascii").strip()
        if current_tip != audit_summary.get("tip"):
            raise SafetyError(
                "rewrite mirror tip differs from audited tip: "
                f"{current_tip} != {audit_summary.get('tip')}"
            )

        email_hash = require_hash(
            args.email_map,
            args.email_map_sha256,
            label="email mapping",
        )
        email_map = load_email_map(args.email_map)
        proposed_map = load_email_map(args.audit_dir / "proposed-email-map.json")
        if email_map != proposed_map:
            raise SafetyError(
                "approved email mapping differs from the deterministic audit proposal"
            )

        template = read_json(args.audit_dir / "exact-replacements.template.json")
        template_entries = template.get("changes") if isinstance(template, dict) else None
        if not isinstance(template_entries, list):
            raise SafetyError("exact replacement template is invalid")
        required_exact: Dict[Tuple[str, str], bytes] = {}
        for index, entry in enumerate(template_entries):
            if not isinstance(entry, dict):
                raise SafetyError(f"invalid exact replacement template entry {index}")
            commit = str(entry.get("commit", ""))
            field = str(entry.get("field", ""))
            old_b64 = str(entry.get("old_b64", ""))
            required_exact[(commit, field)] = unb64(
                old_b64, label=f"template changes[{index}].old_b64"
            )

        if required_exact and args.exact_changes is None:
            raise SafetyError(
                f"{len(required_exact)} exact replacements require an approved file"
            )
        if args.exact_changes is not None and not args.exact_changes_sha256:
            raise SafetyError("--exact-changes-sha256 is required with --exact-changes")
        if args.exact_changes is None and args.exact_changes_sha256:
            raise SafetyError("--exact-changes-sha256 requires --exact-changes")

        exact_hash = ""
        exact_changes_list = load_exact_changes(args.exact_changes)
        exact_changes = exact_change_map(exact_changes_list)
        if args.exact_changes is not None:
            exact_hash = require_hash(
                args.exact_changes,
                str(args.exact_changes_sha256),
                label="exact changes",
            )
        if set(exact_changes) != set(required_exact):
            raise SafetyError(
                "exact-change keys differ from audit blockers: "
                f"missing={len(set(required_exact) - set(exact_changes))}, "
                f"extra={len(set(exact_changes) - set(required_exact))}"
            )
        for key, old in required_exact.items():
            if exact_changes[key].old != old:
                raise SafetyError(f"approved old value differs from audit for {key}")

        ordered = commits_for_ref(args.git_bin, args.repo, args.ref)
        bodies = batch_commits(args.git_bin, args.repo, ordered)
        parents = parent_map(bodies)
        signed = signed_commits(bodies)
        directly_changed: Set[str] = set()

        for commit in ordered:
            fields = commit_fields(bodies[commit])
            expected = dict(fields)
            for field in ("author_email", "committer_email"):
                if expected[field] in email_map:
                    expected[field] = email_map[expected[field]]
                    directly_changed.add(commit)
            for field in fields:
                rule = exact_changes.get((commit, field))
                if rule is not None:
                    if fields[field] != rule.old:
                        raise SafetyError(
                            f"approved old value does not match {commit}:{field}"
                        )
                    expected[field] = rule.new
                    directly_changed.add(commit)
                if contains_forbidden(expected[field]):
                    raise SafetyError(
                        f"forbidden token remains unresolved in {commit}:{field}"
                    )
            for field in ("author_email", "committer_email"):
                value = fields[field]
                mapped = supported_email_mapping(value)
                if mapped is not None and email_map.get(value) != mapped:
                    raise SafetyError(
                        f"deterministic email mapping missing for {commit}:{field}"
                    )

        affected = affected_descendants(
            ordered, parents, directly_changed
        )
        predicted_signature_loss = len(affected & signed)
        if predicted_signature_loss != args.approved_signature_loss:
            raise SafetyError(
                f"predicted signature loss is {predicted_signature_loss}, "
                f"but approval is {args.approved_signature_loss}"
            )
        if not affected:
            raise SafetyError("nothing needs rewriting")

        plan = {
            "version": 1,
            "ref": args.ref,
            "old_tip": current_tip,
            "email_map_path": str(args.email_map.resolve()),
            "email_map_sha256": email_hash,
            "exact_changes_path": (
                str(args.exact_changes.resolve()) if args.exact_changes else None
            ),
            "exact_changes_sha256": exact_hash or None,
            "directly_changed_commits": len(directly_changed),
            "affected_commits": len(affected),
            "signed_commits": len(signed),
            "approved_signature_loss": args.approved_signature_loss,
            "filter_repo_version": FILTER_REPO_VERSION,
            "filter_repo_sha256": filter_hash,
        }
        write_json(args.output / "approved-change-plan.json", plan)
        (args.output / "affected-commits-approved.txt").write_text(
            "".join(f"{commit}\n" for commit in sorted(affected)),
            encoding="ascii",
        )
        (args.output / "affected-signed-commits-approved.txt").write_text(
            "".join(f"{commit}\n" for commit in sorted(affected & signed)),
            encoding="ascii",
        )
        callback = callback_source(email_map, exact_changes)
        (args.output / "commit-callback.py").write_text(
            callback + "\n", encoding="utf-8"
        )

        command = [
            sys.executable,
            str(args.filter_repo),
            "--refs",
            args.ref,
            "--commit-callback",
            callback,
        ]
        completed = run(command, cwd=args.repo, check=False)
        (args.output / "git-filter-repo.stdout.txt").write_bytes(completed.stdout)
        (args.output / "git-filter-repo.stderr.txt").write_bytes(completed.stderr)
        if completed.returncode != 0:
            raise SafetyError(
                "git-filter-repo failed; dedicated rewrite mirror must be discarded. "
                "No retry with --force is permitted.\n"
                + completed.stderr.decode("utf-8", "replace").strip()
            )

        candidates = (
            args.repo / "filter-repo" / "commit-map",
            args.repo / ".git" / "filter-repo" / "commit-map",
        )
        commit_map_source = next((path for path in candidates if path.is_file()), None)
        if commit_map_source is None:
            raise SafetyError("git-filter-repo did not produce commit-map evidence")
        commit_map = args.output / "commit-map.txt"
        shutil.copyfile(commit_map_source, commit_map)

        new_tip = git(
            args.git_bin, args.repo, "rev-parse", args.ref
        ).decode("ascii").strip()
        new_tree = git(
            args.git_bin, args.repo, "rev-parse", f"{new_tip}^{{tree}}"
        ).decode("ascii").strip()
        result = {
            "version": 1,
            "status": "REWRITTEN_PENDING_VALIDATION",
            "ref": args.ref,
            "old_tip": current_tip,
            "new_tip": new_tip,
            "new_tree": new_tree,
            "commit_map": str(commit_map.resolve()),
            "commit_map_sha256": sha256_file(commit_map),
            "affected_commits": len(affected),
            "approved_signature_loss": args.approved_signature_loss,
        }
        write_json(args.output / "rewrite-result.json", result)
        print("STATUS=REWRITTEN_PENDING_VALIDATION")
        print(f"OLD_TIP={current_tip}")
        print(f"NEW_TIP={new_tip}")
        print(f"AFFECTED_COMMITS={len(affected)}")
        print(f"APPROVED_SIGNATURE_LOSS={args.approved_signature_loss}")
        print(f"COMMIT_MAP={commit_map.resolve()}")
        print("NEXT=RUN_STRICT_VALIDATION")
    except SafetyError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
