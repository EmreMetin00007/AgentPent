import os
import tempfile
from unittest.mock import patch

import pytest

from tools.browser_tool import BrowserVisionTool


class _FakePage:
    def set_default_timeout(self, timeout):
        self.timeout = timeout

    async def goto(self, url, wait_until="networkidle", timeout=15000):
        self.url = url
        self.wait_until = wait_until

    async def evaluate(self, script):
        return {
            "textSnippet": "Hello Vision",
            "interactives": ["button -> Secure Login"],
        }

    async def screenshot(self, full_page=True, type="jpeg", quality=60, timeout=0):
        return b"x" * 256


class _FakeBrowser:
    def __init__(self):
        self.last_page = None

    async def new_page(self, **kwargs):
        self.last_page = _FakePage()
        return self.last_page

    async def close(self):
        return None


class _FakeChromium:
    def __init__(self):
        self.launch_kwargs = None
        self.browser = _FakeBrowser()

    async def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        return self.browser


class _FakePlaywright:
    def __init__(self):
        self.chromium = _FakeChromium()


class _FakePlaywrightContext:
    def __init__(self):
        self.playwright = _FakePlaywright()

    async def __aenter__(self):
        return self.playwright

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_browser_vision_local_file():
    fd, path = tempfile.mkstemp(suffix=".html")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("""
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Hello Vision</h1>
                <button id="login-btn">Secure Login</button>
            </body>
        </html>
        """)

    url = f"file:///{path.replace(chr(92), '/')}"
    tool = BrowserVisionTool()
    tool.validate_scope = lambda x, y: True

    with patch(
        "tools.browser_tool.async_playwright",
        return_value=_FakePlaywrightContext(),
    ):
        result = await tool.execute({"url": url})

    os.remove(path)

    assert result.success is True
    assert "Secure Login" in result.stdout
    assert "image_base64" in result.parsed_data
    assert len(result.parsed_data["image_base64"]) > 100
    assert result.parsed_data["url"].startswith("file:///")
    assert "file:///" in result.command


@pytest.mark.asyncio
async def test_browser_vision_uses_no_sandbox_when_running_as_root(monkeypatch):
    tool = BrowserVisionTool()
    tool.validate_scope = lambda x, y: True
    fake_context = _FakePlaywrightContext()

    monkeypatch.setattr("tools.browser_tool.os.geteuid", lambda: 0, raising=False)

    with patch(
        "tools.browser_tool.async_playwright",
        return_value=fake_context,
    ):
        result = await tool.execute({"url": "http://example.com"})

    assert result.success is True
    assert fake_context.playwright.chromium.launch_kwargs["args"] == [
        "--no-sandbox",
        "--disable-setuid-sandbox",
    ]
    assert fake_context.playwright.chromium.browser.last_page.wait_until == "domcontentloaded"
