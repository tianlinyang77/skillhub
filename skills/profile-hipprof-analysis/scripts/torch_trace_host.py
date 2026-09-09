# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

from torch_trace_common import (
    Event,
    build_dispatch_reason,
    build_event_starts,
    build_external_id_map,
    build_runtime_external_id_index,
    classify_cpu_stage,
    classify_runtime_api,
    clipped_coverage_us,
    find_leaf_cpu_ops,
    format_us,
    intervals_coverage_us,
    iter_event_overlaps,
    match_runtime_for_kernel,
    merge_event_intervals,
    merge_interval_groups,
    print_header,
    safe_div,
)


def summarize_gpu_gaps(
    kernels: Sequence[Event],
    runtime_ops: Sequence[Event],
    cpu_ops: Sequence[Event],
    top_k: int,
    post_launch_example_top_k: int,
) -> Dict:
    kernels = sorted(kernels, key=lambda event: event["ts"])
    runtime_ops = sorted(runtime_ops, key=lambda event: event["ts"])
    cpu_leaf_ops = sorted(find_leaf_cpu_ops(cpu_ops), key=lambda event: event["ts"])
    cpu_leaf_starts = build_event_starts(cpu_leaf_ops)
    runtime_by_correlation = {
        event.get("args", {}).get("correlation"): event
        for event in runtime_ops
        if event.get("args", {}).get("correlation") is not None
    }

    if not kernels:
        return {
            "total_bubble_us": 0.0,
            "total_pre_launch_us": 0.0,
            "total_launch_us": 0.0,
            "total_post_launch_us": 0.0,
            "total_sync_wait_us": 0.0,
            "total_other_runtime_prelaunch_us": 0.0,
            "total_cpu_prep_us": 0.0,
            "total_host_unattributed_us": 0.0,
            "top_bubbles": [],
            "top_sync_source": {},
            "top_cpu_prep_source": {},
            "top_post_launch_source": {},
            "top_post_launch_examples": [],
            "top_post_launch_instance": {},
        }

    bubble_by_transition = defaultdict(
        lambda: {
            "total_gap": 0.0,
            "count": 0,
            "max_gap": 0.0,
            "pre_launch": 0.0,
            "launch": 0.0,
            "post_launch": 0.0,
            "sync_wait": 0.0,
            "other_runtime_prelaunch": 0.0,
            "cpu_prep": 0.0,
            "host_unattributed": 0.0,
            "cpu_contributors": defaultdict(float),
            "runtime_contributors": defaultdict(float),
        }
    )
    gaps = []

    for index, (prev_event, next_event) in enumerate(zip(kernels, kernels[1:]), start=1):
        gap_start = prev_event["ts"] + prev_event["dur"]
        gap_end = next_event["ts"]
        gap = gap_end - gap_start
        if gap <= 0:
            continue

        next_runtime = runtime_by_correlation.get(next_event.get("args", {}).get("correlation"))
        launch_start = gap_end
        launch_end = gap_end
        if next_runtime is not None:
            launch_start = max(gap_start, min(gap_end, next_runtime["ts"]))
            launch_end = max(launch_start, min(gap_end, next_runtime["ts"] + next_runtime["dur"]))
        gap_before_launch = max(0.0, launch_start - gap_start)
        gap_runtime = max(0.0, launch_end - launch_start)
        gap_after_launch = max(0.0, gap_end - launch_end)

        gap_transition_key: Tuple[str, str] = (prev_event["name"], next_event["name"])
        transition_item = bubble_by_transition[gap_transition_key]
        transition_item["total_gap"] += gap
        transition_item["count"] += 1
        transition_item["max_gap"] = max(transition_item["max_gap"], gap)
        transition_item["pre_launch"] += gap_before_launch
        transition_item["launch"] += gap_runtime
        transition_item["post_launch"] += gap_after_launch

        prelaunch_runtime_events = [
            event
            for event in runtime_ops
            if event["ts"] < launch_start and event["ts"] + event["dur"] > gap_start
        ]
        sync_events = [event for event in prelaunch_runtime_events if classify_runtime_api(event["name"]) == "sync"]
        other_runtime_events = [
            event for event in prelaunch_runtime_events if classify_runtime_api(event["name"]) == "other"
        ]
        sync_wait = intervals_coverage_us(merge_event_intervals(sync_events, gap_start, launch_start))
        other_runtime_wait = intervals_coverage_us(
            merge_event_intervals(other_runtime_events, gap_start, launch_start)
        )

        cpu_matches = list(iter_event_overlaps(cpu_leaf_ops, cpu_leaf_starts, gap_start, launch_start))
        cpu_prep_wall = clipped_coverage_us(cpu_matches, gap_start, launch_start)
        cpu_contributors = defaultdict(float)
        for event, overlap in cpu_matches:
            cpu_contributors[event["name"]] += overlap

        runtime_launch_name = next_runtime["name"] if next_runtime is not None else "N/A"
        if gap_runtime > 0.0 and next_runtime is not None:
            transition_item["runtime_contributors"][runtime_launch_name] += gap_runtime
        for event in sync_events + other_runtime_events:
            overlap = max(0.0, min(launch_start, event["ts"] + event["dur"]) - max(gap_start, event["ts"]))
            if overlap > 0.0:
                transition_item["runtime_contributors"][event["name"]] += overlap

        covered_by_runtime = merge_event_intervals(prelaunch_runtime_events, gap_start, launch_start)
        covered_by_cpu = merge_event_intervals([event for event, _ in cpu_matches], gap_start, launch_start)
        host_unattributed = max(
            0.0,
            gap_before_launch - intervals_coverage_us(merge_interval_groups(covered_by_runtime, covered_by_cpu)),
        )

        transition_item["sync_wait"] += sync_wait
        transition_item["other_runtime_prelaunch"] += other_runtime_wait
        transition_item["cpu_prep"] += cpu_prep_wall
        transition_item["host_unattributed"] += host_unattributed
        for name, overlap in cpu_contributors.items():
            transition_item["cpu_contributors"][name] += overlap

        gaps.append(
            {
                "index": index,
                "gap": gap,
                "prev": prev_event,
                "next": next_event,
                "pre_launch_idle": gap_before_launch,
                "launch_runtime": gap_runtime,
                "post_launch_wait": gap_after_launch,
                "sync_wait": sync_wait,
                "other_runtime_wait": other_runtime_wait,
                "cpu_prep_wall": cpu_prep_wall,
                "host_unattributed": host_unattributed,
                "runtime_name": runtime_launch_name,
                "cpu_contributors": sorted(cpu_contributors.items(), key=lambda item: item[1], reverse=True),
            }
        )

    def build_reason(stat: Dict, total_gap_us: float) -> str:
        total_gap = stat["total_gap"]
        if total_gap <= 0.0:
            return "无有效空泡。"

        top_cpu_name, top_cpu_time = ("-", 0.0)
        if stat["cpu_contributors"]:
            top_cpu_name, top_cpu_time = max(stat["cpu_contributors"].items(), key=lambda item: item[1])

        sync_ratio = safe_div(stat["sync_wait"], total_gap)
        post_ratio = safe_div(stat["post_launch"], total_gap)
        cpu_ratio = safe_div(stat["cpu_prep"], total_gap)
        launch_ratio = safe_div(stat["launch"], total_gap)
        unattributed_ratio = safe_div(stat["host_unattributed"], total_gap)

        if sync_ratio >= 0.25:
            return (
                "主要由同步等待造成，典型表现是 pre-launch 窗口里有 hipDeviceSynchronize/类似 API；"
                "常见于显式 synchronize、profiler step 边界或框架强制同步。"
            )
        if post_ratio >= 0.35:
            return (
                "主要是 launch 之后 GPU 端还未立刻开跑下一个 kernel；"
                "通常意味着设备侧调度等待、stream 依赖或前序同步影响。"
            )
        if cpu_ratio >= 0.25:
            return f"主要是 host 侧准备下一算子，热点 CPU op 是 {top_cpu_name} ({format_us(top_cpu_time)})。"
        if launch_ratio >= 0.15:
            return "launch API 自身开销占比偏高，说明 kernel 提交频繁且较碎。"
        if unattributed_ratio >= 0.25:
            return (
                "大量时间落在 pre-launch 但没有命中 leaf CPU op；"
                "通常是框架调度、driver/运行时等待，或 trace 粒度不足。"
            )
        return "空泡由 CPU prep、runtime launch 和 post-launch device wait 共同构成。"

    def build_bubble_row(rank: int, prev_name: str, next_name: str, stat: Dict, total_gap_us: float) -> Dict:
        avg_gap = stat["total_gap"] / stat["count"]
        top_cpu_name = ""
        top_cpu_time = 0.0
        if stat["cpu_contributors"]:
            top_cpu_name, top_cpu_time = max(stat["cpu_contributors"].items(), key=lambda item: item[1])
        top_runtime_name = ""
        top_runtime_time = 0.0
        if stat["runtime_contributors"]:
            top_runtime_name, top_runtime_time = max(stat["runtime_contributors"].items(), key=lambda item: item[1])
        return {
            "rank": rank,
            "prev_kernel": prev_name,
            "next_kernel": next_name,
            "bubble_total_us": stat["total_gap"],
            "bubble_share_pct": safe_div(stat["total_gap"], total_gap_us) * 100.0,
            "avg_gap_us": avg_gap,
            "count": stat["count"],
            "max_gap_us": stat["max_gap"],
            "pre_launch_us": stat["pre_launch"],
            "sync_wait_us": stat["sync_wait"],
            "cpu_prep_us": stat["cpu_prep"],
            "other_runtime_prelaunch_us": stat["other_runtime_prelaunch"],
            "host_unattributed_us": stat["host_unattributed"],
            "launch_us": stat["launch"],
            "post_launch_us": stat["post_launch"],
            "top_cpu_op": top_cpu_name,
            "top_cpu_op_us": top_cpu_time,
            "top_runtime": top_runtime_name,
            "top_runtime_us": top_runtime_time,
            "reason": build_reason(stat, total_gap_us),
        }

    print_header(f"3. 空泡耗时 Top{top_k} 来源与原因分析")
    total_gap_us = sum(item["gap"] for item in gaps)
    total_pre_launch_us = sum(item["pre_launch_idle"] for item in gaps)
    total_launch_us = sum(item["launch_runtime"] for item in gaps)
    total_post_launch_us = sum(item["post_launch_wait"] for item in gaps)
    total_sync_wait_us = sum(item["sync_wait"] for item in gaps)
    total_other_runtime_prelaunch_us = sum(item["other_runtime_wait"] for item in gaps)
    total_cpu_prep_us = sum(item["cpu_prep_wall"] for item in gaps)
    total_host_unattributed_us = sum(item["host_unattributed"] for item in gaps)
    print(f"total_bubble_time : {format_us(total_gap_us)}")

    ranked_sources_all = sorted(bubble_by_transition.items(), key=lambda item: item[1]["total_gap"], reverse=True)
    bubble_rows_all: List[Dict] = [
        build_bubble_row(rank, prev_name, next_name, stat, total_gap_us)
        for rank, ((prev_name, next_name), stat) in enumerate(ranked_sources_all, start=1)
    ]
    bubble_rows: List[Dict] = []
    for row in bubble_rows_all[:top_k]:
        print(
            f"[Top {row['rank']}] bubble_total={format_us(row['bubble_total_us'])} "
            f"share={row['bubble_share_pct']:.2f}% avg={format_us(row['avg_gap_us'])} "
            f"count={row['count']} max={format_us(row['max_gap_us'])}"
        )
        print(f"  prev_kernel : {row['prev_kernel']}")
        print(f"  next_kernel : {row['next_kernel']}")
        print(
            "  breakdown   : "
            f"pre_launch={format_us(row['pre_launch_us'])}, "
            f"sync_wait={format_us(row['sync_wait_us'])}, "
            f"cpu_prep={format_us(row['cpu_prep_us'])}, "
            f"host_unattributed={format_us(row['host_unattributed_us'])}, "
            f"launch={format_us(row['launch_us'])}, "
            f"post_launch={format_us(row['post_launch_us'])}"
        )
        top_cpu_text = f"{row['top_cpu_op']}({format_us(row['top_cpu_op_us'])})" if row["top_cpu_op"] else "-"
        top_runtime_text = f"{row['top_runtime']}({format_us(row['top_runtime_us'])})" if row["top_runtime"] else "-"
        print(f"  top_cpu_op  : {top_cpu_text}")
        print(f"  top_runtime : {top_runtime_text}")
        print(f"  reason      : {row['reason']}")
        bubble_rows.append(row)

    top_sync_source = max(bubble_rows_all, key=lambda row: row["sync_wait_us"], default={})
    if top_sync_source and top_sync_source.get("sync_wait_us", 0.0) <= 0.0:
        top_sync_source = {}
    top_cpu_prep_source = max(bubble_rows_all, key=lambda row: row["cpu_prep_us"], default={})
    if top_cpu_prep_source and top_cpu_prep_source.get("cpu_prep_us", 0.0) <= 0.0:
        top_cpu_prep_source = {}
    top_post_launch_source = max(bubble_rows_all, key=lambda row: row["post_launch_us"], default={})
    if top_post_launch_source and top_post_launch_source.get("post_launch_us", 0.0) <= 0.0:
        top_post_launch_source = {}

    top_post_launch_examples: List[Dict] = []
    ranked_post_launch_gaps = sorted(
        [item for item in gaps if item.get("post_launch_wait", 0.0) > 0.0],
        key=lambda item: (item["post_launch_wait"], item["gap"], item["launch_runtime"]),
        reverse=True,
    )[:post_launch_example_top_k]
    for rank, gap_item in enumerate(ranked_post_launch_gaps, start=1):
        top_cpu_name = ""
        top_cpu_time = 0.0
        if gap_item.get("cpu_contributors"):
            top_cpu_name, top_cpu_time = gap_item["cpu_contributors"][0]
        top_post_launch_examples.append(
            {
                "rank": rank,
                "index": gap_item.get("index", 0),
                "prev_kernel": gap_item.get("prev", {}).get("name", ""),
                "next_kernel": gap_item.get("next", {}).get("name", ""),
                "bubble_total_us": gap_item.get("gap", 0.0),
                "pre_launch_us": gap_item.get("pre_launch_idle", 0.0),
                "launch_us": gap_item.get("launch_runtime", 0.0),
                "post_launch_us": gap_item.get("post_launch_wait", 0.0),
                "sync_wait_us": gap_item.get("sync_wait", 0.0),
                "cpu_prep_us": gap_item.get("cpu_prep_wall", 0.0),
                "host_unattributed_us": gap_item.get("host_unattributed", 0.0),
                "runtime": gap_item.get("runtime_name", ""),
                "top_cpu_op": top_cpu_name,
                "top_cpu_op_us": top_cpu_time,
            }
        )
    top_post_launch_instance = top_post_launch_examples[0] if top_post_launch_examples else {}

    return {
        "total_bubble_us": total_gap_us,
        "total_pre_launch_us": total_pre_launch_us,
        "total_launch_us": total_launch_us,
        "total_post_launch_us": total_post_launch_us,
        "total_sync_wait_us": total_sync_wait_us,
        "total_other_runtime_prelaunch_us": total_other_runtime_prelaunch_us,
        "total_cpu_prep_us": total_cpu_prep_us,
        "total_host_unattributed_us": total_host_unattributed_us,
        "top_bubbles": bubble_rows,
        "top_sync_source": top_sync_source,
        "top_cpu_prep_source": top_cpu_prep_source,
        "top_post_launch_source": top_post_launch_source,
        "top_post_launch_examples": top_post_launch_examples,
        "top_post_launch_instance": top_post_launch_instance,
    }


