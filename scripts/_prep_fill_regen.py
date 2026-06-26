"""提取 Paper 1 的 4 个填空错位 slot 为独立 regen handoff。"""
import yaml
from pathlib import Path

base = Path("workspace/4c0e71a4c616")
hf = yaml.safe_load((base / "compose/paper_request.yaml").read_text(encoding="utf-8"))
keep = ["Q16", "Q17", "Q18", "Q20"]
hf["slots"] = [s for s in hf["slots"] if s.get("slot_id") in keep]
out = base / "compose/_regen_fill_4.yaml"
out.write_text(yaml.safe_dump(hf, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("wrote", out, "slots:", [s["slot_id"] for s in hf["slots"]])
