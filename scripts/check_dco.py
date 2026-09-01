#!/usr/bin/env python3
# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""Require a valid Developer Certificate of Origin trailer on PR commits."""

from __future__ import print_function

import argparse
import re
import subprocess
import sys


SIGNOFF_RE = re.compile(
    r"^Signed-off-by:\s+[^<>\r\n]+\s+<[^<>\s]+@[^<>\s]+>\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def has_valid_signoff(message):
    return bool(SIGNOFF_RE.search(message))


def commits_between(base, head):
    output = subprocess.check_output(
        ["git", "log", "--format=%H%x00%B%x00", "{}..{}".format(base, head)],
        universal_newlines=True,
    )
    fields = output.split("\0")
    commits = []
    for index in range(0, len(fields) - 1, 2):
        commit = fields[index].strip()
        message = fields[index + 1]
        if commit:
            commits.append((commit, message))
    return commits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="pull-request base commit")
    parser.add_argument("--head", required=True, help="pull-request head commit")
    args = parser.parse_args()

    commits = commits_between(args.base, args.head)
    failures = []
    for commit, message in commits:
        if not has_valid_signoff(message):
            failures.append(commit)
            print("ERROR: {} is missing a valid Signed-off-by trailer".format(commit))
    if failures:
        print("DCO check failed for {} commit(s). Use git commit --signoff.".format(
            len(failures)))
        return 1
    print("DCO check passed for {} commit(s).".format(len(commits)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
