# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze hipprof CSV outputs and export a compact markdown report."
    )
    parser.add_argument(
        "input",
        type=str,
        help="hipprof artifact prefix or one of *.hipkernel.csv / *.hiptrace.csv / *.hsatrace.csv",
    )
    parser.add_argument(
        "--export-dir",
        type=str,
        default="",
        help="Directory to write report.md and copied artifacts",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Top rows to keep per table",
    )
    parser.add_argument(
        "--export-analysis-json",
        action="store_true",
        help="Also write analysis.json next to report.md",
    )
    return parser.parse_args()


def resolve_prefix(input_path: str) -> Path:
    path = Path(input_path)
    suffixes = [".hipkernel.csv", ".hiptrace.csv", ".hsatrace.csv"]
    as_str = str(path)
    for suffix in suffixes:
        if as_str.endswith(suffix):
            return Path(as_str[: -len(suffix)])
    return path


def artifact_paths(prefix: Path) -> dict[str, Path]:
    prefix_str = str(prefix)
    return {
        "hipkernel": Path(prefix_str + ".hipkernel.csv"),
        "hiptrace": Path(prefix_str + ".hiptrace.csv"),
        "hsatrace": Path(prefix_str + ".hsatrace.csv"),
        "db": Path(prefix_str + ".db"),
    }


def to_int(value: str) -> int:
    return int(str(value).strip().replace(",", ""))


def to_float(value: str) -> float:
    return float(str(value).strip().replace(",", ""))


# ── hipprof CSV 列名映射 (兼容不同 DTK 版本) ──
CSV_COLUMN_ALIASES = {
    "Name": ["Name", "KernelName", "name", "API Name"],
    "Calls": ["Calls", "call_count", "count"],
    "TotalDurationNs": ["TotalDurationNs", "total_duration_ns", "TotalDuration", "total_time_ns"],
    "AverageNs": ["AverageNs", "average_ns", "AvgDuration", "AverageDurationNs"],
    "Percentage": ["Percentage", "percentage", "Percent", "time_pct"],
}

def resolve_columns(headers: list[str]) -> dict:
    """自动检测 hipprof CSV 列名版本 (兼容 DTK 24.04/25.04/26.04)"""
    mapping = {}
    for canonical, aliases in CSV_COLUMN_ALIASES.items():
        for h in headers:
            h_clean = h.strip().strip('"').strip("'")
            if h_clean in aliases or h_clean.lower() in [a.lower() for a in aliases]:
                mapping[canonical] = h
                break
    return mapping

def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        cols = resolve_columns(fieldnames)

        # 检查关键列是否存在
        missing = [c for c in ["Name", "TotalDurationNs"] if c not in cols]
        if missing:
            print(f"[WARN] hipprof CSV missing expected columns: {missing}")
            print(f"       Available: {fieldnames}")

        for row in reader:
            name_col = cols.get("Name", "")
            name = (row.get(name_col, "") or "").strip()
            if not name or name == "Total":
                continue

            total_col = cols.get("TotalDurationNs", "TotalDurationNs")
            calls_col = cols.get("Calls", "Calls")
            avg_col = cols.get("AverageNs", "AverageNs")
            pct_col = cols.get("Percentage", "Percentage")

            rows.append(
                {
                    "name": name,
                    "calls": to_int(row.get(calls_col, "0")),
                    "total_duration_ns": to_int(row.get(total_col, "0")),
                    "average_ns": to_int(row.get(avg_col, "0")),
                    "percentage": to_float(row.get(pct_col, "0")),
                }
            )
    rows.sort(key=lambda item: item["total_duration_ns"], reverse=True)
    return rows


def top_rows(rows: list[dict], limit: int) -> list[dict]:
    return rows[: max(limit, 0)]


def ns_to_ms(ns: int) -> float:
    return ns / 1_000_000.0


def summarize_runtime(rows: list[dict]) -> list[str]:
    notes: list[str] = []
    by_name = {row["name"]: row for row in rows}
    sync = by_name.get("hipDeviceSynchronize")
    launch = by_name.get("hipLaunchKernel")
    if sync and sync["percentage"] >= 20.0:
        notes.append(
            f"HIP runtime shows heavy synchronize pressure: hipDeviceSynchronize {sync['percentage']:.1f}%."
        )
    if launch and launch["percentage"] >= 15.0:
        notes.append(
            f"HIP runtime shows visible launch overhead: hipLaunchKernel {launch['percentage']:.1f}%."
        )
    return notes


def summarize_hsa(rows: list[dict]) -> list[str]:
    notes: list[str] = []
    by_name = {row["name"]: row for row in rows}
    wait = by_name.get("hsa_signal_wait_scacquire")
    alloc = by_name.get("hsa_amd_memory_pool_allocate")
    if wait and wait["percentage"] >= 20.0:
        notes.append(
            f"HSA runtime shows visible device wait: hsa_signal_wait_scacquire {wait['percentage']:.1f}%."
        )
    if alloc and alloc["percentage"] >= 20.0:
        notes.append(
            f"HSA runtime shows visible allocation/setup pressure: hsa_amd_memory_pool_allocate {alloc['percentage']:.1f}%."
        )
    return notes


