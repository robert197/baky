import pytest


@pytest.fixture
def user(db):
    from apps.accounts.models import User

    return User.objects.create_user(username="testuser", password="testpass123", role=User.Role.OWNER)


@pytest.fixture
def inspector(db):
    from apps.accounts.models import User

    return User.objects.create_user(username="inspector", password="testpass123", role=User.Role.INSPECTOR)
