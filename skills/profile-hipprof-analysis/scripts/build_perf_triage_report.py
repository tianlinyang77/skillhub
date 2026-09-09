# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import os
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Sequence

from torch_trace_common import markdown_table, sanitize_markdown_cell, shorten_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge hipprof and optional framework attribution into one concise performance triage report."
    )
    parser.add_argument(
        "--hipprof-analysis-json",
        type=str,
        required=True,
        help="analysis.json exported by analyze_hipprof_csv.py",
    )
    parser.add_argument(
        "--framework-analysis-json",
        type=str,
        default="",
        help="Optional analysis.json exported by analyze_torch_trace.py or analyze_xprof_xplane.py",
    )
    parser.add_argument(
        "--export-dir",
        type=str,
        default="",
        help="Directory to write report.md and optional analysis.json",
    )
    parser.add_argument(
        "--export-analysis-json",
        action="store_true",
        help="Also export a normalized triage analysis.json payload",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top rows to keep in the human-facing report",
    )
    return parser.parse_args()


def load_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pct(value: float) -> str:
    return f"{value * 100.0:.2f}%"


def ns_to_us(value: int | float) -> float:
    return float(value) / 1_000.0


def top_or_empty(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(rows[0]) if rows else {}


def run_text(cmd: list[str]) -> str:
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or result.stderr or "").strip()


def detect_observed_arch() -> str:
    rocminfo_text = run_text(["rocminfo"])
    if not rocminfo_text:
        return "unknown"
    for token in rocminfo_text.replace("\n", " ").split():
        if token.startswith("gfx"):
            return token.strip()
    return "unknown"


def detect_dtk_or_rocm_version() -> str:
    dtk_path = Path("/opt/dtk")
    if dtk_path.exists():
        try:
            return str(dtk_path.resolve())
        except OSError:
            return str(dtk_path)
    for cmd in (["hipcc", "--version"], ["rocminfo"]):
        text = run_text(cmd)
        if text:
            first_line = text.splitlines()[0].strip()
            if first_line and "Invalid arg" not in first_line:
                return first_line
    return "unknown"


def detect_framework_name(framework_backend: str, framework_payload: Dict[str, Any]) -> str:
    if framework_backend == "torch_profiler":
        return "pytorch"
    if framework_backend == "xprof_summary":
        top_names = [str(row.get("name", "")) for row in framework_payload.get("top_framework_regions", []) or []]
        joined = " ".join(top_names).lower()
        if any(token in joined for token in ("eager", "tf.", "addv2", "randomstandardnormal")):
            return "tensorflow"
        if any(token in joined for token in ("xla", "pjit", "jax")):
            return "jax"
        return "xprof-backed-framework"
    return "unknown"


def classify_wait_copy_type(name: str) -> str:
    lowered = name.lower()
    if "copy" in lowered or "memcpy" in lowered:
        return "copy"
    if "sync" in lowered or "wait" in lowered or "queue_create" in lowered:
        return "wait"
    if "malloc" in lowered or "allocate" in lowered or "free" in lowered:
        return "allocation"
    return "overhead"


def classify_wait_copy_priority(name: str, share_pct: float = 0.0, duration_us: float = 0.0) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ("sync", "wait", "copy", "memcpy")) and (share_pct >= 5.0 or duration_us >= 50.0):
        return "high"
    if share_pct >= 1.0 or duration_us >= 10.0:
        return "medium"
    return "low"


def build_copy_recommendation(name: str) -> str:
    lowered = name.lower()
    if "eagercopytodevice" in lowered or "memcpyhtod" in lowered:
        return "检查 host->device 数据搬运是否能提前驻留、批量化或并入更大的 steady-state 区域。"
    if "memcpydtoh" in lowered:
        return "检查 device->host 读回是否为调试、同步取值或不必要的标量回传。"
    if "streamsynchronize" in lowered or "devicesynchronize" in lowered or "wait" in lowered:
        return "检查是否存在显式同步、隐式标量同步或 stream/event 依赖导致 GPU 等 host。"
    if "malloc" in lowered or "allocate" in lowered or "free" in lowered:
        return "检查是否能复用缓冲区，避免 steady-state 中反复申请/释放。"
    return "检查该 runtime/host 信号是否属于可消除的非必要开销。"


def detect_framework_backend(payload: Dict[str, Any]) -> str:
    if not payload:
        return "none"
    if "utilization" in payload and "joint_summary" in payload:
        return "torch_profiler"
    if "phase_summary" in payload and "top_framework_regions" in payload:
        return "xprof_summary"
    return "unknown"


