# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from torch_trace_common import (
    Event,
    build_external_id_map,
    build_event_starts,
    build_markdown_table_from_dicts,
    build_runtime_external_id_index,
    filter_events,
    iter_event_overlaps,
    load_events,
    markdown_table,
    match_runtime_for_kernel,
    safe_div,
    sanitize_markdown_cell,
    shorten_text,
)


DEFAULT_KERNEL_TERMS = [
    "FillFunctor<long>",
    "indexFuncLargeIndex",
    "indexSelectLargeIndex",
    "random_from_to_kernel",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate torch.profiler record_function/user_annotation ranges and "
            "attribute overlapping CPU ops, runtime APIs, and GPU kernels."
        )
    )
    parser.add_argument("trace", type=str, help="Chrome trace JSON exported by torch.profiler")
    parser.add_argument(
        "--annotation-prefix",
        action="append",
        default=[],
        help=(
            "Only include record_function names with this prefix. Can be passed multiple "
            "times. Default: include all user annotations."
        ),
    )
    parser.add_argument(
        "--kernel-term",
        action="append",
        default=[],
        help=(
            "Kernel substring to attribute to enclosing GPU annotations. Can be passed "
            f"multiple times. Default: {', '.join(DEFAULT_KERNEL_TERMS)}"
        ),
    )
    parser.add_argument("--top-k", type=int, default=12, help="Rows per table")
    parser.add_argument("--export-json", type=str, default="", help="Optional structured JSON output")
    parser.add_argument("--export-md", type=str, default="", help="Optional markdown report output")
    return parser.parse_args()


def event_end(event: Event) -> float:
    return float(event["ts"]) + float(event["dur"])


def event_name(event: Event) -> str:
    return str(event.get("name", ""))


def matches_prefix(name: str, prefixes: Sequence[str]) -> bool:
    return not prefixes or any(name.startswith(prefix) for prefix in prefixes)


def classify_kernel(name: str) -> str:
    if "indexFuncLargeIndex" in name:
        return "indexFuncLargeIndex"
    if "indexSelectLargeIndex" in name:
        return "indexSelectLargeIndex"
    if "FillFunctor<long>" in name:
        return "FillFunctor<long>"
    if "random_from_to_kernel" in name or "distribution_elementwise_grid_stride_kernel" in name:
        return "random_from_to_kernel"
    if "masked_fill_kernel" in name:
        return "masked_fill_kernel"
    if "jagged" in name.lower():
        return "fbgemm_jagged"
    if name.startswith("Cijk_"):
        return "gemm"
    if "DivFunctor" in name:
        return "elementwise_div"
    if "MulFunctor" in name:
        return "elementwise_mul"
    if "elementwise_kernel" in name or "vectorized_elementwise" in name:
        return "elementwise_other"
    if "reduce_kernel" in name:
        return "reduce"
    return shorten_text(name, 80)


def sorted_x_events(events: Iterable[Event]) -> List[Event]:
    return sorted(
        [
            event
            for event in events
            if event.get("ph") == "X" and "ts" in event and "dur" in event
        ],
        key=lambda event: event["ts"],
    )


def annotation_events(events: Sequence[Event], cat: str, prefixes: Sequence[str]) -> List[Event]:
    return [
        event
        for event in sorted_x_events(events)
        if event.get("cat") == cat and matches_prefix(event_name(event), prefixes)
    ]


def aggregate_counter_items(counter: Dict[str, float], counts: Counter, top_k: int) -> List[Dict]:
    rows = []
    for name, total_us in sorted(counter.items(), key=lambda item: item[1], reverse=True)[:top_k]:
        rows.append(
            {
                "name": name,
                "total_us": total_us,
                "count": int(counts.get(name, 0)),
                "avg_us": safe_div(total_us, counts.get(name, 0)),
            }
        )
    return rows


