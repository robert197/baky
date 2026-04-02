import pytest

from apps.dashboard.tasks import (
    send_extra_inspection_notification,
    send_plan_change_notification,
    send_subscription_action_notification,
)
from tests.factories import ApartmentFactory


@pytest.mark.django_db
class TestAdminNotificationTasks:
    def test_send_plan_change_notification(self, subscription, mailoutbox):
        send_plan_change_notification(subscription.owner.pk, "premium", "Upgrade bitte")
        assert len(mailoutbox) == 2  # admin + owner confirmation
        admin_mail = mailoutbox[0]
        assert "Planänderung" in admin_mail.subject
        assert "premium" in admin_mail.body.lower() or "Premium" in admin_mail.body

    def test_send_plan_change_without_message(self, subscription, mailoutbox):
        send_plan_change_notification(subscription.owner.pk, "standard", "")
        assert len(mailoutbox) == 2

    def test_send_pause_notification(self, subscription, mailoutbox):
        send_subscription_action_notification(subscription.owner.pk, "pause", "Urlaub")
        assert len(mailoutbox) == 2
        assert "Pausierung" in mailoutbox[0].subject or "pausier" in mailoutbox[0].subject.lower()

    def test_send_cancel_notification(self, subscription, mailoutbox):
        send_subscription_action_notification(subscription.owner.pk, "cancel", "")
        assert len(mailoutbox) == 2
        assert "Kündigung" in mailoutbox[0].subject or "kündig" in mailoutbox[0].subject.lower()

    def test_send_extra_inspection_notification(self, subscription, mailoutbox):
        apartment = ApartmentFactory(owner=subscription.owner)
        send_extra_inspection_notification(subscription.owner.pk, apartment.pk, "2026-04-15", "Dringend")
        assert len(mailoutbox) == 2
        assert "Inspektion" in mailoutbox[0].subject

    def test_send_extra_inspection_without_notes(self, subscription, mailoutbox):
        apartment = ApartmentFactory(owner=subscription.owner)
        send_extra_inspection_notification(subscription.owner.pk, apartment.pk, "2026-04-15", "")
        assert len(mailoutbox) == 2

    def test_owner_receives_confirmation(self, subscription, mailoutbox):
        send_plan_change_notification(subscription.owner.pk, "premium", "")
        owner_mail = mailoutbox[1]
        assert subscription.owner.email in owner_mail.to
        assert "Bestätigung" in owner_mail.subject or "bestätigung" in owner_mail.subject.lower()