def summarize_dispatch_ahead(
    kernels: Sequence[Event],
    runtime_ops: Sequence[Event],
    cpu_ops: Sequence[Event],
    top_k: int,
    example_top_k: int,
) -> Dict:
    kernels = sorted(kernels, key=lambda event: event["ts"])
    runtime_by_correlation = {
        event.get("args", {}).get("correlation"): event
        for event in runtime_ops
        if event.get("args", {}).get("correlation") is not None
    }
    runtime_by_external_id = build_runtime_external_id_index(runtime_ops)
    cpu_by_external_id = build_external_id_map(cpu_ops)

    kernels_by_stream: Dict[Tuple[int, int], List[Event]] = defaultdict(list)
    for kernel in kernels:
        args = kernel.get("args", {})
        stream_key = (args.get("device", -1), args.get("stream", -1))
        kernels_by_stream[stream_key].append(kernel)
    for group in kernels_by_stream.values():
        group.sort(key=lambda event: event["ts"])

    followup_kernels = sum(max(0, len(group) - 1) for group in kernels_by_stream.values())
    stats = {
        "followup_kernels": followup_kernels,
        "comparable_kernels": 0,
        "unknown_count": 0,
        "fully_ahead_count": 0,
        "partial_ahead_count": 0,
        "late_count": 0,
        "strict_ahead_ratio": 0.0,
        "prestarted_ratio": 0.0,
        "late_ratio": 0.0,
        "total_dispatch_exposed_us": 0.0,
        "total_late_submit_us": 0.0,
        "total_runtime_submit_us": 0.0,
        "total_post_launch_gap_us": 0.0,
        "total_ahead_margin_us": 0.0,
        "total_prestart_margin_us": 0.0,
        "total_cpu_tail_after_launch_us": 0.0,
        "cpu_tail_after_launch_count": 0,
        "fully_ahead_with_cpu_tail_count": 0,
        "top_cpu_ops": [],
        "top_examples": [],
    }

    per_cpu_op = defaultdict(
        lambda: {
            "dispatch_exposed_us": 0.0,
            "late_submit_us": 0.0,
            "runtime_submit_us": 0.0,
            "post_launch_gap_us": 0.0,
            "ahead_margin_us": 0.0,
            "prestart_margin_us": 0.0,
            "cpu_tail_after_launch_us": 0.0,
            "count": 0,
            "fully_ahead_count": 0,
            "partial_ahead_count": 0,
            "late_count": 0,
            "async_tail_count": 0,
            "done_before_prev_end_count": 0,
            "running_across_prev_end_count": 0,
            "started_after_prev_end_count": 0,
            "unknown_cpu_stage_count": 0,
            "max_dispatch_exposed_us": 0.0,
            "example_kernel": "",
            "example_prev_kernel": "",
            "example_runtime": "",
            "example_status": "",
        }
    )
    examples: List[Dict] = []

    for stream_key, stream_kernels in sorted(kernels_by_stream.items()):
        for prev_kernel, kernel in zip(stream_kernels, stream_kernels[1:]):
            prev_end = prev_kernel["ts"] + prev_kernel["dur"]
            next_start = kernel["ts"]
            next_end = next_start + kernel["dur"]
            runtime_event = match_runtime_for_kernel(
                kernel=kernel,
                runtime_by_correlation=runtime_by_correlation,
                runtime_by_external_id=runtime_by_external_id,
            )
            if runtime_event is None:
                stats["unknown_count"] += 1
                continue

            runtime_start = runtime_event["ts"]
            runtime_end = runtime_start + runtime_event["dur"]
            clipped_runtime_start = min(runtime_start, next_start)
            clipped_runtime_end = min(max(clipped_runtime_start, runtime_end), next_start)

            external_id = runtime_event.get("args", {}).get("External id")
            if external_id is None:
                external_id = kernel.get("args", {}).get("External id")
            cpu_event = cpu_by_external_id.get(external_id) if external_id is not None else None
            cpu_name = cpu_event["name"] if cpu_event is not None else "UNKNOWN_CPU_OP"
            cpu_stage = classify_cpu_stage(cpu_event, prev_end)

            if runtime_end <= prev_end:
                status = "fully_ahead"
            elif runtime_start < prev_end < runtime_end:
                status = "partial_ahead"
            else:
                status = "late"

            dispatch_exposed_us = max(0.0, clipped_runtime_end - prev_end)
            late_submit_us = max(0.0, min(clipped_runtime_start, next_start) - prev_end)
            runtime_submit_us = max(
                0.0,
                clipped_runtime_end - max(prev_end, min(clipped_runtime_start, next_start)),
            )
            post_launch_gap_us = max(0.0, next_start - max(prev_end, clipped_runtime_end))
            ahead_margin_us = max(0.0, prev_end - runtime_end)
            prestart_margin_us = max(0.0, prev_end - runtime_start)

            cpu_tail_after_launch_us = 0.0
            if cpu_event is not None:
                cpu_end = cpu_event["ts"] + cpu_event["dur"]
                cpu_tail_after_launch_us = max(0.0, cpu_end - runtime_end)

            stats["comparable_kernels"] += 1
            stats["total_dispatch_exposed_us"] += dispatch_exposed_us
            stats["total_late_submit_us"] += late_submit_us
            stats["total_runtime_submit_us"] += runtime_submit_us
            stats["total_post_launch_gap_us"] += post_launch_gap_us
            stats["total_ahead_margin_us"] += ahead_margin_us
            stats["total_prestart_margin_us"] += prestart_margin_us
            stats["total_cpu_tail_after_launch_us"] += cpu_tail_after_launch_us

            if cpu_tail_after_launch_us > 0.0:
                stats["cpu_tail_after_launch_count"] += 1
            if status == "fully_ahead":
                stats["fully_ahead_count"] += 1
                if cpu_tail_after_launch_us > 0.0:
                    stats["fully_ahead_with_cpu_tail_count"] += 1
            elif status == "partial_ahead":
                stats["partial_ahead_count"] += 1
            else:
                stats["late_count"] += 1

            item = per_cpu_op[cpu_name]
            item["dispatch_exposed_us"] += dispatch_exposed_us
            item["late_submit_us"] += late_submit_us
            item["runtime_submit_us"] += runtime_submit_us
            item["post_launch_gap_us"] += post_launch_gap_us
            item["ahead_margin_us"] += ahead_margin_us
            item["prestart_margin_us"] += prestart_margin_us
            item["cpu_tail_after_launch_us"] += cpu_tail_after_launch_us
            item["count"] += 1
            if status == "fully_ahead":
                item["fully_ahead_count"] += 1
            elif status == "partial_ahead":
                item["partial_ahead_count"] += 1
            else:
                item["late_count"] += 1
            if cpu_tail_after_launch_us > 0.0:
                item["async_tail_count"] += 1
            if cpu_stage == "done_before_prev_end":
                item["done_before_prev_end_count"] += 1
            elif cpu_stage == "running_across_prev_end":
                item["running_across_prev_end_count"] += 1
            elif cpu_stage == "started_after_prev_end":
                item["started_after_prev_end_count"] += 1
            else:
                item["unknown_cpu_stage_count"] += 1

            if dispatch_exposed_us >= item["max_dispatch_exposed_us"]:
                item["max_dispatch_exposed_us"] = dispatch_exposed_us
                item["example_kernel"] = kernel["name"]
                item["example_prev_kernel"] = prev_kernel["name"]
                item["example_runtime"] = runtime_event["name"]
                item["example_status"] = status

            examples.append(
                {
                    "stream": stream_key[1],
                    "device": stream_key[0],
                    "prev_kernel": prev_kernel["name"],
                    "kernel": kernel["name"],
                    "runtime": runtime_event["name"],
                    "cpu_op": cpu_name,
                    "status": status,
                    "dispatch_exposed_us": dispatch_exposed_us,
                    "late_submit_us": late_submit_us,
                    "runtime_submit_us": runtime_submit_us,
                    "post_launch_gap_us": post_launch_gap_us,
                    "ahead_margin_us": ahead_margin_us,
                    "prestart_margin_us": prestart_margin_us,
                    "cpu_tail_after_launch_us": cpu_tail_after_launch_us,
                    "cpu_stage": cpu_stage,
                    "prev_end_us": prev_end,
                    "launch_start_us": runtime_start,
                    "launch_end_us": runtime_end,
                    "kernel_start_us": next_start,
                    "kernel_end_us": next_end,
                }
            )

    comparable = stats["comparable_kernels"]
    stats["strict_ahead_ratio"] = safe_div(stats["fully_ahead_count"], comparable)
    stats["prestarted_ratio"] = safe_div(stats["fully_ahead_count"] + stats["partial_ahead_count"], comparable)
    stats["late_ratio"] = safe_div(stats["late_count"], comparable)

    top_cpu_rows: List[Dict] = []
    ranked_cpu_ops = sorted(
        per_cpu_op.items(),
        key=lambda item: (item[1]["dispatch_exposed_us"], item[1]["late_count"], item[1]["count"]),
        reverse=True,
    )[:top_k]
    for rank, (cpu_name, item) in enumerate(ranked_cpu_ops, start=1):
        top_cpu_rows.append(
            {
                "rank": rank,
                "cpu_op": cpu_name,
                "dispatch_exposed_us": item["dispatch_exposed_us"],
                "dispatch_share_pct": safe_div(item["dispatch_exposed_us"], stats["total_dispatch_exposed_us"]) * 100.0,
                "late_submit_us": item["late_submit_us"],
                "runtime_submit_us": item["runtime_submit_us"],
                "post_launch_gap_us": item["post_launch_gap_us"],
                "ahead_margin_us": item["ahead_margin_us"],
                "prestart_margin_us": item["prestart_margin_us"],
                "cpu_tail_after_launch_us": item["cpu_tail_after_launch_us"],
                "count": item["count"],
                "fully_ahead_count": item["fully_ahead_count"],
                "partial_ahead_count": item["partial_ahead_count"],
                "late_count": item["late_count"],
                "async_tail_count": item["async_tail_count"],
                "done_before_prev_end_count": item["done_before_prev_end_count"],
                "running_across_prev_end_count": item["running_across_prev_end_count"],
                "started_after_prev_end_count": item["started_after_prev_end_count"],
                "unknown_cpu_stage_count": item["unknown_cpu_stage_count"],
                "avg_dispatch_exposed_us": safe_div(item["dispatch_exposed_us"], item["count"]),
                "max_dispatch_exposed_us": item["max_dispatch_exposed_us"],
                "example_kernel": item["example_kernel"],
                "example_prev_kernel": item["example_prev_kernel"],
                "example_runtime": item["example_runtime"],
                "example_status": item["example_status"],
                "reason": build_dispatch_reason(item),
            }
        )

    top_examples = sorted(
        examples,
        key=lambda row: (
            row["dispatch_exposed_us"],
            row["late_submit_us"],
            row["runtime_submit_us"],
            row["post_launch_gap_us"],
        ),
        reverse=True,
    )[:example_top_k]
    for rank, row in enumerate(top_examples, start=1):
        row["rank"] = rank

    stats["top_cpu_ops"] = top_cpu_rows
    stats["top_examples"] = top_examples

    print_header("4. CPU->Kernel 提前下发分析")
    print(
        f"followup_kernels                : {followup_kernels}\n"
        f"comparable_kernels              : {comparable}\n"
        f"unknown_kernels                 : {stats['unknown_count']}\n"
        f"fully_ahead                     : {stats['fully_ahead_count']} ({safe_div(stats['fully_ahead_count'], comparable) * 100.0:.2f}%)\n"
        f"partial_ahead                   : {stats['partial_ahead_count']} ({safe_div(stats['partial_ahead_count'], comparable) * 100.0:.2f}%)\n"
        f"late_launch                     : {stats['late_count']} ({safe_div(stats['late_count'], comparable) * 100.0:.2f}%)\n"
        f"strict_ahead_ratio              : {stats['strict_ahead_ratio']:.4f} ({stats['strict_ahead_ratio'] * 100.0:.2f}%)\n"
        f"prestarted_ratio                : {stats['prestarted_ratio']:.4f} ({stats['prestarted_ratio'] * 100.0:.2f}%)\n"
        f"dispatch_exposed_total          : {format_us(stats['total_dispatch_exposed_us'])}\n"
        f"  ├─ late_submit_total          : {format_us(stats['total_late_submit_us'])}\n"
        f"  └─ runtime_submit_total       : {format_us(stats['total_runtime_submit_us'])}\n"
        f"post_launch_gap_total           : {format_us(stats['total_post_launch_gap_us'])}\n"
        f"ahead_margin_total              : {format_us(stats['total_ahead_margin_us'])}\n"
        f"cpu_tail_after_launch_total     : {format_us(stats['total_cpu_tail_after_launch_us'])}\n"
        f"cpu_tail_after_launch_count     : {stats['cpu_tail_after_launch_count']}\n"
        f"fully_ahead_with_cpu_tail_count : {stats['fully_ahead_with_cpu_tail_count']}"
    )
    print(
        "说明: fully_ahead=launch API 在上一 kernel 结束前已完成；"
        "partial_ahead=launch 已开始但未在上一 kernel 结束前完成；"
        "late_launch=上一 kernel 结束后才开始 launch。"
    )
    print(
        "注: cpu_tail_after_launch_total 是按 kernel 关联累计，"
        "用于判断 launch 后 host 尾部能否继续与 GPU overlap，并非去重后的 wall time。"
    )

    print("-" * 96)
    print(f"Top{top_k} 迟下发 CPU Op 来源（按 dispatch_exposed_us 排序）")
    if not top_cpu_rows:
        print("无可用 dispatch 归因数据。")
    for row in top_cpu_rows:
        print(
            f"[Top {row['rank']}] dispatch_exposed={format_us(row['dispatch_exposed_us'])} "
            f"share={row['dispatch_share_pct']:.2f}% avg={format_us(row['avg_dispatch_exposed_us'])} "
            f"count={row['count']} late={row['late_count']} partial={row['partial_ahead_count']} "
            f"fully={row['fully_ahead_count']}"
        )
        print(f"  cpu_op     : {row['cpu_op']}")
        print(
            "  breakdown  : "
            f"late_submit={format_us(row['late_submit_us'])}, "
            f"runtime_submit={format_us(row['runtime_submit_us'])}, "
            f"post_launch_gap={format_us(row['post_launch_gap_us'])}, "
            f"cpu_tail_after_launch={format_us(row['cpu_tail_after_launch_us'])}"
        )
        print(
            "  cpu_stage  : "
            f"done_before_prev_end={row['done_before_prev_end_count']}, "
            f"running_across_prev_end={row['running_across_prev_end_count']}, "
            f"started_after_prev_end={row['started_after_prev_end_count']}, "
            f"unknown={row['unknown_cpu_stage_count']}"
        )
        print(
            "  example    : "
            f"prev={row['example_prev_kernel']}, "
            f"kernel={row['example_kernel']}, "
            f"runtime={row['example_runtime']}, "
            f"status={row['example_status']}"
        )
        print(f"  reason     : {row['reason']}")

    print("-" * 96)
    print(f"Top{top_k} 迟下发具体实例")
    if not top_examples:
        print("无可用实例。")
    for row in top_examples:
        print(
            f"[Top {row['rank']}] dispatch_exposed={format_us(row['dispatch_exposed_us'])} "
            f"late_submit={format_us(row['late_submit_us'])} "
            f"runtime_submit={format_us(row['runtime_submit_us'])} "
            f"post_launch_gap={format_us(row['post_launch_gap_us'])}"
        )
        print(
            "  item       : "
            f"cpu_op={row['cpu_op']}, runtime={row['runtime']}, status={row['status']}, "
            f"stream={row['stream']}, device={row['device']}"
        )
        print(f"  prev_kernel : {row['prev_kernel']}")
        print(f"  next_kernel : {row['kernel']}")
        print(
            "  timing     : "
            f"prev_end={format_us(row['prev_end_us'])}, "
            f"launch=[{format_us(row['launch_start_us'])}, {format_us(row['launch_end_us'])}], "
            f"kernel_start={format_us(row['kernel_start_us'])}, "
            f"cpu_tail_after_launch={format_us(row['cpu_tail_after_launch_us'])}, "
            f"cpu_stage={row['cpu_stage']}"
        )

    return stats


