# SPDX-License-Identifier: Apache-2.0

import argparse
import ast
import re
import textwrap
from pathlib import Path


HELPER_SENTINEL_START = "# >>> TORCH_PROFILER_HELPERS START >>>"
HELPER_SENTINEL_END = "# <<< TORCH_PROFILER_HELPERS END <<<"
DEFAULT_LOOP_START = "# TORCH_PROFILER_LOOP_START"
DEFAULT_LOOP_END = "# TORCH_PROFILER_LOOP_END"
DEFAULT_STEP_MARKER = "# TORCH_PROFILER_STEP"


HELPER_BLOCK = textwrap.dedent(
    f'''
    {HELPER_SENTINEL_START}
    def _torch_profiler_env_flag(name: str, default: str = "0") -> bool:
        import os
        return os.environ.get(name, default).strip().lower() in {{"1", "true", "yes", "on"}}


    def _torch_profiler_config(label: str) -> dict:
        import os
        return {{
            "enabled": _torch_profiler_env_flag("TORCH_PROFILER_ENABLE", "0"),
            "trace_path": os.environ.get("TORCH_PROFILER_TRACE", ""),
            "profile_json": os.environ.get("TORCH_PROFILER_JSON", ""),
            "top_k": int(os.environ.get("TORCH_PROFILER_TOPK", "40")),
            "sync_each_step": _torch_profiler_env_flag("TORCH_PROFILER_SYNC_EACH_STEP", "0"),
            "record_shapes": _torch_profiler_env_flag("TORCH_PROFILER_RECORD_SHAPES", "1"),
            "profile_memory": _torch_profiler_env_flag("TORCH_PROFILER_PROFILE_MEMORY", "1"),
            "with_stack": _torch_profiler_env_flag("TORCH_PROFILER_WITH_STACK", "0"),
            "label": label,
        }}


    def _torch_profiler_operator_rows(key_averages, use_device_time: bool, top_k: int):
        sort_attr = "self_device_time_total" if use_device_time else "self_cpu_time_total"
        rows = []
        for event in sorted(key_averages, key=lambda item: getattr(item, sort_attr, 0.0), reverse=True)[:top_k]:
            rows.append(
                {{
                    "name": event.key,
                    "count": int(getattr(event, "count", 0)),
                    "self_cpu_time_total_us": float(getattr(event, "self_cpu_time_total", 0.0)),
                    "cpu_time_total_us": float(getattr(event, "cpu_time_total", 0.0)),
                    "cpu_time_avg_us": float(getattr(event, "cpu_time", 0.0)),
                    "self_device_time_total_us": float(getattr(event, "self_device_time_total", 0.0)),
                    "device_time_total_us": float(getattr(event, "device_time_total", 0.0)),
                    "device_time_avg_us": float(getattr(event, "device_time", 0.0)),
                    "self_cpu_memory_bytes": int(getattr(event, "self_cpu_memory_usage", 0)),
                    "cpu_memory_bytes": int(getattr(event, "cpu_memory_usage", 0)),
                    "self_device_memory_bytes": int(getattr(event, "self_device_memory_usage", 0)),
                    "device_memory_bytes": int(getattr(event, "device_memory_usage", 0)),
                }}
            )
        return rows


    class _TorchProfilerRegion:
        def __init__(self, label: str):
            self.label = label
            self.prof = None
            self.config = None

        def __enter__(self):
            import torch

            self.config = _torch_profiler_config(self.label)
            if not self.config["enabled"]:
                return None

            activities = [torch.profiler.ProfilerActivity.CPU]
            if torch.cuda.is_available():
                activities.append(torch.profiler.ProfilerActivity.CUDA)

            self.prof = torch.profiler.profile(
                activities=activities,
                record_shapes=self.config["record_shapes"],
                profile_memory=self.config["profile_memory"],
                with_stack=self.config["with_stack"],
            )
            self.prof.__enter__()
            return self.prof

        def __exit__(self, exc_type, exc, tb):
            import json
            from pathlib import Path
            import torch

            if self.prof is None:
                return False

            self.prof.__exit__(exc_type, exc, tb)
            key_averages = self.prof.key_averages()
            use_device_time = torch.cuda.is_available()
            sort_by = "self_cuda_time_total" if use_device_time else "self_cpu_time_total"

            trace_path = self.config.get("trace_path")
            if trace_path:
                trace_file = Path(trace_path)
                trace_file.parent.mkdir(parents=True, exist_ok=True)
                self.prof.export_chrome_trace(str(trace_file))

            profile_json = self.config.get("profile_json")
            if profile_json:
                profile_file = Path(profile_json)
                profile_file.parent.mkdir(parents=True, exist_ok=True)
                payload = {{
                    "label": self.config["label"],
                    "profiler": {{
                        "top_k": self.config["top_k"],
                        "sort_by": sort_by,
                        "table": key_averages.table(sort_by=sort_by, row_limit=self.config["top_k"]),
                        "operators": _torch_profiler_operator_rows(
                            key_averages=key_averages,
                            use_device_time=use_device_time,
                            top_k=self.config["top_k"],
                        ),
                    }},
                }}
                with profile_file.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
            return False


    def _torch_profiler_region(label: str = "profiled-region"):
        return _TorchProfilerRegion(label)


    def _torch_profiler_step(prof) -> None:
        if prof is None:
            return
        config = _torch_profiler_config("step")
        if config["sync_each_step"]:
            import torch
            if torch.cuda.is_available():
                torch.cuda.synchronize()
        prof.step()
    {HELPER_SENTINEL_END}
    '''
).strip("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Insert reusable torch.profiler template code into a Python file using markers."
    )
    parser.add_argument("file", type=str, help="Python file to patch")
    parser.add_argument(
        "--label",
        type=str,
        default="profiled-region",
        help="Profiler label prefix written into the generated helper context",
    )
    parser.add_argument(
        "--start-marker",
        type=str,
        default=DEFAULT_LOOP_START,
        help="Marker line that starts the block to wrap",
    )
    parser.add_argument(
        "--end-marker",
        type=str,
        default=DEFAULT_LOOP_END,
        help="Marker line that ends the block to wrap",
    )
    parser.add_argument(
        "--step-marker",
        type=str,
        default=DEFAULT_STEP_MARKER,
        help="Marker line inside the loop where prof.step() should be inserted",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input file. If omitted, write to --output.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Output file path when not using --in-place",
    )
    parser.add_argument(
        "--backup-suffix",
        type=str,
        default=".bak",
        help="Backup suffix used with --in-place",
    )
    return parser.parse_args()


