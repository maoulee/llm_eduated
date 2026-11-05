# Experiments

This directory contains standalone experiment and A/B test scripts. These are not pytest tests — they're manual exploration scripts.

## Scripts

| Script | Purpose |
|--------|---------|
| `adversarial_review.py` | Adversarial review: Qwen (local) reviews both Qwen's and GLM 5.1's generated questions |
| `analysis_ab.py` | A/B test: run analysis agent with current vs enhanced prompt (K-value difficulty, condition audit) |
| `glm_q43.py` | Quick test: run Q43 full pipeline with GLM (no WebGPT) |
| `hybrid_outline.py` | Test hybrid composition: use GPT to generate paper outline via WebGPT |
| `model_compare.py` | Quick comparison: Qwen (local) vs GLM 5.1 (remote) question generation for Q14 |
| `question_ab.py` | A/B test: question agent with brief thinking vs deep thinking (uses existing Q43 blueprint) |
| `sc_question_local.py` | Quick test: run SCQuestionAgent only (no review) with local model for Q12 and Q18 |
| `self_adversarial.py` | Qwen self-adversarial loop: generate → review → fix → review → ... until pass |

## Usage

Each script has an `if __name__ == "__main__"` guard. Run directly:

```bash
python3 experiments/adversarial_review.py
```
