import pytest

from tests.factories import AdminFactory, InspectorFactory, UserFactory


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
