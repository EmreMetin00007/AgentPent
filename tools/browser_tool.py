"""AgentPent — Browser Vision Tool.

Playwright kullanarak hedefe gider, ekran görüntüsü alır ve DOM analizini döner.
"""

import base64
import logging
from typing import Any, Dict
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.browser")

class BrowserVisionTool(BaseTool):
    """Headless tarayıcı fonksiyonları sağlayan araç."""

    name = "browser_vision"
    description = (
        "Hedef web sayfasına headless Chromium tarayıcısı ile gider, tam ekran "
        "görüntüsü (screenshot) alır ve sayfa DOM/Özet yapısını metin olarak döner. "
        "Parametreler: 'url' (hedef adres)."
    )

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        """Kabul edilen parametreler: 'url'"""
        # Hedef kontrolünü (scope guard) BaseTool.execute yapıyor.
        url = params.get("url")

        if not url:
            return ToolResult(tool_name=self.name, success=False, error="'url' eksik")

        if not url.startswith("http") and not url.startswith("file://"):
            url = f"http://{url}"

        try:
            logger.info("[BrowserVision] Sayfaya gidiliyor: %s", url)
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(
                    viewport={"width": 1280, "height": 1024},
                    device_scale_factor=1,
                    ignore_https_errors=True
                )
                
                # Navigate and wait for network to be idle
                try:
                    await page.goto(url, wait_until="networkidle", timeout=15000)
                except PlaywrightTimeoutError:
                    logger.warning("[BrowserVision] Sayfa yüklemesi timeout oldu (15s), devam ediliyor.")
                
                # Extract clean DOM structure for LLM
                html_snippet = await page.evaluate('''() => {
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
                }''')
                
                # Capture full page screenshot
                screenshot_bytes = await page.screenshot(full_page=True, type="jpeg", quality=60)
                encoded_image = base64.b64encode(screenshot_bytes).decode("utf-8")
                
                await browser.close()

            # Output preparation
            output_text = (
                f"URL: {url}\n"
                f"Page Text Snippet:\n{html_snippet['textSnippet']}\n\n"
                f"Interactive Elements:\n" + "\n".join(html_snippet['interactives'])
            )

            return ToolResult(
                tool_name=self.name,
                success=True,
                stdout=output_text,
                command=f"browser_vision go {url}",
                parsed_data={"url": url, "image_base64": encoded_image}
            )

        except Exception as e:
            logger.error("[BrowserVision] Hata: %s", e)
            return ToolResult(tool_name=self.name, success=False, error=str(e))

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """Ham çıktıyı parse etmeye gerek yok."""
        return {}

