import pytest
from playwright.sync_api import Page, expect


@pytest.mark.django_db
class TestPublicPages:
    """Smoke tests: public pages load and render basic content."""

    def test_landing_page_loads(self, page: Page, live_server):
        page.goto(f"{live_server.url}/")
        expect(page).to_have_title(page.title())
        assert page.locator("body").is_visible()

    def test_landing_page_has_content(self, page: Page, live_server):
        page.goto(f"{live_server.url}/")
        # Page should have some visible text content
        body_text = page.locator("body").inner_text()
        assert len(body_text) > 0
