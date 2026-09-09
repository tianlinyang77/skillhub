# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, Sequence

from torch_trace_common import build_markdown_table_from_dicts, markdown_table, sanitize_markdown_cell


def build_truncated_text_preview(text: str, max_line_length: int = 140) -> str:
    lines = text.rstrip().splitlines()
    preview_lines = []
    for line in lines:
        if len(line) > max_line_length:
            preview_lines.append(line[: max_line_length - 3] + "...")
        else:
            preview_lines.append(line)
    return "\n".join(preview_lines)


def build_measurement_notes(utilization: Dict, joint_summary: Dict, dispatch_summary: Dict) -> list[str]:
    notes: list[str] = []
    e2e_total_us = float(utilization.get("e2e_total_us", 0.0) or 0.0)
    total_bubble_us = float(joint_summary.get("total_bubble_us", 0.0) or 0.0)
    host_unattributed_us = float(joint_summary.get("total_host_unattributed_us", 0.0) or 0.0)
    top_dispatch = (dispatch_summary.get("top_cpu_ops") or [{}])[0]
    top_cpu_op = top_dispatch.get("cpu_op", "")
    max_dispatch_us = float(top_dispatch.get("max_dispatch_exposed_us", 0.0) or 0.0)
    dispatch_exposed_us = float(top_dispatch.get("dispatch_exposed_us", 0.0) or 0.0)

    if e2e_total_us and max_dispatch_us >= max(100_000.0, e2e_total_us * 0.10):
        notes.append(
            "检测到单个 CPU->kernel 下发暴露时间异常大"
            f"（`{top_cpu_op or 'unknown'}` max_dispatch_exposed=`{max_dispatch_us:.3f} us`）。"
            "这通常表示 profiler 窗口边界、异步尾部或一次性 host 等待进入了采集窗口；"
            "此时不要只看 e2e/utilization，应优先对比 GPU busy、Top kernel 和稳态 attribution。"
        )

    if total_bubble_us and host_unattributed_us / total_bubble_us >= 0.5:
        notes.append(
            "Host unattributed bubble 占比较高"
            f"（`{host_unattributed_us:.3f} / {total_bubble_us:.3f} us`）。"
            "该部分不能可靠归因到具体模型算子，建议结合 record_function 标记或 profiler-on/off 对比复核。"
        )

    if total_bubble_us and dispatch_exposed_us / total_bubble_us >= 0.8 and max_dispatch_us >= dispatch_exposed_us * 0.5:
        notes.append(
            "Dispatch 暴露主要集中在少数极端实例，而不是均匀分布在稳态迭代中；"
            "优化建议应先确认这些实例是否属于真实热路径。"
        )

    return notes


