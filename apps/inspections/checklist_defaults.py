import json
from pathlib import Path


def get_default_checklist_items() -> list[dict]:
    """Return the 22 default checklist items from the fixture file."""
    fixture_path = Path(__file__).parent / "fixtures" / "default_checklist.json"
    with open(fixture_path) as f:
        return json.load(f)
