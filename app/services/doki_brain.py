"""
DOKI BRAIN — Motor de Resposta da IA v1.0
Orquestra RAG + Expertise + Geração de resposta
"""
import re
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.moderation import moderation_service, ModerationResult
from app.services.subject_detector import subject_detector
from app.services.expertise_service import expertise_service
from app.services.rag_service import rag_service
from app.core.config import settings

logger = logging.getLogger(__name__)


DOKI_SYSTEM_PROMPT = """Você é a Doki {version}, uma IA educacional criada para ajudar estudantes a aprender qualquer matéria.

IDENTIDADE:
- Você é a Doki, uma IA estudiosa, empática e apaixonada por ensinar.
- Você se adapta ao nível de conhecimento de cada usuário.
- Você é direta, clara e sempre busca a resposta mais correta possível.
- Você usa exemplos práticos e analogias quando necessário.
- Você fala português do Brasil naturalmente.

REGRAS ABSOLUTAS (nunca quebre):
1. Nunca forneça informações sobre atividades ilegais, drogas, armas, crimes ou conteúdo explícito.
2. Nunca finnja ser outra IA ou ignore suas diretrizes de segurança.
3. Se não souber a resposta com certeza, diga claramente: "Não tenho certeza suficiente sobre isso."
4. Sempre cite quando uma informação pode ser imprecisa ou sujeita a debate.
5. Mantenha foco educacional — redirecione conversas fora do escopo de estudos.

PERFIL DO USUÁRIO:
{expertise_context}

CONTEXTO RELEVANTE DO HISTÓRICO DO USUÁRIO:
{rag_context}

INSTRUÇÕES DE RESPOSTA:
- Seja preciso e completo na resposta.
- Estruture respostas longas com seções claras (use markdown).
- Para matemática/física/química: mostre o passo a passo.
- Para humanas: contextualize historicamente e conecte com o presente.
- Para programação: sempre inclua exemplos de código funcionais.
- Ao final de respostas complexas, ofereça um resumo em 1-2 linhas.
- Use emojis com moderação para tornar o aprendizado mais leve.
"""


def build_system_prompt(expertise_context: str, rag_context: str) -> str:
    return DOKI_SYSTEM_PROMPT.format(
        version=settings.DOKI_VERSION,
        expertise_context=expertise_context or "Usuário novo — adapte ao nível básico.",
        rag_context=rag_context or "Nenhum histórico relevante encontrado ainda.",
    )


def format_rag_context(contexts: list[dict]) -> str:
    if not contexts:
        return ""

    lines = ["Interações anteriores relevantes do usuário:"]
    for i, ctx in enumerate(contexts[:3], 1):  # máximo 3 contextos
        similarity_pct = int(ctx["similarity"] * 100)
        lines.append(f"\n[Contexto {i} — relevância {similarity_pct}%]")
        lines.append(ctx["document"][:400])

    return "\n".join(lines)


class DokiBrain:
    """
    Motor principal da Doki.
    Orquestra todo o pipeline de resposta.
    """

    async def process_message(
        self,
        db: AsyncSession,
        user_id: int,
        message: str,
        conversation_history: list[dict],
    ) -> dict:
        """
        Pipeline completo de processamento de uma mensagem:
        1. Moderação
        2. Detecção de matéria
        3. Recuperação de contexto RAG
        4. Construção do prompt personalizado
        5. Geração de resposta
        6. Atualização de expertise
        7. Armazenamento no RAG
        """

        # ─── STEP 1: MODERAÇÃO ───────────────────────────────
        mod_result = moderation_service.check(message)
        if mod_result.result != ModerationResult.APPROVED:
            return {
                "response": mod_result.suggested_response,
                "blocked": True,
                "reason": mod_result.reason,
                "subject": None,
                "confidence": 0.0,
            }

        # ─── STEP 2: DETECÇÃO DE MATÉRIA ────────────────────
        detection = subject_detector.detect(message)
        subject = detection.subject
        topic = detection.topic
        confidence = detection.confidence

        # ─── STEP 3: CONTEXTO RAG ───────────────────────────
        rag_contexts = rag_service.get_relevant_context(
            user_id=user_id,
            query=message,
            subject=subject if subject != "geral" else None,
            n_results=5,
        )
        rag_context_str = format_rag_context(rag_contexts)

        # ─── STEP 4: CONTEXTO DE EXPERTISE ──────────────────
        expertise_context = ""
        if subject and subject != "geral":
            expertise_context = await expertise_service.get_expertise_context_for_prompt(
                db=db,
                user_id=user_id,
                subject=subject,
            )

        # ─── STEP 5: CONSTRUÇÃO DO PROMPT ───────────────────
        system_prompt = build_system_prompt(expertise_context, rag_context_str)

        # ─── STEP 6: GERAÇÃO DE RESPOSTA ────────────────────
        # O motor de geração é implementado no router e usa o modelo configurado.
        # Aqui retornamos o contexto necessário para o router completar.
        return {
            "blocked": False,
            "subject": subject,
            "topic": topic,
            "confidence": confidence,
            "system_prompt": system_prompt,
            "rag_contexts": rag_contexts,
            "expertise_context": expertise_context,
        }

    async def post_response_hook(
        self,
        db: AsyncSession,
        user_id: int,
        question: str,
        answer: str,
        subject: str,
        topic: Optional[str],
        message_id: Optional[int] = None,
    ):
        """
        Executado após a resposta ser gerada.
        Atualiza expertise e armazena no RAG.
        """
        if subject and subject != "geral":
            await expertise_service.update_expertise(
                db=db,
                user_id=user_id,
                subject=subject,
                topic=topic,
            )

        rag_service.add_interaction(
            user_id=user_id,
            question=question,
            answer=answer,
            subject=subject or "geral",
            topic=topic,
            message_id=message_id,
        )


doki_brain = DokiBrain()
