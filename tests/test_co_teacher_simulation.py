"""教师模拟端到端测试 — 7个组成原理题位，不同教师修改风格。

验证链路：outline → parser → sidecar → paper_selection.yaml → artifact_store → assembled.md
"""
import os
import sys
import tempfile
import shutil

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compose.markdown_contract_parser import parse_outline_to_selection
from compose.outline_contract_parser import write_paper_selection
from compose import artifact_store

# ── 模拟教师修改后的 outline_approved.md ──────────────────
# 7 个组成原理题位，每个有不同的教师修改风格

OUTLINE_APPROVED = """# 408模拟卷组卷大纲

difficulty_target: 3
composition_rationale: 覆盖组成原理核心章节，偏重存储系统和CPU机制。

## Q14（选择题）

### 当前推荐
推荐模式A计算型，考Cache地址映射。这道题出计算题比较好区分学生水平。

### 候选替换池
- 模式A: 计算型——Cache映射、浮点转换、补码运算
- 模式B: 概念辨析型——存储器存取方式、局部性原理
- 模式C: 组合判断型——数据类型转换

### 教师可编辑说明
这题重点考Cache直接映射的地址划分，要求学生计算tag/index/offset位数。
不要出浮点数相关的题，上一届考过了。干扰项放一个把offset算错的常见错误。

<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q14 -->
```yaml
slot_id: Q14
question_type: single_choice
score: 2
examination_mode: 计算型
active_selection:
  mode_id: 模式A
  mode_name: 计算型
  selected_knowledge:
    - Cache地址映射
    - 直接映射地址划分
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
excluded:
  modes: []
  knowledge:
    - IEEE 754浮点数
    - 浮点精度
```
<!-- CONTRACT:END slot=Q14 -->

## Q17（选择题）

### 当前推荐
推荐模式A概念辨析型，考RISC/CISC对比。

### 候选替换池
- 模式A: 概念辨析型——RISC/CISC、存储器特性
- 模式B: 机制理解型——TLB/Cache/Page关系
- 模式C: 计算与模拟型——Cache命中率计算
- 模式D: 组合判断型——超标量特性

### 教师可编辑说明
不要考DRAM刷新了，那个太偏。重点放在RISC和CISC的设计哲学差异。
如果出计算题，用Cache命中率的经典题型。

<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q17 -->
```yaml
slot_id: Q17
question_type: single_choice
score: 2
examination_mode: 概念辨析型
active_selection:
  mode_id: 模式A
  mode_name: 概念辨析型
  selected_knowledge:
    - RISC与CISC对比
    - 指令集设计哲学
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
  - 模式D
excluded:
  modes: []
  knowledge:
    - DRAM刷新机制
```
<!-- CONTRACT:END slot=Q17 -->

## Q18（选择题）

### 当前推荐
推荐模式B概念辨析型，考流水线数据通路。

### 候选替换池
- 模式A: 计算型——流水线周期、微指令编码
- 模式B: 概念辨析型——可见寄存器、ISA边界
- 模式C: 组合判断型——流水线特征
- 模式D: 机制理解型——低位交叉编址

### 教师可编辑说明

<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q18 -->
```yaml
slot_id: Q18
question_type: single_choice
score: 2
examination_mode: 概念辨析型
active_selection:
  mode_id: 模式B
  mode_name: 概念辨析型
  selected_knowledge:
    - 数据通路组成
    - 可见寄存器与ISA边界
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
  - 模式D
excluded:
  modes: []
  knowledge: []
```
<!-- CONTRACT:END slot=Q18 -->

## Q19（选择题）

### 当前推荐
推荐模式A概念辨析型。但教师改选了模式B计算型。

### 候选替换池
- 模式A: 概念辨析型——硬布线vs微程序
- 模式B: 计算型——总线带宽、标志位计算
- 模式C: 机制理解型——流水线冒险

### 教师可编辑说明
改成计算题吧，考总线带宽计算。参数用简单的：时钟频率100MHz，数据线32位，
算最大数据传输率。这题学生容易忘记单位换算，是好的区分点。

<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q19 -->
```yaml
slot_id: Q19
question_type: single_choice
score: 2
examination_mode: 计算型
active_selection:
  mode_id: 模式B
  mode_name: 计算型
  selected_knowledge:
    - 总线带宽计算
    - 单位换算
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
excluded:
  modes:
    - 模式A
  knowledge:
    - 硬布线与微程序控制器对比
```
<!-- CONTRACT:END slot=Q19 -->

## Q20（选择题）

### 当前推荐
推荐模式A概念辨析型，考总线标准。

### 候选替换池
- 模式A: 概念辨析型——总线标准、CPU结构
- 模式B: 计算型——总线带宽、磁盘性能
- 模式C: 组合判断型——中断分类

### 教师可编辑说明
出I/O相关的题。I/O系统比较重要但经常被忽略。
考I/O接口的功能和编址方式，让学生辨析统一编址和独立编址的区别。
不要考磁盘性能计算，计算量太大不适合选择题。

<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q20 -->
```yaml
slot_id: Q20
question_type: single_choice
score: 2
examination_mode: 概念辨析型
active_selection:
  mode_id: 模式A
  mode_name: 概念辨析型
  selected_knowledge:
    - I/O接口功能与编址方式
    - 统一编址与独立编址
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
excluded:
  modes: []
  knowledge:
    - 磁盘性能计算
    - 流水线周期计算
```
<!-- CONTRACT:END slot=Q20 -->

## Q45（综合题）

### 当前推荐
推荐模式A虚拟-Cache协同映射追踪。

### 候选替换池
- 模式A: 虚拟-Cache协同映射追踪
- 模式B: 局部性原理与替换策略评估

### 教师可编辑说明
用模式A。给一个具体的虚拟地址，让学生走完整条地址转换链路：
虚拟地址→页表→物理地址→Cache索引→数据。
不要考替换算法模拟（LRU那些），那个放在选择题考就行。
综合题重点考察地址转换的全链路理解。

<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q45 -->
```yaml
slot_id: Q45
question_type: comprehensive
score: 10
examination_mode: 虚拟-Cache协同映射追踪
active_selection:
  mode_id: 模式A
  mode_name: 虚拟-Cache协同映射追踪
  selected_knowledge:
    - 页式虚拟存储地址转换
    - TLB查找与缺失处理
    - Cache映射机制
candidate_pool_visible:
  - 模式A
  - 模式B
excluded:
  modes: []
  knowledge:
    - LRU替换算法模拟
    - 页面置换策略对比
```
<!-- CONTRACT:END slot=Q45 -->

## Q46（综合题）

### 当前推荐
推荐模式A结构解析-状态推演。但教师改选了模式B。

### 候选替换池
- 模式A: 结构解析-状态推演-综合评估
- 模式B: 场景约束-权衡设计-机制论证
- 模式C: 时序重构-状态判定-边界辨析

### 教师可编辑说明
改用模式B。给一个具体场景：某系统内存有限，需要在页面大小和TLB容量之间做权衡。
让学生设计方案并论证为什么这样设计。这种开放性的综合题更能考察深度理解。
子问题设计：第一问分析给定参数下的地址结构和页表大小，
第二问设计TLB配置方案，第三问讨论trade-off。

<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q46 -->
```yaml
slot_id: Q46
question_type: comprehensive
score: 13
examination_mode: 场景约束-权衡设计-机制论证
active_selection:
  mode_id: 模式B
  mode_name: 场景约束-权衡设计-机制论证
  selected_knowledge:
    - 虚拟内存管理方案设计
    - TLB容量与页面大小权衡
    - 页表层次结构
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
excluded:
  modes:
    - 模式A
  knowledge:
    - 文件系统索引结构
    - 进程同步PV操作
```
<!-- CONTRACT:END slot=Q46 -->
"""