def summarize_joint_attribution(bubble_summary: Dict, dispatch_summary: Dict) -> Dict:
    total_bubble_us = bubble_summary.get("total_bubble_us", 0.0)
    total_pre_launch_us = bubble_summary.get("total_pre_launch_us", 0.0)
    total_launch_us = bubble_summary.get("total_launch_us", 0.0)
    total_post_launch_us = bubble_summary.get("total_post_launch_us", 0.0)
    total_sync_wait_us = bubble_summary.get("total_sync_wait_us", 0.0)
    total_cpu_prep_us = bubble_summary.get("total_cpu_prep_us", 0.0)
    total_host_unattributed_us = bubble_summary.get("total_host_unattributed_us", 0.0)

    dispatch_exposed_us = dispatch_summary.get("total_dispatch_exposed_us", 0.0)
    late_submit_us = dispatch_summary.get("total_late_submit_us", 0.0)
    runtime_submit_us = dispatch_summary.get("total_runtime_submit_us", 0.0)
    post_launch_gap_us = dispatch_summary.get("total_post_launch_gap_us", 0.0)

    dispatch_share_pct = safe_div(dispatch_exposed_us, total_bubble_us) * 100.0
    post_launch_share_pct = safe_div(post_launch_gap_us, total_bubble_us) * 100.0
    pre_launch_share_pct = safe_div(total_pre_launch_us, total_bubble_us) * 100.0
    launch_share_pct = safe_div(total_launch_us, total_bubble_us) * 100.0
    sync_wait_share_pct = safe_div(total_sync_wait_us, total_bubble_us) * 100.0
    cpu_prep_share_pct = safe_div(total_cpu_prep_us, total_bubble_us) * 100.0
    host_unattributed_share_pct = safe_div(total_host_unattributed_us, total_bubble_us) * 100.0

    late_submit_share_in_dispatch_pct = safe_div(late_submit_us, dispatch_exposed_us) * 100.0
    runtime_submit_share_in_dispatch_pct = safe_div(runtime_submit_us, dispatch_exposed_us) * 100.0

    top_sync_source = bubble_summary.get("top_sync_source") or {}
    top_cpu_prep_source = bubble_summary.get("top_cpu_prep_source") or {}
    top_post_launch_source = bubble_summary.get("top_post_launch_source") or {}
    top_dispatch_cpu = (dispatch_summary.get("top_cpu_ops") or [{}])[0]

    if dispatch_share_pct >= 60.0:
        bubble_shape = "总空泡以 dispatch 暴露为主"
    elif post_launch_share_pct >= 60.0:
        bubble_shape = "总空泡以 post-launch 设备侧等待为主"
    else:
        bubble_shape = "总空泡由 dispatch 暴露和 post-launch 等待共同构成"

    if late_submit_share_in_dispatch_pct >= 70.0:
        dispatch_shape = "dispatch 暴露里以 late_submit 为主，说明主要在等 host 更早发起 launch"
    elif runtime_submit_share_in_dispatch_pct >= 30.0:
        dispatch_shape = "dispatch 暴露里 runtime_submit 占比偏高，说明 runtime/driver 提交成本比较显著"
    else:
        dispatch_shape = "dispatch 暴露在 late_submit 和 runtime_submit 之间较为混合"

    sync_note = "未观察到显著同步泡。"
    if top_sync_source:
        sync_note = (
            "最大的同步泡来源是 "
            f"`{top_sync_source['prev_kernel']}` -> `{top_sync_source['next_kernel']}`，"
            f"sync_wait={top_sync_source['sync_wait_us']:.3f} us。"
        )

    dispatch_hotspot_note = "未识别到明显的 dispatch 热点 CPU Op。"
    if top_dispatch_cpu and top_dispatch_cpu.get("cpu_op"):
        dispatch_hotspot_note = (
            "最大的 steady-state dispatch 热点是 "
            f"`{top_dispatch_cpu['cpu_op']}`，"
            f"dispatch_exposed={top_dispatch_cpu['dispatch_exposed_us']:.3f} us，"
            f"late_submit={top_dispatch_cpu['late_submit_us']:.3f} us。"
        )

    conclusion = (
        f"{bubble_shape}；其中 dispatch_exposed={dispatch_share_pct:.2f}% ，"
        f"post_launch={post_launch_share_pct:.2f}%。"
        f"{dispatch_shape}。{dispatch_hotspot_note}"
    )
    if top_sync_source and safe_div(top_sync_source.get("sync_wait_us", 0.0), total_bubble_us) >= 0.10:
        conclusion += f" 同时 {sync_note} 这部分更像同步/测量边界效应，应与 steady-state dispatch 泡区分看。"

    summary = {
        "total_bubble_us": total_bubble_us,
        "dispatch_exposed_us": dispatch_exposed_us,
        "dispatch_share_of_bubble_pct": dispatch_share_pct,
        "post_launch_gap_us": post_launch_gap_us,
        "post_launch_share_of_bubble_pct": post_launch_share_pct,
        "total_pre_launch_us": total_pre_launch_us,
        "pre_launch_share_of_bubble_pct": pre_launch_share_pct,
        "total_launch_us": total_launch_us,
        "launch_share_of_bubble_pct": launch_share_pct,
        "total_sync_wait_us": total_sync_wait_us,
        "sync_wait_share_of_bubble_pct": sync_wait_share_pct,
        "total_cpu_prep_us": total_cpu_prep_us,
        "cpu_prep_share_of_bubble_pct": cpu_prep_share_pct,
        "total_host_unattributed_us": total_host_unattributed_us,
        "host_unattributed_share_of_bubble_pct": host_unattributed_share_pct,
        "late_submit_us": late_submit_us,
        "late_submit_share_of_dispatch_pct": late_submit_share_in_dispatch_pct,
        "runtime_submit_us": runtime_submit_us,
        "runtime_submit_share_of_dispatch_pct": runtime_submit_share_in_dispatch_pct,
        "top_sync_source": top_sync_source,
        "top_cpu_prep_source": top_cpu_prep_source,
        "top_post_launch_source": top_post_launch_source,
        "top_dispatch_cpu_op": top_dispatch_cpu,
        "bubble_shape": bubble_shape,
        "dispatch_shape": dispatch_shape,
        "sync_note": sync_note,
        "dispatch_hotspot_note": dispatch_hotspot_note,
        "conclusion": conclusion,
    }

    print_header("5. Bubble / Dispatch 联合归因总结")
    print(
        f"bubble_total                    : {format_us(total_bubble_us)}\n"
        f"dispatch_exposed_total         : {format_us(dispatch_exposed_us)} ({dispatch_share_pct:.2f}%)\n"
        f"post_launch_gap_total          : {format_us(post_launch_gap_us)} ({post_launch_share_pct:.2f}%)\n"
        f"pre_launch_total               : {format_us(total_pre_launch_us)} ({pre_launch_share_pct:.2f}%)\n"
        f"launch_total                   : {format_us(total_launch_us)} ({launch_share_pct:.2f}%)\n"
        f"sync_wait_total                : {format_us(total_sync_wait_us)} ({sync_wait_share_pct:.2f}%)\n"
        f"cpu_prep_total                 : {format_us(total_cpu_prep_us)} ({cpu_prep_share_pct:.2f}%)\n"
        f"host_unattributed_total        : {format_us(total_host_unattributed_us)} ({host_unattributed_share_pct:.2f}%)\n"
        f"late_submit_total              : {format_us(late_submit_us)} ({late_submit_share_in_dispatch_pct:.2f}% of dispatch)\n"
        f"runtime_submit_total           : {format_us(runtime_submit_us)} ({runtime_submit_share_in_dispatch_pct:.2f}% of dispatch)"
    )
    if top_dispatch_cpu and top_dispatch_cpu.get("cpu_op"):
        print(
            "top_dispatch_cpu_op            : "
            f"{top_dispatch_cpu['cpu_op']} "
            f"(dispatch_exposed={format_us(top_dispatch_cpu['dispatch_exposed_us'])}, "
            f"late_submit={format_us(top_dispatch_cpu['late_submit_us'])})"
        )
    if top_sync_source:
        print(
            "top_sync_bubble               : "
            f"{top_sync_source['prev_kernel']} -> {top_sync_source['next_kernel']} "
            f"(sync_wait={format_us(top_sync_source['sync_wait_us'])}, "
            f"bubble_total={format_us(top_sync_source['bubble_total_us'])})"
        )
    print(f"joint_conclusion              : {conclusion}")

    return summary
