#!/usr/bin/env python3
# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""Run the pinned Agent Skills reference validator over catalog candidates."""

from __future__ import print_function

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from skillhub import ROOT


def published_directories():
    parent = ROOT / "skills"
    if not parent.is_dir():
        return []
    return [
        path for path in sorted(parent.iterdir())
        if path.is_dir() and (path / "SKILL.md").is_file()
    ]


def staging_directories():
    parent = ROOT / "staging"
    if not parent.is_dir():
        return []
    return [
        path for path in sorted(parent.iterdir())
        if path.is_dir() and (path / "SKILL.md.candidate").is_file()
    ]


def main():
    # skills-ref currently calls Path.read_text() without an encoding. Re-exec
    # once in UTF-8 mode on Windows so Chinese skill bodies are not decoded as
    # the active legacy code page.
    if os.name == "nt" and not sys.flags.utf8_mode and os.environ.get("SKILLHUB_UTF8_REEXEC") != "1":
        environment = dict(os.environ)
        environment["PYTHONUTF8"] = "1"
        environment["SKILLHUB_UTF8_REEXEC"] = "1"
        return subprocess.call([sys.executable, str(Path(__file__).resolve())], env=environment)

    try:
        from skills_ref import validate
    except ImportError:
        print("ERROR: skills-ref is unavailable; install requirements-dev.txt")
        return 1

    published = published_directories()
    staging = staging_directories()
    problems = 0
    for skill_dir in published:
        errors = validate(skill_dir)
        for error in errors:
            print("ERROR: {}: {}".format(skill_dir.relative_to(ROOT), error))
        problems += len(errors)

    # Staging entrypoints deliberately use SKILL.md.candidate so even a
    # --full-depth installer cannot publish them. Validate an isolated renamed
    # copy against the official reference implementation.
    with tempfile.TemporaryDirectory(prefix="skillhub-spec-") as temp:
        temp_root = Path(temp)
        for candidate_dir in staging:
            isolated = temp_root / candidate_dir.name
            shutil.copytree(str(candidate_dir), str(isolated))
            (isolated / "SKILL.md.candidate").replace(isolated / "SKILL.md")
            errors = validate(isolated)
            for error in errors:
                print("ERROR: {}: {}".format(candidate_dir.relative_to(ROOT), error))
            problems += len(errors)

    if problems:
        print("Agent Skills reference validation failed with {} problem(s).".format(problems))
        return 1
    print("Agent Skills reference validation passed for {} published and {} staging skill(s).".format(
        len(published), len(staging)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