def summarize_gpu_annotations(
    gpu_annotations: Sequence[Event],
    kernels: Sequence[Event],
    top_k: int,
) -> List[Dict]:
    kernel_starts = build_event_starts(kernels)
    by_annotation: Dict[str, Dict] = defaultdict(
        lambda: {
            "annotation": "",
            "count": 0,
            "annotation_dur_us": 0.0,
            "kernel_overlap_us": 0.0,
            "kernel_class_us": defaultdict(float),
            "kernel_class_count": Counter(),
            "kernel_class_full_count": Counter(),
            "kernel_examples": {},
        }
    )

    for annotation in gpu_annotations:
        ann_name = event_name(annotation)
        ann_start = float(annotation["ts"])
        ann_end = event_end(annotation)
        item = by_annotation[ann_name]
        item["annotation"] = ann_name
        item["count"] += 1
        item["annotation_dur_us"] += float(annotation["dur"])
        for kernel, overlap_us in iter_event_overlaps(kernels, kernel_starts, ann_start, ann_end):
            kernel_name = event_name(kernel)
            kernel_class = classify_kernel(kernel_name)
            item["kernel_overlap_us"] += overlap_us
            item["kernel_class_us"][kernel_class] += overlap_us
            item["kernel_class_count"][kernel_class] += 1
            if float(kernel["ts"]) >= ann_start and event_end(kernel) <= ann_end:
                item["kernel_class_full_count"][kernel_class] += 1
            item["kernel_examples"].setdefault(kernel_class, kernel_name)

    rows = []
    for item in by_annotation.values():
        top_kernel_classes = []
        for kernel_class, overlap_us in sorted(
            item["kernel_class_us"].items(),
            key=lambda pair: pair[1],
            reverse=True,
        )[:top_k]:
            top_kernel_classes.append(
                {
                    "kernel_class": kernel_class,
                    "overlap_us": overlap_us,
                    "count": int(item["kernel_class_count"].get(kernel_class, 0)),
                    "full_count": int(item["kernel_class_full_count"].get(kernel_class, 0)),
                    "example": item["kernel_examples"].get(kernel_class, ""),
                }
            )
        rows.append(
            {
                "annotation": item["annotation"],
                "count": item["count"],
                "annotation_dur_us": item["annotation_dur_us"],
                "kernel_overlap_us": item["kernel_overlap_us"],
                "top_kernel_classes": top_kernel_classes,
            }
        )

    return sorted(rows, key=lambda row: row["kernel_overlap_us"], reverse=True)


def summarize_cpu_annotations(
    cpu_annotations: Sequence[Event],
    cpu_ops: Sequence[Event],
    runtime_ops: Sequence[Event],
    top_k: int,
) -> List[Dict]:
    cpu_starts = build_event_starts(cpu_ops)
    runtime_starts = build_event_starts(runtime_ops)
    by_annotation: Dict[str, Dict] = defaultdict(
        lambda: {
            "annotation": "",
            "count": 0,
            "annotation_dur_us": 0.0,
            "cpu_op_us": defaultdict(float),
            "cpu_op_count": Counter(),
            "runtime_us": defaultdict(float),
            "runtime_count": Counter(),
        }
    )

    for annotation in cpu_annotations:
        ann_name = event_name(annotation)
        ann_start = float(annotation["ts"])
        ann_end = event_end(annotation)
        item = by_annotation[ann_name]
        item["annotation"] = ann_name
        item["count"] += 1
        item["annotation_dur_us"] += float(annotation["dur"])
        for cpu_op, overlap_us in iter_event_overlaps(cpu_ops, cpu_starts, ann_start, ann_end):
            name = event_name(cpu_op)
            item["cpu_op_us"][name] += overlap_us
            item["cpu_op_count"][name] += 1
        for runtime_op, overlap_us in iter_event_overlaps(runtime_ops, runtime_starts, ann_start, ann_end):
            name = event_name(runtime_op)
            item["runtime_us"][name] += overlap_us
            item["runtime_count"][name] += 1

    rows = []
    for item in by_annotation.values():
        rows.append(
            {
                "annotation": item["annotation"],
                "count": item["count"],
                "annotation_dur_us": item["annotation_dur_us"],
                "top_cpu_ops": aggregate_counter_items(
                    item["cpu_op_us"],
                    item["cpu_op_count"],
                    top_k,
                ),
                "top_runtime_ops": aggregate_counter_items(
                    item["runtime_us"],
                    item["runtime_count"],
                    top_k,
                ),
            }
        )

    return sorted(rows, key=lambda row: row["annotation_dur_us"], reverse=True)