def classify_from_hipprof(hip: Dict[str, Any]) -> tuple[str, str]:
    top_kernel_pct = float((hip.get("top_kernels") or [{}])[0].get("percentage", 0.0) or 0.0) / 100.0
    top_hip = {row.get("name"): row for row in hip.get("top_hip_runtime", []) or []}
    top_hsa = {row.get("name"): row for row in hip.get("top_hsa_runtime", []) or []}
    sync_pct = float(top_hip.get("hipDeviceSynchronize", {}).get("percentage", 0.0) or 0.0) / 100.0
    launch_pct = float(top_hip.get("hipLaunchKernel", {}).get("percentage", 0.0) or 0.0) / 100.0
    wait_pct = float(top_hsa.get("hsa_signal_wait_scacquire", {}).get("percentage", 0.0) or 0.0) / 100.0
    copy_pct = 0.0
    for row in hip.get("top_hip_runtime", []) or []:
        if any(token in str(row.get("name", "")).lower() for token in ("memcpy", "copy")):
            copy_pct += float(row.get("percentage", 0.0) or 0.0) / 100.0
    if sync_pct >= 0.2 or wait_pct >= 0.2 or copy_pct >= 0.2:
        return "bubble-scheduling", "HIP/HSA runtime already shows visible sync/wait/copy pressure."
    if top_kernel_pct >= 0.6 and launch_pct < 0.15:
        return "kernel-operator", "Kernel time is concentrated and runtime overhead is not dominant."
    return "mixed", "Kernel and runtime signals are both visible at the hardware layer."


def classify_from_torch(hip: Dict[str, Any], torch_payload: Dict[str, Any]) -> tuple[str, str]:
    util = torch_payload.get("utilization", {}) or {}
    joint = torch_payload.get("joint_summary", {}) or {}
    top_kernel_pct = float((hip.get("top_kernels") or [{}])[0].get("percentage", 0.0) or 0.0) / 100.0
    util_ratio = float(util.get("utilization_ratio", 0.0) or 0.0)
    bubble_ratio = float(joint.get("total_bubble_us", 0.0) or 0.0) / max(float(util.get("e2e_total_us", 0.0) or 0.0), 1.0)
    dispatch_share = float(joint.get("dispatch_share_of_bubble_pct", 0.0) or 0.0) / 100.0
    copy_ratio = float(util.get("copy_share_of_gpu_busy", 0.0) or 0.0)
    if util_ratio <= 0.3 or bubble_ratio >= 0.4 or dispatch_share >= 0.5 or copy_ratio >= 0.35:
        return "bubble-scheduling", str(joint.get("conclusion") or "GPU is spending too much time waiting on host/copy/scheduling.")
    if top_kernel_pct >= 0.6 and util_ratio >= 0.5:
        return "kernel-operator", "GPU time is concentrated in a small set of kernels and bubble pressure is limited."
    return "mixed", str(joint.get("conclusion") or "Both kernel hotspots and non-kernel overhead are visible.")


def classify_from_xprof(xprof_payload: Dict[str, Any]) -> tuple[str, str]:
    next_step = xprof_payload.get("next_step", {}) or {}
    classification = str(next_step.get("classification") or "mixed")
    reason = str(next_step.get("reason") or "XProf summary shows both framework and device-side signals.")
    return classification, reason


def decide_classification(hip: Dict[str, Any], framework_backend: str, framework_payload: Dict[str, Any]) -> tuple[str, str]:
    if framework_backend == "torch_profiler":
        return classify_from_torch(hip, framework_payload)
    if framework_backend == "xprof_summary":
        return classify_from_xprof(framework_payload)
    return classify_from_hipprof(hip)


def choose_route(classification: str, framework_backend: str) -> Dict[str, str]:
    if classification == "kernel-operator":
        return {
            "recommended_route": "kernel_optimization",
            "recommended_route_reason": "当前主要矛盾是热点 kernel，本轮 profiling 结果已经足够支持进入后续 kernel 深化优化。",
            "recommended_route_action": "进入 kernel 深化优化流，继续做 kernel 归因、baseline 生成和 DCU kernel 优化。",
        }
    if classification == "bubble-scheduling":
        return {
            "recommended_route": "bubble_optimization",
            "recommended_route_reason": "当前主要矛盾是 GPU 空泡、等待、同步或拷贝，先做上层消空泡比继续深打单个 kernel 更合算。",
            "recommended_route_action": "优先做消空泡：查同步、拷贝、host 迟下发、图 break、小算子密集下发和不必要的数据搬运。",
        }
    if framework_backend in {"torch_profiler", "xprof_summary"}:
        return {
            "recommended_route": "framework_operator_rewrite",
            "recommended_route_reason": "当前是 mixed，但已经具备框架侧归因信息，先做 module/op 级改写、融合或调度清理，比直接下潜 kernel 更稳妥。",
            "recommended_route_action": "先做 framework/operator 级改写或融合实验，再决定是否进入 kernel 优化。",
        }
    return {
        "recommended_route": "need_more_attribution",
        "recommended_route_reason": "当前还是 mixed，且缺少足够的框架归因，继续动作前应先补 attribution 或对比实验。",
        "recommended_route_action": "先补框架归因或再做一轮对比实验，再决定走 kernel 还是消空泡路径。",
    }


