"""408 exam helper functions for CodeActSolver.

Provides verified computation primitives so the solver can execute
rather than reason in text.
"""

from __future__ import annotations

import struct
from typing import Dict, List, Tuple


def twos_complement_value(hex_str: str, bits: int) -> int:
    """Interpret a hex string as a two's complement integer."""
    val = int(hex_str, 16)
    if val >= (1 << (bits - 1)):
        val -= 1 << bits
    return val


def twos_complement_hex(value: int, bits: int) -> str:
    """Encode an integer as a hex string in two's complement."""
    if value < 0:
        value = (1 << bits) + value
    return format(value, f"0{bits // 4}X")


def ieee754_single_hex(x: float) -> str:
    """Return the IEEE 754 single-precision hex representation of x."""
    bits = struct.unpack(">I", struct.pack(">f", x))[0]
    return format(bits, "08X")


def ieee754_single_from_hex(hex_str: str) -> float:
    """Decode an IEEE 754 single-precision hex string to float."""
    bits = int(hex_str, 16)
    return struct.unpack(">f", struct.pack(">I", bits))[0]


def ieee754_double_hex(x: float) -> str:
    """Return the IEEE 754 double-precision hex representation of x."""
    bits = struct.unpack(">Q", struct.pack(">d", x))[0]
    return format(bits, "016X")


def cache_address_fields(
    address_bits: int,
    cache_size: int,
    block_size: int,
    associativity: int,
) -> Dict[str, int]:
    """Compute offset, index, and tag bit widths for a set-associative cache."""
    offset_bits = (block_size - 1).bit_length()
    total_blocks = cache_size // block_size
    num_sets = total_blocks // associativity
    index_bits = (num_sets - 1).bit_length() if num_sets > 1 else 0
    tag_bits = address_bits - index_bits - offset_bits
    return {
        "offset_bits": offset_bits,
        "index_bits": index_bits,
        "tag_bits": tag_bits,
        "num_sets": num_sets,
        "total_blocks": total_blocks,
    }


def cache_decompose_address(
    address: int,
    offset_bits: int,
    index_bits: int,
) -> Dict[str, int]:
    """Decompose an address into offset, index, and tag."""
    offset = address & ((1 << offset_bits) - 1)
    index = (address >> offset_bits) & ((1 << index_bits) - 1) if index_bits else 0
    tag = address >> (offset_bits + index_bits)
    return {"tag": tag, "index": index, "offset": offset}


def simulate_cache(
    addresses: List[int],
    cache_size: int,
    block_size: int,
    associativity: int,
    address_bits: int = 32,
    policy: str = "LRU",
) -> Dict:
    """Simulate a set-associative cache with a sequence of addresses.

    Returns hit/miss sequence and final hit rate.
    """
    fields = cache_address_fields(address_bits, cache_size, block_size, associativity)
    num_sets = fields["num_sets"]
    offset_bits = fields["offset_bits"]
    index_bits = fields["index_bits"]

    # Each set holds a list of (tag, insertion_order) for LRU tracking
    cache: Dict[int, List[int]] = {s: [] for s in range(num_sets)}
    order = 0
    results = []

    for addr in addresses:
        decomposed = cache_decompose_address(addr, offset_bits, index_bits)
        tag = decomposed["tag"]
        idx = decomposed["index"]

        set_lines = cache[idx]
        hit = False
        for i, (t, _) in enumerate(set_lines):
            if t == tag:
                hit = True
                if policy.upper() == "LRU":
                    set_lines[i] = (tag, order)
                break

        if hit:
            results.append("hit")
        else:
            results.append("miss")
            if len(set_lines) >= associativity:
                # Evict LRU (lowest order)
                min_idx = min(range(len(set_lines)), key=lambda j: set_lines[j][1])
                set_lines[min_idx] = (tag, order)
            else:
                set_lines.append((tag, order))

        order += 1

    hits = results.count("hit")
    total = len(results)
    return {
        "access_sequence": results,
        "hits": hits,
        "misses": total - hits,
        "hit_rate": hits / total if total else 0,
        "address_fields": fields,
    }


def crc_remainder(data_bits: str, generator_bits: str) -> str:
    """Compute CRC remainder using binary long division."""
    gen_len = len(generator_bits)
    # Append (gen_len - 1) zeros to data
    data = list(data_bits + "0" * (gen_len - 1))
    gen = list(generator_bits)

    for i in range(len(data_bits)):
        if data[i] == "1":
            for j in range(gen_len):
                data[i + j] = str(int(data[i + j]) ^ int(gen[j]))

    remainder = "".join(data[-(gen_len - 1):])
    return remainder


