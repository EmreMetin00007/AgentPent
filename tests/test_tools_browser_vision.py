import os
import tempfile
from unittest.mock import patch

import pytest

from tools.browser_tool import BrowserVisionTool


class _FakePage:
    async def goto(self, url, wait_until="networkidle", timeout=15000):
        self.url = url

    async def evaluate(self, script):
        return {
            "textSnippet": "Hello Vision",
            "interactives": ["button -> Secure Login"],
        }

    async def screenshot(self, full_page=True, type="jpeg", quality=60):
        return b"x" * 256


class _FakeBrowser:
    async def new_page(self, **kwargs):
        return _FakePage()

    async def close(self):
        return None


class _FakeChromium:
    async def launch(self, headless=True):
        return _FakeBrowser()


class _FakePlaywright:
    chromium = _FakeChromium()


class _FakePlaywrightContext:
    async def __aenter__(self):
        return _FakePlaywright()

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
