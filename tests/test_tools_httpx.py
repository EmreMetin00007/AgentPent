"""Httpx tool regression tests."""

import io
import urllib.error
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.base_tool import ToolResult
from tools.httpx_tool import HttpxTool


def _response_context(status: int, body: str, headers=None):
    response = MagicMock()
    response.status = status
    response.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
    response.read.return_value = body.encode("utf-8")

    context = MagicMock()
    context.__enter__.return_value = response
    context.__exit__.return_value = False
    return context


def test_build_probe_targets_for_bare_host_includes_common_web_and_proxy_ports():
    targets = HttpxTool._build_probe_targets("10.10.10.5")

    assert "http://10.10.10.5" in targets
    assert "https://10.10.10.5" in targets
    assert "http://10.10.10.5:8080" in targets
    assert "https://10.10.10.5:8443" in targets
    assert "http://10.10.10.5:3128" in targets


@pytest.mark.asyncio
async def test_httpx_falls_back_to_urllib_when_cli_flags_fail():
    tool = HttpxTool()
    tool.run_command = AsyncMock(return_value=ToolResult(
        tool_name="httpx",
        success=False,
        stderr="unknown arguments: -json -silent",
    ))

    def _fake_urlopen(request, timeout=0, context=None):
        if request.full_url == "http://10.10.10.5:8080":
            return _response_context(
                200,
                "<html><title>Proxy UI</title><body>ok</body></html>",
                {"Content-Type": "text/html", "Server": "nginx"},
            )
        raise urllib.error.URLError("connection refused")

    with patch("tools.httpx_tool.urllib.request.urlopen", side_effect=_fake_urlopen):
        result = await tool._run({"target": "10.10.10.5", "timeout": 1})

    assert result.success is True
    assert "http://10.10.10.5:8080" in result.parsed_data["attempted_targets"]
    assert result.parsed_data["total"] == 1
    assert result.parsed_data["results"][0]["title"] == "Proxy UI"
    assert result.parsed_data["results"][0]["looks_like_proxy"] is False


@pytest.mark.asyncio
async def test_httpx_fallback_marks_proxy_like_responses():
    tool = HttpxTool()
    tool.run_command = AsyncMock(return_value=ToolResult(
        tool_name="httpx",
        success=False,
        stderr="wrong httpx cli detected",
    ))

    proxy_error = urllib.error.HTTPError(
        url="http://10.10.10.5:3128",
        code=407,
        msg="Proxy Authentication Required",
        hdrs={"Proxy-Agent": "Squid", "Content-Type": "text/html"},
        fp=io.BytesIO(b"Proxy Authentication Required"),
    )

    def _fake_urlopen(request, timeout=0, context=None):
        if request.full_url == "http://10.10.10.5:3128":
            raise proxy_error
        raise urllib.error.URLError("connection refused")

    with patch("tools.httpx_tool.urllib.request.urlopen", side_effect=_fake_urlopen):
        result = await tool._run({"target": "10.10.10.5", "timeout": 1})

    assert result.success is True
    assert result.parsed_data["results"][0]["status_code"] == 407
    assert result.parsed_data["results"][0]["looks_like_proxy"] is True