def build_kernel_rows(
    hip: Dict[str, Any],
    framework_backend: str,
    framework_payload: Dict[str, Any],
    top_k: int,
) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    framework_kernel_names = set()
    if framework_backend == "torch_profiler":
        framework_kernel_names = {row.get("name", "") for row in framework_payload.get("top_kernels", []) or []}
    elif framework_backend == "xprof_summary":
        framework_kernel_names = set(
            framework_payload.get("hipprof_alignment", {}).get("overlap_names", []) or []
        )
    for row in (hip.get("top_kernels") or [])[: max(top_k, 0)]:
        rows.append(
            {
                "name": row.get("name", ""),
                "share": f"{float(row.get('percentage', 0.0) or 0.0):.2f}%",
                "calls": str(row.get("calls", 0)),
                "avg_us": f"{ns_to_us(row.get('average_ns', 0.0)):.3f}",
                "framework_seen": "yes" if row.get("name", "") in framework_kernel_names else "no",
            }
        )
    return rows


def build_profile_metadata(
    hip: Dict[str, Any],
    framework_backend: str,
    framework_payload: Dict[str, Any],
    hipprof_path: str,
    framework_path: str,
) -> Dict[str, Any]:
    observed_arch = detect_observed_arch()
    framework_name = detect_framework_name(framework_backend, framework_payload)
    source_artifacts = [path for path in [hipprof_path, framework_path] if path]
    visible_devices = {
        key: os.environ.get(key, "")
        for key in ["HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES"]
        if os.environ.get(key) is not None
    }
    profiling_degraded = False
    degraded_reasons: list[str] = []
    if framework_backend == "unknown":
        profiling_degraded = True
        degraded_reasons.append("framework attribution backend is unknown")
    if observed_arch == "unknown":
        degraded_reasons.append("observed gfx target could not be detected from current environment")
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "framework": framework_name,
        "hardware_profiler_backend": "hipprof",
        "framework_attribution_backend": framework_backend,
        "observed_arch": observed_arch,
        "arch_match": "exact" if observed_arch != "unknown" else "unknown",
        "hardware_relevance_reason": (
            "Generated on a live DCU environment with visible gfx target."
            if observed_arch != "unknown"
            else "Could not confirm the exact gfx target from the current environment."
        ),
        "dtk_or_rocm_version": detect_dtk_or_rocm_version(),
        "visible_devices": visible_devices,
        "run_entrypoint": "unknown",
        "source_artifacts": source_artifacts,
        "profiling_degraded": profiling_degraded,
        "profiling_degraded_reason": "; ".join(degraded_reasons),
        "hipprof_input_prefix": str(hip.get("input_prefix", "")),
    }


