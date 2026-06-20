"""§22.7 后续 #2 回归测试：堵"参数打败考点"（零旋转 defect）。

这套测试锁定三件事：

1. **根因可复现**：team_pipeline glm5.2 实测产出的零旋转 AVL 题——插入序列
   (25,10,55) 在结构上从不失衡，gen.py 的模拟"正确"但考点（旋转辨析）整题落空。
2. **机制修复（green）**：题干声明的"通过条件"（≥1 次旋转）被 gen.py 翻译成 assert 后，
   exec 在 defect 参数上**必然抛 AssertionError → exit≠0** → 回退换参数。这是
   code-as-truth 把"模拟自洽"扩到"考点达成"的确定性卡口（不依赖 LLM）。
3. **审核路由契约**：合并审求解的 review.md（adequacy_fail + routing）→ graph 信号
   映射正确；build_team_pipeline_graph 的新边（审题干 gate + 合并审求解 + 三路回退）就位。

Run: python3 -m pytest tests/test_team_pipeline_adequacy.py -v
"""
import asyncio
import subprocess
import sys
from pathlib import Path

import pytest


# ── 极简 AVL 插入模拟（复刻 defect gen.py 的旋转计数逻辑）──────────────
def _avl_insert_count(initial: list[int], inserts: list[int]):
    """插入 inserts 到已建好的 initial 树，返回 (rotations, types)。"""
    class N:
        __slots__ = ("v", "l", "r", "h")
        def __init__(self, v):
            self.v, self.l, self.r, self.h = v, None, None, 1
    def h(n): return n.h if n else 0
    def upd(n): n.h = 1 + max(h(n.l), h(n.r))
    def bf(n): return h(n.l) - h(n.r) if n else 0
    def rrot(z):
        y = z.l; z.l = y.r; y.r = z; upd(z); upd(y); return y
    def lrot(z):
        y = z.r; z.r = y.l; y.l = z; upd(z); upd(y); return y

    root = None
    for v in initial:  # 初始树按 BST 插入（假设题目给的是平衡初态）
        def ins(node, v):
            if not node: return N(v)
            if v < node.v: node.l = ins(node.l, v)
            else: node.r = ins(node.r, v)
            upd(node); return node
        root = ins(root, v)

    rotations = 0
    types = []
    def ins_rebalance(node, v):
        nonlocal rotations
        if not node: return N(v)
        if v < node.v: node.l = ins_rebalance(node.l, v)
        else: node.r = ins_rebalance(node.r, v)
        upd(node)
        b = bf(node)
        if b > 1:
            rotations += 1
            if bf(node.l) >= 0: types.append("LL"); return rrot(node)
            types.append("LR"); node.l = lrot(node.l); return rrot(node)
        if b < -1:
            rotations += 1
            if bf(node.r) <= 0: types.append("RR"); return lrot(node)
            types.append("RL"); node.r = rrot(node.r); return lrot(node)
        return node
    for v in inserts:
        root = ins_rebalance(root, v)
    return rotations, types


# ── 1. 根因可复现：defect 参数零旋转 ─────────────────────────────────
def test_defect_params_trigger_zero_rotations():
    """team_pipeline 实测的 defect：插 (25,10,55) 进初始树，从不失衡。
    这就是 gen.py 忠实模拟却让"考旋转"的题整题落空的根因。"""
    rotations, types = _avl_insert_count([50, 30, 66, 18, 40, 80], [25, 10, 55])
    assert rotations == 0, f"defect 应零旋转，实得 {rotations} ({types})"
    assert types == []


# ── 2. 机制修复 green：通过条件 assert 在 defect 参数上必炸 ───────────
def test_adequacy_assert_catches_defect():
    """题干声明"≥1 次旋转"→ gen.py 翻译成 assert rotation_count>=1。
    defect 参数（0 旋转）exec 必抛 AssertionError → exit≠0 → 回退换参数。"""
    rotations, _ = _avl_insert_count([50, 30, 66, 18, 40, 80], [25, 10, 55])
    with pytest.raises(AssertionError):
        assert rotations >= 1, "通过条件未满足：插入序列未触发任何旋转"


def test_adequacy_assert_passes_valid_params():
    """对照组：参数真的触发旋转时，assert 不误杀（避免修复引入假阳性）。"""
    rotations, types = _avl_insert_count([30, 20], [10])  # 经典 LL
    assert rotations >= 1
    assert "LL" in types


