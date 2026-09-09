# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import sys
from bisect import bisect_right
from collections import defaultdict
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Sequence, Tuple


Event = Dict
Interval = Tuple[float, float]


def load_events(trace_path: str) -> List[Event]:
    # Some DTK/ROCTracer Chrome traces contain raw control characters in long
    # metadata/kernel argument strings. Python's strict JSON mode rejects those
    # even when Perfetto-style viewers and PyTorch's exporter accept the file.
    text = Path(trace_path).read_text()
    try:
        obj = json.loads(text, strict=False)
        return obj["traceEvents"]
    except JSONDecodeError as exc:
        events = _load_trace_events_recovering_bad_records(text)
        if events:
            print(
                f"warning: recovered {len(events)} trace events from malformed JSON; "
                f"first parse error at line {exc.lineno} column {exc.colno}: {exc.msg}",
                file=sys.stderr,
            )
            return events
        raise


def _load_trace_events_recovering_bad_records(text: str) -> List[Event]:
    key_pos = text.find('"traceEvents"')
    if key_pos < 0:
        return []
    array_start = text.find("[", key_pos)
    if array_start < 0:
        return []

    decoder = json.JSONDecoder(strict=False)
    idx = array_start + 1
    events: List[Event] = []
    skipped = 0
    while idx < len(text):
        idx = _skip_json_ws_and_commas(text, idx)
        if idx >= len(text) or text[idx] == "]":
            break
        if text[idx] != "{":
            next_obj = text.find("\n  {", idx + 1)
            next_end = text.find("\n  ]", idx + 1)
            if next_obj < 0 or (next_end >= 0 and next_end < next_obj):
                break
            skipped += 1
            idx = next_obj + 3
            continue
        try:
            event, idx = decoder.raw_decode(text, idx)
        except JSONDecodeError:
            next_obj = text.find("\n  {", idx + 1)
            next_end = text.find("\n  ]", idx + 1)
            if next_obj < 0 or (next_end >= 0 and next_end < next_obj):
                break
            skipped += 1
            idx = next_obj + 3
            continue
        if isinstance(event, dict):
            events.append(event)

    if skipped:
        print(f"warning: skipped {skipped} malformed trace events", file=sys.stderr)
    return events


def _skip_json_ws_and_commas(text: str, idx: int) -> int:
    while idx < len(text) and text[idx] in " \t\r\n,":
        idx += 1
    return idx


def load_profile_payload(profile_json_path: str) -> Dict:
    if not profile_json_path:
        return {}
    return json.loads(Path(profile_json_path).read_text())


def filter_events(events: Iterable[Event], cat: str) -> List[Event]:
    return [
        event
        for event in events
        if event.get("cat") == cat and event.get("ph") == "X" and "ts" in event and "dur" in event
    ]


def merge_intervals(events: Sequence[Event]) -> List[Interval]:
    intervals: List[List[float]] = []
    for event in sorted(events, key=lambda item: item["ts"]):
        start = event["ts"]
        end = start + event["dur"]
        if not intervals or start > intervals[-1][1]:
            intervals.append([start, end])
        else:
            intervals[-1][1] = max(intervals[-1][1], end)
    return [(start, end) for start, end in intervals]


def build_event_starts(events: Sequence[Event]) -> List[float]:
    return [event["ts"] for event in events]


def interval_overlap_us(start: float, end: float, intervals: Sequence[Interval]) -> float:
    if start >= end or not intervals:
        return 0.0

    starts = [left for left, _ in intervals]
    idx = bisect_right(starts, start) - 1
    if idx < 0:
        idx = 0

    overlap = 0.0
    while idx < len(intervals):
        left, right = intervals[idx]
        if left >= end:
            break
        if right <= start:
            idx += 1
            continue
        overlap += max(0.0, min(end, right) - max(start, left))
        idx += 1
    return overlap


def iter_event_overlaps(
    events: Sequence[Event],
    event_starts: Sequence[float],
    start: float,
    end: float,
) -> Iterator[Tuple[Event, float]]:
    if start >= end or not events:
        return

    idx = bisect_right(event_starts, start) - 1
    if idx < 0:
        idx = 0

    while idx < len(events):
        event = events[idx]
        event_start = event["ts"]
        if event_start >= end:
            break
        event_end = event_start + event["dur"]
        overlap = max(0.0, min(end, event_end) - max(start, event_start))
        if overlap > 0.0:
            yield event, overlap
        idx += 1


