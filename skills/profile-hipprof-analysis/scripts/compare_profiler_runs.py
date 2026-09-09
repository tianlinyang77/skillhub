# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from torch_trace_common import markdown_table, sanitize_markdown_cell, shorten_text
from torch_trace_report import build_measurement_notes


DEFAULT_KERNEL_TERMS = [
    "indexFuncLargeIndex",
    "indexSelectLargeIndex",
    "FillFunctor<long>",
    "random_from_to_kernel",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare multiple profile-hipprof-analysis export directories. "
            "Each run can be PATH or LABEL=PATH, where PATH is a run directory, "
            "an analysis directory, or analysis.json."
        )
    )
    parser.add_argument("runs", nargs="+", help="Run paths, optionally prefixed with LABEL=")
    parser.add_argument(
        "--kernel-term",
        action="append",
        default=[],
        help=f"Kernel substring to compare. Default: {', '.join(DEFAULT_KERNEL_TERMS)}",
    )
    parser.add_argument(
        "--annotation",
        action="append",
        default=[],
        help="record_function annotation substring to compare. Can be passed multiple times.",
    )
    parser.add_argument("--export-md", type=str, default="", help="Optional markdown output path")
    parser.add_argument("--export-json", type=str, default="", help="Optional structured JSON output path")
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def split_run_arg(value: str) -> Tuple[str | None, Path]:
    if "=" in value:
        label, raw_path = value.split("=", 1)
        if label and raw_path:
            return label, Path(raw_path)
    return None, Path(value)


