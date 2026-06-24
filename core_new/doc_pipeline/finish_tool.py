"""FinishTool — agent 自声明本轮完成，通知系统接管（新范式）。

旧范式：scheduler 检测 agent 写了 target 文件即判定完成（文件当闸门）。
新范式：完成由 agent 自己决定 —— 产出齐备且有信心时，调用 finish 通知系统
"本轮结束"。scheduler 见到 finish 即 break，不再用文件产出强迫 agent。
系统只在「agent 通知完成」或「越界（跑飞/卡死/产物缺）」时介入。

finish 带 self-assessment（status + summary），供节点做边界核对：
agent 说 finish 了但产物缺 = 越界 → 退回让 agent 重写（不 fail，max_attempts 用尽才 fail）。

本工具无副作用，纯信号。
"""

from __future__ import annotations

import json
from typing import Any

from core_new.agent_runtime.base import Tool


class FinishTool(Tool):
    """Agent calls this to declare the round complete and hand off to the system.

    No side effects — purely a completion signal. The scheduler breaks the
    agent loop on this call (precedence over file-write completion). Carries
    an optional self-assessment so the orchestrator node can verify artifacts
    afterwards (finish declared but artifact missing = boundary violation).
    """

    @property
    def name(self) -> str:
        return "finish"

    @property
    def description(self) -> str:
        return (
            "完成本轮全部产出后调用此工具通知系统：本轮结束，交回系统接管（审核/下一阶段）。"
            "只有当你确信所有目标产出都已就绪（如 gen.py 已 exec 验证通过、solution.md 已写、"
            "question.md 已更新）时才调用。status 固定填 done；summary 简述你本轮产出了什么。"
            "调用后无需再做任何操作。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["done"],
                    "description": "完成状态，本轮完成填 done",
                },
                "summary": {
                    "type": "string",
                    "description": "本轮产出摘要：产出了哪些文件、exec 是否通过、关键结论（供系统核对）",
                },
            },
            "required": ["status"],
        }

    async def execute(self, status: str = "done", summary: str = "") -> str:
        return json.dumps(
            {"ok": True, "finished": True, "status": status, "summary": summary or ""},
            ensure_ascii=False,
        )
