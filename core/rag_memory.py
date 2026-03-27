"""AgentPent — RAG (Long-Term) Vector Memory.

Bu modül, ajanların bulduğu payload'ları ve taktikleri
görevler arası geçişte hatırlaması için basit bir RAG altyapısı sunar.
Dış ML kütüphanesi (FAISS/Chroma) gerektirmeden, SQLite + OpenAI Embedding kullanır.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from typing import Any, Dict, List, Optional
from pathlib import Path

from config.settings import settings

logger = logging.getLogger("agentpent.rag_memory")


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """İki vektör arası Kosinüs Benzerliği (Cosine Similarity) hesaplar."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude_v1 = math.sqrt(sum(a * a for a in v1))
    magnitude_v2 = math.sqrt(sum(b * b for b in v2))
    if magnitude_v1 == 0 or magnitude_v2 == 0:
        return 0.0
    return dot_product / (magnitude_v1 * magnitude_v2)


class RAGMemory:
    """AgentPent Otonom RAG Belleği."""

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            db_dir = Path(settings.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(db_dir / "rag_memory.db")
        else:
            self.db_path = db_path

        self._init_db()
        self._openai_client = None
        self._init_openai()

    def _init_openai(self) -> None:
        """OpenAI client'ını başlat (sadece embedding için)."""
        if not settings.openai_api_key:
            logger.warning("[RAG] OpenAI API Key eksik. Embedding API kullanılamayacak.")
            return
            
        try:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )
            logger.debug("[RAG] OpenAI Client başarıyla yüklendi.")
        except ImportError:
            logger.warning("[RAG] `openai` paketi kurulu değil. Pip install openai yapın.")

    def _init_db(self) -> None:
        """SQLite yapısını oluştur."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS experiences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    context TEXT,
                    embedding TEXT NOT NULL
                )
            ''')
            conn.commit()

    async def _get_embedding(self, text: str) -> List[float]:
        """Verilen metnin Embedding vektörünü al (text-embedding-3-small)."""
        if not self._openai_client:
            return []
        try:
            # 1536 veya 512 boyutlu
            response = await self._openai_client.embeddings.create(
                input=[text],
                model="text-embedding-ada-002"
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.error("[RAG] Embedding alınırken hata: %s", exc)
            return []

    async def add_experience(self, topic: str, payload: str, context: str = "") -> bool:
        """Yeni bir pentest tecrübesini DB'ye vektörüyle kaydet."""
        if not self._openai_client:
            logger.warning("[RAG] İstemci bağlantısı yok, tecrübe eklenemedi: %s", topic)
            return False
            
        text_to_embed = f"Topic: {topic}. Context: {context}. Payload: {payload}"
        embedding = await self._get_embedding(text_to_embed)
        
        if not embedding:
            return False

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO experiences (topic, payload, context, embedding) VALUES (?, ?, ?, ?)",
                    (topic, payload, context, json.dumps(embedding))
                )
                conn.commit()
            logger.info("[RAG] Yeni tecrübe eklendi: %s", topic)
            return True
        except Exception as exc:
            logger.error("[RAG] DB kayıt hatası: %s", exc)
            return False

    async def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Benzer geçmiş tecrübeleri (vektörel aramayla) getir."""
        if not self._openai_client:
            return []
            
        query_embedding = await self._get_embedding(query)
        if not query_embedding:
            return []

        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, topic, payload, context, embedding FROM experiences")
                rows = cursor.fetchall()

            for row in rows:
                exp_id, topic, payload, context, emb_str = row
                try:
                    exp_embedding = json.loads(emb_str)
                    sim = cosine_similarity(query_embedding, exp_embedding)
                    results.append({
                        "id": exp_id,
                        "topic": topic,
                        "payload": payload,
                        "context": context,
                        "score": sim
                    })
                except json.JSONDecodeError:
                    continue
                    
            # Skora göre büyükten küçüğe sırala ve top_k dön
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]
            
        except Exception as exc:
            logger.error("[RAG] Arama hatası: %s", exc)
            return []