def build_bubble_summary(framework_backend: str, framework_payload: Dict[str, Any]) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    if framework_backend == "torch_profiler":
        util = framework_payload.get("utilization", {}) or {}
        joint = framework_payload.get("joint_summary", {}) or {}
        e2e = float(util.get("e2e_total_us", 0.0) or 0.0)
        rows.extend(
            [
                ("GPU busy ratio", pct(float(util.get("utilization_ratio", 0.0) or 0.0)), "稳态窗口内 GPU 实际工作占比"),
                (
                    "Bubble ratio",
                    pct(float(joint.get("total_bubble_us", 0.0) or 0.0) / max(e2e, 1.0)),
                    "kernel 间空泡占整个窗口的比例",
                ),
                (
                    "Dispatch exposed",
                    f"{float(joint.get('dispatch_share_of_bubble_pct', 0.0) or 0.0):.2f}%",
                    "空泡里有多少直接暴露为 host 迟下发",
                ),
                (
                    "Post-launch gap",
                    f"{float(joint.get('post_launch_share_of_bubble_pct', 0.0) or 0.0):.2f}%",
                    "下发后 GPU 仍未立即工作的占比",
                ),
                (
                    "Copy busy / GPU busy",
                    pct(float(util.get("copy_share_of_gpu_busy", 0.0) or 0.0)),
                    "GPU 时间里拷贝类 kernel 的占比",
                ),
            ]
        )
        return rows
    if framework_backend == "xprof_summary":
        phase = framework_payload.get("phase_summary", {}) or {}
        rows.extend(
            [
                ("GPU busy ratio", pct(float(phase.get("gpu_busy_ratio", 0.0) or 0.0)), "measured step 窗口内 GPU 实际工作占比"),
                ("GPU gap ratio", pct(float(phase.get("gpu_gap_ratio", 0.0) or 0.0)), "measured step 窗口内 GPU 无工作 gap 占比"),
                ("Measured steps", str(phase.get("step_count", 0)), "这次 XProf 识别到的 step 数"),
                (
                    "Avg step duration",
                    f"{float(phase.get('avg_step_duration_us', 0.0) or 0.0):.3f} us",
                    "平均 step 时长",
                ),
            ]
        )
        return rows
    rows.append(("Bubble evidence", "limited", "当前只有硬件层摘要，空泡因果拆解信息有限。"))
    return rows


def collect_wait_copy_rows(hip: Dict[str, Any], framework_backend: str, framework_payload: Dict[str, Any], top_k: int) -> list[Dict[str, str]]:
    rows: list[Dict[str, Any]] = []
    if framework_backend == "xprof_summary":
        for row in framework_payload.get("top_wait_or_copy_regions", []) or []:
            rows.append(
                {
                    "priority": 0,
                    "score": float(row.get("total_duration_us", 0.0) or 0.0),
                    "source": "xprof",
                    "name": str(row.get("name", "")),
                    "share": "",
                    "detail": f"calls={row.get('calls', 0)} total_us={float(row.get('total_duration_us', 0.0) or 0.0):.3f}",
                }
            )
    for row in hip.get("top_hip_runtime", []) or []:
        name = str(row.get("name", ""))
        lname = name.lower()
        if any(token in lname for token in ("sync", "wait", "memcpy", "copy", "malloc", "free")):
            rows.append(
                {
                    "priority": 1,
                    "score": float(row.get("percentage", 0.0) or 0.0),
                    "source": "hip_runtime",
                    "name": name,
                    "share": f"{float(row.get('percentage', 0.0) or 0.0):.2f}%",
                    "detail": f"calls={row.get('calls', 0)} avg_us={ns_to_us(row.get('average_ns', 0.0)):.3f}",
                }
            )
    for row in hip.get("top_hsa_runtime", []) or []:
        name = str(row.get("name", ""))
        lname = name.lower()
        if any(token in lname for token in ("wait", "allocate", "copy", "queue_create")):
            rows.append(
                {
                    "priority": 2,
                    "score": float(row.get("percentage", 0.0) or 0.0),
                    "source": "hsa_runtime",
                    "name": name,
                    "share": f"{float(row.get('percentage', 0.0) or 0.0):.2f}%",
                    "detail": f"calls={row.get('calls', 0)} avg_us={ns_to_us(row.get('average_ns', 0.0)):.3f}",
                }
            )
    rows.sort(key=lambda item: (item["priority"], -item["score"], item["name"]))
    return [
        {
            "source": row["source"],
            "name": row["name"],
            "share": row["share"],
            "detail": row["detail"],
        }
        for row in rows[: max(top_k, 0)]
    ]


def build_kernel_table_sidecar(
    hip: Dict[str, Any],
    framework_backend: str,
    framework_payload: Dict[str, Any],
) -> list[Dict[str, Any]]:
    framework_kernel_names = set()
    if framework_backend == "torch_profiler":
        framework_kernel_names = {row.get("name", "") for row in framework_payload.get("top_kernels", []) or []}
    elif framework_backend == "xprof_summary":
        framework_kernel_names = set(
            framework_payload.get("hipprof_alignment", {}).get("overlap_names", []) or []
        )
    rows: list[Dict[str, Any]] = []
    for row in hip.get("top_kernels", []) or []:
        kernel_name = str(row.get("name", ""))
        framework_seen = kernel_name in framework_kernel_names
        rows.append(
            {
                "kernel_name": kernel_name,
                "time_share_pct": float(row.get("percentage", 0.0) or 0.0),
                "calls": int(row.get("calls", 0) or 0),
                "avg_us": ns_to_us(row.get("average_ns", 0.0)),
                "framework_seen": framework_seen,
                "framework_location": (
                    framework_backend if framework_seen and framework_backend != "none" else "unknown"
                ),
                "notes": (
                    "kernel also appears in framework attribution"
                    if framework_seen
                    else "visible only in hardware-layer top kernels"
                ),
            }
        )
    return rows


