# ===== 题目参数定义 =====
VA_BITS = 30       # 虚拟地址位数
PA_BITS = 24       # 物理地址位数
PAGE_SIZE = 4096   # 页面大小 4KB = 2^12
PAGE_OFFSET_BITS = 12  # 页内偏移位数

# TLB参数
TLB_WAYS = 2       # 2路组相联
TLB_SETS = 8       # 8组
TLB_INDEX_BITS = 3 # 组号位数 (log2(8)=3)

# Cache参数
CACHE_LINES = 16   # 16行
BLOCK_SIZE = 64    # 块大小 64B = 2^6
CACHE_OFFSET_BITS = 6  # 块内偏移位数
CACHE_INDEX_BITS = 4   # Cache组号位数 (log2(16)=4)

# 虚拟地址访问序列
VA_ACCESS = [0x0000100, 0x0000110, 0x0000300, 0x0000500, 0x0000700]

# ===== 子问题(1) 地址字段划分 =====
print("=" * 60)
print("子问题(1): 地址字段划分")
print("=" * 60)

vpn_bits = VA_BITS - PAGE_OFFSET_BITS  # 18
ppn_bits = PA_BITS - PAGE_OFFSET_BITS  # 12

print(f"虚拟地址({VA_BITS}位):")
print(f"  页内偏移: 低{PAGE_OFFSET_BITS}位 (bit 0-{PAGE_OFFSET_BITS-1})")
print(f"  虚页号(VPN): 高{vpn_bits}位 (bit {PAGE_OFFSET_BITS}-{VA_BITS-1})")
print(f"物理地址({PA_BITS}位):")
print(f"  页内偏移: 低{PAGE_OFFSET_BITS}位 (bit 0-{PAGE_OFFSET_BITS-1})")
print(f"  物理页号(PPN): 高{ppn_bits}位 (bit {PAGE_OFFSET_BITS}-{PA_BITS-1})")

# TLB字段
tlb_tag_bits = vpn_bits - TLB_INDEX_BITS  # 15
print(f"\nTLB映射:")
print(f"  组号(Index): VPN低{TLB_INDEX_BITS}位")
print(f"  Tag: VPN高{tlb_tag_bits}位")

# Cache字段
cache_tag_bits = PA_BITS - CACHE_OFFSET_BITS - CACHE_INDEX_BITS  # 14
print(f"\nCache映射(物理地址{PA_BITS}位):")
print(f"  Offset(块内偏移): 低{CACHE_OFFSET_BITS}位 (bit 0-{CACHE_OFFSET_BITS-1})")
print(f"  Index(Cache组号): 中间{CACHE_INDEX_BITS}位 (bit {CACHE_OFFSET_BITS}-{CACHE_OFFSET_BITS+CACHE_INDEX_BITS-1})")
print(f"  Tag(标记): 高{cache_tag_bits}位 (bit {CACHE_OFFSET_BITS+CACHE_INDEX_BITS}-{PA_BITS-1})")

# ===== 初始化TLB =====
# TLB结构: 每组2路，每路有(有效位, Tag, PPN)
# 组号由VPN低3位决定
tlb = {}
# 表1 TLB当前内容
tlb_data = {
    0: {
        'way0': {'valid': 1, 'tag': 0x0000, 'ppn': 0x050},
        'way1': {'valid': 1, 'tag': 0x0001, 'ppn': 0x051},
        'lru': 0  # 0=路0最近使用
    },
    2: {
        'way0': {'valid': 1, 'tag': 0x0000, 'ppn': 0x052},
        'way1': {'valid': 1, 'tag': 0x0001, 'ppn': 0x053},
        'lru': 1  # 1=路1最近使用
    },
    4: {
        'way0': {'valid': 1, 'tag': 0x0000, 'ppn': 0x054},
        'way1': {'valid': 1, 'tag': 0x0001, 'ppn': 0x055},
        'lru': 0
    },
    6: {
        'way0': {'valid': 1, 'tag': 0x0000, 'ppn': 0x056},
        'way1': {'valid': 1, 'tag': 0x0001, 'ppn': 0x057},
        'lru': 1
    }
}
tlb = tlb_data

# 页表
page_table = {
    0x00001: {'ppn': 0x058, 'valid': 1},
    0x00003: {'ppn': 0x059, 'valid': 1},
    0x00005: {'ppn': 0x05A, 'valid': 1},
    0x00007: {'ppn': 0x05B, 'valid': 1},
}

# ===== 子问题(2) TLB命中情况与物理地址计算 =====
print("\n" + "=" * 60)
print("子问题(2): TLB命中情况与物理地址计算")
print("=" * 60)

results_tlb = []

