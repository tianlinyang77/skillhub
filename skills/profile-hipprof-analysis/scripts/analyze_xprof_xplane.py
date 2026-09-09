# SPDX-License-Identifier: Apache-2.0

import argparse
import importlib.util
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

PS_PER_US = 1_000_000


def load_xplane_pb2():
    candidates = [
        Path("/usr/local/lib/python3.10/site-packages/tensorflow/tsl/profiler/protobuf/xplane_pb2.py"),
        Path("/usr/local/lib/python3.10/site-packages/tensorflow/core/profiler/protobuf/xplane_pb2.py"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        spec = importlib.util.spec_from_file_location("codex_xplane_pb2", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    raise ImportError("Unable to locate xplane_pb2.py from the installed TensorFlow profiler package")


xplane_pb2 = load_xplane_pb2()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze XProf xplane.pb artifacts and export an agent-friendly summary."
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to an xplane.pb file or an XProf logdir containing plugins/profile/*/*.xplane.pb",
    )
    parser.add_argument(
        "--hipprof-analysis-json",
        type=str,
        default="",
        help="Optional hipprof analysis.json for cross-alignment with XProf kernel hotspots",
    )
    parser.add_argument(
        "--export-dir",
        type=str,
        default="",
        help="Directory to write report.md / analysis.json / copied xplane.pb",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Top rows to keep per section",
    )
    parser.add_argument(
        "--gap-top-k",
        type=int,
        default=5,
        help="Top inter-kernel gaps to keep",
    )
    parser.add_argument(
        "--export-analysis-json",
        action="store_true",
        help="Also write analysis.json next to report.md",
    )
    return parser.parse_args()


def resolve_xplane(input_path: str) -> Path:
    path = Path(input_path)
    if path.is_file():
        return path
    matches = sorted(
        path.rglob("*.xplane.pb"),
        key=lambda item: (item.stat().st_mtime_ns, str(item)),
    )
    if not matches:
        raise FileNotFoundError(f"No xplane.pb found under {path}")
    return matches[-1]


def ps_to_us(value: int) -> float:
    return value / PS_PER_US


def stat_value(stat: Any, stat_metadata: dict[int, Any]) -> Any:
    for descriptor, value in stat.ListFields():
        field_name = descriptor.name
        if field_name == "metadata_id":
            continue
        if field_name == "ref_value":
            ref = stat_metadata.get(int(value))
            return ref.name if ref is not None else int(value)
        if field_name == "bytes_value":
            return bytes(value).decode("utf-8", errors="replace")
        return value
    return None


def load_xspace(xplane_path: Path) -> xplane_pb2.XSpace:
    xspace = xplane_pb2.XSpace()
    with xplane_path.open("rb") as f:
        xspace.ParseFromString(f.read())
    return xspace


def collect_events(xspace: xplane_pb2.XSpace) -> tuple[list[dict], list[dict]]:
    host_events: list[dict] = []
    device_events: list[dict] = []

    for plane in xspace.planes:
        plane_name = plane.name
        plane_kind = ""
        lower_name = plane_name.lower()
        if "/host:" in lower_name:
            plane_kind = "host"
        elif "/device:gpu:" in lower_name:
            plane_kind = "device"
        else:
            continue

        event_metadata = {key: value.name for key, value in plane.event_metadata.items()}
        stat_metadata = {key: value for key, value in plane.stat_metadata.items()}
        for line in plane.lines:
            base_ps = int(line.timestamp_ns) * 1000
            for event in line.events:
                name = event_metadata.get(event.metadata_id, str(event.metadata_id))
                stats: dict[str, Any] = {}
                for stat in event.stats:
                    stat_name = stat_metadata.get(stat.metadata_id)
                    key = stat_name.name if stat_name is not None else str(stat.metadata_id)
                    stats[key] = stat_value(stat, stat_metadata)
                row = {
                    "plane_name": plane_name,
                    "line_name": line.name,
                    "name": name,
                    "start_ps": base_ps + int(event.offset_ps),
                    "end_ps": base_ps + int(event.offset_ps) + int(event.duration_ps),
                    "duration_ps": int(event.duration_ps),
                    "stats": stats,
                }
                if plane_kind == "host":
                    host_events.append(row)
                else:
                    device_events.append(row)

    host_events.sort(key=lambda item: (item["start_ps"], item["end_ps"], item["name"]))
    device_events.sort(key=lambda item: (item["start_ps"], item["end_ps"], item["name"]))
    return host_events, device_events


def intersect_duration_ps(start_ps: int, end_ps: int, window_start_ps: int, window_end_ps: int) -> int:
    return max(0, min(end_ps, window_end_ps) - max(start_ps, window_start_ps))


def clip_events(events: list[dict], window_start_ps: int, window_end_ps: int) -> list[dict]:
    clipped: list[dict] = []
    for event in events:
        overlap_ps = intersect_duration_ps(
            event["start_ps"],
            event["end_ps"],
            window_start_ps,
            window_end_ps,
        )
        if overlap_ps <= 0:
            continue
        item = dict(event)
        item["clipped_duration_ps"] = overlap_ps
        item["clipped_start_ps"] = max(event["start_ps"], window_start_ps)
        item["clipped_end_ps"] = min(event["end_ps"], window_end_ps)
        clipped.append(item)
    return clipped


def union_duration_ps(events: list[dict], start_key: str, end_key: str) -> int:
    if not events:
        return 0
    intervals = sorted((event[start_key], event[end_key]) for event in events)
    total = 0
    current_start, current_end = intervals[0]
    for start_ps, end_ps in intervals[1:]:
        if start_ps <= current_end:
            current_end = max(current_end, end_ps)
            continue
        total += current_end - current_start
        current_start, current_end = start_ps, end_ps
    total += current_end - current_start
    return total


def find_step_events(host_events: list[dict]) -> list[dict]:
    steps = [event for event in host_events if "step_num" in event["stats"]]
    steps.sort(key=lambda item: (int(item["stats"]["step_num"]), item["start_ps"]))
    return steps


def infer_window_ps(host_events: list[dict], device_events: list[dict], step_events: list[dict]) -> tuple[int, int]:
    if step_events:
        return step_events[0]["start_ps"], step_events[-1]["end_ps"]
    all_events = host_events + device_events
    if not all_events:
        raise ValueError("No host/device events found in xplane")
    return min(event["start_ps"] for event in all_events), max(event["end_ps"] for event in all_events)


def summarize_steps(step_events: list[dict], kernel_events: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for step in step_events:
        clipped_kernels = clip_events(kernel_events, step["start_ps"], step["end_ps"])
        gpu_busy_ps = union_duration_ps(clipped_kernels, "clipped_start_ps", "clipped_end_ps")
        rows.append(
            {
                "step_num": int(step["stats"]["step_num"]),
                "name": step["name"],
                "start_us": ps_to_us(step["start_ps"]),
                "end_us": ps_to_us(step["end_ps"]),
                "duration_us": ps_to_us(step["duration_ps"]),
                "gpu_busy_us": ps_to_us(gpu_busy_ps),
                "gpu_busy_ratio": (gpu_busy_ps / step["duration_ps"]) if step["duration_ps"] > 0 else 0.0,
            }
        )
    return rows


def is_kernel_event(event: dict) -> bool:
    line_name = event["line_name"].lower()
    return "kernel" in line_name or "compute" in line_name


def aggregate_rows(events: list[dict], name_fn) -> list[dict]:
    total_by_name: dict[str, dict[str, Any]] = defaultdict(lambda: {"calls": 0, "total_duration_ps": 0})
    for event in events:
        name = name_fn(event)
        if not name:
            continue
        total_by_name[name]["calls"] += 1
        total_by_name[name]["total_duration_ps"] += event["clipped_duration_ps"]
    rows = [
        {
            "name": name,
            "calls": payload["calls"],
            "total_duration_us": ps_to_us(payload["total_duration_ps"]),
            "avg_duration_us": ps_to_us(payload["total_duration_ps"]) / payload["calls"],
        }
        for name, payload in total_by_name.items()
        if payload["calls"] > 0 and payload["total_duration_ps"] > 0
    ]
    rows.sort(key=lambda item: (item["total_duration_us"], item["calls"], item["name"]), reverse=True)
    return rows


def normalize_framework_region(event: dict) -> str:
    stats = event["stats"]
    eager_op = stats.get("eager_op")
    if eager_op:
        return str(eager_op)
    name = event["name"]
    if name.startswith("EagerLocalExecute: "):
        return name.split(": ", 1)[1]
    if name.startswith("tf."):
        return name
    for token in ("Xla", "PartitionedCall", "jit(", "pjit", "train_step", "apply_gradients"):
        if token in name:
            return name
    return ""


def normalize_host_region(event: dict) -> str:
    if "step_num" in event["stats"]:
        return ""
    return event["name"]


def detect_wait_copy(event: dict) -> str:
    name = event["name"].lower()
    for token in ("wait", "sync", "barrier", "join", "sleep", "memcpy", "copy"):
        if token in name:
            return event["name"]
    return ""


def summarize_gpu_gaps(kernel_events: list[dict], top_k: int) -> dict[str, Any]:
    if len(kernel_events) < 2:
        return {"total_gap_us": 0.0, "top_gaps": []}

    gaps: list[dict[str, Any]] = []
    total_gap_ps = 0
    prev = kernel_events[0]
    for current in kernel_events[1:]:
        gap_ps = max(0, current["clipped_start_ps"] - prev["clipped_end_ps"])
        if gap_ps > 0:
            total_gap_ps += gap_ps
            gaps.append(
                {
                    "gap_us": ps_to_us(gap_ps),
                    "prev_kernel": prev["name"],
                    "next_kernel": current["name"],
                }
            )
        if current["clipped_end_ps"] > prev["clipped_end_ps"]:
            prev = current
    gaps.sort(key=lambda item: item["gap_us"], reverse=True)
    return {"total_gap_us": ps_to_us(total_gap_ps), "top_gaps": gaps[: max(top_k, 0)]}


def load_hipprof_alignment(path: str, xprof_kernel_rows: list[dict], top_k: int) -> dict[str, Any]:
    if not path:
        return {}
    hipprof_path = Path(path)
    if not hipprof_path.exists():
        return {
            "hipprof_analysis_json": str(hipprof_path),
            "available": False,
            "reason": "hipprof analysis.json not found",
        }
    payload = json.loads(hipprof_path.read_text(encoding="utf-8"))
    hipprof_rows = payload.get("top_kernels", [])[: max(top_k, 0)]
    xprof_names = [row["name"] for row in xprof_kernel_rows[: max(top_k, 0)]]
    hipprof_names = [row.get("name", "") for row in hipprof_rows]
    overlap = [name for name in xprof_names if name in set(hipprof_names)]
    return {
        "hipprof_analysis_json": str(hipprof_path),
        "available": True,
        "xprof_top_kernel_names": xprof_names,
        "hipprof_top_kernel_names": hipprof_names,
        "overlap_names": overlap,
        "overlap_count": len(overlap),
    }


def classify(payload: dict[str, Any]) -> dict[str, str]:
    gpu_busy_ratio = payload["phase_summary"]["gpu_busy_ratio"]
    gap_ratio = payload["phase_summary"]["gpu_gap_ratio"]
    wait_rows = payload["top_wait_or_copy_regions"]
    top_kernel_share = payload["top_device_regions"][0]["share"] if payload["top_device_regions"] else 0.0
    if wait_rows or gap_ratio >= 0.35 or gpu_busy_ratio <= 0.30:
        return {
            "classification": "bubble-scheduling",
            "reason": "GPU busy ratio is low or visible wait/copy/gap signals exist in the measured step window.",
        }
    if top_kernel_share >= 0.60:
        return {
            "classification": "kernel-operator",
            "reason": "GPU time is concentrated in a small number of kernels and scheduling gaps are not dominant.",
        }
    return {
        "classification": "mixed",
        "reason": "Framework-side hot regions and kernel-side hotspots are both visible; inspect both layers together.",
    }


def build_payload(
    xplane_path: Path,
    hipprof_analysis_json: str,
    top_k: int,
    gap_top_k: int,
) -> dict[str, Any]:
    xspace = load_xspace(xplane_path)
    host_events, device_events = collect_events(xspace)
    step_events = find_step_events(host_events)
    window_start_ps, window_end_ps = infer_window_ps(host_events, device_events, step_events)

    window_host_events = clip_events(host_events, window_start_ps, window_end_ps)
    window_device_events = clip_events(device_events, window_start_ps, window_end_ps)
    kernel_events = [event for event in window_device_events if is_kernel_event(event)]

    step_rows = summarize_steps(step_events, kernel_events)
    top_framework_regions = aggregate_rows(window_host_events, normalize_framework_region)
    top_host_regions = aggregate_rows(window_host_events, normalize_host_region)
    top_device_regions = aggregate_rows(kernel_events, lambda event: event["name"])
    top_wait_or_copy_regions = aggregate_rows(
        window_host_events + window_device_events,
        detect_wait_copy,
    )

    total_kernel_us = sum(row["total_duration_us"] for row in top_device_regions)
    for row in top_device_regions:
        row["share"] = (row["total_duration_us"] / total_kernel_us) if total_kernel_us > 0 else 0.0

    gpu_busy_ps = union_duration_ps(kernel_events, "clipped_start_ps", "clipped_end_ps")
    gpu_first_ps = min((event["clipped_start_ps"] for event in kernel_events), default=window_start_ps)
    gpu_last_ps = max((event["clipped_end_ps"] for event in kernel_events), default=window_start_ps)
    measured_duration_ps = max(0, window_end_ps - window_start_ps)
    gap_summary = summarize_gpu_gaps(kernel_events, gap_top_k)

    phase_summary = {
        "window_start_us": ps_to_us(window_start_ps),
        "window_end_us": ps_to_us(window_end_ps),
        "measured_duration_us": ps_to_us(measured_duration_ps),
        "step_count": len(step_rows),
        "avg_step_duration_us": (
            sum(item["duration_us"] for item in step_rows) / len(step_rows) if step_rows else 0.0
        ),
        "gpu_busy_us": ps_to_us(gpu_busy_ps),
        "gpu_busy_ratio": (gpu_busy_ps / measured_duration_ps) if measured_duration_ps > 0 else 0.0,
        "gpu_span_us": ps_to_us(max(0, gpu_last_ps - gpu_first_ps)),
        "gpu_gap_total_us": gap_summary["total_gap_us"],
        "gpu_gap_ratio": (
            gap_summary["total_gap_us"] / ps_to_us(measured_duration_ps) if measured_duration_ps > 0 else 0.0
        ),
    }

    payload = {
        "input_xplane": str(xplane_path),
        "step_ranges": step_rows,
        "top_framework_regions": top_framework_regions[: max(top_k, 0)],
        "top_host_regions": top_host_regions[: max(top_k, 0)],
        "top_device_regions": top_device_regions[: max(top_k, 0)],
        "top_wait_or_copy_regions": top_wait_or_copy_regions[: max(top_k, 0)],
        "top_gpu_gaps": gap_summary["top_gaps"],
        "phase_summary": phase_summary,
        "hipprof_alignment": load_hipprof_alignment(hipprof_analysis_json, top_device_regions, top_k),
    }
    payload["next_step"] = classify(payload)
    return payload


def render_table(title: str, rows: list[dict], columns: list[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in columns) + " |"
    divider = "| " + " | ".join("---:" if key != "name" else "---" for key, _ in columns) + " |"
    lines = [f"## {title}", "", header, divider]
    if not rows:
        lines.append("| _none_ |" + " |".join("" for _ in columns[1:]) + " |")
        return "\n".join(lines)
    for row in rows:
        values: list[str] = []
        for key, _ in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                if key.endswith("_ratio") or key == "share":
                    values.append(f"{value:.4f}")
                else:
                    values.append(f"{value:.3f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_report(payload: dict[str, Any]) -> str:
    phase = payload["phase_summary"]
    next_step = payload["next_step"]
    lines = [
        "# xprof summary report",
        "",
        "## 1. Input",
        "",
        f"- xplane: `{payload['input_xplane']}`",
        f"- measured step count: {phase['step_count']}",
        "",
        "## 2. Step Window",
        "",
        f"- measured window: {phase['measured_duration_us']:.3f} us",
        f"- avg step duration: {phase['avg_step_duration_us']:.3f} us",
        f"- gpu busy ratio in measured window: {phase['gpu_busy_ratio']:.4f}",
        f"- gpu gap ratio in measured window: {phase['gpu_gap_ratio']:.4f}",
        "",
        render_table(
            "3. Step Ranges",
            payload["step_ranges"],
            [
                ("step_num", "Step"),
                ("name", "Name"),
                ("start_us", "Start us"),
                ("duration_us", "Duration us"),
                ("gpu_busy_us", "GPU Busy us"),
                ("gpu_busy_ratio", "GPU Busy Ratio"),
            ],
        ),
        "",
        render_table(
            "4. Top Framework Op / Region",
            payload["top_framework_regions"],
            [
                ("name", "Name"),
                ("calls", "Calls"),
                ("total_duration_us", "Total us"),
                ("avg_duration_us", "Avg us"),
            ],
        ),
        "",
        render_table(
            "5. Top Host Regions",
            payload["top_host_regions"],
            [
                ("name", "Name"),
                ("calls", "Calls"),
                ("total_duration_us", "Total us"),
                ("avg_duration_us", "Avg us"),
            ],
        ),
        "",
        render_table(
            "6. Top Device Regions",
            payload["top_device_regions"],
            [
                ("name", "Name"),
                ("calls", "Calls"),
                ("total_duration_us", "Total us"),
                ("avg_duration_us", "Avg us"),
                ("share", "Share"),
            ],
        ),
        "",
        render_table(
            "7. Wait / Copy Signals",
            payload["top_wait_or_copy_regions"],
            [
                ("name", "Name"),
                ("calls", "Calls"),
                ("total_duration_us", "Total us"),
                ("avg_duration_us", "Avg us"),
            ],
        ),
        "",
        render_table(
            "8. Top GPU Gaps",
            payload["top_gpu_gaps"],
            [
                ("gap_us", "Gap us"),
                ("prev_kernel", "Prev Kernel"),
                ("next_kernel", "Next Kernel"),
            ],
        ),
        "",
        "## 9. hipprof Alignment",
        "",
    ]

    alignment = payload["hipprof_alignment"]
    if not alignment:
        lines.append("- No hipprof alignment input was provided.")
    elif not alignment.get("available", False):
        lines.append(f"- {alignment['reason']}")
    else:
        overlap_names = alignment.get("overlap_names", [])
        lines.append(f"- overlap_count: {alignment['overlap_count']}")
        lines.append(
            "- overlap_names: "
            + (", ".join(f"`{name}`" for name in overlap_names) if overlap_names else "none")
        )
        lines.append(f"- hipprof_analysis_json: `{alignment['hipprof_analysis_json']}`")

    lines.extend(
        [
            "",
            "## 10. Next-Step Classification",
            "",
            f"- classification: `{next_step['classification']}`",
            f"- reason: {next_step['reason']}",
            "",
        ]
    )
    return "\n".join(lines)


def copy_artifacts(xplane_path: Path, export_dir: Path) -> list[str]:
    copied: list[str] = []
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / xplane_path.name
    shutil.copy2(xplane_path, target)
    copied.append(target.name)
    return copied


def main() -> None:
    args = parse_args()
    xplane_path = resolve_xplane(args.input)
    payload = build_payload(
        xplane_path=xplane_path,
        hipprof_analysis_json=args.hipprof_analysis_json,
        top_k=args.top_k,
        gap_top_k=args.gap_top_k,
    )
    report = build_report(payload)

    if args.export_dir:
        export_dir = Path(args.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / "report.md").write_text(report, encoding="utf-8")
        payload["copied_artifacts"] = copy_artifacts(xplane_path, export_dir)
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