def merge_clipped_intervals(
    events_with_overlap: Sequence[Tuple[Event, float]],
    start: float,
    end: float,
) -> List[Interval]:
    intervals: List[List[float]] = []
    for event, _ in events_with_overlap:
        clipped_start = max(start, event["ts"])
        clipped_end = min(end, event["ts"] + event["dur"])
        if clipped_start >= clipped_end:
            continue
        if not intervals or clipped_start > intervals[-1][1]:
            intervals.append([clipped_start, clipped_end])
        else:
            intervals[-1][1] = max(intervals[-1][1], clipped_end)
    return [(left, right) for left, right in intervals]


def clipped_coverage_us(
    events_with_overlap: Sequence[Tuple[Event, float]],
    start: float,
    end: float,
) -> float:
    return sum(right - left for left, right in merge_clipped_intervals(events_with_overlap, start, end))


def classify_runtime_api(name: str) -> str:
    lowered = name.lower()
    if "synchronize" in lowered or "streamwait" in lowered or "waitevent" in lowered:
        return "sync"
    if "launch" in lowered:
        return "launch"
    return "other"


def merge_event_intervals(events: Sequence[Event], start: float, end: float) -> List[Interval]:
    intervals: List[List[float]] = []
    for event in events:
        left = max(start, event["ts"])
        right = min(end, event["ts"] + event["dur"])
        if left >= right:
            continue
        if not intervals or left > intervals[-1][1]:
            intervals.append([left, right])
        else:
            intervals[-1][1] = max(intervals[-1][1], right)
    return [(left, right) for left, right in intervals]


def intervals_coverage_us(intervals: Sequence[Interval]) -> float:
    return sum(right - left for left, right in intervals)


def merge_interval_groups(*groups: Sequence[Interval]) -> List[Interval]:
    merged: List[List[float]] = []
    all_intervals = sorted(
        [interval for group in groups for interval in group],
        key=lambda interval: interval[0],
    )
    for left, right in all_intervals:
        if not merged or left > merged[-1][1]:
            merged.append([left, right])
        else:
            merged[-1][1] = max(merged[-1][1], right)
    return [(left, right) for left, right in merged]


def find_leaf_cpu_ops(cpu_ops: Sequence[Event]) -> List[Event]:
    ordered = sorted(cpu_ops, key=lambda event: (event["ts"], -event["dur"]))
    stack: List[List] = []
    leaves: List[Event] = []

    for event in ordered:
        start = event["ts"]
        end = start + event["dur"]
        while stack and stack[-1][1] <= start:
            popped_event, _, has_child = stack.pop()
            if not has_child:
                leaves.append(popped_event)
        if stack:
            stack[-1][2] = True
        stack.append([event, end, False])

    while stack:
        popped_event, _, has_child = stack.pop()
        if not has_child:
            leaves.append(popped_event)

    return leaves