for i, va in enumerate(VA_ACCESS):
    print(f"\n--- 访问{i+1}: VA = 0x{va:06X} ---")
    
    # 分解虚拟地址
    vpn = va >> PAGE_OFFSET_BITS
    offset = va & ((1 << PAGE_OFFSET_BITS) - 1)
    
    print(f"  VPN = 0x{va:06X} >> {PAGE_OFFSET_BITS} = 0x{vpn:X}")
    print(f"  页内偏移 = 0x{offset:03X}")
    
    # TLB组号和Tag
    tlb_index = vpn & ((1 << TLB_INDEX_BITS) - 1)
    tlb_tag = vpn >> TLB_INDEX_BITS
    
    print(f"  TLB组号 = VPN低{TLB_INDEX_BITS}位 = 0x{vpn:X} & 0x{(1<<TLB_INDEX_BITS)-1:X} = {tlb_index}")
    print(f"  TLB Tag = VPN高{tlb_tag_bits}位 = 0x{vpn:X} >> {TLB_INDEX_BITS} = 0x{tlb_tag:04X}")
    
    # TLB查找
    hit = False
    ppn = None
    
    if tlb_index in tlb:
        group = tlb[tlb_index]
        way0 = group['way0']
        way1 = group['way1']
        
        print(f"  组{tlb_index}路0: 有效={way0['valid']}, Tag=0x{way0['tag']:04X}, PPN=0x{way0['ppn']:03X}")
        print(f"  组{tlb_index}路1: 有效={way1['valid']}, Tag=0x{way1['tag']:04X}, PPN=0x{way1['ppn']:03X}")
        
        if way0['valid'] and way0['tag'] == tlb_tag:
            hit = True
            ppn = way0['ppn']
            print(f"  → 路0 Tag匹配! TLB命中")
            # 更新LRU
            group['lru'] = 0
        elif way1['valid'] and way1['tag'] == tlb_tag:
            hit = True
            ppn = way1['ppn']
            print(f"  → 路1 Tag匹配! TLB命中")
            # 更新LRU
            group['lru'] = 1
        else:
            print(f"  → 两路均不匹配, TLB缺失")
            # 查页表
            if vpn in page_table and page_table[vpn]['valid']:
                ppn = page_table[vpn]['ppn']
                print(f"  → 页表查到 PPN = 0x{ppn:03X}")
            else:
                print(f"  → 页表也未找到, 缺页异常!")
    else:
        print(f"  → 组{tlb_index}不在TLB中, TLB缺失")
        if vpn in page_table and page_table[vpn]['valid']:
            ppn = page_table[vpn]['ppn']
            print(f"  → 页表查到 PPN = 0x{ppn:03X}")
    
    # 计算物理地址
    if ppn is not None:
        pa = (ppn << PAGE_OFFSET_BITS) | offset
        print(f"  PPN = 0x{ppn:03X}")
        print(f"  PA = (0x{ppn:03X} << {PAGE_OFFSET_BITS}) | 0x{offset:03X} = 0x{pa:06X}")
        print(f"  TLB命中情况: {'命中' if hit else '缺失'}")
    else:
        pa = None
        print(f"  无法获得物理地址")
    
    results_tlb.append({
        'va': va, 'vpn': vpn, 'tlb_index': tlb_index, 'tlb_tag': tlb_tag,
        'hit': hit, 'ppn': ppn, 'pa': pa, 'offset': offset
    })

# 汇总表
print("\n" + "-" * 70)
print(f"{'访问':>4} | {'VA':>10} | {'VPN':>6} | {'TLB组':>5} | {'TLB命中':>6} | {'PPN':>6} | {'PA':>10}")
print("-" * 70)
for i, r in enumerate(results_tlb):
    print(f"{i+1:>4} | 0x{r['va']:06X} | 0x{r['vpn']:03X} | {r['tlb_index']:>5} | {'命中' if r['hit'] else '缺失':>6} | 0x{r['ppn']:03X} | 0x{r['pa']:06X}")

# ===== 子问题(3) Cache命中情况 =====
print("\n" + "=" * 60)
print("子问题(3): Cache命中情况")
print("=" * 60)

# Cache初始为空 (直接映射)
cache = {}  # index -> {'valid': bool, 'tag': int}

results_cache = []

for i, r in enumerate(results_tlb):
    pa = r['pa']
    print(f"\n--- 访问{i+1}: PA = 0x{pa:06X} ---")
    
    # 分解物理地址
    offset = pa & ((1 << CACHE_OFFSET_BITS) - 1)
    index = (pa >> CACHE_OFFSET_BITS) & ((1 << CACHE_INDEX_BITS) - 1)
    tag = pa >> (CACHE_OFFSET_BITS + CACHE_INDEX_BITS)
    
    print(f"  Offset = 0x{pa:06X} & 0x{(1<<CACHE_OFFSET_BITS)-1:X} = 0x{offset:02X}")
    print(f"  Index = (0x{pa:06X} >> {CACHE_OFFSET_BITS}) & 0x{(1<<CACHE_INDEX_BITS)-1:X} = 0x{(pa>>CACHE_OFFSET_BITS):X} & 0x{(1<<CACHE_INDEX_BITS)-1:X} = 0x{index:X}")
    print(f"  Tag = 0x{pa:06X} >> {CACHE_OFFSET_BITS+CACHE_INDEX_BITS} = 0x{tag:X}")
    
    # Cache查找
    hit = False
    if index in cache and cache[index]['valid'] and cache[index]['tag'] == tag:
        hit = True
        print(f"  Cache行{index:X}: Tag=0x{cache[index]['tag']:X}, 匹配! → 命中")
    else:
        if index in cache and cache[index]['valid']:
            print(f"  Cache行{index:X}: Tag=0x{cache[index]['tag']:X}, 不匹配! → 缺失(冲突)")
        else:
            print(f"  Cache行{index:X}: 空/无效 → 缺失(强制)")
        # 装入
        cache[index] = {'valid': True, 'tag': tag}
        print(f"  装入Cache行{index:X}, Tag=0x{tag:X}")
    
    results_cache.append({
        'pa': pa, 'tag': tag, 'index': index, 'offset': offset, 'hit': hit
    })

# 汇总表
print("\n" + "-" * 70)
print(f"{'访问':>4} | {'PA':>10} | {'Tag':>6} | {'Index':>6} | {'Offset':>7} | {'Cache命中':>7}")
print("-" * 70)
for i, r in enumerate(results_cache):
    print(f"{i+1:>4} | 0x{r['pa']:06X} | 0x{r['tag']:X} | 0x{r['index']:X} | 0x{r['offset']:02X} | {'命中' if r['hit'] else '缺失':>7}")

# 命中率
hits = sum(1 for r in results_cache if r['hit'])
print(f"\nCache命中率 = {hits}/{len(results_cache)} = {hits/len(results_cache)*100:.0f}%")
