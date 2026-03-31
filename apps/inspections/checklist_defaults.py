import functools
import json
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


@functools.lru_cache(maxsize=1)
def get_default_checklist_items() -> list[dict]:
    """Return the 22 default checklist items from the fixture file."""
    fixture_path = Path(__file__).parent / "fixtures" / "default_checklist.json"
    if not fixture_path.exists():
        raise ImproperlyConfigured(f"Default checklist fixture not found: {fixture_path}")
    with open(fixture_path) as f:
        return json.load(f)