def resolve_analysis_path(path: Path) -> Path:
    if path.is_file():
        return path
    candidates = [
        path / "analysis.json",
        path / "analysis" / "analysis.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"cannot locate analysis.json under {path}")


def resolve_record_attribution_path(path: Path, analysis_path: Path) -> Path | None:
    candidates = [
        analysis_path.parent / "record_function_attribution.json",
        path / "record_function_attribution.json",
        path / "analysis" / "record_function_attribution.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def us_to_ms(value: float) -> float:
    return float(value or 0.0) / 1000.0


def pct_delta(value: float, baseline: float) -> str:
    if not baseline:
        return "n/a"
    return f"{((value - baseline) / baseline) * 100.0:+.2f}%"


def find_first(items: Sequence[Dict[str, Any]], key: str, value: str) -> Dict[str, Any] | None:
    for item in items:
        if item.get(key) == value:
            return item
    return None


def find_kernel_term_in_top_kernels(analysis: Dict[str, Any], term: str) -> Dict[str, Any]:
    total_us = 0.0
    count = 0
    share_pct = 0.0
    example = ""
    for kernel in analysis.get("top_kernels", []) or []:
        name = str(kernel.get("name", ""))
        if term not in name:
            continue
        total_us += float(kernel.get("device_time_total_us", 0.0) or 0.0)
        count += int(kernel.get("count", 0) or 0)
        share_pct += float(kernel.get("device_share_pct", 0.0) or 0.0)
        if not example:
            example = name
    return {
        "kernel_term": term,
        "total_us": total_us,
        "count": count,
        "share_pct": share_pct,
        "source": "analysis.top_kernels" if count else "",
        "example": example,
    }


def find_special_kernel(record: Dict[str, Any], section: str, term: str) -> Dict[str, Any] | None:
    return find_first(record.get(section, []) or [], "kernel_term", term)


def summarize_kernel_term(analysis: Dict[str, Any], record: Dict[str, Any], term: str) -> Dict[str, Any]:
    row = find_special_kernel(record, "special_kernels_by_launch_cpu_op", term)
    top_launch = {}
    if row and row.get("by_cpu_op"):
        top_launch = row["by_cpu_op"][0]

    annotation_row = find_special_kernel(record, "special_kernels", term)
    top_annotation = {}
    if annotation_row and annotation_row.get("by_annotation"):
        top_annotation = annotation_row["by_annotation"][0]

    if row:
        return {
            "kernel_term": term,
            "total_us": float(row.get("total_us", 0.0) or 0.0),
            "count": int(row.get("count", 0) or 0),
            "source": "record.special_kernels_by_launch_cpu_op",
            "top_launch_cpu_op": top_launch.get("cpu_op", ""),
            "top_launch_cpu_op_us": float(top_launch.get("total_us", 0.0) or 0.0),
            "top_launch_cpu_op_count": int(top_launch.get("count", 0) or 0),
            "top_annotation": top_annotation.get("annotation", ""),
            "top_annotation_us": float(top_annotation.get("total_us", 0.0) or 0.0),
            "top_annotation_count": int(top_annotation.get("count", 0) or 0),
        }

    if annotation_row:
        top = top_annotation
        return {
            "kernel_term": term,
            "total_us": float(annotation_row.get("total_us", 0.0) or 0.0),
            "count": int(annotation_row.get("count", 0) or 0),
            "source": "record.special_kernels",
            "top_launch_cpu_op": "",
            "top_launch_cpu_op_us": 0.0,
            "top_launch_cpu_op_count": 0,
            "top_annotation": top.get("annotation", ""),
            "top_annotation_us": float(top.get("total_us", 0.0) or 0.0),
            "top_annotation_count": int(top.get("count", 0) or 0),
        }

    fallback = find_kernel_term_in_top_kernels(analysis, term)
    fallback.update(
        {
            "top_launch_cpu_op": "",
            "top_launch_cpu_op_us": 0.0,
            "top_launch_cpu_op_count": 0,
            "top_annotation": "",
            "top_annotation_us": 0.0,
            "top_annotation_count": 0,
        }
    )
    return fallback


def summarize_annotation(record: Dict[str, Any], annotation_substring: str) -> Dict[str, Any]:
    total_annotation_us = 0.0
    total_kernel_overlap_us = 0.0
    count = 0
    top_kernel_class = ""
    top_kernel_overlap_us = 0.0
    for row in record.get("gpu_annotations", []) or []:
        name = str(row.get("annotation", ""))
        if annotation_substring not in name:
            continue
        total_annotation_us += float(row.get("annotation_dur_us", 0.0) or 0.0)
        total_kernel_overlap_us += float(row.get("kernel_overlap_us", 0.0) or 0.0)
        count += int(row.get("count", 0) or 0)
        for item in row.get("top_kernel_classes", []) or []:
            overlap_us = float(item.get("overlap_us", 0.0) or 0.0)
            if overlap_us > top_kernel_overlap_us:
                top_kernel_overlap_us = overlap_us
                top_kernel_class = str(item.get("kernel_class", ""))
    return {
        "annotation": annotation_substring,
        "count": count,
        "annotation_dur_us": total_annotation_us,
        "kernel_overlap_us": total_kernel_overlap_us,
        "top_kernel_class": top_kernel_class,
        "top_kernel_overlap_us": top_kernel_overlap_us,
    }


def summarize_run(label: str, input_path: Path, kernel_terms: Sequence[str], annotations: Sequence[str]) -> Dict[str, Any]:
    analysis_path = resolve_analysis_path(input_path)
    analysis = load_json(analysis_path)
    record_path = resolve_record_attribution_path(input_path, analysis_path)
    record = load_json(record_path) if record_path else {}

    utilization = analysis.get("utilization", {}) or {}
    joint_summary = analysis.get("joint_summary", {}) or {}
    dispatch = analysis.get("dispatch_analysis", {}) or {}
    top_kernel = (analysis.get("top_kernels", []) or [{}])[0]
    top_dispatch = (dispatch.get("top_cpu_ops", []) or [{}])[0]

    return {
        "label": label,
        "input_path": str(input_path),
        "analysis_json": str(analysis_path),
        "record_function_attribution_json": str(record_path) if record_path else "",
        "utilization": utilization,
        "joint_summary": joint_summary,
        "top_kernel": {
            "name": top_kernel.get("name", ""),
            "device_time_total_us": float(top_kernel.get("device_time_total_us", 0.0) or 0.0),
            "count": int(top_kernel.get("count", 0) or 0),
            "device_share_pct": float(top_kernel.get("device_share_pct", 0.0) or 0.0),
        },
        "top_dispatch_cpu_op": {
            "cpu_op": top_dispatch.get("cpu_op", ""),
            "dispatch_exposed_us": float(top_dispatch.get("dispatch_exposed_us", 0.0) or 0.0),
            "count": int(top_dispatch.get("count", 0) or 0),
            "max_dispatch_exposed_us": float(top_dispatch.get("max_dispatch_exposed_us", 0.0) or 0.0),
        },
        "kernel_terms": [summarize_kernel_term(analysis, record, term) for term in kernel_terms],
        "annotations": [summarize_annotation(record, annotation) for annotation in annotations],
        "measurement_notes": analysis.get("measurement_notes")
        or build_measurement_notes(utilization, joint_summary, dispatch),
    }


def make_run_label(raw_label: str | None, path: Path) -> str:
    if raw_label:
        return raw_label
    if path.name == "analysis.json":
        return path.parent.parent.name if path.parent.name == "analysis" else path.parent.name
    return path.name


def fmt_ms(us: float) -> str:
    return f"{us_to_ms(us):.1f}"


def build_markdown(summary: Dict[str, Any]) -> str:
    runs = summary["runs"]
    baseline = runs[0]

    overview_rows = []
    for run in runs:
        util = run["utilization"]
        joint = run["joint_summary"]
        top_kernel = run["top_kernel"]
        top_dispatch = run["top_dispatch_cpu_op"]
        overview_rows.append(
            [
                sanitize_markdown_cell(run["label"]),
                f"{float(util.get('utilization_ratio', 0.0) or 0.0) * 100.0:.2f}",
                fmt_ms(util.get("e2e_total_us", 0.0)),
                fmt_ms(util.get("gpu_busy_us", 0.0)),
                fmt_ms(joint.get("total_bubble_us", 0.0)),
                fmt_ms(joint.get("dispatch_exposed_us", 0.0)),
                fmt_ms(joint.get("post_launch_gap_us", 0.0)),
                sanitize_markdown_cell(shorten_text(top_kernel.get("name", ""), 52)),
                f"{fmt_ms(top_kernel.get('device_time_total_us', 0.0))}/{top_kernel.get('count', 0)}",
                sanitize_markdown_cell(shorten_text(top_dispatch.get("cpu_op", ""), 36)),
                f"{fmt_ms(top_dispatch.get('dispatch_exposed_us', 0.0))}/{top_dispatch.get('count', 0)}",
            ]
        )

    delta_rows = []
    base_util = baseline["utilization"]
    base_joint = baseline["joint_summary"]
    base_top = baseline["top_kernel"]
    for run in runs[1:]:
        util = run["utilization"]
        joint = run["joint_summary"]
        top = run["top_kernel"]
        delta_rows.append(
            [
                sanitize_markdown_cell(run["label"]),
                pct_delta(float(util.get("e2e_total_us", 0.0) or 0.0), float(base_util.get("e2e_total_us", 0.0) or 0.0)),
                pct_delta(float(util.get("gpu_busy_us", 0.0) or 0.0), float(base_util.get("gpu_busy_us", 0.0) or 0.0)),
                pct_delta(float(joint.get("total_bubble_us", 0.0) or 0.0), float(base_joint.get("total_bubble_us", 0.0) or 0.0)),
                pct_delta(float(top.get("device_time_total_us", 0.0) or 0.0), float(base_top.get("device_time_total_us", 0.0) or 0.0)),
            ]
        )

    kernel_term_rows = []
    for run in runs:
        for item in run["kernel_terms"]:
            kernel_term_rows.append(
                [
                    sanitize_markdown_cell(run["label"]),
                    sanitize_markdown_cell(item["kernel_term"]),
                    fmt_ms(item.get("total_us", 0.0)),
                    str(item.get("count", 0)),
                    sanitize_markdown_cell(shorten_text(item.get("source", ""), 36)),
                    sanitize_markdown_cell(shorten_text(item.get("top_launch_cpu_op", ""), 52)),
                    f"{fmt_ms(item.get('top_launch_cpu_op_us', 0.0))}/{item.get('top_launch_cpu_op_count', 0)}",
                    sanitize_markdown_cell(shorten_text(item.get("top_annotation", ""), 52)),
                    f"{fmt_ms(item.get('top_annotation_us', 0.0))}/{item.get('top_annotation_count', 0)}",
                ]
            )

    annotation_rows = []
    has_annotations = any(run["annotations"] for run in runs)
    if has_annotations:
        for run in runs:
            for item in run["annotations"]:
                annotation_rows.append(
                    [
                        sanitize_markdown_cell(run["label"]),
                        sanitize_markdown_cell(shorten_text(item["annotation"], 52)),
                        str(item["count"]),
                        fmt_ms(item.get("annotation_dur_us", 0.0)),
                        fmt_ms(item.get("kernel_overlap_us", 0.0)),
                        sanitize_markdown_cell(shorten_text(item.get("top_kernel_class", ""), 36)),
                        fmt_ms(item.get("top_kernel_overlap_us", 0.0)),
                    ]
                )

    warning_rows = []
    for run in runs:
        notes = run.get("measurement_notes") or []
        warning_rows.append(
            [
                sanitize_markdown_cell(run["label"]),
                "<br>".join(sanitize_markdown_cell(note) for note in notes) if notes else "-",
            ]
        )

    artifact_rows = [
        [
            sanitize_markdown_cell(run["label"]),
            f"`{run['analysis_json']}`",
            f"`{run['record_function_attribution_json']}`" if run["record_function_attribution_json"] else "-",
        ]
        for run in runs
    ]

    lines = [
        "# Torch Profiler 多运行对比报告",
        "",
        "## 1. Overview",
        *markdown_table(
            [
                "run",
                "util%",
                "e2e ms",
                "gpu busy ms",
                "bubble ms",
                "dispatch ms",
                "post-launch ms",
                "top kernel",
                "top kernel ms/count",
                "top dispatch",
                "top dispatch ms/count",
            ],
            overview_rows,
        ),
        "",
        "## 2. Delta vs Baseline",
        f"Baseline: `{sanitize_markdown_cell(baseline['label'])}`",
        "",
        *markdown_table(
            ["run", "e2e delta", "gpu busy delta", "bubble delta", "top kernel delta"],
            delta_rows or [["-", "-", "-", "-", "-"]],
        ),
        "",
        "## 3. Kernel Terms",
        *markdown_table(
            [
                "run",
                "kernel term",
                "total ms",
                "count",
                "source",
                "top launch CPU op",
                "launch op ms/count",
                "top annotation",
                "annotation ms/count",
            ],
            kernel_term_rows,
        ),
        "",
    ]

    if has_annotations:
        lines.extend(
            [
                "## 4. Annotation Terms",
                *markdown_table(
                    [
                        "run",
                        "annotation",
                        "count",
                        "annotation ms",
                        "kernel overlap ms",
                        "top kernel class",
                        "top kernel class ms",
                    ],
                    annotation_rows,
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## 5. Measurement Notes",
            *markdown_table(["run", "notes"], warning_rows),
            "",
            "## 6. Artifacts",
            *markdown_table(["run", "analysis.json", "record attribution"], artifact_rows),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    kernel_terms = args.kernel_term or DEFAULT_KERNEL_TERMS
    runs = []
    for raw in args.runs:
        raw_label, path = split_run_arg(raw)
        label = make_run_label(raw_label, path)
        runs.append(summarize_run(label, path, kernel_terms, args.annotation))

    summary = {
        "metadata": {
            "kernel_terms": list(kernel_terms),
            "annotations": list(args.annotation),
        },
        "runs": runs,
    }

    if args.export_json:
        export_json = Path(args.export_json)
        export_json.parent.mkdir(parents=True, exist_ok=True)
        export_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = build_markdown(summary)
    if args.export_md:
        export_md = Path(args.export_md)
        export_md.parent.mkdir(parents=True, exist_ok=True)
        export_md.write_text(markdown, encoding="utf-8")

    print(markdown)


if __name__ == "__main__":
    main()
