"""Run slot-template driven paper composition and generation.

Thin shim — all logic lives in the compose/ package.

Usage:
    python run_slot_composition.py --routing hybrid --slots Q12 Q13
    python run_slot_composition.py --routing all_local --slots Q12 Q13
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# Re-export public API for backward compatibility (tests monkeypatch these)
from compose import (  # noqa: E402
    assemble_slot_experience_doc,
    compose_paper,
    main,
    run_compose,
    run_composition,
    run_generate,
)

if __name__ == "__main__":
    asyncio.run(main())
