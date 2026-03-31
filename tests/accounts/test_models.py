from apps.accounts.models import User
from tests.factories import AdminFactory, InspectorFactory, UserFactory


class TestUserModel:
    def test_create_user(self, db):
        user = UserFactory()
        assert user.pk is not None
        assert user.role == User.Role.OWNER

    def test_owner_property(self, db):
        user = UserFactory()
        assert user.is_owner is True
        assert user.is_inspector is False

    def test_inspector_property(self, db):
        inspector = InspectorFactory()
        assert inspector.is_inspector is True
        assert inspector.is_owner is False

    def test_admin_factory(self, db):
        admin = AdminFactory()
        assert admin.role == User.Role.ADMIN

    def test_user_str(self, db):
        user = UserFactory(username="testuser")
        assert str(user) == "testuser (owner)"