def build_overlap_opportunities_sidecar(
    hip: Dict[str, Any],
    framework_backend: str,
    framework_payload: Dict[str, Any],
) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    if framework_backend == "torch_profiler":
        util = framework_payload.get("utilization", {}) or {}
        joint = framework_payload.get("joint_summary", {}) or {}
        dispatch_hotspot = joint.get("top_dispatch_cpu_op", {}) or {}
        if dispatch_hotspot:
            rows.append(
                {
                    "type": "dispatch",
                    "priority": "high",
                    "location": str(dispatch_hotspot.get("cpu_op", "unknown")),
                    "evidence": (
                        f"dispatch_exposed_us={float(dispatch_hotspot.get('dispatch_exposed_us', 0.0) or 0.0):.3f}, "
                        f"late_submit_us={float(dispatch_hotspot.get('late_submit_us', 0.0) or 0.0):.3f}"
                    ),
                    "recommendation": "优先检查该上层 op 的 host 迟下发、graph break、标量同步和小算子密集下发。",
                }
            )
        cpu_prep = joint.get("top_cpu_prep_source", {}) or {}
        if cpu_prep:
            rows.append(
                {
                    "type": "cpu_prep",
                    "priority": "high",
                    "location": str(cpu_prep.get("top_cpu_op", "unknown")),
                    "evidence": (
                        f"cpu_prep_us={float(cpu_prep.get('cpu_prep_us', 0.0) or 0.0):.3f}, "
                        f"top_runtime={cpu_prep.get('top_runtime', 'unknown')}"
                    ),
                    "recommendation": "检查该 CPU 准备路径是否包含标量回传、shape churn、临时张量或重复 layout 变换。",
                }
            )
        post_launch = joint.get("top_post_launch_source", {}) or {}
        if post_launch:
            rows.append(
                {
                    "type": "post_launch_gap",
                    "priority": "medium",
                    "location": (
                        f"{shorten_text(post_launch.get('prev_kernel', ''), 48)} -> "
                        f"{shorten_text(post_launch.get('next_kernel', ''), 48)}"
                    ),
                    "evidence": (
                        f"post_launch_us={float(post_launch.get('post_launch_us', 0.0) or 0.0):.3f}, "
                        f"host_unattributed_us={float(post_launch.get('host_unattributed_us', 0.0) or 0.0):.3f}"
                    ),
                    "recommendation": "检查 launch 后 device 侧等待是否来自 stream/event 依赖，或 trace 粒度不足导致的 host unattributed 泡。",
                }
            )
        copy_ratio = float(util.get("copy_share_of_gpu_busy", 0.0) or 0.0)
        if copy_ratio > 0.0:
            rows.append(
                {
                    "type": "copy",
                    "priority": "high" if copy_ratio >= 0.35 else "medium",
                    "location": "gpu_copy_kernels",
                    "evidence": f"copy_share_of_gpu_busy={pct(copy_ratio)}",
                    "recommendation": "检查 steady-state 中的 copy-like kernel 是否来自 layout 变换、临时张量搬运或不必要的数据回传。",
                }
            )
        return rows

    if framework_backend == "xprof_summary":
        for row in framework_payload.get("top_wait_or_copy_regions", []) or []:
            name = str(row.get("name", ""))
            rows.append(
                {
                    "type": classify_wait_copy_type(name),
                    "priority": classify_wait_copy_priority(
                        name,
                        duration_us=float(row.get("total_duration_us", 0.0) or 0.0),
                    ),
                    "location": name,
                    "evidence": (
                        f"calls={int(row.get('calls', 0) or 0)} "
                        f"total_us={float(row.get('total_duration_us', 0.0) or 0.0):.3f}"
                    ),
                    "recommendation": build_copy_recommendation(name),
                }
            )
        for row in framework_payload.get("top_gpu_gaps", []) or []:
            rows.append(
                {
                    "type": "gap",
                    "priority": "high" if float(row.get("gap_us", 0.0) or 0.0) >= 100.0 else "medium",
                    "location": (
                        f"{shorten_text(row.get('prev_kernel', ''), 48)} -> "
                        f"{shorten_text(row.get('next_kernel', ''), 48)}"
                    ),
                    "evidence": f"gap_us={float(row.get('gap_us', 0.0) or 0.0):.3f}",
                    "recommendation": "检查该 gap 前后的 host 调度、同步点或框架侧 region，确认 GPU 是否在等 host 或等数据。",
                }
            )
        return rows

    for row in collect_wait_copy_rows(hip, framework_backend, framework_payload, top_k=5):
        rows.append(
            {
                "type": classify_wait_copy_type(row["name"]),
                "priority": classify_wait_copy_priority(row["name"]),
                "location": row["name"],
                "evidence": f"{row['source']} {row['share']} {row['detail']}".strip(),
                "recommendation": build_copy_recommendation(row["name"]),
            }
        )
    return rows


