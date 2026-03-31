import os

import pytest
from django.test.utils import override_settings
from playwright.sync_api import Page

# Playwright runs an internal event loop; Django's async safety check must be disabled for e2e.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture(scope="session")
def browser_context_args():
    """Default browser context args for all tests."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture()
def mobile_page(page: Page):
    """Mobile viewport for inspector tests (375x812 = iPhone X)."""
    page.set_viewport_size({"width": 375, "height": 812})
    return page


@pytest.fixture()
def live_url(live_server):
    """Return the live server URL for e2e tests."""
    return live_server.url


@pytest.fixture(autouse=True)
def _e2e_settings():
    """Override settings for e2e tests."""
    with override_settings(
        STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
        DEFAULT_FILE_STORAGE="django.core.files.storage.FileSystemStorage",
    ):
        yield