def summarize_special_kernels(
    kernels: Sequence[Event],
    annotations: Sequence[Event],
    kernel_terms: Sequence[str],
) -> List[Dict]:
    annotation_starts = build_event_starts(annotations)
    rows = []
    for term in kernel_terms:
        total_us = 0.0
        count = 0
        unassigned_us = 0.0
        unassigned_count = 0
        by_annotation_us: Dict[str, float] = defaultdict(float)
        by_annotation_count: Counter = Counter()
        for kernel in kernels:
            kernel_name = event_name(kernel)
            if term not in kernel_name:
                continue
            total_us += float(kernel["dur"])
            count += 1
            overlaps = list(
                iter_event_overlaps(
                    annotations,
                    annotation_starts,
                    float(kernel["ts"]),
                    event_end(kernel),
                )
            )
            if not overlaps:
                unassigned_us += float(kernel["dur"])
                unassigned_count += 1
                continue
            annotation, _overlap_us = max(overlaps, key=lambda pair: pair[1])
            annotation_name = event_name(annotation)
            by_annotation_us[annotation_name] += float(kernel["dur"])
            by_annotation_count[annotation_name] += 1
        rows.append(
            {
                "kernel_term": term,
                "total_us": total_us,
                "count": count,
                "unassigned_us": unassigned_us,
                "unassigned_count": unassigned_count,
                "by_annotation": [
                    {
                        "annotation": annotation,
                        "total_us": total,
                        "count": int(by_annotation_count.get(annotation, 0)),
                    }
                    for annotation, total in sorted(
                        by_annotation_us.items(),
                        key=lambda pair: pair[1],
                        reverse=True,
                    )
                ],
            }
        )
    return rows


def summarize_special_kernels_by_launch_cpu_op(
    kernels: Sequence[Event],
    runtime_ops: Sequence[Event],
    cpu_ops: Sequence[Event],
    kernel_terms: Sequence[str],
) -> List[Dict]:
    runtime_by_correlation = {
        event.get("args", {}).get("correlation"): event
        for event in runtime_ops
        if event.get("args", {}).get("correlation") is not None
    }
    runtime_by_external_id = build_runtime_external_id_index(runtime_ops)
    cpu_by_external_id = build_external_id_map(cpu_ops)
    rows = []

    for term in kernel_terms:
        total_us = 0.0
        count = 0
        unassigned_us = 0.0
        unassigned_count = 0
        by_cpu_op_us: Dict[str, float] = defaultdict(float)
        by_cpu_op_count: Counter = Counter()
        by_cpu_op_runtime_count: Counter = Counter()
        by_cpu_op_examples: Dict[str, str] = {}

        for kernel in kernels:
            kernel_name = event_name(kernel)
            if term not in kernel_name:
                continue
            kernel_dur_us = float(kernel["dur"])
            total_us += kernel_dur_us
            count += 1

            runtime_event = match_runtime_for_kernel(
                kernel=kernel,
                runtime_by_correlation=runtime_by_correlation,
                runtime_by_external_id=runtime_by_external_id,
            )
            external_id = None
            if runtime_event is not None:
                external_id = runtime_event.get("args", {}).get("External id")
            if external_id is None:
                external_id = kernel.get("args", {}).get("External id")
            cpu_event = cpu_by_external_id.get(external_id) if external_id is not None else None

            if cpu_event is None:
                unassigned_us += kernel_dur_us
                unassigned_count += 1
                continue

            cpu_op_name = event_name(cpu_event)
            by_cpu_op_us[cpu_op_name] += kernel_dur_us
            by_cpu_op_count[cpu_op_name] += 1
            if runtime_event is not None:
                by_cpu_op_runtime_count[cpu_op_name] += 1
            by_cpu_op_examples.setdefault(cpu_op_name, shorten_text(kernel_name, 120))

        rows.append(
            {
                "kernel_term": term,
                "total_us": total_us,
                "count": count,
                "unassigned_us": unassigned_us,
                "unassigned_count": unassigned_count,
                "by_cpu_op": [
                    {
                        "cpu_op": cpu_op,
                        "total_us": total,
                        "count": int(by_cpu_op_count.get(cpu_op, 0)),
                        "runtime_matched_count": int(by_cpu_op_runtime_count.get(cpu_op, 0)),
                        "example_kernel": by_cpu_op_examples.get(cpu_op, ""),
                    }
                    for cpu_op, total in sorted(
                        by_cpu_op_us.items(),
                        key=lambda pair: pair[1],
                        reverse=True,
                    )
                ],
            }
        )
    return rows


