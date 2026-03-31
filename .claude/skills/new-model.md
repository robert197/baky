---
name: new-model
description: Add a new Django model with admin registration, migration, factory, and tests. Follows BAKY conventions.
user-invokable: true
argument-hint: "<AppName.ModelName> [field1:type field2:type ...]"
---

# Add a New Django Model

## Input
Parse `$ARGUMENTS` for: app name, model name, and optional field definitions.
If not provided, ask the user.

## Step 1: Define the Model

Add to `apps/<app_name>/models.py`:

```python
class ModelName(TimeStampedModel):
    """Brief description."""

    # Fields here
    # Use choices for status/type fields:
    # class Status(models.TextChoices):
    #     ACTIVE = "active", "Active"

    class Meta:
        ordering = ["-created_at"]
        # Add indexes, constraints, unique_together as needed

    def __str__(self):
        return self.name  # or appropriate field
```

**Conventions**:
- Inherit from `TimeStampedModel` (provides `created_at`, `updated_at`)
- Use `TextChoices` for choice fields
- Use `ForeignKey` with `related_name`
- Encrypted fields for sensitive data (access codes, PINs): use `django-encrypted-model-fields`
- JSONField for flexible schemas (checklists)
- Always define `__str__`, `Meta.ordering`

## Step 2: Register in Admin

Add to `apps/<app_name>/admin.py`:

```python
@admin.register(ModelName)
class ModelNameAdmin(admin.ModelAdmin):
    list_display = ["__str__", "created_at"]  # Add key fields
    list_filter = []  # Add filterable fields
    search_fields = []  # Add searchable fields
    readonly_fields = ["created_at", "updated_at"]
```

## Step 3: Create Migration

```bash
make makemigrations
make migrate
```

## Step 4: Create Factory

Add to `tests/factories.py`:

```python
class ModelNameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ModelName

    # Define field defaults using factory.Faker, factory.Sequence, etc.
```

## Step 5: Write Tests

Create `tests/<app_name>/test_models.py`:

```python
import pytest
from tests.factories import ModelNameFactory

@pytest.mark.django_db
class TestModelName:
    def test_create(self):
        obj = ModelNameFactory()
        assert obj.pk is not None

    def test_str(self):
        obj = ModelNameFactory(name="Test")
        assert str(obj) == "Test"
```

## Step 6: Verify

```bash
make test ARGS="-k test_model_name"
make lint
```
