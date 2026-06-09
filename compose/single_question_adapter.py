"""Single question adapter — loads slot_blueprint.yaml for individual question tasks.

Reads intake layer output (slot_blueprint schema) and converts to SlotBlueprint dataclass.
"""

from dataclasses import replace
from pathlib import Path
from typing import Optional

import yaml

from core_new.doc_pipeline.contracts import SlotBlueprint


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

        # Extract routing block if present (metadata only, not part of SlotBlueprint)
        routing = data.pop("routing", None)
        confidence = data.pop("confidence", None)

        # Convert to SlotBlueprint
        return SlotBlueprint(**data)
    except Exception as e:
        print(f"  ERROR: Failed to load slot_blueprint from {path}: {e}")
        return None


def build_blueprint_map(blueprint: SlotBlueprint) -> dict:
    """Build a {slot_id: blueprint} map from a single SlotBlueprint.

    For single question tasks, this creates a singleton map compatible
    with downstream pipeline expecting dict[str, SlotBlueprint].

    Args:
        blueprint: SlotBlueprint instance

    Returns:
        Dict mapping slot_id to blueprint
    """
    return {blueprint.slot_id: blueprint}