def build_summary(
    events: Sequence[Event],
    prefixes: Sequence[str],
    kernel_terms: Sequence[str],
    top_k: int,
) -> Dict:
    cpu_annotations = annotation_events(events, "user_annotation", prefixes)
    gpu_annotations = annotation_events(events, "gpu_user_annotation", prefixes)
    kernels = sorted_x_events(filter_events(events, "kernel"))
    cpu_ops = sorted_x_events(filter_events(events, "cpu_op"))
    runtime_ops = sorted_x_events(filter_events(events, "cuda_runtime"))

    return {
        "metadata": {
            "annotation_prefixes": list(prefixes),
            "kernel_terms": list(kernel_terms),
            "top_k": top_k,
            "counts": {
                "cpu_annotations": len(cpu_annotations),
                "gpu_annotations": len(gpu_annotations),
                "kernels": len(kernels),
                "cpu_ops": len(cpu_ops),
                "runtime_ops": len(runtime_ops),
            },
        },
        "gpu_annotations": summarize_gpu_annotations(gpu_annotations, kernels, top_k),
        "cpu_annotations": summarize_cpu_annotations(cpu_annotations, cpu_ops, runtime_ops, top_k),
        "special_kernels": summarize_special_kernels(kernels, gpu_annotations, kernel_terms),
        "special_kernels_by_cpu_annotation": summarize_special_kernels(kernels, cpu_annotations, kernel_terms),
        "special_kernels_by_launch_cpu_op": summarize_special_kernels_by_launch_cpu_op(
            kernels,
            runtime_ops,
            cpu_ops,
            kernel_terms,
        ),
    }


def build_top_kernel_class_rows(gpu_annotations: Sequence[Dict], top_k: int) -> List[Dict]:
    rows = []
    for annotation in gpu_annotations:
        for item in annotation.get("top_kernel_classes", [])[:top_k]:
            rows.append(
                {
                    "annotation": annotation["annotation"],
                    "annotation_count": annotation["count"],
                    "annotation_dur_us": annotation["annotation_dur_us"],
                    "kernel_class": item["kernel_class"],
                    "overlap_us": item["overlap_us"],
                    "kernel_count": item["count"],
                    "full_count": item["full_count"],
                }
            )
    return sorted(rows, key=lambda row: row["overlap_us"], reverse=True)[:top_k]


def build_top_cpu_op_rows(cpu_annotations: Sequence[Dict], top_k: int) -> List[Dict]:
    rows = []
    for annotation in cpu_annotations:
        for item in annotation.get("top_cpu_ops", [])[:top_k]:
            rows.append(
                {
                    "annotation": annotation["annotation"],
                    "annotation_count": annotation["count"],
                    "annotation_dur_us": annotation["annotation_dur_us"],
                    "cpu_op": item["name"],
                    "overlap_us": item["total_us"],
                    "cpu_op_count": item["count"],
                }
            )
    return sorted(rows, key=lambda row: row["overlap_us"], reverse=True)[:top_k]


