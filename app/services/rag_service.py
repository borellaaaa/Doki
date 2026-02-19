"""
DOKI RAG SERVICE — Retrieval-Augmented Generation com ChromaDB v1.0
Armazena e recupera conhecimento personalizado por usuário.
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from typing import Optional
import logging
import os

from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGService:
    """
    Gerencia o banco vetorial de conhecimento da Doki.
    Cada usuário tem sua própria coleção de documentos/contextos estudados.
    """

    def __init__(self):
        self._client: Optional[chromadb.PersistentClient] = None
        self._embedder: Optional[SentenceTransformer] = None
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized:
            return

        os.makedirs(settings.CHROMA_PATH, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=settings.CHROMA_PATH,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info(f"ChromaDB inicializado em: {settings.CHROMA_PATH}")

        logger.info(f"Carregando modelo de embeddings: {settings.EMBEDDING_MODEL}")
        self._embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Modelo de embeddings carregado.")

        self._initialized = True

    def _get_collection(self, user_id: int):
        """Retorna (ou cria) a coleção do usuário."""
        self._ensure_initialized()
        collection_name = f"user_{user_id}_knowledge"
        return self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_interaction(
        self,
        user_id: int,
        question: str,
        answer: str,
        subject: str,
        topic: Optional[str] = None,
        message_id: Optional[int] = None,
    ):
        """
        Armazena uma interação do usuário no banco vetorial.
        Usada para especializar a Doki conforme o usuário estuda.
        """
        self._ensure_initialized()
        collection = self._get_collection(user_id)

        # Cria um documento combinando pergunta + resposta para embedding rico
        document = f"[{subject.upper()}] Pergunta: {question}\nResposta: {answer[:500]}"
        embedding = self._embedder.encode(document).tolist()

        doc_id = f"msg_{message_id}" if message_id else f"msg_{hash(question)}"

        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[document],
            metadatas=[{
                "subject": subject,
                "topic": topic or "",
                "question": question[:200],
                "user_id": str(user_id),
            }],
        )

    def get_relevant_context(
        self,
        user_id: int,
        query: str,
        subject: Optional[str] = None,
        n_results: int = 5,
    ) -> list[dict]:
        """
        Recupera contextos relevantes do histórico do usuário para a query atual.
        Quanto mais o usuário estudou um tema, mais contexto relevante é encontrado.
        """
        self._ensure_initialized()

        try:
            collection = self._get_collection(user_id)
            count = collection.count()
            if count == 0:
                return []

            query_embedding = self._embedder.encode(query).tolist()
            n_results = min(n_results, count)

            where_filter = {"subject": subject} if subject else None

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            contexts = []
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i]
                similarity = 1 - distance  # cosine: 1 = idêntico, 0 = diferente

                if similarity > 0.3:  # threshold mínimo de relevância
                    contexts.append({
                        "document": doc,
                        "metadata": results["metadatas"][0][i],
                        "similarity": round(similarity, 3),
                    })

            return sorted(contexts, key=lambda x: x["similarity"], reverse=True)

        except Exception as e:
            logger.error(f"Erro ao buscar contexto RAG: {e}")
            return []

    def get_user_knowledge_summary(self, user_id: int) -> dict:
        """Retorna um resumo do conhecimento acumulado do usuário no banco vetorial."""
        self._ensure_initialized()

        try:
            collection = self._get_collection(user_id)
            total = collection.count()

            if total == 0:
                return {"total_documents": 0, "subjects": {}}

            # Busca todos os metadados para contar por matéria
            all_items = collection.get(include=["metadatas"])
            subject_counts: dict[str, int] = {}

            for meta in all_items["metadatas"]:
                subject = meta.get("subject", "geral")
                subject_counts[subject] = subject_counts.get(subject, 0) + 1

            return {
                "total_documents": total,
                "subjects": subject_counts,
            }

        except Exception as e:
            logger.error(f"Erro ao sumarizar conhecimento: {e}")
            return {"total_documents": 0, "subjects": {}}


rag_service = RAGService()
