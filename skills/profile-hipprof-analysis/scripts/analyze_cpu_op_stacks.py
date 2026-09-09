# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


Event = Dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect torch.profiler CPU op stack/context from a Chrome trace. "
            "This is useful after special-kernel launch attribution identifies "
            "a hot ATen op such as aten::index_add_, but the exact model callsite "
            "must be recovered from nested CPU trace ranges."
        )
    )
    parser.add_argument("trace", type=str, help="Chrome trace JSON exported by torch.profiler")
    parser.add_argument(
        "--op",
        action="append",
        default=[],
        help="CPU op name to inspect, e.g. aten::index_add_. Can be repeated.",
    )
    parser.add_argument("--top-k", type=int, default=20, help="Rows per summary table")
    parser.add_argument("--max-chain-depth", type=int, default=12, help="Parent chain depth to keep")
    parser.add_argument("--export-json", type=str, default="", help="Optional structured JSON output")
    parser.add_argument("--export-md", type=str, default="", help="Optional markdown output")
    return parser.parse_args()


def load_trace(path: str) -> List[Event]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "traceEvents" in data:
        return list(data["traceEvents"])
    if isinstance(data, list):
        return data
    raise ValueError(f"unsupported trace format: {path}")


def is_complete_event(event: Event) -> bool:
    return event.get("ph") == "X" and "ts" in event and "dur" in event


def event_end(event: Event) -> float:
    return float(event["ts"]) + float(event.get("dur", 0.0))


def dims_key(event: Event) -> Tuple[Tuple[Any, ...], ...]:
    dims = event.get("args", {}).get("Input Dims", [])
    out: List[Tuple[Any, ...]] = []
    for item in dims:
        if isinstance(item, list):
            out.append(tuple(item))
        else:
            out.append((item,))
    return tuple(out)


def format_dims(dims: Tuple[Tuple[Any, ...], ...]) -> str:
    if not dims:
        return ""
    pieces = []
    for item in dims:
        if len(item) == 0:
            pieces.append("[]")
        else:
            pieces.append("[" + ",".join(str(x) for x in item) + "]")
    return ", ".join(pieces)


def build_thread_index(events: Iterable[Event]) -> Dict[Tuple[Any, Any], List[Event]]:
    by_tid: Dict[Tuple[Any, Any], List[Event]] = defaultdict(list)
    for event in events:
        if is_complete_event(event):
            by_tid[(event.get("pid"), event.get("tid"))].append(event)
    for thread_events in by_tid.values():
        thread_events.sort(key=lambda e: (float(e["ts"]), -float(e.get("dur", 0.0))))
    return by_tid


def parent_chain(event: Event, by_tid: Dict[Tuple[Any, Any], List[Event]], max_depth: int) -> List[Event]:
    ts = float(event["ts"])
    end = event_end(event)
    dur = float(event.get("dur", 0.0))
    candidates: List[Event] = []
    for candidate in by_tid.get((event.get("pid"), event.get("tid")), []):
        if candidate is event:
            continue
        c_ts = float(candidate.get("ts", 0.0))
        c_end = event_end(candidate)
        c_dur = float(candidate.get("dur", 0.0))
        if c_ts <= ts + 1e-6 and c_end >= end - 1e-6 and c_dur >= dur:
            if (
                c_ts == ts
                and c_dur == dur
                and str(candidate.get("name", "")) == str(event.get("name", ""))
            ):
                continue
            candidates.append(candidate)
    candidates.sort(key=lambda e: float(e.get("dur", 0.0)))
    return candidates[:max_depth]


def inspect_op(
    op_name: str,
    events: Sequence[Event],
    by_tid: Dict[Tuple[Any, Any], List[Event]],
    top_k: int,
    max_chain_depth: int,
) -> Dict[str, Any]:
    op_events = [event for event in events if is_complete_event(event) and event.get("name") == op_name]
    dims_counter: Counter[Tuple[Tuple[Any, ...], ...]] = Counter()
    chain_counter: Counter[Tuple[str, ...]] = Counter()
    examples: List[Dict[str, Any]] = []
    for event in op_events:
        dims_counter[dims_key(event)] += 1
        chain = tuple(str(parent.get("name", "")) for parent in parent_chain(event, by_tid, max_chain_depth))
        chain_counter[chain] += 1
        if len(examples) < top_k:
            examples.append(
                {
                    "name": op_name,
                    "dur_us": float(event.get("dur", 0.0)),
                    "dims": dims_key(event),
                    "chain": chain,
                    "external_id": event.get("args", {}).get("External id"),
                }
            )
    return {
        "op": op_name,
        "count": len(op_events),
        "dims": [
            {"count": count, "dims": dims}
            for dims, count in dims_counter.most_common(top_k)
        ],
        "chains": [
            {"count": count, "chain": chain}
            for chain, count in chain_counter.most_common(top_k)
        ],
        "examples": examples,
    }


def md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(x).replace("\n", " ") for x in row) + " |")
    return "\n".join(lines)


def to_markdown(result: Dict[str, Any]) -> str:
    lines = ["# CPU op stack attribution", ""]
    lines.append(f"Trace: `{result['trace']}`")
    lines.append("")
    for op_result in result["ops"]:
        lines.append(f"## {op_result['op']}")
        lines.append("")
        lines.append(f"Count: `{op_result['count']}`")
        lines.append("")
        lines.append("### Input dims")
        lines.append("")
        lines.append(
            md_table(
                ["count", "input_dims"],
                [(row["count"], format_dims(tuple(tuple(x) for x in row["dims"]))) for row in op_result["dims"]],
            )
        )
        lines.append("")
        lines.append("### Parent chains")
        lines.append("")
        lines.append(
            md_table(
                ["count", "chain (inner -> outer)"],
                [(row["count"], " <- ".join(row["chain"])) for row in op_result["chains"]],
            )
        )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    events = load_trace(args.trace)
    by_tid = build_thread_index(events)
    ops = args.op or ["aten::index_add_", "aten::index_select"]
    result = {
        "trace": args.trace,
        "ops": [
            inspect_op(op, events, by_tid, args.top_k, args.max_chain_depth)
            for op in ops
        ],
    }
    if args.export_json:
        out = Path(args.export_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md = to_markdown(result)
    if args.export_md:
        out = Path(args.export_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
    if not args.export_json and not args.export_md:
        print(md)


if __name__ == "__main__":
    main()