def build_fuse_opportunities_sidecar(
    hip: Dict[str, Any],
    framework_backend: str,
    framework_payload: Dict[str, Any],
) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    top_kernel_names = [str(row.get("name", "")) for row in hip.get("top_kernels", []) or []]
    copy_like = [name for name in top_kernel_names if any(token in name.lower() for token in ("copy", "memcpy"))]

    if framework_backend == "torch_profiler":
        util = framework_payload.get("utilization", {}) or {}
        joint = framework_payload.get("joint_summary", {}) or {}
        dispatch_hotspot = joint.get("top_dispatch_cpu_op", {}) or {}
        dispatch_op = str(dispatch_hotspot.get("cpu_op", ""))
        if copy_like or float(util.get("copy_share_of_gpu_busy", 0.0) or 0.0) >= 0.15:
            rows.append(
                {
                    "pattern": "copy_permute_fold",
                    "location": copy_like[0] if copy_like else "copy_like_kernels",
                    "time_signal": f"copy_share_of_gpu_busy={pct(float(util.get('copy_share_of_gpu_busy', 0.0) or 0.0))}",
                    "candidate_path": "检查 layout 变换、临时张量 copy 和 copy+compute 折叠机会。",
                }
            )
        if dispatch_op in {"aten::addmm", "aten::bmm", "aten::mm", "aten::matmul"}:
            rows.append(
                {
                    "pattern": "matmul_pointwise_chain",
                    "location": dispatch_op,
                    "time_signal": (
                        f"dispatch_exposed_us={float(dispatch_hotspot.get('dispatch_exposed_us', 0.0) or 0.0):.3f}"
                    ),
                    "candidate_path": "检查 GEMM 后的 add/mul/gelu/tanh 等 pointwise 是否能通过 torch.compile 或局部改写融合。",
                }
            )
        elementwise_terms = [name for name in top_kernel_names if any(token in name.lower() for token in ("gelu", "tanh", "add", "mul", "softmax"))]
        if len(elementwise_terms) >= 2:
            rows.append(
                {
                    "pattern": "elementwise_chain_fusion",
                    "location": shorten_text(elementwise_terms[0], 80),
                    "time_signal": f"elementwise_like_kernels={len(elementwise_terms)}",
                    "candidate_path": "检查连续 pointwise 链是否能被 torch.compile 吸收，或是否需要局部 operator rewrite。",
                }
            )
        return rows

    if framework_backend == "xprof_summary":
        top_regions = [str(row.get("name", "")) for row in framework_payload.get("top_framework_regions", []) or []]
        lowered = {name.lower() for name in top_regions}
        if any(name for name in top_regions if name in {"MatMul", "BatchMatMulV2"}):
            if any(any(token in item for token in ("mul", "addv2", "relu", "gelu")) for item in lowered):
                rows.append(
                    {
                        "pattern": "matmul_pointwise_chain",
                        "location": "top_framework_regions",
                        "time_signal": "MatMul appears together with AddV2/Mul/Relu in the measured step.",
                        "candidate_path": "检查 MatMul 后的 pointwise 链是否能通过 compile/graph/fusion backend 合并。",
                    }
                )
        if any("copy" in name.lower() or "memcpy" in name.lower() for name in top_regions) or any(
            any(token in row.get("name", "").lower() for token in ("copy", "memcpy"))
            for row in framework_payload.get("top_wait_or_copy_regions", []) or []
        ):
            rows.append(
                {
                    "pattern": "copy_permute_fold",
                    "location": "xprof_wait_copy_regions",
                    "time_signal": "framework-side copy signals are visible in measured steps.",
                    "candidate_path": "检查 host/device copy 和 layout 变换是否能提前驻留、批量化或与邻接 compute 合并。",
                }
            )
        elementwise_regions = [
            name
            for name in top_regions
            if name in {"AddV2", "Mul", "Relu", "Gelu", "Tanh", "BiasAdd", "Sum"}
        ]
        if len(elementwise_regions) >= 2:
            rows.append(
                {
                    "pattern": "elementwise_chain_fusion",
                    "location": "top_framework_regions",
                    "time_signal": f"elementwise_regions={','.join(elementwise_regions[:4])}",
                    "candidate_path": "检查连续 pointwise region 是否能通过图编译或 backend 融合减少 launch 和 gap。",
                }
            )
        return rows

    if copy_like:
        rows.append(
            {
                "pattern": "copy_permute_fold",
                "location": copy_like[0],
                "time_signal": "copy-like kernel appears in hardware top kernels.",
                "candidate_path": "检查 copy-like kernel 是否来自 layout 转换、临时搬运或可合并的数据通路。",
            }
        )
    return rows