def build_special_kernel_rows(special_kernels: Sequence[Dict]) -> List[Dict]:
    rows = []
    for item in special_kernels:
        assigned_us = item["total_us"] - item["unassigned_us"]
        rows.append(
            {
                "kernel_term": item["kernel_term"],
                "total_us": item["total_us"],
                "count": item["count"],
                "assigned_us": assigned_us,
                "unassigned_us": item["unassigned_us"],
                "unassigned_count": item["unassigned_count"],
                "top_annotation": item["by_annotation"][0]["annotation"] if item["by_annotation"] else "",
                "top_annotation_us": item["by_annotation"][0]["total_us"] if item["by_annotation"] else 0.0,
                "top_annotation_count": item["by_annotation"][0]["count"] if item["by_annotation"] else 0,
            }
        )
    return rows


def build_special_kernel_launch_cpu_rows(special_kernels: Sequence[Dict]) -> List[Dict]:
    rows = []
    for item in special_kernels:
        by_cpu_op = item.get("by_cpu_op", []) or []
        top = by_cpu_op[0] if by_cpu_op else {}
        assigned_us = item["total_us"] - item["unassigned_us"]
        rows.append(
            {
                "kernel_term": item["kernel_term"],
                "total_us": item["total_us"],
                "count": item["count"],
                "assigned_us": assigned_us,
                "unassigned_us": item["unassigned_us"],
                "unassigned_count": item["unassigned_count"],
                "top_cpu_op": top.get("cpu_op", ""),
                "top_cpu_op_us": top.get("total_us", 0.0),
                "top_cpu_op_count": top.get("count", 0),
                "runtime_matched_count": top.get("runtime_matched_count", 0),
            }
        )
    return rows


