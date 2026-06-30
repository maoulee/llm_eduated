#!/usr/bin/env python3
"""重写 nmA（池州_正常）5 道判断题为单陈述标准风格。
nmA 格式与 coA 不同：question 无内联 **答案**；solution 直接 ① √。② √。……（无 **答案**/**解析** 头）。"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# nmA 判断题 (与 rewrite_judgment.py 同内容)
RW = {
    'A06': ('SRAM 采用触发器存储信息，存取速度比 DRAM 快，因此其集成度也高于 DRAM。', '×', '错',
            '错误。SRAM 存取确实快于 DRAM，但 SRAM 每位用双稳态触发器（元件多）、集成度**低于** DRAM；DRAM 每位仅 1 个 MOS 管+电容，集成度更高。'),
    'A07': ('虚拟存储器的逻辑地址空间由 CPU 的虚拟地址位数决定，可以大于物理内存的实际容量。', '√', '对',
            '正确。虚存容量取决于虚拟地址位数（程序员可见地址空间），实际运行由辅存支撑，故逻辑地址空间可大于物理内存。'),
    'A08': ('链式查询方式中，离总线控制器越近的设备优先级越高，且这种方式对链路故障较为敏感。', '√', '对',
            '正确。链式查询优先级由物理位置决定（近高远低）；链路上某设备故障会使其后所有设备都无法获总线授权，故对故障敏感。'),
    'A09': ('DMA 方式下，主存与高速外设之间的数据传送由 DMA 控制器接管总线完成，因此 CPU 在整个传送过程（含预处理与后处理）中均不介入。', '×', '错',
            '错误。DMA 仅在**数据传送阶段**由 DMA 控制器接管总线、CPU 不介入；但**预处理**（设置传送参数）与**后处理**（计数/校验/中断通知）仍由 CPU 完成。'),
    'A10': ('指令流水线通过让多条指令在不同段重叠执行来提高吞吐率，理想情况下每个时钟周期可流出一条指令。', '√', '对',
            '正确。流水线分段重叠执行，稳态下每周期流出一条指令；实际因结构/数据/控制冲突停顿而低于该理想值。'),
}

BASE = ROOT / 'docs/test_output/kaodian_full2_nmA/20260627T011949/questions'

# question.md: "判断以下陈述对错：" + ①②③④ 行（无 **答案**）
PAT_Q = re.compile(r'判断以下陈述[的]?对错[：:]\s*\n(?:\s*[①-⑩][^\n]*\n)+', re.S)
# solution.md: 连续的 ① √。/② ×。…… 行
PAT_S = re.compile(r'(?:^[①-⑩]\s*[√×][^\n]*\n?)+', re.M)


def _dir(slot):
    for c in (BASE / slot, BASE / slot / slot):
        if (c / 'question.md').exists():
            return c
    return None


for slot, (stmt, sym, label, reason) in RW.items():
    d = _dir(slot)
    if not d:
        print(f'[SKIP] {slot}'); continue
    q0 = (d / 'question.md').read_text(encoding='utf-8')
    q1 = PAT_Q.sub(f'{stmt}\n\n**答案**：{sym}（{label}）\n', q0, count=1)
    (d / 'question.md').write_text(q1, encoding='utf-8') if q1 != q0 else None
    s0 = (d / 'solution.md').read_text(encoding='utf-8')
    s1 = PAT_S.sub(f'**答案**：{sym}（{label}）\n\n**解析**：{reason}\n', s0, count=1)
    (d / 'solution.md').write_text(s1, encoding='utf-8') if s1 != s0 else None
    status = 'OK' if (q1 != q0 and s1 != s0) else 'PARTIAL'
    print(f'[{status}] nmA/{slot}: {label} — {stmt[:28]}...')
