# SPDX-License-Identifier: Apache-2.0

import argparse

from torch_trace_common import filter_events, load_events, load_profile_payload, print_header
from torch_trace_gpu import summarize_gpu_utilization, summarize_top_kernels
from torch_trace_host import (
    summarize_dispatch_ahead,
    summarize_gpu_gaps,
    summarize_joint_attribution,
)
from torch_trace_report import export_analysis_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="分析 torch.profiler 导出的 trace")
    parser.add_argument("trace", type=str, help="trace JSON 路径")
    parser.add_argument(
        "--profile-json",
        type=str,
        default="",
        help="benchmark_resnet.py 导出的 profile JSON，用于打印 torch.prof 风格 Top 算子",
    )
    parser.add_argument("--op-top-k", type=int, default=20, help="Top kernel 数量，默认 20")
    parser.add_argument("--bubble-top-k", type=int, default=5, help="Top 空泡来源数量，默认 5")
    parser.add_argument(
        "--dispatch-top-k",
        type=int,
        default=5,
        help="CPU->Kernel 提前/迟下发分析的 Top 数量，默认 5",
    )
    parser.add_argument(
        "--dispatch-example-top-k",
        type=int,
        default=10,
        help="report.md / analysis.json 中展示的 Host 迟下发实例数量，默认 10",
    )
    parser.add_argument(
        "--post-launch-example-top-k",
        type=int,
        default=10,
        help="report.md / analysis.json 中展示的 Post-launch 实例数量，默认 10",
    )
    parser.add_argument(
        "--export-dir",
        type=str,
        default="",
        help="导出 report.md / profiler_trace.json（以及可选 analysis.json）的目录",
    )
    parser.add_argument(
        "--export-analysis-json",
        action="store_true",
        help="额外导出 analysis.json；默认关闭，仅保留人类可读 report.md 与 profiler_trace.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    events = load_events(args.trace)
    profile_payload = load_profile_payload(args.profile_json)
    kernels = filter_events(events, "kernel")
    cpu_ops = filter_events(events, "cpu_op")
    runtime_ops = filter_events(events, "cuda_runtime")

    utilization = summarize_gpu_utilization(cpu_ops, runtime_ops, kernels)
    top_kernels = summarize_top_kernels(kernels, args.op_top_k)
    bubble_summary = summarize_gpu_gaps(
        kernels=kernels,
        runtime_ops=runtime_ops,
        cpu_ops=cpu_ops,
        top_k=args.bubble_top_k,
        post_launch_example_top_k=args.post_launch_example_top_k,
    )
    dispatch_summary = summarize_dispatch_ahead(
        kernels=kernels,
        runtime_ops=runtime_ops,
        cpu_ops=cpu_ops,
        top_k=args.dispatch_top_k,
        example_top_k=args.dispatch_example_top_k,
    )
    joint_summary = summarize_joint_attribution(bubble_summary, dispatch_summary)
    exported = export_analysis_outputs(
        export_dir=args.export_dir,
        trace_path=args.trace,
        profile_json_path=args.profile_json,
        profile_payload=profile_payload,
        utilization=utilization,
        top_kernels=top_kernels,
        bubble_summary=bubble_summary,
        dispatch_summary=dispatch_summary,
        joint_summary=joint_summary,
        export_analysis_json=args.export_analysis_json,
    )
    if exported:
        print_header("6. 导出文件")
        for key, path in exported.items():
            if path:
                print(f"{key:16}: {path}")


if __name__ == "__main__":
    main()