def find_helper_insert_index(text: str) -> int:
    lines = text.splitlines()
    index = 0
    if lines and lines[0].startswith("#!"):
        index = 1
    while index < len(lines) and re.match(r"#.*coding[:=]", lines[index]):
        index += 1

    try:
        module = ast.parse(text)
        if module.body:
            first = module.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                return max(index, first.end_lineno or index)
    except SyntaxError:
        pass
    return index


def ensure_helper_block(text: str) -> str:
    if HELPER_SENTINEL_START in text:
        return text

    lines = text.splitlines()
    insert_at = find_helper_insert_index(text)
    helper_lines = HELPER_BLOCK.splitlines()
    new_lines = lines[:insert_at] + [""] + helper_lines + [""] + lines[insert_at:]
    return "\n".join(new_lines).rstrip() + "\n"


def indent_of(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" "))]


def wrap_marked_blocks(
    text: str,
    label_prefix: str,
    start_marker: str,
    end_marker: str,
    step_marker: str,
) -> tuple[str, int]:
    lines = text.splitlines()
    output: list[str] = []
    i = 0
    block_count = 0

    while i < len(lines):
        current = lines[i]
        if current.strip() != start_marker:
            if current.strip() == end_marker:
                raise ValueError(f"Unexpected end marker at line {i + 1}")
            output.append(current)
            i += 1
            continue

        block_count += 1
        start_indent = indent_of(current)
        end_index = None
        for j in range(i + 1, len(lines)):
            if lines[j].strip() == end_marker:
                end_index = j
                break
        if end_index is None:
            raise ValueError(f"Missing end marker for block starting at line {i + 1}")

        block_lines = lines[i + 1 : end_index]
        if not block_lines:
            raise ValueError(f"Empty profiler block at line {i + 1}")

        label = label_prefix if block_count == 1 else f"{label_prefix}-{block_count}"
        output.append(f'{start_indent}with _torch_profiler_region("{label}") as __torch_profiler:')
        found_step = False
        for original_line in block_lines:
            relative_line = (
                original_line[len(start_indent):]
                if original_line.startswith(start_indent)
                else original_line.lstrip(" ")
            )
            if original_line.strip() == step_marker:
                relative_indent = relative_line[: len(relative_line) - len(relative_line.lstrip(" "))]
                output.append(
                    f"{start_indent}    {relative_indent}_torch_profiler_step(__torch_profiler)"
                )
                found_step = True
            else:
                output.append(f"{start_indent}    {relative_line}")
        if not found_step:
            output.append(f"{start_indent}    _torch_profiler_step(__torch_profiler)")

        i = end_index + 1

    return "\n".join(output).rstrip() + "\n", block_count


def main() -> None:
    args = parse_args()
    source_path = Path(args.file)
    text = source_path.read_text(encoding="utf-8")
    text = ensure_helper_block(text)
    patched, block_count = wrap_marked_blocks(
        text=text,
        label_prefix=args.label,
        start_marker=args.start_marker,
        end_marker=args.end_marker,
        step_marker=args.step_marker,
    )

    if block_count == 0:
        raise ValueError("No marked profiler block found. Add start/end markers first.")

    if args.in_place:
        backup_path = source_path.with_name(source_path.name + args.backup_suffix)
        backup_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        source_path.write_text(patched, encoding="utf-8")
        print(f"Patched {source_path} in place. Backup: {backup_path}")
        return

    if not args.output:
        raise ValueError("Use --in-place or specify --output")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(patched, encoding="utf-8")
    print(f"Wrote patched file to {output_path}")


if __name__ == "__main__":
    main()
