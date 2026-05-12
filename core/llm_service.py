from vllm import LLM, SamplingParams
import json
from transformers import AutoTokenizer
from typing import List, Dict, Union
from vllm.config import CompilationConfig, CompilationLevel

class LLMService:
    def __init__(self, model_name, tokenizer_name=None):
        self.llm = LLM(model=model_name, 
                       trust_remote_code=True, 
                       tensor_parallel_size=2,
                       max_model_len=10000,
                       quantization='awq_marlin',
                       gpu_memory_utilization=0.6,
                       compilation_config=CompilationConfig(
        level=CompilationLevel.PIECEWISE,
        # By default, it goes up to max_num_seqs
        cudagraph_capture_sizes=[1, 2, 4, 8, 16],
    ))
        self.tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_name if tokenizer_name else model_name, 
            trust_remote_code=True
        )
        self.sampling_params = SamplingParams(temperature=0.6, top_p=0.9, max_tokens=8192)
        

    def _apply_template_batch(self, messages_batch: List[List[Dict]], enable_thinking=False) -> List[str]:
        """将一批messages应用模板，返回一批待处理的文本。"""
        return [
            self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=enable_thinking,
                max_length=4096
            ) for messages in messages_batch
        ]

    def _generate_batch(self, prompts_batch: List[str], stop_sequences: List[str] = None) -> List[str]:
        """对一批文本进行生成，返回一批结果，支持自定义停止序列。"""
        # 如果传入了stop_sequences，就创建一个新的、临时的采样参数对象
        if stop_sequences:
            sampling_params = SamplingParams(
                temperature=0.6, top_p=0.9, max_tokens=4092, stop=stop_sequences
            )
        else:
            sampling_params = sampling_params = SamplingParams(
                temperature=0.6, top_p=0.9, max_tokens=4092
            )
        
        outputs = self.llm.generate(prompts_batch, sampling_params)
        return [output.outputs[0].text for output in outputs]

    def generate_with_think_and_parse_batch(self, messages_batch: List[List[Dict]], stop_sequences: List[str] = None,enable_thinking:bool=None) -> List[Dict]:
        """对一批messages进行带思考模式的生成和解析，支持停止序列。"""
        input_texts = self._apply_template_batch(messages_batch, enable_thinking=enable_thinking)
        raw_outputs = self._generate_batch(input_texts, stop_sequences=stop_sequences)
        
        results = []
        for raw_output in raw_outputs:
            try:
                # 思考模式的解析保持不变
                think_content = raw_output.split("<think>")[1].split("</think>")[0].strip()
                answer_content = raw_output.split("</think>")[1].strip()
                results.append({"think": think_content, "answer": answer_content})
            except IndexError:
                results.append({"think": "N/A", "answer": raw_output.strip()})
        return results

    def generate_json_batch(self, messages_batch: List[List[Dict]]) -> List[Union[Dict, None]]:
        """对一批messages进行JSON生成和解析。"""
        # JSON生成通常不需要stop token，但我们保持接口一致性
        input_texts = self._apply_template_batch(messages_batch, enable_thinking=False)
        # 这里我们假设JSON生成不需要stop_sequences，所以不传递
        raw_outputs = self._generate_batch(input_texts)
        
        results = []
        for raw_output in raw_outputs:
            try:
                if "```json" in raw_output:
                    clean_output = raw_output.split("```json\n")[1].split("```")[0]
                else:
                    # 对于JSON，我们只取第一个 '{' 和最后一个 '}' 之间的内容，以提高鲁棒性
                    start = raw_output.find('{')
                    end = raw_output.rfind('}')
                    if start != -1 and end != -1:
                        clean_output = raw_output[start:end+1]
                    else:
                        clean_output = raw_output
                results.append(json.loads(clean_output))
            except (json.JSONDecodeError, IndexError) as e:
                print(f"Warning: Failed to parse JSON. Error: {e}\nRaw output: {raw_output}")
                results.append(None)
        return results