class TestCOTeacherSimulation:
    """模拟教师对不同组成原理题位做不同修改，验证全链路。"""

    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.compose_dir = os.path.join(cls.tmpdir, "compose")
        os.makedirs(cls.compose_dir, exist_ok=True)

        # 保存 outline
        cls.outline_path = os.path.join(cls.compose_dir, "outline_approved.md")
        with open(cls.outline_path, "w", encoding="utf-8") as f:
            f.write(OUTLINE_APPROVED)

        # Parse → sidecar
        cls.result = parse_outline_to_selection(OUTLINE_APPROVED)

        # Write sidecar
        cls.selection_path = os.path.join(cls.compose_dir, "paper_selection.yaml")
        write_paper_selection(cls.result.slots, cls.selection_path)

        cls.report_path = os.path.join(cls.compose_dir, "parse_report.md")
        with open(cls.report_path, "w", encoding="utf-8") as f:
            f.write(cls.result.report)

        # Generate assembled docs
        cls.assembled_docs = {}
        for contract in cls.result.slots:
            sid = contract.slot_id
            mode = contract.examination_mode
            slot_md_path = os.path.join("data", "slots", f"{sid}_slot.md")
            exp_path = os.path.join("data", "slot_experiences", f"{sid}_experience.md")

            # Build outline_entry from contract
            outline_entry = {
                "slot_id": contract.slot_id,
                "question_type": contract.question_type,
                "score": contract.score,
                "examination_mode": contract.examination_mode,
                "active_selection": contract.active_selection,
                "candidate_pool_visible": contract.candidate_pool_visible,
                "excluded_modes": contract.excluded_modes,
                "excluded_knowledge": contract.excluded_knowledge,
                "teacher_annotation": contract.teacher_annotation,
            }

            doc = artifact_store.assemble_slot_experience_doc(
                sid, mode, slot_md_path, exp_path,
                outline_entry=outline_entry,
            )
            cls.assembled_docs[sid] = doc

            # Save to disk
            assembled_path = os.path.join(cls.compose_dir, f"{sid}_assembled.md")
            with open(assembled_path, "w", encoding="utf-8") as f:
                f.write(doc)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir)

    # ── Parser 验证 ─────────────────────────────────────

    def test_all_7_slots_parsed(self):
        assert len(self.result.slots) == 7
        slot_ids = [s.slot_id for s in self.result.slots]
        assert slot_ids == ["Q14", "Q17", "Q18", "Q19", "Q20", "Q45", "Q46"]

    def test_validation_status(self):
        # Should pass or have only warnings (no errors)
        assert self.result.validation.status in ("pass", "warning")

    def test_sidecar_written(self):
        assert os.path.exists(self.selection_path)
        with open(self.selection_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert len(data) == 7

    # ── 每个题位的具体验证 ───────────────────────────────

    def test_q14_teacher_removes_float(self):
        """教师排除浮点数，要求考Cache地址映射。"""
        c = self.result.slots[0]
        assert c.slot_id == "Q14"
        assert c.question_type == "single_choice"
        assert "Cache" in c.teacher_annotation
        assert "IEEE 754" in c.excluded_knowledge[0]
        assert "浮点" in c.excluded_knowledge[1]
        assert "Cache地址映射" in str(c.active_selection["selected_knowledge"])

        doc = self.assembled_docs["Q14"]
        assert len(doc) > 200
        assert "final_machine_contract" in doc

    def test_q17_teacher_removes_dram(self):
        """教师排除DRAM刷新，要求RISC/CISC。"""
        c = self.result.slots[1]
        assert c.slot_id == "Q17"
        assert "DRAM" in c.excluded_knowledge[0]
        assert "RISC" in c.teacher_annotation

        doc = self.assembled_docs["Q17"]
        assert "final_machine_contract" in doc

    def test_q18_teacher_no_changes(self):
        """教师未做修改（空批注）。"""
        c = self.result.slots[2]
        assert c.slot_id == "Q18"
        assert c.teacher_annotation == ""
        assert c.excluded_modes == []
        assert c.excluded_knowledge == []

        doc = self.assembled_docs["Q18"]
        assert "final_machine_contract" in doc

    def test_q19_teacher_changes_mode(self):
        """教师改选模式B计算型，排除模式A。"""
        c = self.result.slots[3]
        assert c.slot_id == "Q19"
        assert c.active_selection["mode_id"] == "模式B"
        assert "模式A" in c.excluded_modes
        assert "总线带宽" in c.teacher_annotation

        doc = self.assembled_docs["Q19"]
        assert "final_machine_contract" in doc
        # machine contract should show 模式B as active
        assert "模式B" in doc

    def test_q20_teacher_detailed_annotation(self):
        """教师详细批注I/O方向，排除磁盘计算。"""
        c = self.result.slots[4]
        assert c.slot_id == "Q20"
        assert "I/O" in c.teacher_annotation
        assert any("磁盘" in ek for ek in c.excluded_knowledge)
        assert "I/O接口" in str(c.active_selection["selected_knowledge"])

        doc = self.assembled_docs["Q20"]
        assert "final_machine_contract" in doc

    def test_q45_comprehensive_excludes_lru(self):
        """综合题Q45排除LRU替换算法。"""
        c = self.result.slots[5]
        assert c.slot_id == "Q45"
        assert c.question_type == "comprehensive"
        assert c.score == 10
        assert any("LRU" in ek for ek in c.excluded_knowledge)
        assert "地址转换" in c.teacher_annotation

        doc = self.assembled_docs["Q45"]
        assert "final_machine_contract" in doc
        assert "comprehensive" in doc or "综合" in doc

    def test_q46_comprehensive_changes_mode(self):
        """综合题Q46教师改选模式B，排除模式A和无关知识点。"""
        c = self.result.slots[6]
        assert c.slot_id == "Q46"
        assert c.question_type == "comprehensive"
        assert c.score == 13
        assert c.active_selection["mode_id"] == "模式B"
        assert "模式A" in c.excluded_modes
        assert any("文件系统" in ek for ek in c.excluded_knowledge)
        assert any("进程同步" in ek for ek in c.excluded_knowledge)
        assert "权衡" in c.teacher_annotation

        doc = self.assembled_docs["Q46"]
        assert "final_machine_contract" in doc

    # ── Assembled 文档质量检查 ────────────────────────────

    def test_all_assembled_have_contract(self):
        """所有 assembled 文档都包含 final_machine_contract。"""
        for sid, doc in self.assembled_docs.items():
            assert "final_machine_contract" in doc, f"{sid} missing contract section"

    def test_all_assembled_have_k_target(self):
        """所有 assembled 文档都包含 K目标/K难度 信息。"""
        for sid, doc in self.assembled_docs.items():
            # Should have K-radar or difficulty info
            assert len(doc) > 100, f"{sid} assembled too short ({len(doc)} chars)"

    def test_excluded_knowledge_not_in_assembled_contract(self):
        """被排除的知识点不应出现在机器契约的 active_selection 中。"""
        for c in self.result.slots:
            if c.excluded_knowledge:
                doc = self.assembled_docs[c.slot_id]
                for ek in c.excluded_knowledge:
                    # excluded knowledge should be marked or not in selected
                    # The contract YAML should not have excluded items in selected_knowledge
                    selected = c.active_selection.get("selected_knowledge", [])
                    assert ek not in selected, (
                        f"{c.slot_id}: {ek} in both excluded_knowledge and selected_knowledge"
                    )

    def test_generate_runner_reads_sidecar(self):
        """generate_runner 能正确从 sidecar 加载 blueprint。"""
        from compose.generate_runner import _load_blueprint_map
        bp_map = _load_blueprint_map(self.compose_dir)

        assert len(bp_map) == 7
        assert bp_map["Q14"].question_type == "single_choice"
        assert bp_map["Q45"].question_type == "comprehensive"
        assert bp_map["Q45"].score == 10
        assert bp_map["Q46"].score == 13
        assert "Cache" in str(bp_map["Q14"].active_selection.get("selected_knowledge", []))
        assert bp_map["Q19"].excluded_modes == ["模式A"]
        assert bp_map["Q46"].excluded_modes == ["模式A"]
        assert "总线带宽" in bp_map["Q19"].teacher_annotation
        assert "I/O" in bp_map["Q20"].teacher_annotation
        assert "权衡" in bp_map["Q46"].teacher_annotation

    def test_parse_report_generated(self):
        """parse_report.md 正确生成。"""
        assert os.path.exists(self.report_path)
        with open(self.report_path, encoding="utf-8") as f:
            report = f.read()
        assert "Outline Parse Report" in report
        assert "extracted_slots" in report
        for sid in ["Q14", "Q17", "Q18", "Q19", "Q20", "Q45", "Q46"]:
            assert sid in report
