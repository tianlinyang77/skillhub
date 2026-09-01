#!/usr/bin/env python3
# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""Validate the machine-relevant portion of ``skills add . --list`` output."""

from __future__ import print_function

import re
import sys

from skillhub import ROOT, load_components


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
FOUND_RE = re.compile(r"\bFound\s+(\d+)\s+skills?\b")


def discovery_errors(raw, expected):
    clean = ANSI_RE.sub("", raw)
    errors = []
    match = FOUND_RE.search(clean)
    if match is None:
        return ["skills CLI output did not contain a discovery count"]
    if int(match.group(1)) != len(expected):
        errors.append("skills CLI discovered {} skills; catalog registers {}".format(
            int(match.group(1)), len(expected)))

    output_lines = {
        line.strip().lstrip("|│").strip()
        for line in clean.splitlines()
    }
    missing = [name for name in expected if name not in output_lines]
    if missing:
        errors.append("skills CLI omitted registered skill(s): {}".format(
            ", ".join(missing)))
    return errors


def main():
    raw = sys.stdin.read()
    print(raw, end="")
    expected = sorted(
        spec["catalog_dir"]
        for component in load_components()
        for spec in component["skills"]
    )
    errors = discovery_errors(raw, expected)
    for error in errors:
        print("ERROR: {}".format(error))
    if errors:
        return 1
    print("Validated CLI discovery for {} skill(s).".format(len(expected)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