def build_framework_rows(framework_backend: str, framework_payload: Dict[str, Any], top_k: int) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if framework_backend == "torch_profiler":
        joint = framework_payload.get("joint_summary", {}) or {}
        dispatch_hotspot = joint.get("top_dispatch_cpu_op", {}) or {}
        cpu_prep = joint.get("top_cpu_prep_source", {}) or {}
        post_launch = joint.get("top_post_launch_source", {}) or {}
        if dispatch_hotspot:
            rows.append(
                (
                    "Top dispatch hotspot",
                    f"`{dispatch_hotspot.get('cpu_op', 'unknown')}` "
                    f"(dispatch_exposed={float(dispatch_hotspot.get('dispatch_exposed_us', 0.0) or 0.0):.3f} us)",
                )
            )
        if cpu_prep:
            rows.append(
                (
                    "Top CPU prep source",
                    f"`{cpu_prep.get('top_cpu_op', 'unknown')}` "
                    f"(cpu_prep={float(cpu_prep.get('cpu_prep_us', 0.0) or 0.0):.3f} us)",
                )
            )
        if post_launch:
            rows.append(
                (
                    "Top post-launch pair",
                    f"`{shorten_text(post_launch.get('prev_kernel', ''), 48)}` -> "
                    f"`{shorten_text(post_launch.get('next_kernel', ''), 48)}`",
                )
            )
        for note in (framework_payload.get("measurement_notes") or [])[:1]:
            rows.append(("Measurement note", str(note)))
        return rows[: max(top_k, 0)]
    if framework_backend == "xprof_summary":
        for row in (framework_payload.get("top_framework_regions") or [])[: max(top_k, 0)]:
            rows.append(
                (
                    "Framework region",
                    f"`{row.get('name', '')}` "
                    f"(calls={row.get('calls', 0)} total_us={float(row.get('total_duration_us', 0.0) or 0.0):.3f})",
                )
            )
        for row in (framework_payload.get("step_ranges") or [])[:2]:
            rows.append(
                (
                    f"Step {row.get('step_num', '?')}",
                    f"duration={float(row.get('duration_us', 0.0) or 0.0):.3f} us "
                    f"gpu_busy_ratio={pct(float(row.get('gpu_busy_ratio', 0.0) or 0.0))}",
                )
            )
        return rows[: max(top_k, 0)]
    return [("Framework attribution", "none")]


def build_payload(hip: Dict[str, Any], framework_payload: Dict[str, Any], framework_path: str, top_k: int) -> Dict[str, Any]:
    framework_backend = detect_framework_backend(framework_payload)
    classification, reason = decide_classification(hip, framework_backend, framework_payload)
    route = choose_route(classification, framework_backend)
    top_kernel = top_or_empty(hip.get("top_kernels") or [])
    payload = {
        "inputs": {
            "hipprof_analysis_json": "",
            "framework_analysis_json": framework_path,
            "framework_backend": framework_backend,
        },
        "profile_metadata": build_profile_metadata(
            hip=hip,
            framework_backend=framework_backend,
            framework_payload=framework_payload,
            hipprof_path="",
            framework_path=framework_path,
        ),
        "summary": {
            "classification": classification,
            "reason": reason,
            "recommended_route": route["recommended_route"],
            "recommended_route_reason": route["recommended_route_reason"],
            "recommended_route_action": route["recommended_route_action"],
            "top_kernel_name": top_kernel.get("name", ""),
            "top_kernel_share_pct": float(top_kernel.get("percentage", 0.0) or 0.0),
        },
        "top_kernels": build_kernel_rows(hip, framework_backend, framework_payload, top_k),
        "bubble_summary": build_bubble_summary(framework_backend, framework_payload),
        "wait_copy_signals": collect_wait_copy_rows(hip, framework_backend, framework_payload, top_k),
        "framework_attribution": build_framework_rows(framework_backend, framework_payload, top_k),
        "kernel_table": build_kernel_table_sidecar(hip, framework_backend, framework_payload),
        "overlap_opportunities": build_overlap_opportunities_sidecar(hip, framework_backend, framework_payload),
        "fuse_opportunities": build_fuse_opportunities_sidecar(hip, framework_backend, framework_payload),
    }
    return payload


