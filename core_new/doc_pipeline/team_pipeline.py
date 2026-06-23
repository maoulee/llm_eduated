"""TeamPipeline — per-session 常驻团队，封装四角色序列 + 团队黑板。

核心抽象：智能体 = LLM + 状态。
  team 持久化 = workspace 目录(产物 md) + paper_state.md(黑板) + scheduler(无状态可重建)。
  一个 TeamPipeline 实例对应一张试卷（一个前端 session）。

团队复用：同一个 TeamPipeline 实例连续处理多道题，scheduler/gateway 不重新拉起。
跨题记忆（黑板，路径 B：编排层搬运）：
  - agent 用现有 write_file 在 slot 内写 team_state_entry.md（题目摘要）。
  - 编排层（本类）每题结束后把 entry 追加到 workspace/paper_state.md（slot 外，绕过沙箱）。
  - 下题 design_direct 开头注入 paper_state.md（软提示去重）。
单题工作记忆仍每题 clear（防 token 膨胀），黑板只存轻量摘要。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from core_new.doc_pipeline.doc_parser import (
    get_doc_status,
    parse_doc_section,
    _status_from_text,
)

logger = logging.getLogger(__name__)


def status_of(text: str | None, review_path: str | Path | None = None) -> str:
    """从 review 产物里抽 ## status 的值（pass / needs_fix / unknown）。

    复用 doc_parser 的强解析（完整 fallback：H2 段 / 同行值 / 中文标签 /
    bare header / pass-qualifier 降级），避免 team_pipeline 各自维护脆弱正则。

    优先读 *review_path* 文件（agent 已落盘 review.md 时最可靠）；
    文件不可用时退化到对内存字符串 *text* 调 ``_status_from_text``。
    两者都拿不到有效 status 才返回 ``unknown``（保持原语义）。
    """
    if review_path is not None:
        try:
            status = get_doc_status(review_path)
            if status:
                return status
        except (FileNotFoundError, OSError):
            pass
    status = _status_from_text(text or "")
    return status or "unknown"

_BOARD_HEADER = (
    "# 组卷进度黑板\n"
    "（每题完成后追加一行；design_direct 参考，软性避开重复考点）\n"
)


class TeamPipeline:
    """per-session 常驻团队：封装 design_direct → write_gen → write_solution → dual_review。

    一个实例 = 一张试卷。跨题靠 paper_state.md（黑板）传递轻量记忆，
    scheduler/gateway 实例在全卷生命周期内复用，不重新拉起。
    """

    def __init__(
        self,
        scheduler: Any,
        workspace: str | Path,
        *,
        paper_id: str = "default",
    ) -> None:
        self.scheduler = scheduler
        self.workspace = Path(workspace).resolve()
        self.paper_id = paper_id
        self.workspace.mkdir(parents=True, exist_ok=True)
        # 团队黑板：放 workspace 根目录（slot 外），由编排层写（绕过 write_file 沙箱）。
        self.board_path = self.workspace / "paper_state.md"
        self._init_board()

    # ── 黑板（团队级状态）──────────────────────────────────────

    def _init_board(self) -> None:
        """黑板不存在则建空表头。"""
        if not self.board_path.exists():
            self.board_path.write_text(_BOARD_HEADER, encoding="utf-8")

    def read_board(self) -> str:
        """供下题 design_direct 注入的已出题记录。"""
        return self.board_path.read_text(encoding="utf-8") if self.board_path.exists() else ""

    def append_board(self, slot_id: str, slot: dict[str, Any] | None = None, fallback_status: str = "") -> bool:
        """每题结束后，把 slot 内的 team_state_entry.md 追加到全卷黑板。

        两级来源（防漏写）：
          1. 优先读 slot 内 dual_review 写的 team_state_entry.md（沙箱内，agent 自写）。
          2. 若 agent 没写（needs_fix 时常见——它只顾写 review.md），编排层兜底：
             用 slot 元数据 + fallback_status（从 review.md 提取）自己拼一行。
        然后由编排层（Python 代码）搬运到 slot 外的黑板——绕过 write_file 沙箱。
        返回是否成功搬运。
        """
        entry = self.workspace / slot_id / "team_state_entry.md"
        line = ""
        if entry.exists():
            line = entry.read_text(encoding="utf-8").strip()
        if not line and slot is not None:
            # 兜底：编排层从 review status + slot 元数据自己生成一行
            st = fallback_status or "unknown"
            line = (
                f"| {slot_id} | {slot.get('primary_target_name', '')} | "
                f"{slot.get('question_type', '')} | K{slot.get('target_difficulty', '?')} | {st} |"
            )
        if not line:
            logger.warning("[%s] 无 entry 且无 slot 元数据，黑板未更新", slot_id)
            return False
        with open(self.board_path, "a", encoding="utf-8") as f:
            f.write(f"{line}\n")
        logger.info("[%s] 黑板已更新", slot_id)
        return True

    def _board_inject(self) -> dict[str, Path]:
        """构造 design_direct 的黑板注入项（仅在黑板非空时注入）。"""
        if self.board_path.exists() and self.read_board().strip() != _BOARD_HEADER.strip():
            return {"paper_state.md": self.board_path}
        return {}

    @staticmethod
    def _gen_exec_ok(slot_ws: Path) -> bool:
        """安全 exec gen.py，判断是否可执行（防 write_gen·fix 乱写后覆盖正确代码）。

        gen.py 应是可执行 Python（含 assert）。若被写成 markdown/非代码，exec 会抛 SyntaxError。
        """
        gen_path = slot_ws / "gen.py"
        if not gen_path.exists():
            return False
        src = gen_path.read_text(encoding="utf-8")
        # 快速门禁：gen.py 必须是 Python 代码，不能是 markdown（## 开头）
        stripped = src.lstrip()
        if stripped.startswith("#") and not stripped.startswith("#!"):
            # 可能是注释或被误写成 markdown（## status 这种）
            first_nonblank = next((ln for ln in src.splitlines() if ln.strip()), "")
            if first_nonblank.startswith("## "):
                logger.warning("gen.py 被误写成 markdown，首行: %s", first_nonblank[:50])
                return False
        try:
            import subprocess
            result = subprocess.run(
                ["python3", str(gen_path)],
                capture_output=True, text=True, timeout=30,
                cwd=str(slot_ws),
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception) as exc:
            logger.warning("gen.py exec 失败: %s", exc)
            return False

    # ── 单题意图卡片 ────────────────────────────────────────────

    @staticmethod
    def _intent_block(slot: dict[str, Any]) -> str:
        """把 slot 的设计意图字段拼成文本块，注入 design_card。"""
        parts = [
            f"- slot_id: {slot.get('slot_id', '')}",
            f"- 知识点: {slot.get('primary_target_name', '')}",
            f"- 科目: {slot.get('target_subject', '')}",
        ]
        if slot.get("examination_mode"):
            parts.append(f"- 考察模式(设计意图): {slot['examination_mode']}")
        if slot.get("teacher_annotation"):
            parts.append(f"- 教师批注(设计意图): {slot['teacher_annotation']}")
        if slot.get("k_dominant"):
            parts.append(f"- K主维度: {slot['k_dominant']} (难度{slot.get('target_difficulty', '?')})")
        if slot.get("difficulty_rationale"):
            parts.append(f"- 难度理由: {slot['difficulty_rationale']}")
        hc = slot.get("hard_constraints") or []
        if hc:
            parts.append("- 硬约束: " + "; ".join(hc))
        ct = slot.get("concept_topics") or []
        if ct:
            parts.append("- 概念考点列表: " + " | ".join(ct))
        return "\n".join(parts)

    def _write_design_card(self, slot: dict[str, Any]) -> Path:
        """落 design_card.md（slot 工作目录内，供 design_direct 读）。"""
        slot_id = slot["slot_id"]
        slot_ws = self.workspace / slot_id
        slot_ws.mkdir(parents=True, exist_ok=True)
        dc = (
            "# design_card\n## blueprint_contract\n```yaml\n"
            f"slot_id: {slot_id}\n"
            f"question_type: {slot.get('question_type', '')}\n"
            f"score: {slot.get('score', '')}\n"
            f"examination_mode: {slot.get('examination_mode', '')}\n"
            f"primary_target_name: {slot.get('primary_target_name', '')}\n"
            f"target_difficulty: {slot.get('target_difficulty', '')}\n"
            f"k_dominant: {slot.get('k_dominant', '')}\n"
            f"hard_constraints: {slot.get('hard_constraints', '')}\n"
            "```\n"
            f"## core_knowledge_intent\n{self._intent_block(slot)}\n"
            "## reference_questions\n（无）\n"
        )
        card_path = slot_ws / "design_card.md"
        card_path.write_text(dc, encoding="utf-8")
        return card_path

    # ── 计算题流水线（选择/综合/融合）──────────────────────────

    async def run_question(self, slot: dict[str, Any], label: str, timings: dict[str, float] | None = None) -> dict[str, Any]:
        """跑一道计算题：design_direct → write_gen → write_solution → dual_review(A代码/B文档)。

        选择题额外：write_gen 后派生干扰项。
        开头注入黑板（软提示去重），结尾搬运 entry 到黑板。
        返回该题的产出齐全度 + 耗时记录。
        """
        timings = timings if timings is not None else {}
        slot_id = slot["slot_id"]
        is_choice = slot.get("question_type") == "single_choice"
        slot_ws = self.workspace / slot_id
        print("\n" + "=" * 60, flush=True)
        print(f"{label}（{slot_id}，{'选择题+干扰项' if is_choice else '综合题'}）", flush=True)
        print("=" * 60, flush=True)

        card_path = self._write_design_card(slot)
        sched = self.scheduler

        # ① design_direct（注入黑板：已出题记录，软提示去重）
        inject = {"design_card": card_path}
        inject.update(self._board_inject())
        board_hint = " 参考注入的 paper_state.md（已出题记录），软性避开重复考点。" if self._board_inject() else ""
        t0 = time.monotonic()
        await sched.run_agent(
            "design_direct",
            task=f"根据 design_card 设计题干（含设计意图），写出 question.md。{board_hint}",
            slot_id=slot_id, inject_files=inject, target_file="question.md",
        )
        timings[f"{label}·design"] = time.monotonic() - t0
        print(f"  [design_direct] {timings[f'{label}·design']:.0f}s | question.md={'✓' if (slot_ws/'question.md').exists() else '✗'}", flush=True)

        # ② write_gen
        gen_task_extra = (
            " 写完 gen.py 后，若为选择题，用 exec 输出的正确值派生3个干扰项"
            "（真实计算错误：常见错误步骤的产物），填入 question.md 的 A/B/C/D（A=正确）。"
            if is_choice else ""
        )
        t0 = time.monotonic()
        await sched.run_agent(
            "write_gen",
            task=f"读 question.md 写 gen.py 并 exec 验证（关思考，按工作规范分步）。{gen_task_extra}",
            slot_id=slot_id,
            inject_files={"question.md": slot_ws / "question.md", "design_card": card_path},
            target_file="gen.py", enable_thinking=True,
        )
        timings[f"{label}·gen"] = time.monotonic() - t0
        genok = (slot_ws / "gen.py").exists()
        print(f"  [write_gen] {timings[f'{label}·gen']:.0f}s | gen.py={'✓' if genok else '✗'}", flush=True)

        # ③ write_solution
        solok = False
        if genok:
            t0 = time.monotonic()
            await sched.run_agent(
                "write_solution",
                task="读 gen.py + exec 输出，整理成 solution.md（不重算，忠实整理）。",
                slot_id=slot_id,
                inject_files={"gen.py": slot_ws / "gen.py", "question.md": slot_ws / "question.md"},
                target_file="solution.md",
            )
            timings[f"{label}·solution"] = time.monotonic() - t0
            solok = (slot_ws / "solution.md").exists()
            print(f"  [write_solution] {timings[f'{label}·solution']:.0f}s | solution.md={'✓' if solok else '✗'}", flush=True)

        # ④ dual_review A（审代码）→ [needs_fix 回退 1 轮] → B（审文档）
        #    code-as-truth 闭环：review 发现建模错误 → 回 write_gen 修 → 重审。
        #    安全网：修正前备份 gen.py，修正后若 exec 失败则恢复备份（防 write_gen 死循环末期乱写覆盖正确代码）。
        revok = False
        final_status = "skipped"
        if genok and solok:
            max_fix_rounds = 1  # 有限回退，防死循环
            sa = "needs_fix"
            for fix_round in range(max_fix_rounds + 1):
                round_suffix = "" if fix_round == 0 else f"·r{fix_round}"
                t0 = time.monotonic()
                ra = await sched.run_agent(
                    "dual_review",
                    task=(
                        "## 本轮阶段\n本轮审求解-代码（阶段2·A）。审 gen.py 建模思路对不对（看代码结构，不代入参数）。"
                        + ("\n\n## 上轮审核反馈\n按 review.md 的 fix_instructions 修正后重审。" if fix_round > 0 else "")
                    ),
                    slot_id=slot_id,
                    inject_files={"question.md": slot_ws / "question.md", "gen.py": slot_ws / "gen.py"},
                    target_file="review.md", enable_thinking=True,
                )
                review_path = slot_ws / "review.md"
                sa = status_of(ra, review_path=review_path)
                tkey = f"{label}·review_code{round_suffix}"
                timings[tkey] = time.monotonic() - t0
                print(f"  [review_code{round_suffix}] {timings[tkey]:.0f}s | status={sa}", flush=True)
                if sa == "pass" or fix_round >= max_fix_rounds:
                    break
                # needs_fix：先确认 review.md 确有 fix_instructions（防误触发）。
                # 用 parse_doc_section 而非字符串包含检查，可容忍 header 漂移
                # （## Fix-Instructions / ## fix-instructions 等均归一化命中）。
                # try/except 与上方 status_of 的防御风格对齐：缺文件不崩，按"无指令"处理。
                try:
                    has_fix = bool(parse_doc_section(review_path, "fix_instructions"))
                except (FileNotFoundError, OSError):
                    has_fix = False
                if not has_fix:
                    logger.warning("[%s] review needs_fix 但无 fix_instructions，跳过修正", slot_id)
                    break
                # 安全网：修正前备份 gen.py
                gen_path = slot_ws / "gen.py"
                gen_backup = slot_ws / "gen.py.bak"
                if gen_path.exists():
                    gen_backup.write_bytes(gen_path.read_bytes())
                t0 = time.monotonic()
                await sched.run_agent(
                    "write_gen",
                    task=(
                        "## 审核反馈需修正\n"
                        "review.md 已注入。**只读 `## fix_instructions` 区**——那是审核给出的最小修改指令"
                        "（修改对象/位置/当前问题/目标）。`## status`/`## findings`/`## routing` 是审核结论，"
                        "不是给你的修改指令，别照着 findings 自由发挥。\n"
                        "按 fix_instructions 逐条修正 gen.py，exec 验证 assert 通过。"
                        "`## keep_unchanged` 标注的部分一行都不许动。\n"
                        "**只改 fix_instructions 指出的位置，不要重写整个 gen.py。**"
                    ),
                    slot_id=slot_id,
                    inject_files={
                        "gen.py": gen_path,
                        "review.md": review_path,
                        "question.md": slot_ws / "question.md",
                    },
                    target_file="gen.py", enable_thinking=True,
                    preserve_existing=True,
                )
                timings[f"{label}·gen_fix"] = time.monotonic() - t0
                # 安全网：修正后若 gen.py 无法 exec（被乱写），恢复备份
                if not self._gen_exec_ok(slot_ws):
                    logger.warning("[%s] write_gen·fix 后 gen.py 无法执行，恢复备份", slot_id)
                    print(f"  [write_gen·fix] {timings[f'{label}·gen_fix']:.0f}s | ⚠️ gen.py 修正失败，恢复原版", flush=True)
                    if gen_backup.exists():
                        gen_path.write_bytes(gen_backup.read_bytes())
                else:
                    print(f"  [write_gen·fix] {timings[f'{label}·gen_fix']:.0f}s | gen.py 修正后重审", flush=True)
            final_status = sa

            if sa == "pass":
                t0 = time.monotonic()
                rb = await sched.run_agent(
                    "dual_review",
                    task="## 本轮阶段\n本轮审求解-文档（阶段2·B）。审 solution.md 是否忠实转写 gen.py（形式一致/抄写无误/无幻觉）。",
                    slot_id=slot_id,
                    inject_files={"gen.py": slot_ws / "gen.py", "solution.md": slot_ws / "solution.md"},
                    target_file="review.md",
                )
                timings[f"{label}·review_doc"] = time.monotonic() - t0
                revok = (slot_ws / "review.md").exists()
                sb = status_of(rb, review_path=slot_ws / "review.md")
                final_status = sb
                print(f"  [review_doc] {timings[f'{label}·review_doc']:.0f}s | status={sb}", flush=True)

        # ⑤ 搬运 entry 到全卷黑板（编排层兜底：needs_fix 时 agent 只写 review.md 没写 entry，编排层从 status 补）
        appended = self.append_board(slot_id, slot=slot, fallback_status=final_status)
        print(f"  [blackboard] entry={'✓' if appended else '✗'} | 黑板现有 {len(self.read_board().splitlines())} 行", flush=True)

        return {
            "slot_id": slot_id,
            "question": (slot_ws / "question.md").exists(),
            "gen": genok,
            "solution": solok,
            "review": revok,
        }

    # ── 概念题批量 ─────────────────────────────────────────────

    async def run_concept_batch(self, concept_slots: list[dict[str, Any]], timings: dict[str, float] | None = None) -> dict[str, Any]:
        """概念题批量：收集所有 concept slot 的考点，一次调用 concept_creator。

        同样注入黑板 + 结尾搬运 entry。
        """
        import asyncio  # noqa: F401  (保留给后续并发优化)
        timings = timings if timings is not None else {}
        print("\n" + "=" * 60, flush=True)
        print(f"概念题批量（{len(concept_slots)} 个 slot 合并一次出）", flush=True)
        print("=" * 60, flush=True)
        sched = self.scheduler

        all_topics: list[str] = []
        intent_parts: list[str] = []
        for s in concept_slots:
            all_topics.extend(s.get("concept_topics") or [s.get("primary_target_name", "")])
            intent_parts.append(self._intent_block(s))
        slot_id = concept_slots[0]["slot_id"] if concept_slots else "Q_CONCEPT"
        slot_ws = self.workspace / slot_id
        slot_ws.mkdir(parents=True, exist_ok=True)
        (slot_ws / "blueprint.md").write_text(
            "# 蓝图\n## 考点列表\n" + "\n".join(f"- {t}" for t in all_topics)
            + "\n\n## 设计意图\n" + "\n\n".join(intent_parts),
            encoding="utf-8",
        )

        # 概念题也注入黑板（避免概念题之间重复）
        inject = {"蓝图": slot_ws / "blueprint.md"}
        inject.update(self._board_inject())

        t0 = time.monotonic()
        await sched.run_agent(
            "concept_creator",
            task=(
                f"读 blueprint 考点列表，对每个考点出1道概念题（共{len(all_topics)}道），"
                "write question.md + solution.md。"
                + (" 参考 paper_state.md 已出题，避开重复考点。" if self._board_inject() else "")
            ),
            slot_id=slot_id, inject_files=inject, target_file="question.md",
        )
        timings["概念题批量"] = time.monotonic() - t0
        qok = (slot_ws / "question.md").exists()
        n = open(slot_ws / "question.md").read().count("## 第") if qok else 0
        print(f"  [concept_creator] {timings['概念题批量']:.0f}s | question.md={'✓' if qok else '✗'} | 产出{n}道", flush=True)

        if qok:
            t0 = time.monotonic()
            r = await sched.run_agent(
                "review",
                task=(
                    "§21 概念题审核：事实性检查+设计缺陷。逐题布尔判断"
                    "（答案对不对/干扰项是否真实认知错误/有无设计缺陷），不展开推演。"
                    "用 write_file 写 review.md（## status + 逐题理由）。"
                ),
                slot_id=slot_id,
                inject_files={"题目": slot_ws / "question.md", "解析": slot_ws / "solution.md"},
                target_file="review.md",
            )
            timings["概念题审核"] = time.monotonic() - t0
            concept_status = status_of(r, review_path=slot_ws / "review.md")
            print(f"  [review] {timings['概念题审核']:.0f}s | status={concept_status}", flush=True)
        else:
            concept_status = "no_question"

        # 搬运 entry（编排层兜底：从 slot 元数据 + review status 生成）
        concept_slot_meta = {
            "slot_id": slot_id,
            "primary_target_name": f"概念题批量({n}道)",
            "question_type": "conceptual",
            "target_difficulty": "-",
        }
        self.append_board(slot_id, slot=concept_slot_meta, fallback_status=concept_status)
        return {
            "slot_id": slot_id,
            "question": qok,
            "solution": (slot_ws / "solution.md").exists(),
            "review": (slot_ws / "review.md").exists(),
        }
