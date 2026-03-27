"""AgentPent — Reverse Shell / C2 Server Tests."""

import asyncio
import pytest
from core.c2_server import c2_manager

@pytest.mark.asyncio
async def test_c2_listener_and_interaction():
    # 1. Listener başlat
    port = 4445  # Test portu
    success = await c2_manager.start_listener(port)
    assert success is True

    # 2. Sahte bir client ile bağlan (Reverse Shell simülasyonu)
    reader, writer = await asyncio.open_connection('127.0.0.1', port)
    
    # 3. Bağlantının C2 manager tarafında kaydedilmesini bekle
    await asyncio.sleep(0.5)
    
    sessions = c2_manager.list_sessions()
    assert len(sessions) == 1
    session_id = sessions[0]["session_id"]
    
    # 4. Komut gönder (c2_manager üzerinden)
    session = c2_manager.get_session(session_id)
    assert session is not None
    
    # Arka planda okuma işlemi yapıp cevap döndüren bir mock client
    async def mock_client_response():
        data = await reader.read(100)
        command = data.decode("utf-8").strip()
        if command == "whoami":
            writer.write(b"root\n")
            await writer.drain()

    # 5. execute ile komutu gönder ve cevabı bekle
    # Client'ı arka planda çalıştır ki cevap versin
    client_task = asyncio.create_task(mock_client_response())
    
    # session.execute() bir timeout ile yolladığı komutu okur
    output = await session.execute("whoami", timeout=2.0)
    
    await client_task
    
    # Check if "root" is in output
    assert "root" in output

    # 6. Temizlik
    writer.close()
    await writer.wait_closed()
    c2_manager.stop_listener(port)
    c2_manager.remove_session(session_id)
    
    assert len(c2_manager.list_sessions()) == 0
