# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
import argparse
import bisect
import json
import math
import re
from collections import Counter, defaultdict


def percentile(values, pct):
    if not values:
        return 0.0
    vals = sorted(values)
    idx = (len(vals) - 1) * pct / 100.0
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    return vals[lo] * (hi - idx) + vals[hi] * (idx - lo)


def fmt_us(us):
    return f"{us / 1000.0:.3f} ms"


def get_arg(event, key):
    return (event.get("args") or {}).get(key)


def event_start(event):
    return float(event.get("ts") or 0.0)


def event_duration(event):
    return float(event.get("dur") or 0.0)


def event_end(event):
    return event_start(event) + event_duration(event)


def kernel_label(name):
    text = name or ""
    if text.startswith("Cijk_") or "Cijk_" in text:
        return "rocBLAS/Tensile GEMM"
    if "indexFuncLargeIndex" in text:
        return "index_add_/large-index scatter"
    checks = [
        "calc_subm_conv_indices_kernel",
        "calc_conv_indices_stage1_kernel",
        "calc_conv_indices_stage2_kernel",
        "clean_indices_uniq_kernel",
        "build_subm_hash_table_kernel",
        "build_conv_hash_and_assign_kernel",
        "clear_hash_table_kernel",
        "triton_",
        "radix_sort",
        "merge_sort",
        "partition_kernel",
        "block_reduce_kernel",
        "indexSelect",
        "index_select",
        "scatter_gather",
        "index_elementwise",
        "unrolled_elementwise",
        "vectorized_elementwise",
        "copy_device_to_device",
        "gemm",
        "Gemm",
        "rocblas",
        "conv",
        "hash",
        "sort",
        "unique",
    ]
    for key in checks:
        if key in text:
            return key
    simple = re.sub(r"\s+", " ", text).strip()
    simple = simple.split("<", 1)[0]
    simple = simple.rsplit(" ", 1)[-1]
    return simple[:120] if simple else "<unknown>"


def parse_target(text):
    if "=" not in text:
        raise ValueError("--target must be label=substring")
    label, needle = text.split("=", 1)
    label = label.strip()
    needle = needle.strip()
    if not label or not needle:
        raise ValueError("--target must be label=substring")
    return label, needle