def build_report_markdown(
    trace_path: str,
    copied_trace_name: str,
    profile_payload: Dict,
    utilization: Dict,
    top_kernels: Sequence[Dict],
    bubble_summary: Dict,
    dispatch_summary: Dict,
    joint_summary: Dict,
    include_analysis_json: bool = False,
) -> str:
    meta_rows = []
    if profile_payload:
        meta_keys = [
            ("model", "模型"),
            ("device", "设备"),
            ("device_name", "设备名称"),
            ("precision", "精度"),
            ("batch_size", "Batch Size"),
            ("channels_last", "channels_last"),
            ("compile", "torch.compile"),
            ("warmup", "warmup"),
            ("iters", "iters"),
        ]
        for key, label in meta_keys:
            if key in profile_payload:
                meta_rows.append((label, f"`{profile_payload[key]}`"))
        if "input_shape" in profile_payload:
            meta_rows.append(("输入形状", f"`{profile_payload['input_shape']}`"))

    trace_ref = copied_trace_name or trace_path
    meta_table = markdown_table(["配置项", "值"], meta_rows) if meta_rows else []

    utilization_rows = [
        ("GPU Busy Time", f"`{utilization['gpu_busy_us']:.3f} us`", "统计窗口内 GPU 实际执行 kernel 的累计时间"),
        ("End-to-End Total", f"`{utilization['e2e_total_us']:.3f} us`", "本次 profiler 采集窗口的总时长"),
        (
            "GPU 利用率比",
            f"`{utilization['utilization_ratio']:.4f}` (`{utilization['utilization_ratio'] * 100.0:.2f}%`)",
            "按 `GPU busy time / total time` 计算",
        ),
        (
            "Copy GPU Busy 占比",
            f"`{utilization['copy_share_of_gpu_busy']:.4f}` (`{utilization['copy_share_of_gpu_busy'] * 100.0:.2f}%`)",
            "按名称匹配 `direct_copy/copy/memcpy/memset` 的 GPU kernel busy time / GPU busy time 计算",
        ),
        ("Kernel Span", f"`{utilization['kernel_span_us']:.3f} us`", "首个 kernel 到最后一个 kernel 的时间跨度"),
    ]
    utilization_table = markdown_table(["指标", "数值", "说明"], utilization_rows)

    kernel_lines = [
        "| Rank | Name | Dev total(us) | Avg(us) | Max(us) | Calls | Share(%) |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for idx, row in enumerate(top_kernels, start=1):
        kernel_lines.append(
            "| "
            f"{idx} | {sanitize_markdown_cell(row['name'])} | "
            f"{row['device_time_total_us']:.3f} | "
            f"{row['avg_device_time_us']:.3f} | "
            f"{row['max_device_time_us']:.3f} | "
            f"{row['count']} | "
            f"{row['device_share_pct']:.2f} |"
        )
    if not top_kernels:
        kernel_lines.append("| - | 无可用 kernel 数据 | - | - | - | - | - |")

    host_overview_rows = [
        (
            "Dispatch Exposed",
            f"`{joint_summary.get('dispatch_exposed_us', 0.0):.3f} us`",
            f"`{joint_summary.get('dispatch_share_of_bubble_pct', 0.0):.2f}%` of bubble",
            "与 kernel 下发不及时直接相关",
        ),
        (
            "Late Submit",
            f"`{joint_summary.get('late_submit_us', 0.0):.3f} us`",
            f"`{joint_summary.get('late_submit_share_of_dispatch_pct', 0.0):.2f}%` of dispatch",
            "launch 开始前的 host 等待",
        ),
        (
            "Runtime Submit",
            f"`{joint_summary.get('runtime_submit_us', 0.0):.3f} us`",
            f"`{joint_summary.get('runtime_submit_share_of_dispatch_pct', 0.0):.2f}%` of dispatch",
            "runtime 提交开销",
        ),
    ]
    host_overview_table = markdown_table(["指标", "数值", "占比/比例", "说明"], host_overview_rows)

    post_launch_rows = [
        (
            "Post-Launch Gap",
            f"`{joint_summary.get('post_launch_gap_us', 0.0):.3f} us`",
            f"`{joint_summary.get('post_launch_share_of_bubble_pct', 0.0):.2f}%` of bubble",
            "kernel 已提交但 GPU 未立即执行",
        ),
    ]
    post_launch_table = markdown_table(["指标", "数值", "占比/比例", "说明"], post_launch_rows)

    artifact_rows = []
    if include_analysis_json:
        artifact_rows.append(("`analysis.json`", "结构化分析结果；如需程序化处理或二次汇总可使用"))
    artifact_rows.append((f"`{trace_ref}`", "trace 原始文件；用于 Perfetto/Chrome trace 继续查看时序"))
    artifact_table = markdown_table(["文件", "说明"], artifact_rows)
    measurement_notes = build_measurement_notes(utilization, joint_summary, dispatch_summary)
    measurement_note_lines: list[str] = []
    if measurement_notes:
        measurement_note_lines = ["### 3.1 测量边界提示"]
        measurement_note_lines.extend(f"- {note}" for note in measurement_notes)
        measurement_note_lines.append("")

    top_bubbles_table = build_markdown_table_from_dicts(
        bubble_summary.get("top_bubbles", []),
        [
            ("rank", "rank"),
            ("prev_kernel", "prev_kernel"),
            ("next_kernel", "next_kernel"),
            ("bubble_total_us", "bubble_total_us"),
            ("bubble_share_pct", "bubble_share_pct"),
            ("pre_launch_us", "pre_launch_us"),
            ("launch_us", "launch_us"),
            ("post_launch_us", "post_launch_us"),
            ("sync_wait_us", "sync_wait_us"),
            ("cpu_prep_us", "cpu_prep_us"),
            ("host_unattributed_us", "host_unattributed_us"),
            ("top_cpu_op", "top_cpu_op"),
            ("top_runtime", "top_runtime"),
            ("reason", "reason"),
        ],
        shorten_columns={
            "prev_kernel": 80,
            "next_kernel": 80,
            "top_cpu_op": 60,
            "top_runtime": 60,
            "reason": 100,
        },
    )

    dispatch_examples_table = build_markdown_table_from_dicts(
        dispatch_summary.get("top_examples", []),
        [
            ("rank", "rank"),
            ("cpu_op", "cpu_op"),
            ("status", "status"),
            ("prev_kernel", "prev_kernel"),
            ("kernel", "kernel"),
            ("runtime", "runtime"),
            ("dispatch_exposed_us", "dispatch_exposed_us"),
            ("late_submit_us", "late_submit_us"),
            ("runtime_submit_us", "runtime_submit_us"),
            ("post_launch_gap_us", "post_launch_gap_us"),
            ("cpu_tail_after_launch_us", "cpu_tail_after_launch_us"),
            ("cpu_stage", "cpu_stage"),
        ],
        shorten_columns={
            "cpu_op": 60,
            "prev_kernel": 80,
            "kernel": 80,
            "runtime": 40,
        },
    )

    top_dispatch_table = build_markdown_table_from_dicts(
        dispatch_summary.get("top_cpu_ops", []),
        [
            ("rank", "rank"),
            ("cpu_op", "cpu_op"),
            ("dispatch_exposed_us", "dispatch_exposed_us"),
            ("dispatch_share_pct", "dispatch_share_pct"),
            ("late_submit_us", "late_submit_us"),
            ("runtime_submit_us", "runtime_submit_us"),
            ("post_launch_gap_us", "post_launch_gap_us"),
            ("count", "count"),
            ("fully_ahead_count", "fully_ahead_count"),
            ("partial_ahead_count", "partial_ahead_count"),
            ("late_count", "late_count"),
            ("reason", "reason"),
        ],
        shorten_columns={"cpu_op": 60, "reason": 100},
    )

    post_launch_examples_table = build_markdown_table_from_dicts(
        bubble_summary.get("top_post_launch_examples", []),
        [
            ("rank", "rank"),
            ("prev_kernel", "prev_kernel"),
            ("next_kernel", "next_kernel"),
            ("bubble_total_us", "bubble_total_us"),
            ("pre_launch_us", "pre_launch_us"),
            ("launch_us", "launch_us"),
            ("post_launch_us", "post_launch_us"),
            ("sync_wait_us", "sync_wait_us"),
            ("cpu_prep_us", "cpu_prep_us"),
            ("host_unattributed_us", "host_unattributed_us"),
            ("runtime", "runtime"),
            ("top_cpu_op", "top_cpu_op"),
        ],
        shorten_columns={
            "prev_kernel": 80,
            "next_kernel": 80,
            "runtime": 40,
            "top_cpu_op": 60,
        },
    )
    profiler_section_lines: list[str] = []
    profiler_info = profile_payload.get("profiler", {}) if profile_payload else {}
    profiler_table = profiler_info.get("table", "")
    if profiler_info:
        profiler_meta_rows = [
            ("sort_by", f"`{profiler_info.get('sort_by', 'N/A')}`"),
            ("top_k", f"`{profiler_info.get('top_k', 'N/A')}`"),
        ]
        profiler_section_lines.extend(
            [
                "## 6. torch.prof 输出",
                "以下内容直接来自 profiler 运行时生成的 `key_averages().table(...)` 文本输出，便于与终端观察结果对照。",
                "",
                *markdown_table(["字段", "值"], profiler_meta_rows),
                "",
            ]
        )
        if profiler_table:
            preview_text = build_truncated_text_preview(profiler_table)
            profiler_section_lines.extend(
                [
                    "```text",
                    preview_text,
                    "```",
                ]
            )
        else:
            profiler_section_lines.append("未在 `profile_json` 中找到 `profiler.table` 字段。")
    else:
        profiler_section_lines.extend(
            [
                "## 6. torch.prof 输出",
                "本次未提供 `--profile-json`，因此无法在报告中嵌入原始 torch.prof 文本表格。",
            ]
        )

    lines = [
        "# Torch Profiler 性能分析报告",
        "",
        "## 1. 报告说明",
        "本报告基于 torch.profiler 导出的 trace 与结构化 profile 数据生成，统计边界以本次 profiler 采集窗口为准，",
        "重点关注稳态阶段的 GPU 利用率、纯 GPU kernel 热点以及关键空泡 / 下发行为。",
        "",
        "## 2. 测试配置与交付物",
    ]
    if meta_table:
        lines.extend(["### 2.1 测试配置", *meta_table, "", "### 2.2 交付物", *artifact_table, ""])
    else:
        lines.extend([*artifact_table, ""])
    lines.extend(
        [
            "## 3. GPU 利用率概览",
            *utilization_table,
            "",
            *measurement_note_lines,
            "## 4. 主要 GPU Kernel 热点（Top-K）",
            "说明：本节按 trace 中的 **纯 GPU kernel** 聚合，不混入 CPU op。",
            "",
            *kernel_lines,
            "",
            "## 5. Host 迟下发与 Post-launch",
            "### 5.1 主要空泡来源",
            *top_bubbles_table,
            "",
            "### 5.2 Host 迟下发情况",
            *host_overview_table,
            "",
            "#### 5.2.1 Host 迟下发来源汇总",
            *top_dispatch_table,
            "",
            "#### 5.2.2 Host 迟下发 Top 实例",
            *dispatch_examples_table,
            "",
            "### 5.3 Post-launch 情况",
            *post_launch_table,
            "",
            "#### 5.3.1 Post-launch Top 实例",
            *post_launch_examples_table,
            "",
            *profiler_section_lines,
        ]
    )
    return "\n".join(lines)


def export_analysis_outputs(
    export_dir: str,
    trace_path: str,
    profile_json_path: str,
    profile_payload: Dict,
    utilization: Dict,
    top_kernels: Sequence[Dict],
    bubble_summary: Dict,
    dispatch_summary: Dict,
    joint_summary: Dict,
    export_analysis_json: bool = False,
) -> Dict[str, str]:
    if not export_dir:
        return {}

    out_dir = Path(export_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    copied_trace_name = ""
    if trace_path:
        copied_trace_name = "profiler_trace.json"
        dst_trace_path = out_dir / copied_trace_name
        if Path(trace_path).resolve() != dst_trace_path.resolve():
            shutil.copy2(trace_path, dst_trace_path)

    analysis_payload = {
        "metadata": {
            "trace_path": copied_trace_name or trace_path,
            "profile_json": profile_json_path,
        },
        "run": {
            key: profile_payload.get(key)
            for key in [
                "model",
                "device",
                "device_name",
                "precision",
                "batch_size",
                "input_shape",
                "channels_last",
                "compile",
                "warmup",
                "iters",
            ]
            if key in profile_payload
        },
        "utilization": utilization,
        "top_kernels": list(top_kernels),
        "top_operators": list(top_kernels),
        "bubble_analysis": bubble_summary,
        "dispatch_analysis": dispatch_summary,
        "joint_summary": joint_summary,
        "measurement_notes": build_measurement_notes(utilization, joint_summary, dispatch_summary),
    }

    analysis_json_path = out_dir / "analysis.json"
    if export_analysis_json:
        analysis_json_path.write_text(json.dumps(analysis_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    elif analysis_json_path.exists():
        analysis_json_path.unlink()

    for obsolete_name in (
        "top_bubbles.csv",
        "top_dispatch.csv",
        "dispatch_examples.csv",
        "post_launch_examples.csv",
    ):
        obsolete_path = out_dir / obsolete_name
        if obsolete_path.exists():
            obsolete_path.unlink()

    report_md_path = out_dir / "report.md"
    report_md_path.write_text(
        build_report_markdown(
            trace_path=trace_path,
            copied_trace_name=copied_trace_name,
            profile_payload=profile_payload,
            utilization=utilization,
            top_kernels=top_kernels,
            bubble_summary=bubble_summary,
            dispatch_summary=dispatch_summary,
            joint_summary=joint_summary,
            include_analysis_json=export_analysis_json,
        ),
        encoding="utf-8",
    )

    exported = {
        "report_md": str(report_md_path),
        "profiler_trace": str(out_dir / copied_trace_name) if copied_trace_name else "",
    }
    if export_analysis_json:
        exported["analysis_json"] = str(analysis_json_path)
    return exported
