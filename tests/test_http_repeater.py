"""AgentPent — HTTP Repeater Tool Tests."""

import pytest
from tools.http_repeater_tool import HttpRepeaterTool

@pytest.mark.asyncio
async def test_http_repeater_get():
    tool = HttpRepeaterTool()
    
    # Example.com adresine istek at
    result = await tool._run({"url": "http://example.com/", "method": "GET"})
    
    assert result.success is True
    assert "HTTP/1.1 200" in result.stdout
    assert "Example Domain" in result.stdout
    assert result.parsed_data["status"] == 200
    assert result.parsed_data["body_length"] > 0

@pytest.mark.asyncio
async def test_http_repeater_post():
    tool = HttpRepeaterTool()
    
    # Geçersiz URL testi (httpbin fallback/mock olmadan)
    # Sadece bir POST isteği kurgulayalım
    headers = {"Content-Type": "application/json"}
    data = '{"test": "data"}'
    
    # HTTPError fırlatacak bir URL
    result = await tool._run({
        "url": "http://example.com/notfound",
        "method": "POST",
        "headers": headers,
        "data": data
    })
    
    # 405 dönse bile success = True dönmeli, çünkü http request başarıyla gerçekleşti!
    assert result.success is True
    assert "HTTP/1.1 405" in result.stdout
    assert result.parsed_data["status"] == 405
