from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.services.expertise_service import expertise_service
from app.services.rag_service import rag_service
from app.models.schemas import ExpertiseProfileResponse

router = APIRouter(prefix="/expertise", tags=["Especialização"])


@router.get("/profile", response_model=ExpertiseProfileResponse)
async def get_expertise_profile(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna o perfil completo de especialização do usuário.
    Mostra em quais matérias a Doki se tornou mais especializada para ele.
    """
    profile = await expertise_service.get_user_expertise_profile(db=db, user_id=user_id)
    top_subjects = await expertise_service.get_top_subjects(db=db, user_id=user_id, limit=1)
    knowledge_summary = rag_service.get_user_knowledge_summary(user_id=user_id)

    total_interactions = sum(item["interaction_count"] for item in profile)

    return ExpertiseProfileResponse(
        user_id=user_id,
        profile=profile,
        total_interactions=total_interactions,
        top_subject=top_subjects[0] if top_subjects else None,
        knowledge_summary=knowledge_summary,
    )


@router.get("/leaderboard")
async def get_study_leaderboard(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna um ranking pessoal das matérias mais estudadas."""
    profile = await expertise_service.get_user_expertise_profile(db=db, user_id=user_id)

    ranked = sorted(profile, key=lambda x: x["score"], reverse=True)

    return {
        "user_id": user_id,
        "ranking": [
            {
                "position": i + 1,
                "subject": item["subject"],
                "display_name": item["display_name"],
                "icon": item["icon"],
                "score": item["score"],
                "level": item["level"],
                "interactions": item["interaction_count"],
            }
            for i, item in enumerate(ranked)
        ],
    }
