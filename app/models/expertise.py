from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class UserExpertise(Base):
    """
    Rastreia o nível de especialização do usuário por matéria/tópico.
    Quanto mais o usuário estuda um tópico, maior o score — e mais a Doki
    pesa esse contexto ao responder.
    """
    __tablename__ = "user_expertises"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject = Column(String(100), nullable=False)       # ex: "matemática"
    topic = Column(String(200), nullable=True)           # ex: "cálculo diferencial"
    score = Column(Float, default=0.0)                   # 0.0 a 100.0
    interaction_count = Column(Integer, default=0)       # qtd de perguntas feitas
    total_study_minutes = Column(Integer, default=0)
    last_studied_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Metadata extra (ex: subtópicos mais visitados)
    meta = Column(JSON, default=dict)

    user = relationship("User", back_populates="expertises")

    def __repr__(self):
        return f"<UserExpertise(user_id={self.user_id}, subject='{self.subject}', score={self.score:.1f})>"


class SubjectCategory(Base):
    """Taxonomia de matérias e tópicos suportados pela Doki."""
    __tablename__ = "subject_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    icon = Column(String(10), nullable=True)
    parent_id = Column(Integer, ForeignKey("subject_categories.id"), nullable=True)
    keywords = Column(JSON, default=list)   # palavras-chave para detecção automática
