"""Pipeline trigger — connects interact agent output to question generation.

Reads paper_request.yaml / slot_blueprint.yaml produced by the interact agent,
feeds each slot through DocPipeline, and writes per-question output files
that the display_result_service can pick up.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Progress stages per question
STAGES = ["流水线生成中", "选项设计中", "求解中", "审核中", "排版中"]


class PipelineProgress:
    """Mutable progress tracker for a single generation job."""

    def __init__(self, session_id: str, total_slots: int) -> None:
        self.session_id = session_id
        self.total_slots = total_slots
        self.slot_status: dict[str, dict[str, str]] = {}  # slot_id → {status, stage, label}
        self.started_at = time.monotonic()
        self.finished_at: float | None = None
        self.error: str | None = None

    @property
    def status(self) -> str:
        """Coarse job status for API consumers."""
        if self.error:
            return "failed"
        if not self.slot_status:
            return "pending"

        statuses = [s.get("status") for s in self.slot_status.values()]
        if all(s == "completed" for s in statuses):
            return "completed"
        if all(s in ("completed", "failed") for s in statuses):
            return "failed" if self.completed_count == 0 else "partial"
        if any(s == "generating" for s in statuses):
            return "running"
        return "pending"

    @property
    def is_done(self) -> bool:
        if self.error:
            return True
        return all(
            s.get("status") in ("completed", "failed")
            for s in self.slot_status.values()
        )

    @property
    def completed_count(self) -> int:
        return sum(
            1 for s in self.slot_status.values()
            if s.get("status") == "completed"
        )

    @property
    def failed_count(self) -> int:
        return sum(
            1 for s in self.slot_status.values()
            if s.get("status") == "failed"
        )

    def mark_failed(self, message: str) -> None:
        """Mark a setup-level job failure and close unfinished slots."""
        self.error = message
        self.finished_at = time.monotonic()
        for sid, slot in list(self.slot_status.items()):
            if slot.get("status") not in ("completed", "failed"):
                self.slot_status[sid] = {
                    **slot,
                    "status": "failed",
                    "stage": f"失败: {message[:50]}",
                }

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "total_slots": self.total_slots,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "is_done": self.is_done,
            "elapsed_s": round(
                (self.finished_at or time.monotonic()) - self.started_at, 1
            ),
            "slots": dict(self.slot_status),
            "error": self.error,
        }


# Global registry of active pipeline jobs
_jobs: dict[str, PipelineProgress] = {}


def get_job(session_id: str) -> PipelineProgress | None:
    _cleanup_jobs()
    return _jobs.get(session_id)


def mark_job_failed(session_id: str, message: str) -> PipelineProgress:
    """Record a setup-level failure even if trigger_generation crashed early."""
    progress = _jobs.get(session_id)
    if progress is None:
        progress = PipelineProgress(session_id, 0)
        _jobs[session_id] = progress
    progress.mark_failed(message)
    return progress


def _cleanup_jobs() -> None:
    ttl = _job_ttl_seconds()
    if ttl <= 0:
        return
    now = time.monotonic()
    expired = [
        sid for sid, job in _jobs.items()
        if job.finished_at is not None and now - job.finished_at > ttl
    ]
    for sid in expired:
        _jobs.pop(sid, None)


def _job_ttl_seconds() -> int:
    raw = os.getenv("PIPELINE_JOB_TTL_SECONDS", "3600")
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid PIPELINE_JOB_TTL_SECONDS=%r, using 3600", raw)
        return 3600


async def trigger_generation(
    session_id: str,
    handoff_yaml_path: Path,
    workspace: Path,
    *,
    provider: str = "glm5.2_anthropic",
    on_slot_complete: Callable[[str, str], None] | None = None,
) -> PipelineProgress:
    """Trigger question generation from a handoff YAML file.

    Args:
        session_id: Session identifier.
        handoff_yaml_path: Path to paper_request.yaml or slot_blueprint.yaml.
        workspace: Session workspace directory.
        provider: LLM provider name.
        on_slot_complete: Optional callback(slot_id, status) after each slot.

    Returns:
        PipelineProgress with live status.
    """
    _cleanup_jobs()
    progress = PipelineProgress(session_id, 0)
    _jobs[session_id] = progress

    try:
        import yaml
        from core_new.doc_pipeline import DocPipeline
        from core_new.llm_gateway import get_gateway

        with open(handoff_yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid handoff YAML: {handoff_yaml_path}")

        # Determine if paper (multiple slots) or single question
        slots_data = data.get("slots", [])
        if not slots_data:
            # Single question blueprint
            slots_data = [data]
        if not isinstance(slots_data, list):
            raise ValueError("handoff YAML field 'slots' must be a list")

        total = len(slots_data)
        progress.total_slots = total
        for sb in slots_data:
            if not isinstance(sb, dict):
                raise ValueError("handoff YAML slots must be mappings")
            sid = str(sb.get("slot_id", "Q1"))
            progress.slot_status[sid] = {
                "status": "waiting",
                "stage": STAGES[0],
                "label": f"第{_num_from_slot(sid)}题",
            }

        gateway = get_gateway(provider)
        output_dir = workspace / "questions"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Load experience cards
        exp_cards = _load_experience_cards(slots_data)

        # Augment experience cards with reference questions from paper_request.yaml
        for sb in slots_data:
            sid = str(sb.get("slot_id", "Q1"))
            ref_qs = sb.get("reference_questions", [])
            if ref_qs:
                ref_content = []
                for qf in ref_qs:
                    path = _resolve_reference_question_path(qf, handoff_yaml_path, workspace)
                    if path is not None:
                        try:
                            ref_content.append(path.read_text(encoding="utf-8"))
                        except Exception:
                            logger.warning("Failed to read reference question: %s", path)
                if ref_content:
                    existing = exp_cards.get(sid, "")
                    exp_cards[sid] = (
                        existing
                        + "\n\n=== 参考题目（教师选中考察模式对应的真题） ===\n"
                        + "\n---\n".join(ref_content)
                    )

        try:
            from core_new.slot_prompts import K_RADAR_DEFINITIONS
        except ImportError:
            K_RADAR_DEFINITIONS = ""

        # 并发：本地默认 4，线上默认 1（线上 API 限流，最多 ~2）。均可由
        # PIPELINE_SLOT_CONCURRENCY 覆盖（线上实测可 2 并发）。
        is_local = provider in ("api_vllm", "vllm")
        _default_conc = 4 if is_local else 1
        slot_concurrency = int(os.getenv("PIPELINE_SLOT_CONCURRENCY", str(_default_conc)))
        semaphore = asyncio.Semaphore(max(1, slot_concurrency))
        logger.info("[%s] 出题并发: %d (provider=%s, local=%s)",
                    session_id, slot_concurrency, provider, is_local)

        # 分离概念题和计算题：概念题合并批量出，计算题独立出
        concept_slots = []
        standard_slots = []
        for sb in slots_data:
            if sb.get("complexity") == "conceptual":
                concept_slots.append(sb)
            else:
                standard_slots.append(sb)

        async def _generate_one(sb: dict) -> dict:
            sid = str(sb.get("slot_id", "Q1"))
            num = _num_from_slot(sid)
            exp_card = exp_cards.get(sid, "")

            async with semaphore:
                # Update progress
                progress.slot_status[sid] = {
                    "status": "generating",
                    "stage": STAGES[0],
                    "label": f"第{num}题",
                }

                try:
                    doc_workspace = str(output_dir / sid)
                    dp = DocPipeline(
                        gateway=gateway,
                        workspace=doc_workspace,
                        model_routing={"_default": provider},
                        # Thinking on/off + depth is now resolved by the gateway
                        # from ROLE_THINKING_CONFIG (per-role). Passing None lets
                        # each role use its configured enable_thinking/reasoning_effort
                        # instead of the old hard-coded (provider in vllm) formula
                        # that silently disabled thinking on the GLM path.
                        enable_thinking=None,
                    )

                    # 概念题：如果有多个概念题 slot，合并 concept_topics 批量出
                    if sb.get("complexity") == "conceptual" and len(concept_slots) > 1:
                        # 收集所有概念题的考点（保留空值占位，确保 index 对齐）
                        # 每条带题型前缀（examination_mode 提取），让 concept_creator 按各题题型出（判断≠选择≠填空）
                        concept_topics = [
                            f"【{(s.get('examination_mode') or '').split('——')[0].strip() or '概念辨析'}】{s.get('primary_target_name', '')}"
                            for s in concept_slots
                        ]
                        sb = dict(sb)  # copy to avoid mutating original
                        sb["concept_topics"] = concept_topics

                    # Run the actual pipeline
                    result = await dp.run(
                        slot_id=sid,
                        slot_data=sb,
                        experience_card=exp_card,
                        k_definitions=K_RADAR_DEFINITIONS,
                    )

                    if result.ok and result.final_content:
                        # Write output files
                        q_dir = output_dir / sid
                        q_dir.mkdir(parents=True, exist_ok=True)
                        (q_dir / "final.md").write_text(
                            result.final_content, encoding="utf-8"
                        )

                        # 概念题批量出题：拆分多道题到各 slot 目录
                        if sb.get("complexity") == "conceptual" and len(concept_slots) > 1:
                            _split_concept_questions(q_dir, concept_slots, output_dir)

                        progress.slot_status[sid] = {
                            "status": "completed",
                            "stage": "已完成",
                            "label": f"第{num}题",
                        }
                    else:
                        error_msg = result.error or "generation failed"
                        q_dir = output_dir / sid
                        q_dir.mkdir(parents=True, exist_ok=True)
                        (q_dir / "error.md").write_text(error_msg, encoding="utf-8")
                        progress.slot_status[sid] = {
                            "status": "failed",
                            "stage": f"失败: {error_msg[:50]}",
                            "label": f"第{num}题",
                        }
                        # 概念题失败传播：后续概念题 slot 标记 failed
                        if sb.get("complexity") == "conceptual":
                            for other_sb in concept_slots[1:]:
                                other_sid = str(other_sb.get("slot_id", "Q1"))
                                progress.slot_status[other_sid] = {
                                    "status": "failed",
                                    "stage": f"失败: 概念题批量出题失败",
                                    "label": f"第{_num_from_slot(other_sid)}题",
                                }

                    if on_slot_complete:
                        on_slot_complete(sid, progress.slot_status[sid]["status"])
                    return progress.slot_status[sid]

                except Exception as e:
                    logger.exception("[%s] Slot %s generation failed", session_id, sid)
                    q_dir = output_dir / sid
                    q_dir.mkdir(parents=True, exist_ok=True)
                    (q_dir / "error.md").write_text(str(e), encoding="utf-8")
                    progress.slot_status[sid] = {
                        "status": "failed",
                        "stage": f"失败: {str(e)[:50]}",
                        "label": f"第{num}题",
                    }
                    if on_slot_complete:
                        on_slot_complete(sid, "failed")
                    return progress.slot_status[sid]

        # 概念题：只跑第一个 slot（它包含全部概念题考点），其他概念题标记完成
        # 计算题：每个 slot 独立出题
        tasks = []
        concept_first = True
        for sb in slots_data:
            if sb.get("complexity") == "conceptual":
                if concept_first:
                    tasks.append(_generate_one(sb))
                    concept_first = False
                else:
                    # 后续概念题 slot 由第一个 slot 批量产出，标记为 completed
                    sid = str(sb.get("slot_id", "Q1"))
                    num = _num_from_slot(sid)
                    progress.slot_status[sid] = {
                        "status": "completed",
                        "stage": "已批量产出",
                        "label": f"第{num}题",
                    }
            else:
                tasks.append(_generate_one(sb))

        await asyncio.gather(*tasks)

        progress.finished_at = time.monotonic()
        logger.info(
            "[%s] Pipeline done: %d/%d completed in %.1fs",
            session_id,
            progress.completed_count,
            total,
            (progress.finished_at - progress.started_at),
        )
        return progress
    except Exception as e:
        logger.exception("[%s] Pipeline generation setup failed", session_id)
        progress.mark_failed(str(e))
        raise


def _split_concept_questions(
    source_dir: Path,
    concept_slots: list[dict],
    output_dir: Path,
) -> None:
    """Split batch-generated concept questions into per-slot directories.

    The first concept slot's question.md contains N questions separated by
    '## 第 N 题' or '## 题目 N' headers. Split each into its own slot dir.
    """
    import re as _re

    q_path = source_dir / "question.md"
    s_path = source_dir / "solution.md"
    # DocPipeline 内部 ws=workspace/slot_id 会再建一层 slot_id 子目录，逐题产物
    # （question.md/solution.md）在双层 source_dir/<slot_id>/ 下；单层只有 trigger
    # 写的 final.md。拆分需逐题原文，故优先读双层。
    if not q_path.exists():
        inner_dir = source_dir / source_dir.name
        if (inner_dir / "question.md").exists():
            q_path = inner_dir / "question.md"
            s_path = inner_dir / "solution.md"
    if not q_path.exists():
        return

    q_text = q_path.read_text(encoding="utf-8")
    s_text = s_path.read_text(encoding="utf-8") if s_path.exists() else ""

    # 按 #{2,} 第 N 题 / 题目 N 拆分（容忍 ### / 无空格 等 markdown 漂移；
    # 仍锚定 第N题/题目N 关键字，避免误拆 body 内其它 ## 段）
    q_sections = _re.split(r"(?=^#{2,}\s*(?:第\s*)?\d+\s*题|^#{2,}\s*题目\s*\d+)", q_text, flags=_re.MULTILINE)
    s_sections = _re.split(r"(?=^#{2,}\s*(?:第\s*)?\d+\s*题|^#{2,}\s*题目\s*\d+|^#{2,}\s*第\s*\d+\s*题\s*解析)", s_text, flags=_re.MULTILINE) if s_text else []

    # 过滤空段
    q_sections = [s.strip() for s in q_sections if s.strip() and not s.strip().startswith("# ") and "##" in s]
    s_sections = [s.strip() for s in s_sections if s.strip() and not s.strip().startswith("# ") and "##" in s]

    # 按顺序映射到 concept_slots（含第一个，重写其 final.md 只保留第一题）
    for i, sb in enumerate(concept_slots):
        if i >= len(q_sections):
            break
        sid = str(sb.get("slot_id", f"Q{i+1}"))
        slot_dir = output_dir / sid
        slot_dir.mkdir(parents=True, exist_ok=True)

        # 写该题的 question.md
        (slot_dir / "question.md").write_text(q_sections[i], encoding="utf-8")

        # 写对应的 solution（如果有）
        if i < len(s_sections):
            (slot_dir / "solution.md").write_text(s_sections[i], encoding="utf-8")

        # 写/重写 final.md（只含该题，不含全部）
        final_content = q_sections[i]
        if i < len(s_sections):
            final_content += "\n\n---\n\n" + s_sections[i]
        (slot_dir / "final.md").write_text(final_content, encoding="utf-8")

    logger.info("概念题拆分完成：%d 道题拆分到各 slot 目录", len(concept_slots) - 1)


def _num_from_slot(slot_id: str) -> str:
    digits = re.sub(r"\D+", "", slot_id)
    return str(int(digits)) if digits else slot_id


def _resolve_reference_question_path(
    path_value: Any,
    handoff_yaml_path: Path,
    workspace: Path,
) -> Path | None:
    """Resolve a reference question path from YAML in session context."""
    if not path_value:
        return None
    raw_path = Path(str(path_value))
    candidates = [raw_path] if raw_path.is_absolute() else [
        handoff_yaml_path.parent / raw_path,
        workspace / raw_path,
        raw_path,
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    logger.warning("Reference question not found: %s", path_value)
    return None


def _load_experience_cards(slots_data: list[dict]) -> dict[str, str]:
    """Load experience cards for slots that have them."""
    cards: dict[str, str] = {}
    exp_dir = Path("data/slot_experiences")
    if not exp_dir.is_dir():
        return cards
    for sb in slots_data:
        sid = sb.get("slot_id", "")
        path = exp_dir / f"{sid}_experience.md"
        if path.exists():
            cards[sid] = path.read_text(encoding="utf-8")
    return cards
