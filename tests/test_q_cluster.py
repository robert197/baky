"""Tests for Django-Q2 configuration and admin integration."""

import pytest
from django.conf import settings
from django.contrib.admin.sites import site as admin_site


class TestQClusterConfig:
    def test_cluster_name(self):
        assert settings.Q_CLUSTER["name"] == "baky"

    def test_orm_broker(self):
        assert settings.Q_CLUSTER["orm"] == "default"

    def test_worker_count(self):
        assert settings.Q_CLUSTER["workers"] == 2

    def test_timeout_configured(self):
        assert settings.Q_CLUSTER["timeout"] == 120

    def test_retry_exceeds_timeout(self):
        assert settings.Q_CLUSTER["retry"] > settings.Q_CLUSTER["timeout"]

    def test_queue_limit(self):
        assert settings.Q_CLUSTER["queue_limit"] == 50


@pytest.mark.django_db
class TestDjangoQAdminIntegration:
    def test_django_q_app_installed(self):
        assert "django_q" in settings.INSTALLED_APPS

    def test_failure_model_registered_in_admin(self):
        from django_q.models import Failure

        assert Failure in admin_site._registry

    def test_schedule_model_registered_in_admin(self):
        from django_q.models import Schedule

        assert Schedule in admin_site._registry

    def test_success_model_registered_in_admin(self):
        from django_q.models import Success

        assert Success in admin_site._registry
