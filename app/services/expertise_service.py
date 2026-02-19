"""
DOKI EXPERTISE SERVICE — Sistema de Especialização Adaptativa v1.0
Gerencia o perfil de especialização do usuário por matéria.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime
from typing import Optional
import logging

from app.models.expertise import UserExpertise
from app.services.subject_detector import subject_detector

logger = logging.getLogger(__name__)

# Configurações de pontuação
SCORE_PER_INTERACTION = 2.5      # pontos por interação
SCORE_DECAY_DAYS = 30            # após X dias sem estudar, inicia decaimento
MAX_SCORE = 100.0
EXPERT_THRESHOLD = 70.0          # a partir daqui, Doki trata como "expert"
ADVANCED_THRESHOLD = 40.0


class ExpertiseLevel:
    BEGINNER = "iniciante"
    INTERMEDIATE = "intermediário"
    ADVANCED = "avançado"
    EXPERT = "especialista"

    @staticmethod
    def from_score(score: float) -> str:
        if score >= EXPERT_THRESHOLD:
            return ExpertiseLevel.EXPERT
        elif score >= ADVANCED_THRESHOLD:
            return ExpertiseLevel.ADVANCED
        elif score >= 15.0:
            return ExpertiseLevel.INTERMEDIATE
        return ExpertiseLevel.BEGINNER


class ExpertiseService:

    async def update_expertise(
        self,
        db: AsyncSession,
        user_id: int,
        subject: str,
        topic: Optional[str] = None,
    ) -> UserExpertise:
        """Atualiza a pontuação do usuário para uma matéria após uma interação."""

        result = await db.execute(
            select(UserExpertise).where(
                UserExpertise.user_id == user_id,
                UserExpertise.subject == subject,
            )
        )
        expertise = result.scalar_one_or_none()

        if expertise is None:
            expertise = UserExpertise(
                user_id=user_id,
                subject=subject,
                topic=topic,
                score=SCORE_PER_INTERACTION,
                interaction_count=1,
                last_studied_at=datetime.utcnow(),
            )
            db.add(expertise)
        else:
            new_score = min(expertise.score + SCORE_PER_INTERACTION, MAX_SCORE)
            expertise.score = new_score
            expertise.interaction_count += 1
            expertise.last_studied_at = datetime.utcnow()
            if topic:
                expertise.topic = topic

        await db.flush()
        return expertise

    async def get_user_expertise_profile(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> list[dict]:
        """Retorna o perfil completo de especialização do usuário."""

        result = await db.execute(
            select(UserExpertise)
            .where(UserExpertise.user_id == user_id)
            .order_by(UserExpertise.score.desc())
        )
        expertises = result.scalars().all()

        profile = []
        for exp in expertises:
            level = ExpertiseLevel.from_score(exp.score)
            icon = subject_detector.get_icon(exp.subject)
            display = subject_detector.get_display_name(exp.subject)

            profile.append({
                "subject": exp.subject,
                "display_name": display,
                "icon": icon,
                "score": round(exp.score, 1),
                "level": level,
                "interaction_count": exp.interaction_count,
                "last_studied_at": exp.last_studied_at.isoformat() if exp.last_studied_at else None,
            })

        return profile

    async def get_top_subjects(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int = 3,
    ) -> list[str]:
        """Retorna as matérias em que o usuário mais estudou (mais especializadas)."""

        result = await db.execute(
            select(UserExpertise.subject)
            .where(UserExpertise.user_id == user_id)
            .order_by(UserExpertise.score.desc())
            .limit(limit)
        )
        return [row[0] for row in result.all()]

    async def get_expertise_context_for_prompt(
        self,
        db: AsyncSession,
        user_id: int,
        subject: str,
    ) -> str:
        """
        Gera um bloco de contexto de especialização para incluir no prompt da Doki.
        Quanto mais o usuário sabe, mais avançada é a resposta gerada.
        """
        result = await db.execute(
            select(UserExpertise).where(
                UserExpertise.user_id == user_id,
                UserExpertise.subject == subject,
            )
        )
        expertise = result.scalar_one_or_none()

        if expertise is None:
            return f"O usuário está começando a estudar {subject}. Use linguagem introdutória, analogias simples e exemplos básicos."

        level = ExpertiseLevel.from_score(expertise.score)
        count = expertise.interaction_count
        display = subject_detector.get_display_name(subject)

        instructions = {
            ExpertiseLevel.BEGINNER: (
                f"O usuário é INICIANTE em {display} ({count} interações, score {expertise.score:.0f}/100). "
                "Use linguagem simples, muitos exemplos práticos, evite jargões técnicos sem explicação. "
                "Incentive e mostre que o conteúdo é acessível."
            ),
            ExpertiseLevel.INTERMEDIATE: (
                f"O usuário tem nível INTERMEDIÁRIO em {display} ({count} interações, score {expertise.score:.0f}/100). "
                "Pode usar terminologia técnica básica. Conecte novos conceitos com os que ele já viu antes. "
                "Inclua exemplos práticos e aplicações reais."
            ),
            ExpertiseLevel.ADVANCED: (
                f"O usuário tem nível AVANÇADO em {display} ({count} interações, score {expertise.score:.0f}/100). "
                "Use terminologia técnica sem hesitação. Aprofunde nos detalhes. "
                "Mostre nuances, exceções e casos específicos. Pode usar fórmulas e demonstrações."
            ),
            ExpertiseLevel.EXPERT: (
                f"O usuário é ESPECIALISTA em {display} ({count} interações, score {expertise.score:.0f}/100). "
                "Trate-o como um par. Explore fronteiras do conhecimento, casos extremos, "
                "conexões interdisciplinares e aspectos avançados que não estão em livros introdutórios."
            ),
        }

        return instructions.get(level, "")


expertise_service = ExpertiseService()