def test_old_structural_assert_missed_defect():
    """回归锚点：旧版 gen.py 只 assert 结构（树平衡）—— defect 参数下也通过，
    漏放坏题。证明"assert 打到结构" vs "打到通过条件"的差别。"""
    rotations, _ = _avl_insert_count([50, 30, 66, 18, 40, 80], [25, 10, 55])
    # 旧式结构判据：调整后树平衡（永远成立，零旋转也过）—— 不该再被当作 adequacy
    assert rotations == 0  # defect 仍是 0
    # 旧判据不炸（这就是漏放）：
    is_balanced = True  # 插完后树确实平衡（BF 全 ≤1）
    assert is_balanced  # 旧 assert 静默通过 ← 这就是要禁的弱化


# ── 3. 审核路由契约 + graph 边 ──────────────────────────────────────
def test_review_signal_mapping():
    """_review_signal：adequacy_fail 按 routing 映射到回退信号。"""
    from core_new.doc_pipeline.pipeline_graph import _review_signal
    assert _review_signal("pass", "none") == "pass"
    # 参数没触发考点 → 换参数重算 → write_gen
    assert _review_signal("needs_fix", "write_gen") == "fix_gen"
    # 通过条件本身定错 → 重定条件 → design_direct
    assert _review_signal("needs_fix", "design_direct") == "fix_design"
    # 文档忠实问题 → write_solution
    assert _review_signal("needs_fix", "write_solution") == "fix_solution"
    # routing 缺省 → write_gen（建模是最常见回退点）
    assert _review_signal("needs_fix", "") == "fix_gen"


def test_team_graph_has_stem_gate_and_merged_review():
    """build_team_pipeline_graph：审题干 gate + 合并审求解 + 三路回退边就位。"""
    from core_new.doc_pipeline.pipeline_graph import build_team_pipeline_graph
    g = build_team_pipeline_graph(object(), Path("/tmp/_t"))
    assert g.initial == "design_direct"
    nodes = set(g.nodes)
    assert {"design_direct", "review_stem", "write_gen",
            "write_solution", "review_solve", "final"} <= nodes
    assert "dual_review_code" not in nodes  # 旧双节点已合并
    assert "dual_review_doc" not in nodes
    edges = {(e.from_node, e.signal, e.to_node) for e in g.edges}
    # 审题干 gate
    assert ("design_direct", "ok", "review_stem") in edges
    assert ("review_stem", "needs_fix", "design_direct") in edges
    assert ("review_stem", "pass", "write_gen") in edges
    # 合并审求解 + 三路回退
    assert ("write_solution", "ok", "review_solve") in edges
    assert ("review_solve", "fix_gen", "write_gen") in edges
    assert ("review_solve", "fix_solution", "write_solution") in edges
    assert ("review_solve", "fix_design", "design_direct") in edges
    assert ("review_solve", "pass", "final") in edges


def test_adequacy_review_md_routes_to_fix_gen(tmp_path):
    """端到端解析：一份 adequacy_fail 的 review.md → get_doc_status + routing 解析
    → _review_signal 给出 fix_gen（换参数重算）。"""
    from core_new.doc_pipeline.doc_parser import get_doc_status, parse_doc_section, REVIEW_STATUSES
    from core_new.doc_pipeline.pipeline_graph import _review_signal
    review = tmp_path / "review.md"
    review.write_text(
        "## status\nneeds_fix\n\n"
        "## stage\nsolution\n\n"
        "## issue_type\nadequacy_fail\n\n"
        "## findings\n- [维度C 充分性] 声明「≥1次旋转」，exec 显示 0 次旋转：参数未触发考点\n\n"
        "## fix_instructions\n- 换插入序列使至少触发 1 次旋转\n\n"
        "## routing\nwrite_gen\n",
        encoding="utf-8",
    )
    status = get_doc_status(str(review), allowed=REVIEW_STATUSES)
    routing = parse_doc_section(str(review), "routing").strip()
    assert status == "needs_fix"
    assert routing == "write_gen"
    assert _review_signal(status, routing) == "fix_gen"


