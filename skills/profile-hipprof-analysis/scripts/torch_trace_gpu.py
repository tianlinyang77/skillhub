# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Sequence

from torch_trace_common import (
    Event,
    format_us,
    intervals_coverage_us,
    is_copy_like_kernel,
    merge_intervals,
    print_header,
    safe_div,
)


def summarize_gpu_utilization(
    cpu_ops: Sequence[Event],
    runtime_ops: Sequence[Event],
    kernels: Sequence[Event],
) -> Dict[str, float]:
    kernel_intervals = merge_intervals(kernels)
    gpu_busy_us = intervals_coverage_us(kernel_intervals)
    copy_kernels = [kernel for kernel in kernels if is_copy_like_kernel(kernel.get("name", ""))]
    copy_busy_us = intervals_coverage_us(merge_intervals(copy_kernels))

    e2e_candidates = list(cpu_ops) + list(runtime_ops) + list(kernels)
    if not e2e_candidates:
        raise ValueError("trace 中没有可用于统计端到端耗时的事件")

    e2e_start_us = min(event["ts"] for event in e2e_candidates)
    e2e_end_us = max(event["ts"] + event["dur"] for event in e2e_candidates)
    e2e_total_us = e2e_end_us - e2e_start_us
    kernel_span_us = (kernels[-1]["ts"] + kernels[-1]["dur"] - kernels[0]["ts"]) if kernels else 0.0
    utilization_ratio = gpu_busy_us / e2e_total_us if e2e_total_us else 0.0
    copy_share_of_gpu_busy = safe_div(copy_busy_us, gpu_busy_us)

    print_header("1. GPU 利用率比")
    print(
        f"gpu_busy_time      : {format_us(gpu_busy_us)}\n"
        f"end_to_end_time    : {format_us(e2e_total_us)}\n"
        f"utilization_ratio  : {utilization_ratio:.4f} ({utilization_ratio * 100.0:.2f}%)\n"
        f"copy_busy_time     : {format_us(copy_busy_us)}\n"
        f"copy_busy_ratio    : {copy_share_of_gpu_busy:.4f} ({copy_share_of_gpu_busy * 100.0:.2f}%)"
    )
    print(
        f"补充信息: kernel_span={format_us(kernel_span_us)}, "
        f"first_event={min(e2e_candidates, key=lambda event: event['ts'])['name']}, "
        f"last_event={max(e2e_candidates, key=lambda event: event['ts'] + event['dur'])['name']}"
    )
    return {
        "gpu_busy_us": gpu_busy_us,
        "e2e_total_us": e2e_total_us,
        "utilization_ratio": utilization_ratio,
        "kernel_span_us": kernel_span_us,
        "copy_busy_us": copy_busy_us,
        "copy_share_of_gpu_busy": copy_share_of_gpu_busy,
    }


def summarize_top_kernels(kernels: Sequence[Event], top_k: int) -> list[Dict]:
    print_header(f"2. Top{top_k} Kernel 耗时（纯 GPU Kernel 聚合）")
    if not kernels:
        print("trace 中没有 kernel 事件，无法统计 Top kernel。")
        return []

    kernel_stats = defaultdict(
        lambda: {
            "name": "",
            "self_device_time_total_us": 0.0,
            "device_time_total_us": 0.0,
            "count": 0,
            "avg_device_time_us": 0.0,
            "max_device_time_us": 0.0,
            "device_share_pct": 0.0,
        }
    )
    total_kernel_time_us = 0.0

    for kernel in kernels:
        name = kernel["name"]
        dur = kernel["dur"]
        item = kernel_stats[name]
        item["name"] = name
        item["self_device_time_total_us"] += dur
        item["device_time_total_us"] += dur
        item["count"] += 1
        item["max_device_time_us"] = max(item["max_device_time_us"], dur)
        total_kernel_time_us += dur

    rows = sorted(
        kernel_stats.values(),
        key=lambda row: (row["device_time_total_us"], row["count"]),
        reverse=True,
    )[:top_k]

    for row in rows:
        row["avg_device_time_us"] = safe_div(row["device_time_total_us"], row["count"])
        row["device_share_pct"] = safe_div(row["device_time_total_us"], total_kernel_time_us) * 100.0

    header = (
        f"{'Name':<42} {'Dev total(us)':>14} {'Avg(us)':>12} "
        f"{'Max(us)':>12} {'Calls':>8} {'Share(%)':>10}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['name'][:42]:<42} "
            f"{row['device_time_total_us']:>14.3f} "
            f"{row['avg_device_time_us']:>12.3f} "
            f"{row['max_device_time_us']:>12.3f} "
            f"{row['count']:>8d} "
            f"{row['device_share_pct']:>10.2f}"
        )

    return rows
