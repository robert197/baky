import pytest

from tests.factories import (
    AdminFactory,
    ApartmentFactory,
    ChecklistTemplateFactory,
    InspectionFactory,
    InspectionItemFactory,
    InspectorFactory,
    PhotoFactory,
    SubscriptionFactory,
    UserFactory,
)


@pytest.fixture
def user(db):
    """Owner user (default role)."""
    return UserFactory()


@pytest.fixture
def inspector(db):
    """Inspector user."""
    return InspectorFactory()


@pytest.fixture
def admin_user(db):
    """Admin user."""
    return AdminFactory()


@pytest.fixture
def apartment(db, user):
    """Apartment belonging to the default owner user."""
    return ApartmentFactory(owner=user)


@pytest.fixture
def checklist_template(db, apartment):
    """Checklist template for the default apartment."""
    return ChecklistTemplateFactory(apartment=apartment)


@pytest.fixture
def inspection(db, apartment, inspector):
    """Scheduled inspection for the default apartment."""
    return InspectionFactory(apartment=apartment, inspector=inspector)


@pytest.fixture
def inspection_item(db, inspection):
    """Inspection item for the default inspection."""
    return InspectionItemFactory(inspection=inspection)


@pytest.fixture
def photo(db, inspection):
    """Photo for the default inspection."""
    return PhotoFactory(inspection=inspection)


@pytest.fixture
def subscription(db, user):
    """Subscription for the default owner user."""
    return SubscriptionFactory(owner=user)