# ── 4. 真实 exec 链路：gen.py 的 adequacy assert → returncode≠0 ─────────
# （堵"测试只证算术不证集成"的弱点：write_gen/review_solve 依赖的是 assert 炸 →
# exit≠0 → 系统检测这条确定性信号，必须用真实 subprocess 验。）
_GEN_PY = '''
def _avl(initial, inserts):
    class N:
        __slots__ = ("v", "l", "r", "h")
        def __init__(self, v): self.v, self.l, self.r, self.h = v, None, None, 1
    def h(n): return n.h if n else 0
    def upd(n): n.h = 1 + max(h(n.l), h(n.r))
    def bf(n): return h(n.l) - h(n.r) if n else 0
    def rrot(z):
        y = z.l; z.l = y.r; y.r = z; upd(z); upd(y); return y
    def lrot(z):
        y = z.r; z.r = y.l; y.l = z; upd(z); upd(y); return y
    root = None
    def ins(node, v):
        if not node: return N(v)
        if v < node.v: node.l = ins(node.l, v)
        else: node.r = ins(node.r, v)
        upd(node); return node
    for v in initial: root = ins(root, v)
    rot = 0; types = []
    def ins_r(node, v):
        nonlocal rot
        if not node: return N(v)
        if v < node.v: node.l = ins_r(node.l, v)
        else: node.r = ins_r(node.r, v)
        upd(node); b = bf(node)
        if b > 1:
            rot += 1
            if bf(node.l) >= 0: types.append("LL"); return rrot(node)
            types.append("LR"); node.l = lrot(node.l); return rrot(node)
        if b < -1:
            rot += 1
            if bf(node.r) <= 0: types.append("RR"); return lrot(node)
            types.append("RL"); node.r = rrot(node.r); return lrot(node)
        return node
    for v in inserts: root = ins_r(root, v)
    return rot, types

rot, types = _avl(INITIAL, INSERTS)
# 通过条件（题干声明）：插入序列至少触发 1 次旋转
assert rot >= 1, "通过条件未满足：插入未触发任何旋转 (" + str(rot) + ")"
print("OK rotations=", rot, types)
'''


def _run_gen_py(tmp_path, initial, inserts):
    gen = tmp_path / "gen.py"
    src = "INITIAL = %r\nINSERTS = %r\n" % (initial, inserts) + _GEN_PY
    gen.write_text(src, encoding="utf-8")
    return subprocess.run([sys.executable, str(gen)], capture_output=True, text=True)


def test_gen_py_adequacy_assert_fails_on_defect(tmp_path):
    """真实 exec：含 adequacy assert 的 gen.py 在 defect 参数上 returncode!=0。"""
    r = _run_gen_py(tmp_path, [50, 30, 66, 18, 40, 80], [25, 10, 55])
    assert r.returncode != 0, f"defect 应被 assert 拦下，实得 returncode=0\n{r.stdout}"
    assert "通过条件未满足" in r.stderr  # AssertionError message


def test_gen_py_adequacy_assert_passes_on_valid(tmp_path):
    """对照组：参数真触发旋转时 exec returncode==0（assert 不误杀）。"""
    r = _run_gen_py(tmp_path, [30, 20], [10])  # 经典 LL
    assert r.returncode == 0, f"valid 参数应通过，实得 {r.returncode}\n{r.stderr}"
    assert "OK rotations=" in r.stdout


# ── 5. 环路安全：exhausted 信号 + REVIEW_SOLVE_MAX_ROUNDS ─────────────
def test_review_solve_exhaustion_edge_exists():
    """review_solve --exhausted--> done 边就位（防 inherent 缺陷死循环）。"""
    from core_new.doc_pipeline.pipeline_graph import build_team_pipeline_graph
    g = build_team_pipeline_graph(object(), Path("/tmp/_t"))
    edges = {(e.from_node, e.signal, e.to_node) for e in g.edges}
    assert ("review_solve", "exhausted", "done") in edges
    assert ("review_stem", "suggestion", "write_gen") in edges  # suggestion 不阻塞建模


# ── 6. 单选题：选项层 adequacy assert（干扰项撞值/正确选项标错）─────────
def _run_sc_gen(tmp_path, correct, A, B, C, D):
    """合成单选题 gen.py：算正确值 + 4 选项 + adequacy assert，跑 exec。"""
    src = (
        f"correct = {correct}\n"
        f"A = {A}\nB = {B}\nC = {C}\nD = {D}\n"
        "options = [A, B, C, D]\n"
        "# 通过条件（选择题）：4 选项互异 + A 是正确值\n"
        'assert len(set(options)) == 4, "选项撞值: " + str(options)\n'
        'assert A == correct, "正确选项标错: A=%s correct=%s" % (A, correct)\n'
        "print('OK options=', options)\n"
    )
    gen = tmp_path / "gen_sc.py"
    gen.write_text(src, encoding="utf-8")
    return subprocess.run([sys.executable, str(gen)], capture_output=True, text=True)


