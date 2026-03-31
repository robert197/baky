import pytest
from django.http import Http404, HttpResponse
from django.test import RequestFactory

from apps.accounts.decorators import inspector_required, owner_required, role_required
from tests.factories import AdminFactory, InspectorFactory, UserFactory


@pytest.fixture
def rf():
    return RequestFactory()


def dummy_view(request):
    return HttpResponse("OK")


class TestRoleRequired:
    def test_unauthenticated_redirects_to_login(self, rf):
        from django.contrib.auth.models import AnonymousUser

        request = rf.get("/test/")
        request.user = AnonymousUser()
        decorated = role_required("owner")(dummy_view)
        response = decorated(request)
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_correct_role_allowed(self, rf, db):
        request = rf.get("/test/")
        request.user = UserFactory(role="owner")
        decorated = role_required("owner")(dummy_view)
        response = decorated(request)
        assert response.status_code == 200

    def test_wrong_role_returns_404(self, rf, db):
        request = rf.get("/test/")
        request.user = InspectorFactory()
        decorated = role_required("owner")(dummy_view)
        with pytest.raises(Http404):
            decorated(request)


class TestOwnerRequired:
    def test_owner_allowed(self, rf, db):
        request = rf.get("/test/")
        request.user = UserFactory()
        decorated = owner_required(dummy_view)
        response = decorated(request)
        assert response.status_code == 200

    def test_inspector_gets_404(self, rf, db):
        request = rf.get("/test/")
        request.user = InspectorFactory()
        decorated = owner_required(dummy_view)
        with pytest.raises(Http404):
            decorated(request)

    def test_admin_gets_404(self, rf, db):
        request = rf.get("/test/")
        request.user = AdminFactory()
        decorated = owner_required(dummy_view)
        with pytest.raises(Http404):
            decorated(request)

    def test_unauthenticated_redirects(self, rf):
        from django.contrib.auth.models import AnonymousUser

        request = rf.get("/test/")
        request.user = AnonymousUser()
        decorated = owner_required(dummy_view)
        response = decorated(request)
        assert response.status_code == 302


class TestInspectorRequired:
    def test_inspector_allowed(self, rf, db):
        request = rf.get("/test/")
        request.user = InspectorFactory()
        decorated = inspector_required(dummy_view)
        response = decorated(request)
        assert response.status_code == 200

    def test_owner_gets_404(self, rf, db):
        request = rf.get("/test/")
        request.user = UserFactory()
        decorated = inspector_required(dummy_view)
        with pytest.raises(Http404):
            decorated(request)

    def test_unauthenticated_redirects(self, rf):
        from django.contrib.auth.models import AnonymousUser

        request = rf.get("/test/")
        request.user = AnonymousUser()
        decorated = inspector_required(dummy_view)
        response = decorated(request)
        assert response.status_code == 302
