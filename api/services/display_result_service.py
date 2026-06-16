"""Teacher-facing result aggregation for Interact V2."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from api.schemas_interact_v2 import (
    DisplayQuestion,
    DisplayResult,
    QuestionAnnotationRequest,
    QuestionAnnotationResponse,
)
from api.services.interact_v2_service import InteractV2Service


_OPTION_RE = re.compile(r"^\s*(?:[-*]\s*)?([A-D])[\.:：、]\s*(.+?)\s*$")
_HEADING_RE_TEMPLATE = r"^##\s+{heading}\s*$"


class DisplayResultService:
    """Build DisplayResult JSON from generated files or the latest draft."""

    def __init__(self, interact_service: InteractV2Service) -> None:
        self._interact_service = interact_service
        self._question_annotations: dict[str, dict[str, str]] = {}

    def get_display_result(self, session_id: str) -> DisplayResult:
        """Return a teacher-facing result snapshot for a session."""
        info = self._interact_service.get_session_info(session_id)
        if info is None:
            raise ValueError(f"Session {session_id} not found")

        workspace = self._interact_service.get_session_workspace(session_id)
        questions = self._load_generated_questions(session_id, workspace)
        if questions:
            self._merge_pipeline_progress(session_id, questions)
            status, message = self._aggregate_question_status(questions)
            return DisplayResult(
                status=status,
                message=message,
                title="题目结果",
                questions=questions,
                paper_markdown=self._build_paper_markdown("题目结果", questions),
            )

        draft_result = self._build_result_from_draft(session_id)
        # Merge pipeline progress labels for draft fallback too
        if draft_result.questions:
            self._merge_pipeline_progress(session_id, draft_result.questions)
            draft_result.status, draft_result.message = self._aggregate_question_status(
                draft_result.questions
            )
            draft_result.paper_markdown = self._build_paper_markdown(
                draft_result.title,
                draft_result.questions,
            )
        if draft_result.questions:
            return draft_result

        return DisplayResult(
            status="pending",
            message="题目仍在生成，或尚未提交最终草案。",
            title="题目结果",
            questions=[],
            paper_markdown="",
        )

    async def save_question_annotation(
        self,
        session_id: str,
        slot_id: str,
        request: QuestionAnnotationRequest,
    ) -> QuestionAnnotationResponse:
        """Save a teacher annotation for one display question."""
        info = self._interact_service.get_session_info(session_id)
        if info is None:
            raise ValueError(f"Session {session_id} not found")

        self._question_annotations.setdefault(session_id, {})[slot_id] = request.annotation
        if request.action == "regenerate_question":
            # 触发单题重新生成（带教师批注）
            try:
                await self._regenerate_single_question(session_id, slot_id, request.annotation)
                return QuestionAnnotationResponse(
                    ok=True,
                    status="regenerating",
                    message=f"题目 {slot_id} 正在重新生成（批注：{request.annotation[:50]}）",
                )
            except Exception as e:
                logger.exception("Failed to regenerate question %s", slot_id)
                return QuestionAnnotationResponse(
                    ok=False,
                    status="error",
                    message=f"重新生成失败：{e}",
                )
        return QuestionAnnotationResponse(ok=True, status="recorded", message="批注已保存。")

    async def _regenerate_single_question(
        self, session_id: str, slot_id: str, annotation: str
    ) -> None:
        """Re-run pipeline for a single slot with teacher annotation."""
        import asyncio
        import yaml
        from core_new.doc_pipeline import DocPipeline
        from core_new.llm_gateway import get_gateway

        try:
            from core_new.slot_prompts import K_RADAR_DEFINITIONS
        except ImportError:
            K_RADAR_DEFINITIONS = ""

        workspace = self._interact_service.get_session_workspace(session_id)
        # 找交接 YAML
        handoff_path = None
        for name in ("paper_request.yaml", "slot_blueprint.yaml"):
            p = workspace / name
            if p.exists():
                handoff_path = p
                break
        if not handoff_path:
            # 也可能在 compose/ 下
            for name in ("paper_request.yaml", "slot_blueprint.yaml"):
                p = workspace / "compose" / name
                if p.exists():
                    handoff_path = p
                    break
        if not handoff_path:
            raise ValueError("找不到交接 YAML，无法重生成")

        with open(handoff_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        slots_data = data.get("slots", [data]) if isinstance(data, dict) else []

        # 找到目标 slot
        target_sb = None
        for sb in slots_data:
            if str(sb.get("slot_id", "")) == slot_id:
                target_sb = sb
                break
        if not target_sb:
            raise ValueError(f"交接 YAML 中找不到 slot {slot_id}")

        # 加教师批注
        target_sb = dict(target_sb)
        target_sb["teacher_annotation"] = annotation

        # 获取 provider
        session = self._interact_service.get_session_info(session_id)
        provider = getattr(session, "provider", "api_vllm") if session else "api_vllm"

        # 重新出题
        gateway = get_gateway(provider)
        output_dir = workspace / "questions"
        doc_workspace = str(output_dir / slot_id)

        dp = DocPipeline(
            gateway=gateway,
            workspace=doc_workspace,
            model_routing={"_default": provider},
            enable_thinking=(provider in ("api_vllm", "vllm")),
        )
        result = await dp.run(
            slot_id=slot_id,
            slot_data=target_sb,
            experience_card="",
            k_definitions=K_RADAR_DEFINITIONS if "K_RADAR_DEFINITIONS" in dir() else "",
        )
        if result.ok and result.final_content:
            q_dir = output_dir / slot_id
            q_dir.mkdir(parents=True, exist_ok=True)
            (q_dir / "final.md").write_text(result.final_content, encoding="utf-8")

    def get_paper_markdown(self, session_id: str) -> str:
        """Return the latest paper markdown."""
        result = self.get_display_result(session_id)
        return result.paper_markdown

    # ------------------------------------------------------------------
    # Pipeline progress merge
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_pipeline_progress(session_id: str, questions: list[DisplayQuestion]) -> None:
        """Overlay pipeline progress labels onto display questions."""
        try:
            from api.services.pipeline_trigger import get_job
        except ImportError:
            return
        job = get_job(session_id)
        if not job:
            return
        for q in questions:
            slot_info = job.slot_status.get(q.slot_id)
            if not slot_info:
                slot_info = _find_slot_progress_by_display_id(
                    job.slot_status,
                    q.display_id or _display_id_from_slot(q.slot_id),
                )
            if not slot_info:
                continue
            # If pipeline says completed but question still shows generating, upgrade it
            if slot_info.get("status") == "completed" and q.status != "completed":
                q.status = "completed"
                q.progress_label = "已完成"
            elif slot_info.get("status") == "failed":
                q.status = "failed"
                q.progress_label = slot_info.get("stage", "生成失败")
            elif slot_info.get("status") == "generating":
                q.progress_label = slot_info.get("stage", "生成中")

    @staticmethod
    def _aggregate_question_status(
        questions: list[DisplayQuestion],
    ) -> tuple[str, str]:
        """Derive the DisplayResult status from per-question status."""
        total = len(questions)
        if total == 0:
            return "pending", "题目仍在生成，或尚未提交最终草案。"

        completed = sum(1 for q in questions if q.status == "completed")
        failed = sum(1 for q in questions if q.status == "failed")
        if completed == total:
            return "completed", "题目已全部生成。"
        if failed == total:
            return "failed", "题目生成失败，请查看错误信息。"
        if completed or failed:
            return "partial", f"已完成 {completed}/{total} 题，失败 {failed} 题。"
        return "partial", f"共 {total} 题，正在生成中…"

    # ------------------------------------------------------------------
    # Generated artifact parsing
    # ------------------------------------------------------------------

    def _load_generated_questions(
        self,
        session_id: str,
        workspace: Path | None,
    ) -> list[DisplayQuestion]:
        bases: list[Path] = []
        if workspace is not None:
            bases.append(workspace)
        bases.append(Path("docs/workspace") / session_id)

        seen_dirs: set[Path] = set()
        questions: list[DisplayQuestion] = []
        metadata = self._load_slot_display_metadata(session_id)
        for base in bases:
            if not base.exists():
                continue
            for qdir in self._iter_question_dirs(base):
                resolved = qdir.resolve()
                if resolved in seen_dirs:
                    continue
                seen_dirs.add(resolved)
                question = self._parse_question_dir(session_id, qdir)
                if question:
                    self._apply_question_metadata(question, metadata.get(question.slot_id))
                    questions.append(question)

        return sorted(questions, key=lambda q: _slot_sort_key(q.slot_id))

    @staticmethod
    def _iter_question_dirs(base: Path) -> list[Path]:
        dirs: set[Path] = set()
        for name in ("final.md", "question.md", "solution.md", "error.md"):
            for path in base.rglob(name):
                # Skip interact handoff drafts under compose/.
                if "compose" in path.parts:
                    continue
                dirs.add(_question_artifact_dir(base, path))
        return sorted(dirs, key=lambda p: str(p))

    def _parse_question_dir(self, session_id: str, qdir: Path) -> DisplayQuestion | None:
        slot_id = qdir.name
        display_id = _display_id_from_slot(slot_id)
        title = _title_from_slot(slot_id)

        if (qdir / "error.md").exists():
            return DisplayQuestion(
                slot_id=slot_id,
                display_id=display_id,
                title=title,
                status="failed",
                stem=(qdir / "error.md").read_text(encoding="utf-8"),
                annotation=self._question_annotations.get(session_id, {}).get(slot_id, ""),
            )

        final_md = _read_optional(qdir / "final.md")
        question_md = _read_optional(qdir / "question.md")
        solution_md = _read_optional(qdir / "solution.md")
        source = final_md or question_md
        if not source:
            return None

        stem = _first_nonempty(
            _extract_h2_section(source, "题目"),
            _extract_h2_section(source, "题干"),
        )
        options = _parse_options(_extract_h2_section(source, "选项"))

        answer = _first_nonempty(
            _extract_h2_section(source, "答案"),
            _extract_h2_section(solution_md, "最终答案"),
        )
        explanation = _first_nonempty(
            _extract_h2_section(source, "求解过程"),
            _extract_h2_section(solution_md, "求解过程"),
            answer,
        )

        status = "completed" if stem and (answer or solution_md or final_md) else "generating"
        return DisplayQuestion(
            slot_id=slot_id,
            display_id=display_id,
            title=title,
            status=status,
            stem=stem or source.strip(),
            options=options,
            answer=_clean_answer(answer),
            explanation=explanation.strip(),
            annotation=self._question_annotations.get(session_id, {}).get(slot_id, ""),
        )

    def _load_slot_display_metadata(self, session_id: str) -> dict[str, dict[str, str]]:
        """Build teacher-facing labels for generated slot IDs."""
        metadata: dict[str, dict[str, str]] = {}

        draft = self._interact_service.get_draft(session_id)
        annotation = self._interact_service.get_latest_annotation(session_id)
        if draft:
            selected_map: dict[str, str] = {}
            if annotation:
                for item in annotation.slots:
                    selected = item.selected_option_id or (
                        item.kept_options[0] if item.kept_options else ""
                    )
                    if selected:
                        selected_map[item.slot_id] = selected

            type_map: dict[str, str] = {}
            for section in draft.sections:
                if not _is_question_type_section(section):
                    continue
                base_match = re.search(r"(Q\d+)", section.slot_id)
                if not base_match:
                    continue
                selected_id = selected_map.get(section.slot_id)
                selected = next((o for o in section.options if o.id == selected_id), None)
                if selected:
                    type_map[base_match.group(1)] = selected.text

            question_index = 0
            for section in draft.sections:
                if _is_question_type_section(section):
                    continue
                question_index += 1
                selected_id = selected_map.get(section.slot_id)
                selected = next((o for o in section.options if o.id == selected_id), None)
                q_type = type_map.get(section.slot_id, "")
                title = selected.text if selected else section.title
                if q_type and title and q_type not in title:
                    title = f"{q_type} — {title}"
                metadata[section.slot_id] = {
                    "display_id": section.display_id or str(question_index),
                    "title": _clean_display_title(title),
                }

        result = self._interact_service.get_result(session_id)
        for idx, slot in enumerate(_slot_entries_from_result(result), start=1):
            sid = str(slot.get("slot_id") or f"Q{idx}")
            display_id = _display_id_from_slot(sid)
            if display_id == sid or not display_id:
                display_id = str(idx)

            q_type = _question_type_label(slot.get("question_type", ""))
            primary = _clean_display_title(
                str(
                    slot.get("primary_target_name")
                    or slot.get("examination_mode")
                    or slot.get("target_family")
                    or ""
                )
            )
            title = primary or q_type or "生成题目"
            if q_type and primary and q_type not in primary:
                title = f"{q_type} — {primary}"
            metadata[sid] = {"display_id": display_id, "title": title}

        return metadata

    @staticmethod
    def _apply_question_metadata(
        question: DisplayQuestion,
        metadata: dict[str, str] | None,
    ) -> None:
        if not metadata:
            return
        if metadata.get("display_id"):
            question.display_id = metadata["display_id"]
        if metadata.get("title"):
            question.title = metadata["title"]

    # ------------------------------------------------------------------
    # Draft fallback
    # ------------------------------------------------------------------

    def _build_result_from_draft(self, session_id: str) -> DisplayResult:
        draft = self._interact_service.get_draft(session_id)
        annotation = self._interact_service.get_latest_annotation(session_id)

        if not draft or not draft.sections:
            return DisplayResult(status="pending", message="尚未生成草案。")
        result = self._interact_service.get_result(session_id)
        if not annotation and not result:
            return DisplayResult(status="pending", message="草案已生成，等待教师提交选择。")

        selected_map: dict[str, str] = {}
        annotation_map: dict[str, str] = {}
        type_map: dict[str, str] = {}  # Q1 → "选择题" etc.
        if annotation:
            for item in annotation.slots:
                selected = item.selected_option_id or (item.kept_options[0] if item.kept_options else "")
                if selected:
                    selected_map[item.slot_id] = selected
                if item.annotation:
                    annotation_map[item.slot_id] = item.annotation

        # Collect question-type selections from 题型 sections
        for section in draft.sections:
            if _is_question_type_section(section):
                _q_match = re.search(r"(Q\d+)", section.slot_id)
                if _q_match:
                    base_id = _q_match.group(1)
                    sel_id = selected_map.get(section.slot_id)
                    sel = next((o for o in section.options if o.id == sel_id), None)
                    if sel:
                        type_map[base_id] = sel.text

        questions: list[DisplayQuestion] = []
        for section in draft.sections:
            # Skip 题型 sections — they feed into type_map, not into result cards
            if _is_question_type_section(section):
                continue

            selected_id = selected_map.get(section.slot_id)
            selected = next((opt for opt in section.options if opt.id == selected_id), None)
            if selected is None and section.options:
                selected = section.options[0]

            # Build display_id: plain number
            _q_num = re.sub(r"\D+", "", section.slot_id)
            display_id = _q_num or section.display_id or "?"

            # Title: include question type if available
            q_type = type_map.get(section.slot_id, "")
            if q_type:
                title = f"{q_type} — {selected.text}" if selected else section.title
            else:
                title = selected.text if selected else section.title

            stem = (
                f"已确认出题方向：{selected.text if selected else section.title}。\n\n"
                "完整题干、选项、答案与解析将在出题流水线接入后自动替换。"
            )
            if selected and selected.cognitive_desc:
                stem += f"\n\n考察说明：{selected.cognitive_desc}"

            progress_label = "出题流水线处理中" if result else "等待交接文档"

            questions.append(
                DisplayQuestion(
                    slot_id=section.slot_id,
                    display_id=display_id,
                    title=title,
                    status="generating",
                    progress_label=progress_label,
                    stem=stem,
                    options=[],
                    answer="待出题流水线生成",
                    explanation="当前结果来自草案选择，用于前端连通测试；不是最终考试题。",
                    annotation=annotation_map.get(section.slot_id, section.annotation),
                )
            )

        total = len(questions)
        completed = sum(1 for q in questions if q.status == "completed")
        if completed == total and total > 0:
            status, message = "completed", "题目已全部生成。"
        elif completed > 0:
            status, message = "partial", f"已完成 {completed}/{total} 题。"
        else:
            status, message = "partial", f"共 {total} 题，正在生成中…"
        if result:
            message = "交接文档已生成，出题流水线处理中…"
        return DisplayResult(
            status=status,
            message=message,
            title=draft.title or "题目结果",
            questions=questions,
            paper_markdown=self._build_paper_markdown(draft.title or "题目结果", questions),
        )

    @staticmethod
    def _build_paper_markdown(title: str, questions: list[DisplayQuestion]) -> str:
        lines = [f"# {title or '题目结果'}", "", "## 一、试题", ""]
        for q in questions:
            heading = q.display_id or q.slot_id
            lines.extend([f"### {heading} {q.title}".rstrip(), "", q.stem.strip(), ""])
            if q.options:
                lines.extend(f"{chr(65 + i)}. {opt}" for i, opt in enumerate(q.options))
                lines.append("")

        lines.extend(["## 二、答案与解析", ""])
        for q in questions:
            heading = q.display_id or q.slot_id
            lines.extend(
                [
                    f"### {heading} {q.title}".rstrip(),
                    "",
                    f"**答案：{q.answer or '待生成'}**",
                    "",
                    "**解析：**",
                    q.explanation.strip() or "待生成",
                    "",
                ]
            )

        lines.extend(["## 三、教师批注", ""])
        any_annotation = False
        for q in questions:
            if q.annotation:
                any_annotation = True
                heading = q.display_id or q.slot_id
                lines.extend([f"- **{heading}**：{q.annotation}", ""])
        if not any_annotation:
            lines.append("> 可在此处记录需要修改、替换或重生成的题目。")
        return "\n".join(lines).rstrip() + "\n"


def _read_optional(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _extract_h2_section(text: str, heading: str) -> str:
    if not text:
        return ""
    pattern = re.compile(_HEADING_RE_TEMPLATE.format(heading=re.escape(heading)), re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    next_match = re.search(r"^##\s+", text[match.end():], flags=re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(text)
    return text[match.end():end].strip()


def _parse_options(options_text: str) -> list[str]:
    options: list[str] = []
    current = ""
    for line in options_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _OPTION_RE.match(stripped)
        if match:
            if current:
                options.append(current.strip())
            current = match.group(2).strip()
        elif current:
            current += " " + stripped
    if current:
        options.append(current.strip())
    return options


def _first_nonempty(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _clean_answer(answer: str) -> str:
    answer = re.sub(r"^\*\*|\*\*$", "", answer.strip())
    return answer.replace("**", "").strip()


def _display_id_from_slot(slot_id: str) -> str:
    digits = re.sub(r"\D+", "", slot_id)
    if digits:
        return str(int(digits))
    return slot_id


def _title_from_slot(slot_id: str) -> str:
    if slot_id.startswith("Q") or _is_internal_slot_id(slot_id):
        return "生成题目"
    return slot_id


def _strip_display_prefix(title: str, display_id: str) -> str:
    clean = title.strip()
    for prefix in (display_id, f"{display_id}（选择题·2分）", f"{display_id} "):
        if clean.startswith(prefix):
            clean = clean[len(prefix):].strip(" —-·（）() ")
    return clean or title


def _slot_sort_key(slot_id: str) -> tuple[int, str]:
    digits = re.sub(r"\D+", "", slot_id)
    return (int(digits) if digits else 10_000, slot_id)


def _question_artifact_dir(base: Path, path: Path) -> Path:
    """Collapse nested pipeline work dirs to the public per-slot dir."""
    try:
        rel_parts = path.relative_to(base).parts
    except ValueError:
        rel_parts = path.parts
    if "questions" in rel_parts:
        idx = rel_parts.index("questions")
        if len(rel_parts) > idx + 1:
            return base.joinpath(*rel_parts[:idx + 2])
    return path.parent


def _slot_entries_from_result(result: Any) -> list[dict[str, Any]]:
    if not isinstance(result, dict):
        return []
    slots = result.get("slots")
    if isinstance(slots, list):
        return [slot for slot in slots if isinstance(slot, dict)]
    if result.get("slot_id"):
        return [result]
    return []


def _question_type_label(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "single_choice": "选择题",
        "choice": "选择题",
        "multiple_choice": "多选题",
        "comprehensive": "综合应用题",
        "subjective": "综合应用题",
    }
    if raw in mapping:
        return mapping[raw]
    if "选择" in str(value):
        return "选择题"
    if "综合" in str(value):
        return "综合应用题"
    return str(value or "").strip()


def _clean_display_title(title: str) -> str:
    clean = title.strip().strip('"').strip("'")
    clean = re.sub(r"\s+", " ", clean)
    return clean


def _is_internal_slot_id(slot_id: str) -> bool:
    return bool(re.match(r"^(TOPIC|SLOT|QUESTION)[_-]?\d+$", slot_id, re.IGNORECASE))


def _is_question_type_section(section: Any) -> bool:
    if getattr(section, "phase", "") == "question_type":
        return True
    return "题型" in str(getattr(section, "display_id", "") or getattr(section, "title", ""))


def _find_slot_progress_by_display_id(
    slot_status: dict[str, dict[str, str]],
    display_id: str,
) -> dict[str, str] | None:
    for sid, info in slot_status.items():
        if _display_id_from_slot(sid) == display_id:
            return info
    return None
