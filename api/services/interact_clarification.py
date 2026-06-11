"""Scenario C clarification interception and GLM outline generation.

Extracted from InteractV2Service to isolate the heuristics and LLM calls
for free-composition paper requests (Scenario C).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class ClarificationHandler:
    """Scenario C clarification interception and GLM outline generation."""

    @classmethod
    def needs_clarification(cls, message: str) -> bool:
        """Return True when a free-compose paper request lacks structure."""
        return cls.looks_like_scenario_c(message) and not cls.has_structure(message)

    @staticmethod
    def looks_like_scenario_c(message: str) -> bool:
        """Heuristic: message looks like free composition (Scenario C).

        Scenario C = teacher gives subject + exam type but NO specific topic
        and NO 408/experience card keywords.
        """
        text = message.strip()
        if not text or len(text) < 4:
            return False
        # Scenario A keywords → NOT C
        if re.search(r"408|模拟卷|考研模拟题组卷|Q\d+|组成原理卷", text):
            return False
        # Scenario B keywords → NOT C
        if re.search(r"^一[道道]|^单[题道]|AVL|旋转|Cache映射|^考\s", text):
            return False
        # C keywords: subject + exam type, no specific topic
        c_patterns = [
            r"期末", r"期中", r"自由", r"套卷", r"一套.*卷",
            r"数据结构.*卷", r"组成原理.*卷", r"操作系统.*卷",
            r"计算机网络.*卷", r"出.*[0-9]+道", r"[0-9]+道选择",
            r"自由出题", r"先规划",
        ]
        return bool(re.search("|".join(c_patterns), text))

    @staticmethod
    def has_structure(message: str) -> bool:
        """Detect whether the teacher supplied enough paper structure."""
        text = message.strip()
        if not text:
            return False
        cn_num = "一二两三四五六七八九十"
        has_count = bool(
            re.search(rf"(\d+|[{cn_num}]+)\s*(题|道|个|小题)", text)
            or re.search(rf"(选择|填空|判断|简答|算法|综合|应用|计算|论述|证明)\s*(题)?\s*(\d+|[{cn_num}]+)", text)
            or re.search(rf"(\d+|[{cn_num}]+)\s*(道|个)?\s*(选择|填空|判断|简答|算法|综合|应用|计算|论述|证明)", text)
        )
        type_terms = ("选择", "填空", "判断", "简答", "算法", "综合", "应用", "计算", "论述", "证明", "题型")
        has_type_mix = any(term in text for term in type_terms)
        return has_count and has_type_mix

    @staticmethod
    def merge_requirements(previous: str, latest: str) -> str:
        """Combine initial free-compose intent with later structure details."""
        previous = previous.strip()
        latest = latest.strip()
        if not previous:
            return latest
        if not latest:
            return previous
        return f"{previous}\n教师补充：{latest}"

    @staticmethod
    def clarification_message(requirements: str) -> str:
        """Ask for only the paper-structure fields needed before draft generation."""
        subject = "这门课"
        for candidate in ("数据结构", "组成原理", "计算机组成原理", "操作系统", "计算机网络"):
            if candidate in requirements:
                subject = candidate
                break
        return (
            f"可以。我先确认一下 {subject} 试卷结构，再生成第一轮粗粒度草案："
            "请补充题量和题型结构，最好再说明总分/难度。"
            "例如：`12题，5道选择、3道填空、2道简答、2道算法题，总分100，中等偏难，覆盖主要章节`。"
        )

    @staticmethod
    async def pregenerate_outline(user_requirements: str) -> str:
        """Call GLM-5.1 to generate a knowledge-based outline for Scenario C.

        Reads the KG file for the detected subject, calls GLM-5.1 with a
        structured prompt, and returns the outline text.
        """
        from core_new.llm_gateway import get_gateway

        # Detect subject from message
        subject_map = {
            "数据结构": "data_structure",
            "组成原理": "computer_organization",
            "计算机组成": "computer_organization",
            "操作系统": "operating_system",
            "计算机网络": "computer_network",
        }
        subject_cn = None
        for cn_name in subject_map:
            if cn_name in user_requirements:
                subject_cn = cn_name
                break
        if not subject_cn:
            subject_cn = "数据结构"  # default

        # Load KG
        kg_path = Path(f"data/kg/{subject_cn}.md")
        kg_context = ""
        if kg_path.exists():
            kg_context = kg_path.read_text(encoding="utf-8")[:6000]
        if not kg_context:
            logger.warning("KG not found for subject: %s", subject_cn)
            return ""

        # Build prompt for the coarse first-round plan.
        prompt = f"""基于以下知识点图谱，为一套考试规划第一轮粗粒度题位草案。
只输出粗知识域/章节候选和题型建议，不要展开最终考察方式，不要写题目。

教师要求: {user_requirements}

知识点图谱:
{kg_context}

输出格式（markdown表格）:
| 题号 | 建议题型 | 粗知识域候选 | 覆盖理由 | 难度(1-5) |

要求:
- 知识点必须来自上面的知识点图谱
- 粗知识域候选要偏大粒度，例如"线性表""树和二叉树""图""排序""查找"
- 每个题位给 2-4 个可选粗知识域，供教师第一轮选择
- 题型按教师给出的题型结构分配；如果结构不完整，给出可调整的建议题型
- 确保知识点覆盖主要知识域，避免连续多题考同一知识点
- 难度1-5，整体偏中等"""

        try:
            gateway = get_gateway("glm5.1")
            messages = [{"role": "user", "content": prompt}]
            result = await gateway.stream_chat(messages, max_tokens=4000)
            return result or ""
        except Exception as exc:
            logger.warning("GLM outline pre-generation failed: %s", exc)
            return ""