def build_report(payload: Dict[str, Any]) -> str:
    summary = payload["summary"]
    kernel_rows = [
        [
            sanitize_markdown_cell(row["name"]),
            row["share"],
            row["calls"],
            row["avg_us"],
            row["framework_seen"],
        ]
        for row in payload["top_kernels"]
    ] or [["-", "-", "-", "-", "-"]]
    bubble_rows = [[name, value, detail] for name, value, detail in payload["bubble_summary"]] or [["-", "-", "-"]]
    wait_rows = [
        [row["source"], sanitize_markdown_cell(shorten_text(row["name"], 90)), row["share"], sanitize_markdown_cell(row["detail"])]
        for row in payload["wait_copy_signals"]
    ] or [["-", "-", "-", "-"]]
    fw_rows = [[name, sanitize_markdown_cell(detail)] for name, detail in payload["framework_attribution"]] or [["-", "-"]]

    lines = [
        "# 性能分诊报告",
        "",
        "## 1. 结论",
        "",
        f"- 分类: `{summary['classification']}`",
        f"- 主要原因: {summary['reason']}",
        f"- 当前最热 kernel: `{summary['top_kernel_name']}` ({summary['top_kernel_share_pct']:.2f}%)",
        f"- 推荐下一步: `{summary['recommended_route']}`",
        f"- 路由解释: {summary['recommended_route_reason']}",
        f"- 动作建议: {summary['recommended_route_action']}",
        "",
        "## 2. Top Kernel",
        "",
        *markdown_table(
            ["Kernel", "Share", "Calls", "Avg us", "Framework Seen"],
            kernel_rows,
        ),
        "",
        "## 3. 空泡概览",
        "",
        *markdown_table(["Metric", "Value", "Meaning"], bubble_rows),
        "",
        "## 4. 等待 / 拷贝 / 运行时信号",
        "",
        *markdown_table(["Source", "Name", "Share", "Detail"], wait_rows),
        "",
        "## 5. 框架归因",
        "",
        *markdown_table(["Item", "Detail"], fw_rows),
        "",
        "## 6. 解释方式",
        "",
        "- `Top Kernel` 用来决定是否进入后续 kernel 深化优化。",
        "- `空泡概览` 和 `等待 / 拷贝 / 运行时信号` 用来判断 GPU 没工作的时间是不是主要问题。",
        "- `框架归因` 用来把热点或空泡落回到上层 op / step / host 路径，方便后续做消空泡或算子改写。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    hip_path = Path(args.hipprof_analysis_json)
    framework_path = Path(args.framework_analysis_json) if args.framework_analysis_json else None
    hip = load_json(str(hip_path))
    framework_payload = load_json(str(framework_path)) if framework_path else {}
    payload = build_payload(
        hip=hip,
        framework_payload=framework_payload,
        framework_path=str(framework_path) if framework_path else "",
        top_k=args.top_k,
    )
    payload["inputs"]["hipprof_analysis_json"] = str(hip_path)
    payload["profile_metadata"]["source_artifacts"] = [
        path for path in [str(hip_path), str(framework_path) if framework_path else ""] if path
    ]
    payload["profile_metadata"]["hipprof_input_prefix"] = str(hip.get("input_prefix", ""))

    report = build_report(payload)
    if args.export_dir:
        out_dir = Path(args.export_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.md").write_text(report, encoding="utf-8")
        (out_dir / "profile_metadata.json").write_text(
            json.dumps(payload["profile_metadata"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / "kernel_table.json").write_text(
            json.dumps(payload["kernel_table"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / "overlap_opportunities.json").write_text(
            json.dumps(payload["overlap_opportunities"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / "fuse_opportunities.json").write_text(
            json.dumps(payload["fuse_opportunities"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if args.export_analysis_json:
            (out_dir / "analysis.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        print(f"Wrote report to {out_dir / 'report.md'}")
        if args.export_analysis_json:
            print(f"Wrote analysis to {out_dir / 'analysis.json'}")
        return
    print(report)


if __name__ == "__main__":
    main()
