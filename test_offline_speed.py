"""Offline vLLM throughput test - matching server config."""
import time, json, sys
from vllm import LLM, SamplingParams

MODEL = '/root/shared-nvme/llm_edu/models/Qwen3.6-27B-AWQ-INT4'

if __name__ == '__main__':
    print('Loading model (matching server config + language_model_only)...', flush=True)
    t0 = time.time()
    llm = LLM(
        model=MODEL,
        tensor_parallel_size=1,
        gpu_memory_utilization=0.95,
        max_model_len=15000,
        max_num_batched_tokens=4096,
        trust_remote_code=True,
        kv_cache_dtype='fp8',
        enable_prefix_caching=True,
        enable_chunked_prefill=True,
        compilation_config={
            'cudagraph_capture_sizes': [1, 2, 4, 8],
            'max_cudagraph_capture_size': 8,
        },
        language_model_only=True,
    )
    print(f'Model loaded in {time.time()-t0:.1f}s', flush=True)

    # Test 1: Short responses (20 prompts, batch_size 64)
    print('\n--- Test 1: Short (64 tokens, 20 prompts) ---', flush=True)
    msgs = [[{'role':'user','content':f'{i}+{i}=? 只回答数字'}] for i in range(20)]
    sp_short = SamplingParams(temperature=0.0, max_tokens=64)
    t0 = time.time()
    outs = llm.chat(msgs, sampling_params=sp_short)
    dt = time.time()-t0
    total_toks = sum(len(o.outputs[0].token_ids) for o in outs)
    print(f'  {dt:.1f}s, {20/dt:.1f} prompts/s, {total_toks/dt:.0f} tok/s', flush=True)

    # Test 2: 5 thinking prompts
    print('\n--- Test 2: Thinking (8192 max, 5 prompts) ---', flush=True)
    with open('/home/dev/full_question.json') as f:
        qs = json.load(f)
    test_qs = [qs[i] for i in [0, 10, 20, 30, 40]]
    msgs2 = [[{'role':'user','content':q.get('prompt','')}] for q in test_qs]
    sp_think = SamplingParams(temperature=1.0, top_p=0.95, top_k=20, max_tokens=8192)
    t0 = time.time()
    outs2 = llm.chat(msgs2, sampling_params=sp_think)
    dt2 = time.time()-t0
    total_toks2 = sum(len(o.outputs[0].token_ids) for o in outs2)
    print(f'  {dt2:.1f}s, {5/dt2:.1f} prompts/s, {total_toks2/dt2:.0f} tok/s', flush=True)
    for o in outs2:
        text = o.outputs[0].text
        print(f'  len={len(text)} preview={text[:100].replace(chr(10)," ")}', flush=True)
