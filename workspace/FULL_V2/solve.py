#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cache Mapping Problem Solver
Calculates Tag/Index/Offset fields, analyzes address mapping, and computes Tag RAM capacity.
"""

import math

def solve():
    # ==========================================
    # 1. Define System Parameters
    # ==========================================
    PHYS_ADDR_BITS = 32
    MAIN_MEM_SIZE = 1 * 1024 * 1024 * 1024  # 1 GB = 2^30 Bytes
    CACHE_SIZE = 64 * 1024                   # 64 KB = 2^16 Bytes
    BLOCK_SIZE = 32                          # 32 Bytes = 2^5 Bytes
    ASSOCIATIVITY = 4                        # 4-way Set Associative
    VALID_BITS = 1
    LRU_BITS = 2

    print("="*30)
    print("System Parameters:")
    print(f"Physical Address Size: {PHYS_ADDR_BITS} bits")
    print(f"Main Memory Size: {MAIN_MEM_SIZE} Bytes (1 GB)")
    print(f"Cache Capacity: {CACHE_SIZE} Bytes (64 KB)")
    print(f"Block Size: {BLOCK_SIZE} Bytes")
    print(f"Associativity: {ASSOCIATIVITY}-way")
    print("="*30)

    # ==========================================
    # 2. Solve Sub-question (1): Field Calculation
    # ==========================================
    print("\n--- (1) Field Calculation ---")

    # Main Memory Block Number Bits
    # Main Memory is divided into blocks of BLOCK_SIZE
    num_main_mem_blocks = MAIN_MEM_SIZE // BLOCK_SIZE
    # log2(2^30 / 2^5) = 25
    main_mem_block_bits = int(math.log2(num_main_mem_blocks))
    print(f"Number of blocks in Main Memory: {num_main_mem_blocks} (2^{main_mem_block_bits})")
    print(f"Main Memory Block Number Total Bits: {main_mem_block_bits} bits")

    # Cache Lines (Rows)
    num_cache_lines = CACHE_SIZE // BLOCK_SIZE
    print(f"Cache Total Lines (Rows): {num_cache_lines} (2^{int(math.log2(num_cache_lines))})")

    # Cache Sets
    num_cache_sets = num_cache_lines // ASSOCIATIVITY
    num_sets_bits = int(math.log2(num_cache_sets))
    print(f"Cache Total Sets: {num_cache_sets} (2^{num_sets_bits})")

    # Address Fields Breakdown
    offset_bits = int(math.log2(BLOCK_SIZE))
    index_bits = num_sets_bits
    tag_bits = PHYS_ADDR_BITS - index_bits - offset_bits

    print(f"\nAddress Field Calculation:")
    print(f"Offset (Block Offset): {offset_bits} bits")
    print(f"Index (Set Index):     {index_bits} bits")
    print(f"Tag:                   {tag_bits} bits")
    print(f"Check: {tag_bits} + {index_bits} + {offset_bits} = {tag_bits + index_bits + offset_bits} bits")

    # Bit Ranges (MSB is bit[31], LSB is bit[0])
    # Offset: bit[4:0] -> [offset_bits - 1 : 0]
    # Index:  bit[13:5] -> [offset_bits + index_bits - 1 : offset_bits]
    # Tag:    bit[31:14] -> [PHYS_ADDR_BITS - 1 : offset_bits + index_bits]

    offset_start = 0
    offset_end = offset_bits - 1

    index_start = offset_end + 1
    index_end = index_start + index_bits - 1

    tag_start = index_end + 1
    tag_end = PHYS_ADDR_BITS - 1

    print(f"\nBit Ranges (bit[31] is MSB):")
    print(f"Offset: bit[{offset_end}:{offset_start}]")
    print(f"Index:  bit[{index_end}:{index_start}]")
    print(f"Tag:    bit[{tag_end}:{tag_start}]")

    # ==========================================
    # 3. Solve Sub-question (2): Address Mapping Analysis
    # ==========================================
    print("\n--- (2) Address Mapping Analysis ---")

    A1 = 0x1A234000
    A2 = 0x1A23C000

    def analyze_address(addr, name, offset_bits, index_bits):
        print(f"\nAnalyzing Address {name}: 0x{addr:08X}")
        
        # Masks
        mask_offset = (1 << offset_bits) - 1
        mask_index = ((1 << index_bits) - 1) << offset_bits
        
        # Extract fields
        val_offset = addr & mask_offset
        val_index = (addr & mask_index) >> offset_bits
        val_tag = addr >> (offset_bits + index_bits)

        print(f"Binary (32-bit): {addr:032b}")
        print(f"Offset Field (bit[{offset_bits-1}:0]): {val_offset:0{offset_bits}b} (Decimal: {val_offset})")
        print(f"Index Field  (bit[{index_bits+offset_bits-1}:{offset_bits}]): {val_index:0{index_bits}b} (Decimal: {val_index})")
        print(f"Tag Field    (bit[31:{index_bits+offset_bits}]): 0b{val_tag:0{32-index_bits-offset_bits}b} (Hex: 0x{val_tag:04X})")

        return val_index, val_tag

    idx1, tag1 = analyze_address(A1, "A1", offset_bits, index_bits)
    idx2, tag2 = analyze_address(A2, "A2", offset_bits, index_bits)

    print(f"\nComparison:")
    print(f"A1 Index: {idx1}, A2 Index: {idx2}")
    print(f"Same Index? {idx1 == idx2}")
    
    print(f"A1 Tag: {tag1} (0x{tag1:05X})")
    print(f"A2 Tag: {tag2} (0x{tag2:05X})")
    print(f"Same Tag? {tag1 == tag2}")

    if idx1 == idx2:
        print("\nResult: Both addresses map to the same set (Set 0).")
        if tag1 != tag2:
            print("Reasoning: Although Index fields are identical (mapping to the same set), the Tag fields are different.")
            print(f"Since this is a {ASSOCIATIVITY}-way set associative cache, both blocks can coexist in the set until it is full.")
            print(f"However, if the set is full and contains neither block, or if eviction policies force replacement of a needed block,")
            print(f"conflicts occur. Specifically, because they map to the same set, they compete for the same {ASSOCIATIVITY} lines.")
            print(f"Thus, there is a risk of conflict miss if both are accessed frequently and the set is full.")
        else:
            print("Result: They are the exact same block.")
    else:
        print("Result: They map to different sets.")

    # ==========================================
    # 4. Solve Sub-question (3): Tag RAM & Analysis
    # ==========================================
    print("\n--- (3) Tag RAM Calculation & Analysis ---")

    # 3.1 Tag RAM Capacity
    bits_per_line_tag_ram = tag_bits + VALID_BITS + LRU_BITS
    total_bits_tag_ram = num_cache_lines * bits_per_line_tag_ram
    total_bytes_tag_ram = total_bits_tag_ram // 8

    print(f"3.1 Tag RAM Capacity Calculation:")
    print(f"Bits per Cache Line for Tag RAM: Tag({tag_bits}) + Valid({VALID_BITS}) + LRU({LRU_BITS}) = {bits_per_line_tag_ram} bits")
    print(f"Total Cache Lines: {num_cache_lines}")
    print(f"Total Bits Required: {num_cache_lines} lines * {bits_per_line_tag_ram} bits/line = {total_bits_tag_ram} bits")
    print(f"Total Bytes Required: {total_bits_tag_ram} / 8 = {total_bytes_tag_ram} Bytes")

    # 3.2 Direct Mapping Analysis
    print(f"\n3.2 Mapping Change Analysis (4-way Set Associative -> Direct Mapping):")
    print(f"Parameters kept constant: Cache Capacity ({CACHE_SIZE}B), Block Size ({BLOCK_SIZE}B)")
    
    print(f"\nEffect on Capacity Miss Rate (容量未命中率):")
    print(f"Result: Basically Unchanged (基本不变)")
    print(f"Reason: Capacity miss rate depends on the total amount of cache storage available to hold data.")
    print(f"Since the total cache capacity remains 64KB, the ability to store unique blocks over a long sequence is unchanged.")
    print(f"The mapping scheme does not alter the physical amount of storage.")

    print(f"\nEffect on Conflict Miss Rate (冲突未命中率):")
    print(f"Result: Increases (增大)")
    print(f"Reason: In Direct Mapping (1-way), each main memory block maps to exactly one specific line.")
    print(f"In {ASSOCIATIVITY}-way Set Associative, a block can map to any of the {ASSOCIATIVITY} lines within its set.")
    print(f"Direct Mapping reduces flexibility. If two frequently accessed blocks map to the same line (interference),")
    print(f"they will constantly evict each other (thrashing), causing high conflict misses.")
    print(f"With {ASSOCIATIVITY}-way associativity, these two blocks can coexist in the set (assuming {ASSOCIATIVITY} >= 2),")
    print(f"reducing the likelihood of such conflicts.")

if __name__ == "__main__":
    solve()
