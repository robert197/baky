import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import EmailVerificationToken, OnboardingProgress
from tests.factories import ApartmentFactory, UserFactory


class TestEmailVerificationToken:
    def test_create(self, db):
        user = UserFactory()
        token = EmailVerificationToken.objects.create(user=user)
        assert token.pk is not None
        assert token.token is not None
        assert token.verified_at is None

    def test_str_pending(self, db):
        user = UserFactory(email="test@example.com")
        token = EmailVerificationToken.objects.create(user=user)
        assert "ausstehend" in str(token)

    def test_str_verified(self, db):
        user = UserFactory(email="test@example.com")
        token = EmailVerificationToken.objects.create(user=user, verified_at=timezone.now())
        assert "verifiziert" in str(token)

    def test_is_verified_property(self, db):
        user = UserFactory()
        token = EmailVerificationToken.objects.create(user=user)
        assert token.is_verified is False
        token.verified_at = timezone.now()
        assert token.is_verified is True

    def test_is_expired_within_48h(self, db):
        user = UserFactory()
        token = EmailVerificationToken.objects.create(user=user)
        assert token.is_expired is False

    def test_is_expired_after_48h(self, db):
        user = UserFactory()
        token = EmailVerificationToken.objects.create(user=user)
        token.created_at = timezone.now() - timezone.timedelta(hours=49)
        token.save(update_fields=["created_at"])
        assert token.is_expired is True

    def test_verified_token_not_expired(self, db):
        user = UserFactory()
        token = EmailVerificationToken.objects.create(user=user, verified_at=timezone.now())
        token.created_at = timezone.now() - timezone.timedelta(hours=49)
        token.save(update_fields=["created_at"])
        assert token.is_expired is False

    def test_verify_method(self, db):
        user = UserFactory()
        token = EmailVerificationToken.objects.create(user=user)
        result = token.verify()
        assert result is True
        assert token.is_verified is True

    def test_verify_already_verified(self, db):
        user = UserFactory()
        token = EmailVerificationToken.objects.create(user=user, verified_at=timezone.now())
        result = token.verify()
        assert result is False

    def test_verify_expired_token(self, db):
        user = UserFactory()
        token = EmailVerificationToken.objects.create(user=user)
        token.created_at = timezone.now() - timezone.timedelta(hours=49)
        token.save(update_fields=["created_at"])
        result = token.verify()
        assert result is False

    def test_one_token_per_user(self, db):
        user = UserFactory()
        EmailVerificationToken.objects.create(user=user)
        with pytest.raises(IntegrityError):
            EmailVerificationToken.objects.create(user=user)

    def test_unique_token(self, db):
        user1 = UserFactory()
        user2 = UserFactory()
        t1 = EmailVerificationToken.objects.create(user=user1)
        t2 = EmailVerificationToken.objects.create(user=user2)
        assert t1.token != t2.token

    def test_cascade_delete_user(self, db):
        user = UserFactory()
        token = EmailVerificationToken.objects.create(user=user)
        user.delete()
        assert not EmailVerificationToken.objects.filter(pk=token.pk).exists()


class TestOnboardingProgress:
    def test_create(self, db):
        user = UserFactory()
        progress = OnboardingProgress.objects.create(user=user)
        assert progress.pk is not None
        assert progress.current_step == OnboardingProgress.Step.APARTMENT
        assert progress.is_complete is False

    def test_str(self, db):
        user = UserFactory(username="testuser")
        progress = OnboardingProgress.objects.create(user=user)
        assert "testuser" in str(progress)
        assert "1" in str(progress)

    def test_step_choices(self):
        assert OnboardingProgress.Step.APARTMENT == 1
        assert OnboardingProgress.Step.CHECKLIST == 2
        assert OnboardingProgress.Step.PLAN == 3
        assert OnboardingProgress.Step.CONFIRMATION == 4

    def test_one_per_user(self, db):
        user = UserFactory()
        OnboardingProgress.objects.create(user=user)
        with pytest.raises(IntegrityError):
            OnboardingProgress.objects.create(user=user)

    def test_apartment_nullable(self, db):
        user = UserFactory()
        progress = OnboardingProgress.objects.create(user=user)
        assert progress.apartment is None

    def test_apartment_set_null_on_delete(self, db):
        user = UserFactory()
        apartment = ApartmentFactory(owner=user)
        progress = OnboardingProgress.objects.create(user=user, apartment=apartment)
        apartment.delete()
        progress.refresh_from_db()
        assert progress.apartment is None

    def test_selected_plan_blank(self, db):
        user = UserFactory()
        progress = OnboardingProgress.objects.create(user=user)
        assert progress.selected_plan == ""

    def test_cascade_delete_user(self, db):
        user = UserFactory()
        progress = OnboardingProgress.objects.create(user=user)
        user.delete()
        assert not OnboardingProgress.objects.filter(pk=progress.pk).exists()
