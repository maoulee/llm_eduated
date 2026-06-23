"""§22.7 后续项 #2: team_pipeline 四角色 × glm5.2_anthropic 端到端实测。

验证 §21 思考控制统一 + §22 team_pipeline 四角色 graph 在 glm5.2 上：
  - design_direct(write stem) → write_gen(model+gen.py) → write_solution(transcribe)
      → dual_review_code → (needs_fix→write_gen / pass→dual_review_doc) → final
  - 全角色路由 glm5.2_anthropic（reasoning_effort 按 role: design/solve=high, review=low/high）

只跑 1 题（comprehensive, AVL — 与既有 baseline 同题，便于横向比质量）。

用法:
  python scripts/test_team_pipeline_glm52.py
  # GLM key 来自 /zhaoshu/llm_eduated/.env；proxy 6666 已在 shell env（HTTP(S)_PROXY）
"""
import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 1) 加载运营环境（GLM key）。proxy 6666 由 shell env 注入，httpx 自动走。
from dotenv import load_dotenv
for _env in ("/zhaoshu/llm_eduated/.env", str(ROOT / ".env")):
    if Path(_env).exists():
        load_dotenv(_env)

from core_new.doc_pipeline import pipeline_config as _pcfg
from core_new.doc_pipeline import DocPipeline
from core_new.llm_gateway import get_gateway

# 2) 强制 team_pipeline=true —— 仅本测试进程。
#    关键：orchestrator._should_use_team_pipeline() 通过 load_pipeline_config()
#    （每次重新读 yaml）取值，而非 PIPELINE_CONFIG 单例。所以必须 patch
#    load_pipeline_config 本身，改 PIPELINE_CONFIG 无效（这正是 §21.0 警告的
#    "配置层以为开了、运行层静默没生效"陷阱）。不碰共享 pipeline.yaml，
#    避免影响正在运行的 API 服务。
_orig_load = _pcfg.load_pipeline_config


def _force_team(*args, **kwargs):
    cfg = _orig_load(*args, **kwargs)
    try:
        cfg.params.features["enable_team_pipeline"] = True
    except Exception:
        pass
    return cfg


_pcfg.load_pipeline_config = _force_team

OUTPUT_DIR = Path("docs/test_output/team_pipeline_glm52") / time.strftime("%Y%m%dT%H%M%S")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ASSEMBLED_PATH = ROOT / "docs" / "compose" / "Q41_assembled.md"  # AVL 平衡二叉树

SLOT_DATA = {
    "slot_id": "Q41_TEAM_GL52",
    "subject": "数据结构",
    "knowledge_tag": "DS-5 > 树与二叉树 > 平衡二叉树AVL",
    "primary_target_name": "平衡二叉树AVL的插入与旋转",
    "target_difficulty": "hard",
    "examination_mode": "结构操作与状态维护模拟",
    "difficulty": "hard",
    "question_type": "comprehensive",
}


async def main():
    print("=" * 70)
    print("  team_pipeline × glm5.2_anthropic — 1 题 e2e (comprehensive, AVL)")
    print("=" * 70)
    print(f"  GLM_API_KEY: {'SET' if os.getenv('GLM_API_KEY') else 'MISSING'}")
    print(f"  HTTPS_PROXY: {os.getenv('HTTPS_PROXY', '(none)')}")
    _feat = _force_team().params.features
    print(f"  enable_team_pipeline (forced in-process): {_feat.get('enable_team_pipeline')}")
    print(f"  output: {OUTPUT_DIR}")

    if not ASSEMBLED_PATH.exists():
        print(f"  ✗ assembled doc missing: {ASSEMBLED_PATH}")
        return 1
    assembled = ASSEMBLED_PATH.read_text(encoding="utf-8")
    print(f"  assembled doc: {len(assembled)} chars")

    gateway = get_gateway("glm5.2_anthropic")
    dp = DocPipeline(
        gateway=gateway,
        workspace=str(OUTPUT_DIR),
        model_routing={"_default": "glm5.2_anthropic"},
        enable_thinking=True,
    )

    t0 = time.time()
    try:
        result = await dp.run(
            SLOT_DATA["slot_id"],
            SLOT_DATA,
            assembled_experience_doc=assembled,
            question_type="comprehensive",
        )
    except Exception as e:
        import traceback
        print(f"\n  ✗ RUN FAILED after {time.time()-t0:.1f}s: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 2

    dt = time.time() - t0
    print("\n" + "=" * 70)
    print(f"  RESULT: ok={getattr(result, 'ok', None)}  ({dt:.1f}s)")
    print("=" * 70)
    if hasattr(result, "final_content") and result.final_content:
        print(f"  final.md length: {len(result.final_content)} chars")
    if hasattr(result, "files"):
        print(f"  files: {list(result.files.keys()) if result.files else '—'}")

    # dump 关键产物（质量审阅用）
    print(f"\n  artifacts under {OUTPUT_DIR}:")
    for sub in ("", "Q41_TEAM_GL52"):
        base = OUTPUT_DIR / sub if sub else OUTPUT_DIR
        for name in ("question.md", "gen.py", "solve.py", "solution.md",
                     "review.md", "review2.md", "final.md", "solve_output.txt"):
            f = base / name
            if f.exists():
                txt = f.read_text(encoding="utf-8", errors="ignore")
                print(f"    {f.relative_to(OUTPUT_DIR)}: {len(txt)} chars")
    return 0 if getattr(result, "ok", False) else 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
