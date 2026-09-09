# SPDX-License-Identifier: Apache-2.0

import argparse
import ast
import re
import textwrap
from pathlib import Path


HELPER_SENTINEL_START = "# >>> HIPPROF_HELPERS START >>>"
HELPER_SENTINEL_END = "# <<< HIPPROF_HELPERS END <<<"
DEFAULT_LOOP_START = "# HIPPROF_LOOP_START"
DEFAULT_LOOP_END = "# HIPPROF_LOOP_END"
DEFAULT_STEP_MARKER = "# HIPPROF_STEP"


HELPER_BLOCK = textwrap.dedent(
    f'''
    {HELPER_SENTINEL_START}
    def _hipprof_env_flag(name: str, default: str = "0") -> bool:
        import os
        return os.environ.get(name, default).strip().lower() in {{"1", "true", "yes", "on"}}


    def _hipprof_roctracer_path() -> str:
        import os

        candidates = [
            os.environ.get("HIPPROF_ROCTRACER_LIB", "").strip(),
            "/opt/dtk/roctracer/lib/libroctracer64.so",
            "/opt/dtk/lib/libroctracer64.so",
            "/opt/rocm/lib/libroctracer64.so",
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        raise FileNotFoundError(
            "libroctracer64.so not found. Set HIPPROF_ROCTRACER_LIB or verify the DTK/ROCm install."
        )


    def _hipprof_load_roctracer():
        import ctypes

        tracer = ctypes.cdll.LoadLibrary(_hipprof_roctracer_path())
        tracer.roctracer_start.restype = ctypes.c_int
        tracer.roctracer_stop.restype = ctypes.c_int
        return tracer


    class _HipprofRegion:
        def __init__(self, label: str):
            self.label = label
            self.enabled = False
            self.roctracer = None

        def __enter__(self):
            self.enabled = _hipprof_env_flag("HIPPROF_ENABLE", "0")
            if not self.enabled:
                return None
            self.roctracer = _hipprof_load_roctracer()
            self.roctracer.roctracer_stop()
            rc = self.roctracer.roctracer_start()
            if rc != 0:
                raise RuntimeError(f"roctracer_start failed for {{self.label}} with code {{rc}}")
            return self

        def __exit__(self, exc_type, exc, tb):
            if self.roctracer is None:
                return False
            rc = self.roctracer.roctracer_stop()
            if rc != 0:
                raise RuntimeError(f"roctracer_stop failed for {{self.label}} with code {{rc}}")
            return False


    def _hipprof_region(label: str = "profiled-region"):
        return _HipprofRegion(label)


    def _hipprof_step(region) -> None:
        return None
    {HELPER_SENTINEL_END}
    '''
).strip("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Insert reusable hipprof roctracer template code into a Python file using markers."
    )
    parser.add_argument("file", type=str, help="Python file to patch")
    parser.add_argument(
        "--label",
        type=str,
        default="profiled-region",
        help="Profile label written into the generated helper context",
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
        help="Optional marker line kept for backend symmetry",
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
        output.append(f'{start_indent}with _hipprof_region("{label}") as __hipprof_region:')
        for original_line in block_lines:
            if original_line.strip() == step_marker:
                output.append(f"{start_indent}    _hipprof_step(__hipprof_region)")
                continue
            relative_line = (
                original_line[len(start_indent):]
                if original_line.startswith(start_indent)
                else original_line.lstrip(" ")
            )
            output.append(f"{start_indent}    {relative_line}")

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
