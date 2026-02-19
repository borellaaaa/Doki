"""
DOKI CHAT ROUTER v1.0
Endpoint principal de conversa com a Doki.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.models.conversation import Conversation, Message
from app.models.schemas import ChatMessageRequest, ChatMessageResponse
from app.services.doki_brain import doki_brain
from app.services.subject_detector import subject_detector
from app.services.doki_generator import doki_generator
from app.core.config import settings

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Envia uma mensagem para a Doki e recebe uma resposta personalizada.
    """

    # ─── Recupera ou cria conversa ──────────────────────────
    conversation = None
    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == request.conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.")

    if not conversation:
        conversation = Conversation(user_id=user_id)
        db.add(conversation)
        await db.flush()

    # ─── Recupera histórico da conversa ────────────────────
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(10)
    )
    recent_messages = list(reversed(history_result.scalars().all()))

    conversation_history = [
        {"role": msg.role, "content": msg.content}
        for msg in recent_messages
    ]

    # ─── Salva mensagem do usuário ──────────────────────────
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.flush()

    # ─── Processa pelo DokiBrain ────────────────────────────
    brain_result = await doki_brain.process_message(
        db=db,
        user_id=user_id,
        message=request.message,
        conversation_history=conversation_history,
    )

    # ─── Se bloqueado pela moderação ───────────────────────
    if brain_result["blocked"]:
        user_message.was_blocked = True

        blocked_response = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=brain_result["response"],
            was_blocked=True,
        )
        db.add(blocked_response)
        await db.flush()

        return ChatMessageResponse(
            conversation_id=conversation.id,
            message_id=blocked_response.id,
            response=brain_result["response"],
            subject=None,
            subject_display=None,
            subject_icon=None,
            topic=None,
            confidence=0.0,
            blocked=True,
            doki_version=settings.DOKI_VERSION,
        )

    # ─── Gera resposta via motor de linguagem ───────────────
    subject = brain_result["subject"]
    response_text = await doki_generator.generate(
        system_prompt=brain_result["system_prompt"],
        conversation_history=conversation_history,
        user_message=request.message,
    )

    # ─── Salva resposta da Doki ─────────────────────────────
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        subject_detected=subject,
        confidence_score=brain_result["confidence"],
    )
    db.add(assistant_message)
    await db.flush()

    # ─── Atualiza expertise e RAG ───────────────────────────
    await doki_brain.post_response_hook(
        db=db,
        user_id=user_id,
        question=request.message,
        answer=response_text,
        subject=subject or "geral",
        topic=brain_result["topic"],
        message_id=assistant_message.id,
    )

    # ─── Atualiza título da conversa (se nova) ──────────────
    if not conversation.title:
        conversation.title = request.message[:60] + ("..." if len(request.message) > 60 else "")
        conversation.subject = subject

    subject_display = subject_detector.get_display_name(subject) if subject else None
    subject_icon = subject_detector.get_icon(subject) if subject else None

    return ChatMessageResponse(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        response=response_text,
        subject=subject,
        subject_display=subject_display,
        subject_icon=subject_icon,
        topic=brain_result["topic"],
        confidence=brain_result["confidence"],
        blocked=False,
        doki_version=settings.DOKI_VERSION,
    )


@router.get("/conversations")
async def list_conversations(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Lista todas as conversas do usuário."""

    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    conversations = result.scalars().all()

    output = []
    for conv in conversations:
        count_result = await db.execute(
            select(func.count(Message.id)).where(Message.conversation_id == conv.id)
        )
        msg_count = count_result.scalar() or 0

        output.append({
            "id": conv.id,
            "title": conv.title or "Nova conversa",
            "subject": conv.subject,
            "subject_display": subject_detector.get_display_name(conv.subject) if conv.subject else None,
            "subject_icon": subject_detector.get_icon(conv.subject) if conv.subject else "💬",
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "message_count": msg_count,
        })

    return {"conversations": output, "total": len(output)}


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna as mensagens de uma conversa."""

    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = msg_result.scalars().all()

    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "subject": m.subject_detected,
                "was_blocked": m.was_blocked,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Deleta uma conversa."""

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")

    await db.delete(conversation)
    return {"message": "Conversa deletada com sucesso."}
