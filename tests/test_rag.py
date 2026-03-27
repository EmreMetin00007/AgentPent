"""AgentPent — RAG Memory Unit Tests."""

import json
import sqlite3
import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path

from core.rag_memory import RAGMemory, cosine_similarity

@pytest.fixture
def rag_db(tmp_path):
    db_file = tmp_path / "test_rag.db"
    rag = RAGMemory(db_path=str(db_file))
    return rag

def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert cosine_similarity(v1, v2) == 1.0
    
    v3 = [0.0, 1.0, 0.0]
    assert cosine_similarity(v1, v3) == 0.0

@pytest.mark.asyncio
async def test_init_db(rag_db):
    assert Path(rag_db.db_path).exists()
    with sqlite3.connect(rag_db.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='experiences'")
        assert cursor.fetchone() is not None

@pytest.mark.asyncio
@patch("core.rag_memory.RAGMemory._get_embedding")
async def test_add_experience(mock_get_emb, rag_db):
    rag_db._openai_client = True # Bypass eksik API key kontrolünü
    mock_get_emb.return_value = [0.1, 0.2, 0.3]
    
    success = await rag_db.add_experience("SQLi Bypass", "' OR 1=1 --", "Login page")
    assert success is True
    
    with sqlite3.connect(rag_db.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT topic, payload FROM experiences")
        row = cursor.fetchone()
        assert row[0] == "SQLi Bypass"
        assert row[1] == "' OR 1=1 --"

@pytest.mark.asyncio
@patch("core.rag_memory.RAGMemory._get_embedding")
async def test_search_experience(mock_get_emb, rag_db):
    rag_db._openai_client = True
    
    # Pre-populate DB
    mock_get_emb.return_value = [0.9, 0.1, 0.0]
    await rag_db.add_experience("Test Topic", "Test Payload", "Test Context")
    
    mock_get_emb.return_value = [0.9, 0.1, 0.0] # Same embedding for search
    results = await rag_db.search("Test Query", top_k=2)
    
    assert len(results) == 1
    assert results[0]["topic"] == "Test Topic"
    assert results[0]["payload"] == "Test Payload"
    assert results[0]["score"] > 0.99 # almost 1.0 (cosine similarity of same vector)