def summarize_kernels(rows: list[dict]) -> list[str]:
    if not rows:
        return ["No kernel rows found."]
    top = rows[0]
    notes = [
        f"Top kernel is `{top['name']}` at {top['percentage']:.1f}% ({ns_to_ms(top['total_duration_ns']):.3f} ms total)."
    ]
    if top["percentage"] >= 70.0:
        notes.append("Kernel time is highly concentrated; this looks like a kernel-dominant run.")
    return notes


def render_table(title: str, rows: list[dict]) -> str:
    lines = [f"## {title}", "", "| Name | Calls | Total ms | Avg us | % |", "| --- | ---: | ---: | ---: | ---: |"]
    for row in rows:
        lines.append(
            f"| `{row['name']}` | {row['calls']} | {ns_to_ms(row['total_duration_ns']):.3f} | "
            f"{row['average_ns'] / 1000.0:.3f} | {row['percentage']:.2f} |"
        )
    if len(lines) == 4:
        lines.append("| _none_ | 0 | 0.000 | 0.000 | 0.00 |")
    return "\n".join(lines)


def copy_existing(paths: Iterable[Path], export_dir: Path) -> list[str]:
    copied: list[str] = []
    export_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if not path.exists():
            continue
        target = export_dir / path.name
        shutil.copy2(path, target)
        copied.append(target.name)
    return copied


def build_payload(prefix: Path, top_k: int) -> dict:
    paths = artifact_paths(prefix)
    kernel_rows = load_rows(paths["hipkernel"])
    hip_rows = load_rows(paths["hiptrace"])
    hsa_rows = load_rows(paths["hsatrace"])
    return {
        "input_prefix": str(prefix),
        "artifacts": {name: str(path) for name, path in paths.items() if path.exists()},
        "summary": {
            "kernel_notes": summarize_kernels(kernel_rows),
            "hip_runtime_notes": summarize_runtime(hip_rows),
            "hsa_runtime_notes": summarize_hsa(hsa_rows),
        },
        "top_kernels": top_rows(kernel_rows, top_k),
        "top_hip_runtime": top_rows(hip_rows, top_k),
        "top_hsa_runtime": top_rows(hsa_rows, top_k),
    }


def build_report(payload: dict) -> str:
    lines = [
        "# hipprof report",
        "",
        "## 1. Input",
        "",
        f"- prefix: `{payload['input_prefix']}`",
        f"- artifacts: {', '.join(sorted(payload['artifacts'].keys())) or 'none'}",
        "",
        "## 2. Summary",
        "",
    ]
    for note_group in (
        payload["summary"]["kernel_notes"],
        payload["summary"]["hip_runtime_notes"],
        payload["summary"]["hsa_runtime_notes"],
    ):
        for note in note_group:
            lines.append(f"- {note}")
    if lines[-1] == "":
        lines.append("- No summary notes available.")
    lines.extend(
        [
            "",
            render_table("3. Top GPU Kernels", payload["top_kernels"]),
            "",
            render_table("4. Top HIP Runtime APIs", payload["top_hip_runtime"]),
            "",
            render_table("5. Top HSA Runtime APIs", payload["top_hsa_runtime"]),
            "",
            "## 6. Next-Step Classification",
            "",
        ]
    )

    kernel_top = payload["top_kernels"][0]["percentage"] if payload["top_kernels"] else 0.0
    sync_top = next(
        (row["percentage"] for row in payload["top_hip_runtime"] if row["name"] == "hipDeviceSynchronize"),
        0.0,
    )
    wait_top = next(
        (row["percentage"] for row in payload["top_hsa_runtime"] if row["name"] == "hsa_signal_wait_scacquire"),
        0.0,
    )
    if kernel_top >= 60.0 and sync_top < 20.0 and wait_top < 20.0:
        classification = "kernel-operator"
        reason = "Kernel time is concentrated and runtime wait is not dominant."
    elif sync_top >= 20.0 or wait_top >= 20.0:
        classification = "bubble-scheduling"
        reason = "Runtime synchronize or HSA wait is large enough to inspect launch, dependency, or host pacing."
    else:
        classification = "mixed"
        reason = "Kernel and runtime signals are both visible; inspect model path attribution before deeper changes."
    lines.extend([f"- classification: `{classification}`", f"- reason: {reason}", ""])
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    prefix = resolve_prefix(args.input)
    payload = build_payload(prefix, args.top_k)
    report = build_report(payload)

    if args.export_dir:
        export_dir = Path(args.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / "report.md").write_text(report, encoding="utf-8")
        copied = copy_existing(artifact_paths(prefix).values(), export_dir)
        payload["copied_artifacts"] = copied
        if args.export_analysis_json:
            (export_dir / "analysis.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        print(f"Wrote report to {export_dir / 'report.md'}")
        if args.export_analysis_json:
            print(f"Wrote analysis to {export_dir / 'analysis.json'}")
        return

    print(report)


if __name__ == "__main__":
    main()
