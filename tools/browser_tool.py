"""AgentPent - Browser Vision Tool.

Uses Playwright to open a page, capture a screenshot, and summarize DOM text.
"""

import base64
import logging
import os
from typing import Any, Dict

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.browser")


class BrowserVisionTool(BaseTool):
    """Headless browser helper tool."""

    name = "browser_vision"
    description = (
        "Hedef web sayfasina headless Chromium tarayicisi ile gider, tam ekran "
        "goruntusu alir ve sayfa DOM ozetini metin olarak dondurur. "
        "Parametreler: 'url' (hedef adres)."
    )

    @staticmethod
    def _launch_kwargs() -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"headless": True}
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            kwargs["args"] = ["--no-sandbox", "--disable-setuid-sandbox"]
        return kwargs

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        url = params.get("url")

        if not url:
            return ToolResult(tool_name=self.name, success=False, error="'url' eksik")

        if not url.startswith("http") and not url.startswith("file://"):
            url = f"http://{url}"

        try:
            logger.info("[BrowserVision] Sayfaya gidiliyor: %s", url)

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(**self._launch_kwargs())
                page = await browser.new_page(
                    viewport={"width": 1280, "height": 1024},
                    device_scale_factor=1,
                    ignore_https_errors=True,
                )

                if hasattr(page, "set_default_timeout"):
                    page.set_default_timeout(10000)

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                except PlaywrightTimeoutError:
                    logger.warning("[BrowserVision] Sayfa yuklemesi timeout oldu (10s), devam ediliyor.")

                html_snippet = await page.evaluate(
                    """() => {
                        const cleanHtml = document.body ? document.body.innerText.substring(0, 3000) : '';
                        let interactives = [];
                        document.querySelectorAll('a, button, input, textarea, select').forEach(el => {
                            let text = el.innerText || el.placeholder || el.name || el.value || '';
                            text = text.trim();
                            if (text && text.length < 50) {
                                interactives.push(`${el.tagName.toLowerCase()} -> ${text}`);
                            }
                        });
                        return {
                            textSnippet: cleanHtml,
                            interactives: interactives.slice(0, 50)
                        };
                    }"""
                )

                screenshot_bytes = await page.screenshot(
                    full_page=True,
                    type="jpeg",
                    quality=60,
                    timeout=10000,
                )
                encoded_image = base64.b64encode(screenshot_bytes).decode("utf-8")
                await browser.close()

            output_text = (
                f"URL: {url}\n"
                f"Page Text Snippet:\n{html_snippet['textSnippet']}\n\n"
                f"Interactive Elements:\n" + "\n".join(html_snippet["interactives"])
            )

            return ToolResult(
                tool_name=self.name,
                success=True,
                stdout=output_text,
                command=f"browser_vision go {url}",
                parsed_data={"url": url, "image_base64": encoded_image},
            )

        except Exception as exc:
            error_text = str(exc)
            if "sandbox" in error_text.lower():
                error_text += " | Root altinda Playwright icin --no-sandbox gerekli olabilir."
            logger.error("[BrowserVision] Hata: %s", error_text)
            return ToolResult(tool_name=self.name, success=False, error=error_text)

    def parse_output(self, raw: str) -> Dict[str, Any]:
        return {}
