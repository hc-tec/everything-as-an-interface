

import pytest
from playwright.async_api import Page, BrowserContext
from playwright.async_api import async_playwright

from src import BrowserAutomation

@pytest.fixture
def mock_page(mocker):
    page = mocker.Mock(spec=Page)
    yield page

@pytest.fixture
def mock_context(mocker):
    ctx = mocker.Mock(spec=BrowserContext)
    yield ctx

@pytest.fixture
def mock_browser(mocker, mock_page, mock_context):
    browser = BrowserAutomation()
    mocker.patch.object(browser, 'start', return_value=None)
    # browser.start = mocker.AsyncMock(return_value=None)
    browser.page = mock_page
    browser.context = mock_context
    yield browser

@pytest.fixture
async def page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page_ = await context.new_page()
        yield page_
        await browser.close()
