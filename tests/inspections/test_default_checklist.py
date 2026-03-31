import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.inspections.checklist_defaults import get_default_checklist_items

EXPECTED_CATEGORIES = [
    "Allgemeiner Eindruck",
    "Küche",
    "Badezimmer",
    "Wohnbereiche",
    "Geräte",
    "Schlafzimmer",
    "Zugang & Sicherheit",
    "Nach der Reinigung",
]

VALID_RESULTS = {"ok", "flagged", "na"}


class TestDefaultChecklistFixture:
    def test_fixture_file_exists(self):
        fixture_path = Path(__file__).parents[2] / "apps" / "inspections" / "fixtures" / "default_checklist.json"
        assert fixture_path.exists(), "default_checklist.json fixture file not found"

    def test_fixture_is_valid_json(self):
        fixture_path = Path(__file__).parents[2] / "apps" / "inspections" / "fixtures" / "default_checklist.json"
        with open(fixture_path) as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_fixture_has_22_items(self):
        items = get_default_checklist_items()
        assert len(items) == 22

    def test_all_categories_present(self):
        items = get_default_checklist_items()
        categories = {item["category"] for item in items}
        assert categories == set(EXPECTED_CATEGORIES)

    def test_items_have_required_fields(self):
        items = get_default_checklist_items()
        required_fields = {"category", "label", "allowed_results", "order"}
        for item in items:
            missing = required_fields - set(item.keys())
            assert not missing, f"Item '{item.get('label', '?')}' missing fields: {missing}"

    def test_allowed_results_are_valid(self):
        items = get_default_checklist_items()
        for item in items:
            for result in item["allowed_results"]:
                assert (
                    result in VALID_RESULTS
                ), f"Item '{item['label']}' has invalid result '{result}'. Valid: {VALID_RESULTS}"

    def test_order_is_sequential(self):
        items = get_default_checklist_items()
        orders = [item["order"] for item in items]
        assert orders == list(range(1, 23))

    def test_na_items_are_correct(self):
        """Items that should allow N/A are those with optional equipment."""
        items = get_default_checklist_items()
        na_items = [item for item in items if "na" in item["allowed_results"]]
        na_labels = {item["label"] for item in na_items}
        # These items should allow N/A per the PRD
        assert len(na_items) == 5, f"Expected 5 N/A-capable items, got {len(na_items)}: {na_labels}"

    def test_labels_contain_german_text(self):
        """All labels should be in German."""
        items = get_default_checklist_items()
        german_chars = {"ä", "ö", "ü", "ß", "Ä", "Ö", "Ü"}
        has_german = any(any(c in item["label"] for c in german_chars) for item in items)
        assert has_german, "Expected German text with umlauts in labels"

    def test_category_order_follows_inspection_flow(self):
        """Categories should appear in logical inspection order."""
        items = get_default_checklist_items()
        seen_categories = []
        for item in items:
            if item["category"] not in seen_categories:
                seen_categories.append(item["category"])
        assert seen_categories == EXPECTED_CATEGORIES

    def test_items_compatible_with_checklist_template_format(self):
        """Items should be compatible with ChecklistTemplate.items JSONField format."""
        items = get_default_checklist_items()
        for item in items:
            assert isinstance(item["category"], str)
            assert isinstance(item["label"], str)
            assert isinstance(item["allowed_results"], list)
            assert isinstance(item["order"], int)
            assert len(item["label"]) <= 255  # Matches InspectionItem.checklist_label max_length
            assert len(item["category"]) <= 100  # Matches InspectionItem.category max_length


@pytest.mark.django_db
class TestLoadDefaultChecklistCommand:
    def test_command_runs_successfully(self):
        out = StringIO()
        call_command("load_default_checklist", stdout=out)
        output = out.getvalue()
        assert "22" in output
        assert "Loaded" in output

    def test_command_lists_all_categories(self):
        out = StringIO()
        call_command("load_default_checklist", stdout=out)
        output = out.getvalue()
        for category in EXPECTED_CATEGORIES:
            assert category in output, f"Category '{category}' not in command output"
