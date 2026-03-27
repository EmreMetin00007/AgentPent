import os
import tempfile
import pytest
from tools.browser_tool import BrowserVisionTool

@pytest.mark.asyncio
async def test_browser_vision_local_file():
    # Geçici bir HTML dosyası oluştur
    fd, path = tempfile.mkstemp(suffix=".html")
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write('''
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Hello Vision</h1>
                <button id="login-btn">Secure Login</button>
            </body>
        </html>
        ''')
    
    url = f"file:///{path.replace(chr(92), '/')}"
    
    tool = BrowserVisionTool()
    tool.validate_scope = lambda x, y: True  # Bypass ScopeGuard
    
    result = await tool.execute({"url": url})
    
    # Temizlik
    os.remove(path)
    
    assert result.success is True
    assert "Secure Login" in result.stdout
    assert "image_base64" in result.parsed_data
    assert len(result.parsed_data["image_base64"]) > 100