def simulate_page_replacement(
    references: List[int],
    num_frames: int,
    policy: str = "LRU",
) -> Dict:
    """Simulate a page replacement algorithm over a reference string.

    Supports LRU, FIFO, and OPT.
    """
    frames: List[int] = []
    usage_order: Dict[int, int] = {}
    order = 0
    results = []

    for i, page in enumerate(references):
        if page in frames:
            results.append("hit")
            usage_order[page] = order
            order += 1
            continue

        results.append("miss")
        if len(frames) < num_frames:
            frames.append(page)
            usage_order[page] = order
        else:
            if policy.upper() == "LRU":
                victim = min(frames, key=lambda p: usage_order.get(p, 0))
            elif policy.upper() == "FIFO":
                victim = frames[0]
            elif policy.upper() == "OPT":
                # Look ahead: find page used farthest in future (or never)
                future = {}
                for p in frames:
                    try:
                        future[p] = references[i + 1:].index(p)
                    except ValueError:
                        future[p] = float("inf")
                victim = max(frames, key=lambda p: future[p])
            else:
                victim = frames[0]

            victim_idx = frames.index(victim)
            frames[victim_idx] = page
            usage_order[page] = order
            del usage_order[victim]

        order += 1

    hits = results.count("hit")
    total = len(results)
    return {
        "access_sequence": results,
        "hits": hits,
        "misses": total - hits,
        "hit_rate": hits / total if total else 0,
        "page_faults": total - hits,
        "final_frames": list(frames),
    }


def cpu_time(
    instruction_count: int,
    cpi: float,
    frequency_hz: float,
) -> Dict:
    """Compute CPU execution time."""
    cycles = instruction_count * cpi
    time_s = cycles / frequency_hz
    return {
        "cycles": cycles,
        "time_s": time_s,
        "time_ms": time_s * 1000,
        "time_us": time_s * 1_000_000,
    }


def pipeline_performance(
    num_stages: int,
    num_instructions: int,
    clock_cycle_ns: float,
    stalls: int = 0,
) -> Dict:
    """Compute pipeline performance metrics."""
    total_cycles = num_stages + (num_instructions - 1) + stalls
    total_time_ns = total_cycles * clock_cycle_ns
    speedup = (num_instructions * num_stages) / total_cycles if total_cycles else 0
    return {
        "total_cycles": total_cycles,
        "total_time_ns": total_time_ns,
        "speedup": round(speedup, 4),
        "throughput": round(num_instructions / (total_time_ns / 1e9), 2),
    }


def address_translation(
    virtual_addr: int,
    page_size: int,
    page_table: Dict[int, int],
    address_bits: int = 32,
) -> Dict:
    """Translate a virtual address to physical using a flat page table."""
    offset_bits = (page_size - 1).bit_length()
    page_num = virtual_addr >> offset_bits
    offset = virtual_addr & (page_size - 1)

    if page_num in page_table:
        phys_frame = page_table[page_num]
        phys_addr = (phys_frame << offset_bits) | offset
        hit = True
    else:
        phys_addr = None
        hit = False

    return {
        "page_number": page_num,
        "offset": offset,
        "offset_bits": offset_bits,
        "physical_address": phys_addr,
        "tlb_hit": hit,
    }


def booth_multiply(multiplicand: int, multiplier: int, bits: int = 8) -> Dict:
    """Simulate Booth's multiplication algorithm."""
    n = bits
    AC = 0
    QR = multiplier & ((1 << n) - 1)
    Qn_1 = 0
    SC = n
    steps = []

    while SC > 0:
        QR0 = QR & 1
        if QR0 == 0 and Qn_1 == 1:
            AC = (AC + multiplicand) & ((1 << n) - 1)
            action = f"AC += M ({multiplicand})"
        elif QR0 == 1 and Qn_1 == 0:
            AC = (AC - multiplicand) & ((1 << n) - 1)
            action = f"AC -= M ({multiplicand})"
        else:
            action = "no add"

        combined = (AC << n) | QR
        Qn_1 = QR & 1
        combined >>= 1
        AC = (combined >> n) & ((1 << n) - 1)
        QR = combined & ((1 << n) - 1)
        SC -= 1

        steps.append({
            "AC": AC,
            "QR": QR,
            "Qn_1": Qn_1,
            "SC": SC,
            "action": action,
        })

    product = (AC << n) | QR
    if product >= (1 << (2 * n - 1)):
        product -= 1 << (2 * n)

    return {
        "product": product,
        "product_hex": twos_complement_hex(product, 2 * n),
        "steps": steps,
    }