def format_us(value: float) -> str:
    return f"{value:.3f} us"


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def sanitize_markdown_cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def shorten_text(text: str, max_len: int = 120) -> str:
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> List[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return lines


def build_markdown_table_from_dicts(
    rows: Sequence[Dict],
    columns: Sequence[Tuple[str, str]],
    *,
    shorten_columns: Dict[str, int] | None = None,
) -> List[str]:
    shorten_columns = shorten_columns or {}
    headers = [header for _, header in columns]
    table_rows: List[List[str]] = []
    for row in rows:
        table_row = []
        for key, _header in columns:
            value = row.get(key, "")
            text = f"{value:.3f}" if isinstance(value, float) else str(value)
            if key in shorten_columns:
                text = shorten_text(text, shorten_columns[key])
            table_row.append(sanitize_markdown_cell(text))
        table_rows.append(table_row)
    if not table_rows:
        table_rows = [["-"] * len(headers)]
    return markdown_table(headers, table_rows)


def percentage_text(numerator: float, denominator: float) -> str:
    return f"{safe_div(numerator, denominator) * 100.0:.2f}%"


def print_header(title: str) -> None:
    print("=" * 96)
    print(title)
    print("=" * 96)


def is_copy_like_kernel(name: str) -> bool:
    lowered = str(name).lower()
    return any(token in lowered for token in ["direct_copy", "copy", "memcpy", "memset"])


def build_external_id_map(events: Sequence[Event]) -> Dict[int, Event]:
    mapping: Dict[int, Event] = {}
    for event in events:
        external_id = event.get("args", {}).get("External id")
        if external_id is None:
            continue
        current = mapping.get(external_id)
        if current is None:
            mapping[external_id] = event
            continue
        current_key = (current["dur"], -current["ts"])
        next_key = (event["dur"], -event["ts"])
        if next_key < current_key:
            mapping[external_id] = event
    return mapping


def build_runtime_external_id_index(runtime_ops: Sequence[Event]) -> Dict[int, List[Event]]:
    runtime_by_external_id: Dict[int, List[Event]] = defaultdict(list)
    for event in runtime_ops:
        external_id = event.get("args", {}).get("External id")
        if external_id is not None:
            runtime_by_external_id[external_id].append(event)
    for events in runtime_by_external_id.values():
        events.sort(key=lambda item: item["ts"])
    return runtime_by_external_id


def match_runtime_for_kernel(
    kernel: Event,
    runtime_by_correlation: Dict[int, Event],
    runtime_by_external_id: Dict[int, List[Event]],
) -> Event | None:
    correlation = kernel.get("args", {}).get("correlation")
    if correlation is not None and correlation in runtime_by_correlation:
        return runtime_by_correlation[correlation]

    external_id = kernel.get("args", {}).get("External id")
    if external_id is None:
        return None

    candidates = runtime_by_external_id.get(external_id) or []
    if not candidates:
        return None

    kernel_ts = kernel["ts"]
    best = None
    for event in candidates:
        if event["ts"] <= kernel_ts:
            best = event
        else:
            break
    return best or candidates[0]


def classify_cpu_stage(cpu_event: Event | None, prev_end: float) -> str:
    if cpu_event is None:
        return "unknown"

    cpu_start = cpu_event["ts"]
    cpu_end = cpu_start + cpu_event["dur"]
    if cpu_end <= prev_end:
        return "done_before_prev_end"
    if cpu_start < prev_end < cpu_end:
        return "running_across_prev_end"
    return "started_after_prev_end"


def build_dispatch_reason(stat: Dict) -> str:
    total_dispatch = stat["dispatch_exposed_us"]
    if total_dispatch <= 0.0:
        if stat["fully_ahead_count"] > 0:
            return "该 CPU Op 基本都在上一 kernel 结束前完成下发，host 侧不是主瓶颈。"
        return "没有足够的可归因 dispatch 暴露时间。"

    late_submit_ratio = safe_div(stat["late_submit_us"], total_dispatch)
    runtime_submit_ratio = safe_div(stat["runtime_submit_us"], total_dispatch)
    post_launch_ratio = safe_div(stat["post_launch_gap_us"], total_dispatch)
    async_tail_ratio = safe_div(stat["cpu_tail_after_launch_us"], total_dispatch)

    if late_submit_ratio >= 0.5:
        if stat["started_after_prev_end_count"] >= stat["running_across_prev_end_count"]:
            return "很多实例在上一 kernel 结束后 CPU Op 才开始或才进入关键准备阶段，GPU 明显在等 host。"
        return "CPU Op 虽然已开始，但直到上一 kernel 结束后才真正进入 launch，说明 host 内部准备路径偏长。"
    if runtime_submit_ratio >= 0.35:
        return "launch API 经常跨过上一 kernel 结束点，runtime/driver 提交成本暴露较明显。"
    if post_launch_ratio >= 0.35:
        return "下发并不算太晚，但 launch 完成后仍有明显等待，更像是 stream 依赖或设备侧调度问题。"
    if async_tail_ratio >= 0.35 and stat["fully_ahead_count"] > 0:
        return "该 CPU Op 常在 kernel 已经提交后继续执行 host 尾部，具备较强异步性，GPU 不需要等它完全结束。"
    return "该 CPU Op 同时存在提前下发和迟下发，建议结合具体实例继续看依赖链和 launch 时序。"