def build_markdown(summary: Dict) -> str:
    metadata = summary["metadata"]
    counts = metadata["counts"]
    prefix_text = ", ".join(f"`{prefix}`" for prefix in metadata["annotation_prefixes"]) or "all"
    kernel_text = ", ".join(f"`{term}`" for term in metadata["kernel_terms"])
    top_k = int(metadata["top_k"])

    count_table = markdown_table(
        ["item", "count"],
        [
            ("annotation_prefix", prefix_text),
            ("kernel_terms", kernel_text),
            ("cpu_annotations", str(counts["cpu_annotations"])),
            ("gpu_annotations", str(counts["gpu_annotations"])),
            ("kernels", str(counts["kernels"])),
            ("cpu_ops", str(counts["cpu_ops"])),
            ("runtime_ops", str(counts["runtime_ops"])),
        ],
    )

    gpu_rows = [
        {
            "annotation": row["annotation"],
            "count": row["count"],
            "annotation_dur_us": row["annotation_dur_us"],
            "kernel_overlap_us": row["kernel_overlap_us"],
            "top_kernel_class": row["top_kernel_classes"][0]["kernel_class"]
            if row.get("top_kernel_classes")
            else "",
            "top_kernel_overlap_us": row["top_kernel_classes"][0]["overlap_us"]
            if row.get("top_kernel_classes")
            else 0.0,
        }
        for row in summary["gpu_annotations"][:top_k]
    ]
    gpu_table = build_markdown_table_from_dicts(
        gpu_rows,
        [
            ("annotation", "annotation"),
            ("count", "count"),
            ("annotation_dur_us", "annotation_dur_us"),
            ("kernel_overlap_us", "kernel_overlap_us"),
            ("top_kernel_class", "top_kernel_class"),
            ("top_kernel_overlap_us", "top_kernel_overlap_us"),
        ],
        shorten_columns={"annotation": 72, "top_kernel_class": 48},
    )

    kernel_class_table = build_markdown_table_from_dicts(
        build_top_kernel_class_rows(summary["gpu_annotations"], top_k),
        [
            ("annotation", "annotation"),
            ("kernel_class", "kernel_class"),
            ("overlap_us", "overlap_us"),
            ("kernel_count", "kernel_count"),
            ("full_count", "full_count"),
        ],
        shorten_columns={"annotation": 72, "kernel_class": 48},
    )

    cpu_rows = [
        {
            "annotation": row["annotation"],
            "count": row["count"],
            "annotation_dur_us": row["annotation_dur_us"],
            "top_cpu_op": row["top_cpu_ops"][0]["name"] if row.get("top_cpu_ops") else "",
            "top_cpu_op_us": row["top_cpu_ops"][0]["total_us"] if row.get("top_cpu_ops") else 0.0,
            "top_runtime": row["top_runtime_ops"][0]["name"] if row.get("top_runtime_ops") else "",
            "top_runtime_us": row["top_runtime_ops"][0]["total_us"] if row.get("top_runtime_ops") else 0.0,
        }
        for row in summary["cpu_annotations"][:top_k]
    ]
    cpu_table = build_markdown_table_from_dicts(
        cpu_rows,
        [
            ("annotation", "annotation"),
            ("count", "count"),
            ("annotation_dur_us", "annotation_dur_us"),
            ("top_cpu_op", "top_cpu_op"),
            ("top_cpu_op_us", "top_cpu_op_us"),
            ("top_runtime", "top_runtime"),
            ("top_runtime_us", "top_runtime_us"),
        ],
        shorten_columns={"annotation": 72, "top_cpu_op": 48, "top_runtime": 36},
    )

    cpu_op_table = build_markdown_table_from_dicts(
        build_top_cpu_op_rows(summary["cpu_annotations"], top_k),
        [
            ("annotation", "annotation"),
            ("cpu_op", "cpu_op"),
            ("overlap_us", "overlap_us"),
            ("cpu_op_count", "cpu_op_count"),
        ],
        shorten_columns={"annotation": 72, "cpu_op": 48},
    )

    special_table = build_markdown_table_from_dicts(
        build_special_kernel_rows(summary["special_kernels"]),
        [
            ("kernel_term", "kernel_term"),
            ("total_us", "total_us"),
            ("count", "count"),
            ("assigned_us", "assigned_us"),
            ("unassigned_us", "unassigned_us"),
            ("unassigned_count", "unassigned_count"),
            ("top_annotation", "top_annotation"),
            ("top_annotation_us", "top_annotation_us"),
            ("top_annotation_count", "top_annotation_count"),
        ],
        shorten_columns={"kernel_term": 40, "top_annotation": 72},
    )
    cpu_special_table = build_markdown_table_from_dicts(
        build_special_kernel_rows(summary.get("special_kernels_by_cpu_annotation", [])),
        [
            ("kernel_term", "kernel_term"),
            ("total_us", "total_us"),
            ("count", "count"),
            ("assigned_us", "assigned_us"),
            ("unassigned_us", "unassigned_us"),
            ("unassigned_count", "unassigned_count"),
            ("top_annotation", "top_cpu_annotation"),
            ("top_annotation_us", "top_cpu_annotation_us"),
            ("top_annotation_count", "top_cpu_annotation_count"),
        ],
        shorten_columns={"kernel_term": 40, "top_annotation": 72},
    )
    launch_cpu_special_table = build_markdown_table_from_dicts(
        build_special_kernel_launch_cpu_rows(summary.get("special_kernels_by_launch_cpu_op", [])),
        [
            ("kernel_term", "kernel_term"),
            ("total_us", "total_us"),
            ("count", "count"),
            ("assigned_us", "assigned_us"),
            ("unassigned_us", "unassigned_us"),
            ("unassigned_count", "unassigned_count"),
            ("top_cpu_op", "top_launch_cpu_op"),
            ("top_cpu_op_us", "top_launch_cpu_op_us"),
            ("top_cpu_op_count", "top_launch_cpu_op_count"),
            ("runtime_matched_count", "runtime_matched_count"),
        ],
        shorten_columns={"kernel_term": 40, "top_cpu_op": 72},
    )

    lines = [
        "# Record Function Attribution",
        "",
        "## 1. Scope",
        *count_table,
        "",
        "## 2. GPU Annotation Summary",
        *gpu_table,
        "",
        "## 3. GPU Kernel Classes Inside Annotations",
        *kernel_class_table,
        "",
        "## 4. CPU Annotation Summary",
        *cpu_table,
        "",
        "## 5. CPU Ops Inside Annotations",
        *cpu_op_table,
        "",
        "## 6. Special Kernel Attribution",
        *special_table,
        "",
        "## 7. Special Kernel Attribution By CPU Annotation",
        *cpu_special_table,
        "",
        "## 8. Special Kernel Attribution By Launch CPU Op",
        *launch_cpu_special_table,
        "",
    ]

    for item in summary["special_kernels"]:
        if not item["by_annotation"]:
            continue
        lines.extend(
            [
                f"### {sanitize_markdown_cell(item['kernel_term'])}",
                *build_markdown_table_from_dicts(
                    item["by_annotation"],
                    [
                        ("annotation", "annotation"),
                        ("total_us", "total_us"),
                        ("count", "count"),
                    ],
                    shorten_columns={"annotation": 72},
                ),
                "",
            ]
        )

    for item in summary.get("special_kernels_by_cpu_annotation", []):
        if not item["by_annotation"]:
            continue
        lines.extend(
            [
                f"### CPU annotation: {sanitize_markdown_cell(item['kernel_term'])}",
                *build_markdown_table_from_dicts(
                    item["by_annotation"],
                    [
                        ("annotation", "annotation"),
                        ("total_us", "total_us"),
                        ("count", "count"),
                    ],
                    shorten_columns={"annotation": 72},
                ),
                "",
            ]
        )

    for item in summary.get("special_kernels_by_launch_cpu_op", []):
        if not item.get("by_cpu_op"):
            continue
        lines.extend(
            [
                f"### Launch CPU op: {sanitize_markdown_cell(item['kernel_term'])}",
                *build_markdown_table_from_dicts(
                    item["by_cpu_op"],
                    [
                        ("cpu_op", "cpu_op"),
                        ("total_us", "total_us"),
                        ("count", "count"),
                        ("runtime_matched_count", "runtime_matched_count"),
                    ],
                    shorten_columns={"cpu_op": 72},
                ),
                "",
            ]
        )

    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    kernel_terms = args.kernel_term or DEFAULT_KERNEL_TERMS
    summary = build_summary(
        load_events(args.trace),
        prefixes=args.annotation_prefix,
        kernel_terms=kernel_terms,
        top_k=args.top_k,
    )

    if args.export_json:
        export_json_path = Path(args.export_json)
        export_json_path.parent.mkdir(parents=True, exist_ok=True)
        export_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.export_md:
        export_md_path = Path(args.export_md)
        export_md_path.parent.mkdir(parents=True, exist_ok=True)
        export_md_path.write_text(build_markdown(summary), encoding="utf-8")

    print(json.dumps(summary["metadata"], ensure_ascii=False, indent=2))
    print("Top GPU annotations by kernel overlap:")
    for row in summary["gpu_annotations"][: args.top_k]:
        print(
            f"- {row['annotation']}: annotation={row['annotation_dur_us']:.3f}us "
            f"kernel_overlap={row['kernel_overlap_us']:.3f}us count={row['count']}"
        )
    print("Special kernels:")
    for row in build_special_kernel_rows(summary["special_kernels"]):
        print(
            f"- {row['kernel_term']}: total={row['total_us']:.3f}us count={row['count']} "
            f"top={row['top_annotation']} {row['top_annotation_us']:.3f}us"
        )
    print("Special kernels by CPU annotation:")
    for row in build_special_kernel_rows(summary.get("special_kernels_by_cpu_annotation", [])):
        print(
            f"- {row['kernel_term']}: total={row['total_us']:.3f}us count={row['count']} "
            f"top={row['top_annotation']} {row['top_annotation_us']:.3f}us"
        )
    print("Special kernels by launch CPU op:")
    for row in build_special_kernel_launch_cpu_rows(summary.get("special_kernels_by_launch_cpu_op", [])):
        print(
            f"- {row['kernel_term']}: total={row['total_us']:.3f}us count={row['count']} "
            f"top={row['top_cpu_op']} {row['top_cpu_op_us']:.3f}us"
        )


if __name__ == "__main__":
    main()
