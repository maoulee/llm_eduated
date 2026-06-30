#!/usr/bin/env python3
"""把池州两套的判断题从"4条捆绑+套话+内联√/×"重写为标准风格：
每题 1 条独立陈述；对/错+理由放 solution.md；错误项用隐蔽概念错（无绝对化信号词）。

每 slot 保留其分值（5 题 × 单陈述 = 标准判断题量）。"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (paper_rel, slot) → (statement, symbol √/×, label 对/错, reason)
RW = {
    ('kaodian_full2_coA/20260626T233539', 'Q6'): (
        'CPU 中的控制器负责完成算术运算与逻辑运算。', '×', '错',
        '错误。算术运算与逻辑运算是**运算器（ALU）**的职责；控制器负责解释指令、产生控制信号、协调各部件，并不执行运算——此处把运算器的功能安到了控制器上。'),
    ('kaodian_full2_coA/20260626T233539', 'Q7'): (
        '异步通信依靠"请求—回答"（握手）信号协调主从模块，模块之间没有统一的公共时钟。', '√', '对',
        '正确。异步通信不依赖公共时钟，而由握手信号（请求/回答）实现主从模块的时序协调。'),
    ('kaodian_full2_coA/20260626T233539', 'Q8'): (
        'Cache—主存层次用于解决 CPU 与主存之间的速度差距，主存—辅存层次用于扩大可供使用的存储容量。', '√', '对',
        '正确。存储层次两级目标不同：Cache—主存基于局部性原理提速，主存—辅存借助虚拟存储扩容。'),
    ('kaodian_full2_coA/20260626T233539', 'Q9'): (
        '垂直型微指令的字长通常比水平型微指令更长。', '×', '错',
        '错误。水平型微指令含多位控制字段、可并行定义多个微操作，字长更长；垂直型微指令类似机器指令（操作码+地址码），字长较短——此处正相反。'),
    ('kaodian_full2_coA/20260626T233539', 'Q10'): (
        '同一 CPU 中，加法指令和乘法指令的指令周期相同。', '×', '错',
        '错误。指令周期与指令功能及寻址方式有关：乘法通常需多次"加法+移位"，机器周期数多于普通加法，故二者指令周期不同。'),
    ('kaodian_full2_nmA/20260627T011949', 'A06'): (
        'SRAM 采用触发器存储信息，存取速度比 DRAM 快，因此其集成度也高于 DRAM。', '×', '错',
        '错误。SRAM 存取确实快于 DRAM，但 SRAM 每位用双稳态触发器（元件多）、集成度**低于** DRAM；DRAM 每位仅 1 个 MOS 管+电容，集成度更高。'),
    ('kaodian_full2_nmA/20260627T011949', 'A07'): (
        '虚拟存储器的逻辑地址空间由 CPU 的虚拟地址位数决定，可以大于物理内存的实际容量。', '√', '对',
        '正确。虚存容量取决于虚拟地址位数（程序员可见地址空间），实际运行由辅存支撑，故逻辑地址空间可大于物理内存。'),
    ('kaodian_full2_nmA/20260627T011949', 'A08'): (
        '链式查询方式中，离总线控制器越近的设备优先级越高，且这种方式对链路故障较为敏感。', '√', '对',
        '正确。链式查询优先级由物理位置决定（近高远低）；链路上某设备故障会使其后所有设备都无法获总线授权，故对故障敏感。'),
    ('kaodian_full2_nmA/20260627T011949', 'A09'): (
        'DMA 方式下，主存与高速外设之间的数据传送由 DMA 控制器接管总线完成，因此 CPU 在整个传送过程（含预处理与后处理）中均不介入。', '×', '错',
        '错误。DMA 仅在**数据传送阶段**由 DMA 控制器接管总线、CPU 不介入；但**预处理**（设置传送参数）与**后处理**（计数/校验/中断通知）仍由 CPU 完成。'),
    ('kaodian_full2_nmA/20260627T011949', 'A10'): (
        '指令流水线通过让多条指令在不同段重叠执行来提高吞吐率，理想情况下每个时钟周期可流出一条指令。', '√', '对',
        '正确。流水线分段重叠执行，稳态下每周期流出一条指令；实际因结构/数据/控制冲突停顿而低于该理想值。'),
}

PAT_Q = re.compile(r'判断以下陈述[的]?对错[：:].*?\*\*答案\*\*[：:][^\n]*', re.S)
PAT_S = re.compile(r'(\*\*答案\*\*[：:].*?\n\*\*解析\*\*[：:])[\s\S]*?(?=\n---|\n\n---|\Z)', re.S)


def _slot_dir(paper_rel, slot):
    base = ROOT / 'docs/test_output' / paper_rel / 'questions' / slot
    for cand in (base, base / slot):
        if (cand / 'question.md').exists():
            return cand
    return None


n = 0
for (paper, slot), (stmt, sym, label, reason) in RW.items():
    d = _slot_dir(paper, slot)
    if not d:
        print(f'[SKIP] {slot}: 找不到目录')
        continue
    qf, sf = d / 'question.md', d / 'solution.md'
    # question.md: 4条捆绑 → 单陈述
    q0 = qf.read_text(encoding='utf-8')
    q1 = PAT_Q.sub(f'{stmt}\n\n**答案**：{sym}（{label}）', q0, count=1)
    if q1 == q0:
        print(f'[WARN] {slot} question 未匹配到捆绑块')
    else:
        qf.write_text(q1, encoding='utf-8')
    # solution.md: 4条答案/解析 → 单
    s0 = sf.read_text(encoding='utf-8')
    s1 = PAT_S.sub(lambda m: f'{m.group(1)}{reason}', s0, count=1)
    if s1 == s0:
        print(f'[WARN] {slot} solution 未匹配')
    else:
        sf.write_text(s1, encoding='utf-8')
    n += 1
    print(f'[OK] {paper.split("_")[-1]}/{slot}: {label} — {stmt[:30]}...')

print(f'\n重写 {n} 道判断题为单陈述标准风格')