def load_events(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    raw_events = data.get("traceEvents", data if isinstance(data, list) else [])
    return [
        e for e in raw_events
        if isinstance(e, dict) and e.get("ph") == "X" and e.get("ts") is not None
    ]


def summarize(events):
    durations = [event_duration(e) for e in events]
    total = sum(durations)
    return {
        "count": len(durations),
        "total": total,
        "avg": total / len(durations) if durations else 0.0,
        "p50": percentile(durations, 50),
        "p90": percentile(durations, 90),
        "p99": percentile(durations, 99),
        "max": max(durations) if durations else 0.0,
    }


def collect_nested(events_by_thread, starts_by_thread, interval):
    key = (interval.get("pid"), interval.get("tid"))
    thread_events = events_by_thread.get(key, [])
    starts = starts_by_thread.get(key, [])
    left = bisect.bisect_left(starts, event_start(interval))
    right = bisect.bisect_right(starts, event_end(interval))
    start = event_start(interval)
    end = event_end(interval)
    out = []
    for event in thread_events[left:right]:
        if event is interval:
            continue
        if event_start(event) >= start and event_end(event) <= end + 1.0:
            out.append(event)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace")
    parser.add_argument("--target", action="append", required=True,
                        help="Target scope as label=substring. Repeatable.")
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    targets = [parse_target(t) for t in args.target]
    events = load_events(args.trace)

    print("=== Trace event categories ===")
    for cat, count in Counter(e.get("cat", "") for e in events).most_common(20):
        print(f"{cat or '<none>'}: {count}")

    events_by_thread = defaultdict(list)
    for event in events:
        events_by_thread[(event.get("pid"), event.get("tid"))].append(event)
    starts_by_thread = {}
    for key, thread_events in events_by_thread.items():
        thread_events.sort(key=event_start)
        starts_by_thread[key] = [event_start(e) for e in thread_events]

    kernels_by_corr = defaultdict(list)
    memcpy_by_corr = defaultdict(list)
    runtime_by_corr = defaultdict(list)
    for event in events:
        corr = get_arg(event, "correlation")
        if corr is None:
            continue
        cat = event.get("cat", "")
        name = event.get("name", "")
        if cat == "kernel":
            kernels_by_corr[corr].append(event)
        elif cat in ("gpu_memcpy", "gpu_memset"):
            memcpy_by_corr[corr].append(event)
        elif cat in ("cuda_runtime", "cuda_driver") or name.startswith(("hip", "cuda")):
            runtime_by_corr[corr].append(event)

    print("\n=== Target scopes ===")
    for label, needle in targets:
        target_events = [e for e in events if needle in e.get("name", "")]
        stats = summarize(target_events)
        print(
            f"{label}: count={stats['count']} total={fmt_us(stats['total'])} "
            f"avg={fmt_us(stats['avg'])} p50={fmt_us(stats['p50'])} "
            f"p90={fmt_us(stats['p90'])} p99={fmt_us(stats['p99'])} "
            f"max={fmt_us(stats['max'])}"
        )

        ext_ids = set()
        correlations = set()
        child_time = Counter()
        child_count = Counter()
        child_cat_time = Counter()
        for interval in target_events:
            for child in collect_nested(events_by_thread, starts_by_thread, interval):
                ext_id = get_arg(child, "External id")
                corr = get_arg(child, "correlation")
                if ext_id is not None:
                    ext_ids.add(ext_id)
                if child.get("cat") in ("cuda_runtime", "cuda_driver") and corr is not None:
                    correlations.add(corr)
                child_time[child.get("name", "")] += event_duration(child)
                child_count[child.get("name", "")] += 1
                child_cat_time[child.get("cat", "")] += event_duration(child)

        print(f"  nested External ids: {len(ext_ids)}")
        print(f"  nested runtime correlations: {len(correlations)}")
        print("  top nested event categories:")
        for cat, total in child_cat_time.most_common(10):
            print(f"    {fmt_us(total)}  {cat or '<none>'}")
        print("  top nested events:")
        for name, total in child_time.most_common(args.top):
            print(f"    {fmt_us(total)}  x{child_count[name]}  {name}")

        kernel_time = Counter()
        kernel_count = Counter()
        memcpy_time = Counter()
        runtime_time = Counter()
        for corr in correlations:
            for kernel in kernels_by_corr.get(corr, []):
                raw_name = kernel.get("name") or get_arg(kernel, "kernel") or ""
                group = kernel_label(raw_name)
                kernel_time[group] += event_duration(kernel)
                kernel_count[group] += 1
            for memcpy in memcpy_by_corr.get(corr, []):
                memcpy_time[memcpy.get("name", memcpy.get("cat", ""))] += event_duration(memcpy)
            for runtime in runtime_by_corr.get(corr, []):
                runtime_time[runtime.get("name", "")] += event_duration(runtime)

        print(f"  attributed GPU kernel time: {fmt_us(sum(kernel_time.values()))}")
        print("  top attributed GPU kernels:")
        for name, total in kernel_time.most_common(args.top):
            print(f"    {fmt_us(total)}  x{kernel_count[name]}  {name}")
        if memcpy_time:
            print("  attributed GPU memcpy/memset:")
            for name, total in memcpy_time.most_common(args.top):
                print(f"    {fmt_us(total)}  {name}")
        if runtime_time:
            print("  top runtime API time:")
            for name, total in runtime_time.most_common(10):
                print(f"    {fmt_us(total)}  {name}")


if __name__ == "__main__":
    main()
