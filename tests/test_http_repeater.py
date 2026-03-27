"""AgentPent â€” HTTP Repeater Tool Tests."""

import io
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from tools.http_repeater_tool import HttpRepeaterTool


def _response_context(status: int, body: str, headers=None):
    response = MagicMock()
    response.status = status
    response.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
    response.read.return_value = body.encode("utf-8")

    context = MagicMock()
    context.__enter__.return_value = response
    context.__exit__.return_value = False
    return context


@pytest.mark.asyncio
async def test_http_repeater_get():
    tool = HttpRepeaterTool()

    with patch(
        "tools.http_repeater_tool.urllib.request.urlopen",
        return_value=_response_context(200, "Example Domain"),
    ):
        result = await tool._run({"url": "http://example.com/", "method": "GET"})

    assert result.success is True
    assert "HTTP/1.1 200" in result.stdout
    assert "Example Domain" in result.stdout
    assert result.parsed_data["status"] == 200
    assert result.parsed_data["body_length"] > 0


@pytest.mark.asyncio
async def test_http_repeater_post():
    tool = HttpRepeaterTool()

    error = urllib.error.HTTPError(
        url="http://example.com/notfound",
        code=405,
        msg="Method Not Allowed",
        hdrs={"Allow": "GET"},
        fp=io.BytesIO(b"Method Not Allowed"),
    )

    with patch(
        "tools.http_repeater_tool.urllib.request.urlopen",
        side_effect=error,
    ):
        result = await tool._run({
            "url": "http://example.com/notfound",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "data": '{"test": "data"}',
        })

    assert result.success is True
    assert "HTTP/1.1 405" in result.stdout
    assert result.parsed_data["status"] == 405
