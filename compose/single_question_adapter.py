"""Single question adapter — loads slot_blueprint.yaml for individual question tasks.

Reads intake layer output (slot_blueprint schema) and converts to SlotBlueprint dataclass.
Handles field name differences between the LLM-generated YAML and the dataclass.
"""

from pathlib import Path
from typing import Optional

import yaml

from core_new.doc_pipeline.contracts import SlotBlueprint


def normalize_slot_blueprint_data(data: dict) -> dict:
    """Normalize LLM-generated slot_blueprint YAML to match SlotBlueprint dataclass fields.

    Handles: alias fields, nested→flat conversion, extra metadata removal.
    """
    data = dict(data)  # shallow copy

    # Remove metadata / non-dataclass fields
    for key in ("schema_version", "task_type", "routing", "confidence",
                "constraints", "kg_node_path"):
        data.pop(key, None)

    # Alias: difficulty_level → target_difficulty
    if "difficulty_level" in data and "target_difficulty" not in data:
        data["target_difficulty"] = data.pop("difficulty_level")
    else:
        data.pop("difficulty_level", None)

    # Nested excluded → flat excluded_modes / excluded_knowledge
    excluded = data.pop("excluded", None)
    if isinstance(excluded, dict):
        data.setdefault("excluded_modes", excluded.get("modes", []))
        data.setdefault("excluded_knowledge", excluded.get("knowledge", []))

    # Only keep fields that exist in SlotBlueprint
    allowed = set(SlotBlueprint.__dataclass_fields__)
    return {k: v for k, v in data.items() if k in allowed}


def load_slot_blueprint(path: str) -> Optional[SlotBlueprint]:
    """Load slot_blueprint.yaml and convert to SlotBlueprint dataclass.

    Args:
        path: Path to slot_blueprint.yaml file

    Returns:
        SlotBlueprint instance or None if file doesn't exist/invalid
    """
    blueprint_path = Path(path)
    if not blueprint_path.exists():
        return None

    try:
        with open(blueprint_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        normalized = normalize_slot_blueprint_data(data)
        return SlotBlueprint(**normalized)
    except Exception as e:
        print(f"  ERROR: Failed to load slot_blueprint from {path}: {e}")
        return None


def build_blueprint_map(blueprint: SlotBlueprint) -> dict:
    """Build a {slot_id: blueprint} map from a single SlotBlueprint.

    For single question tasks, this creates a singleton map compatible
    with downstream pipeline expecting dict[str, SlotBlueprint].
    """
    return {blueprint.slot_id: blueprint}