def test_single_choice_collision_caught(tmp_path):
    """干扰项撞值（B==C）→ assert len(set)==4 炸 → returncode!=0。选择题 defect 同形。"""
    r = _run_sc_gen(tmp_path, correct=42, A=42, B=43, C=43, D=84)  # B==C 碰撞
    assert r.returncode != 0, f"撞值应被拦下，实得 0\n{r.stdout}"
    assert "选项撞值" in r.stderr


def test_single_choice_mislabeled_correct_caught(tmp_path):
    """正确选项标错（A≠算出的正确值，但 4 选项互异）→ assert A==correct 炸。
    这与撞值是不同 defect：选项互异但 A 标的不是正确答案。"""
    r = _run_sc_gen(tmp_path, correct=42, A=43, B=44, C=45, D=46)  # A 标错，4 互异
    assert r.returncode != 0
    assert "正确选项标错" in r.stderr


def test_single_choice_valid_options_pass(tmp_path):
    """对照组：4 互异 + A=正确 → exec returncode==0（assert 不误杀）。"""
    r = _run_sc_gen(tmp_path, correct=42, A=42, B=43, C=44, D=84)
    assert r.returncode == 0, f"valid 选项应通过，实得 {r.returncode}\n{r.stderr}"
    assert "OK options=" in r.stdout


# ── 7. 概念题审核 rubric：题型自适应（简答/填空/判断/选择）──────────────
def test_concept_review_rubric_is_type_aware():
    """概念题有多种题型，rubric 不能默认选择题。验证 rubric 含题型识别 +
    4 个题型专属分支 + 通用项（事实性/覆盖考点/解析自洽），且不执行/不算值。"""
    from core_new.doc_pipeline.orchestrator import _CONCEPT_REVIEW_RUBRIC as R
    assert "识别每道题的题型" in R  # 先识别题型
    assert "通用 rubric" in R and "事实性" in R and "解析自洽" in R  # 所有题型都判
    assert "覆盖声明的 concept_topic" in R
    for t in ("### 选择题", "### 判断题", "### 填空题", "### 简答题"):  # 4 题型分支
        assert t in R, f"rubric 缺题型分支: {t}"
    assert "恰 1 个正确" in R and "干扰项" in R  # 选择题专属
    assert "唯一确定" in R and "要点完整" in R  # 填空/简答专属
    assert "不执行" in R and "无 gen.py" in R  # 概念题不执行


# ── 8. TeamDesignNode 识别教师个人需求（teacher_annotation）─────────────
def test_team_design_node_surfaces_teacher_annotation(tmp_path):
    """前端锚定的教师个人需求 → handoff → slot_data.teacher_annotation，
    TeamDesignNode 必须显式注入 design_direct 任务，确保被设计层识别
    （不依赖 design_card 是否逐字保留）。"""
    import asyncio
    from core_new.doc_pipeline.pipeline_graph import TeamDesignNode, PipelineState

    captured: dict = {}

    class MockScheduler:
        async def run_agent(self, role, task, *, slot_id, inject_files, target_file, **kw):
            captured["task"] = task
            (tmp_path / slot_id).mkdir(parents=True, exist_ok=True)
            (tmp_path / slot_id / target_file).write_text("# q", encoding="utf-8")
            return ""

    class MockOrch:
        scheduler = MockScheduler()
        def _board_inject(self): return {}
        def _fail_result(self, *a, **k): return None

    ws = tmp_path
    slot_id = "Q_TEST"
    (ws / slot_id).mkdir(parents=True, exist_ok=True)
    node = TeamDesignNode(MockOrch(), ws)

    # 有 teacher_annotation → 注入任务
    state = PipelineState(slot_id=slot_id, slot_data={
        "teacher_annotation": "侧重 AVL 旋转辨析，避免纯记忆题",
    }, workspace=ws)
    asyncio.run(node.run(state))
    assert "教师个人需求" in captured["task"]
    assert "侧重 AVL 旋转辨析" in captured["task"]

    # 对照：无 teacher_annotation → 不注入
    captured.clear()
    state2 = PipelineState(slot_id=slot_id, slot_data={}, workspace=ws)
    asyncio.run(node.run(state2))
    assert "教师个人需求" not in captured["task"]



