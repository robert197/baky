import factory

from apps.accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    role = User.Role.OWNER

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or "testpass123")
        if create:
            self.save(update_fields=["password"])


class InspectorFactory(UserFactory):
    role = User.Role.INSPECTOR


class AdminFactory(UserFactory):
    role = User.Role.ADMIN


# Alias for readability — UserFactory already defaults to OWNER
OwnerFactory = UserFactory
