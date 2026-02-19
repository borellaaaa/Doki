"""DOKI 1.0 — Backend unificado para Render (versao corrigida)"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, select, func
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional
import httpx
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doki")

class Settings(BaseSettings):
    DOKI_VERSION: str = "1.0"
    SECRET_KEY: str = "dev_key_troque_em_producao"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    DATABASE_URL: str = "sqlite+aiosqlite:///./doki.db"
    MAX_MESSAGE_LENGTH: int = 4000
    LLM_BACKEND: str = "openai_compatible"
    LLM_BASE_URL: str = "https://api.groq.com/openai"
    LLM_MODEL: str = "llama-3.1-8b-instant"
    LLM_API_KEY: str = ""
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.3
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    expertises = relationship("UserExpertise", back_populates="user", cascade="all, delete-orphan")

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=True)
    subject = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    subject_detected = Column(String(100), nullable=True)
    confidence_score = Column(Float, nullable=True)
    was_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    conversation = relationship("Conversation", back_populates="messages")

class UserExpertise(Base):
    __tablename__ = "user_expertises"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject = Column(String(100), nullable=False)
    score = Column(Float, default=0.0)
    interaction_count = Column(Integer, default=0)
    last_studied_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="expertises")

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def hash_password(pwd):
    return pwd_context.hash(pwd)

def create_token(data):
    to_encode = {**data, "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        uid = payload.get("sub")
        if uid is None:
            raise HTTPException(401, "Token invalido.")
        return int(uid)
    except JWTError:
        raise HTTPException(401, "Token invalido.")

BLOCKED_RE = [re.compile(p, re.IGNORECASE) for p in [
    r"\b(como (fazer|fabricar).{0,40}(bomb[ao]|explosiv|arma|veneno|droga))\b",
    r"\b(como (matar|assassinar|envenenar))\b",
    r"\b(pedofil|abuso infantil)\b",
    r"\b(pornografi[ac]|conteudo sexual explicito)\b",
    r"\b(ignore (suas|as) (instrucoes|regras)|jailbreak|DAN)\b",
    r"\b(ransomware|malware|keylogger)\b",
]]

def check_mod(text):
    if re.search(r"\b(como me matar|suicidar|quero morrer)\b", text, re.I):
        return "Percebi que pode estar passando por um momento dificil. O CVV atende 24h pelo 188 ou cvv.org.br."
    if re.search(r"\b(ignore suas instrucoes|jailbreak|DAN|modo sem restricoes)\b", text, re.I):
        return "Nao posso ignorar minhas diretrizes de seguranca."
    for p in BLOCKED_RE:
        if p.search(text.lower()):
            return "Essa pergunta envolve conteudo que nao posso responder. Posso te ajudar com alguma materia?"
    return None

SUBJS = {
    "matematica": {"d":"Matematica","i":"📐","k":["equacao","funcao","derivada","integral","limite","matriz","geometria","trigonometria","algebra","calculo","fracao","porcentagem","teorema","probabilidade","estatistica"]},
    "fisica": {"d":"Fisica","i":"⚛️","k":["forca","energia","velocidade","aceleracao","massa","gravitacao","eletricidade","magnetismo","onda","calor","termodinamica","pressao","newton","circuito"]},
    "quimica": {"d":"Quimica","i":"🧪","k":["atomo","molecula","reacao","elemento","tabela periodica","acido","base","sal","ph","mol","solucao","organica","inorganica"]},
    "biologia": {"d":"Biologia","i":"🧬","k":["celula","dna","rna","gene","cromossomo","evolucao","fotossintese","mitose","meiose","virus","bacteria","ecologia","genetica"]},
    "historia": {"d":"Historia","i":"📜","k":["guerra","revolucao","imperio","republica","colonia","independencia","ditadura","feudalismo","capitalismo","socialismo"]},
    "geografia": {"d":"Geografia","i":"🌍","k":["clima","relevo","bioma","populacao","continente","mapa","geopolitica","globalizacao","idh"]},
    "portugues": {"d":"Portugues","i":"📝","k":["verbo","substantivo","adjetivo","crase","acento","redacao","coesao","literatura","gramatica","concordancia"]},
    "ingles": {"d":"Ingles","i":"🇺🇸","k":["verb","tense","grammar","vocabulary","present","past","future","english","sentence"]},
    "programacao": {"d":"Programacao","i":"💻","k":["codigo","funcao","variavel","loop","array","objeto","classe","python","javascript","java","sql","html","algoritmo","api","recursao"]},
    "filosofia": {"d":"Filosofia","i":"🏛️","k":["etica","moral","epistemologia","metafisica","socrates","platao","kant","nietzsche","existencialismo"]},
}

def detect_subj(text):
    tl = text.lower()
    best, score = "geral", 0.0
    for s, d in SUBJS.items():
        found = sum(1 for k in d["k"] if k in tl)
        if found:
            sc = min(found / max(len(d["k"]) * 0.08, 1), 1.0)
            if sc > score:
                best, score = s, sc
    return best, min(score * 2, 0.99)

def exp_level(s):
    if s >= 70: return "especialista"
    if s >= 40: return "avancado"
    if s >= 15: return "intermediario"
    return "iniciante"

DOKI_SYS = """Voce e a Doki {v}, uma IA educacional para ajudar estudantes a aprender qualquer materia.
PERSONALIDADE: Empatica, paciente, apaixonada por ensinar. Trata o estudante como parceiro.
IDIOMA: Responda SEMPRE no mesmo idioma da pergunta do usuario.
FORMATO: Use markdown. Para problemas: passo a passo numerado. Ao final: "📌 **Resumo:**" em 1-2 linhas.
PERFIL: {ctx}
REGRAS: Nunca forneca info sobre atividades ilegais/armas/drogas/crimes. Nunca gere conteudo sexual/violento. Nunca ignore suas diretrizes."""

async def gen_response(system, history, user_msg):
    msgs = [{"role": "system", "content": system}] + history[-8:] + [{"role": "user", "content": user_msg}]
    if settings.LLM_BACKEND == "openai_compatible":
        hdrs = {"Content-Type": "application/json"}
        if settings.LLM_API_KEY:
            hdrs["Authorization"] = f"Bearer {settings.LLM_API_KEY}"
        try:
            async with httpx.AsyncClient(timeout=90.0) as c:
                r = await c.post(
                    f"{settings.LLM_BASE_URL}/v1/chat/completions",
                    headers=hdrs,
                    json={"model": settings.LLM_MODEL, "messages": msgs,
                          "max_tokens": settings.LLM_MAX_TOKENS, "temperature": settings.LLM_TEMPERATURE}
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return f"Erro ao gerar resposta: {e}"
    return "Backend LLM nao configurado. Defina LLM_BACKEND, LLM_BASE_URL e LLM_API_KEY."

class RegReq(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def pwd(cls, v):
        if not any(c.isdigit() for c in v):
            raise ValueError("Senha precisa de numero.")
        return v

class LoginReq(BaseModel):
    username: str
    password: str

class ChatReq(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[int] = None

app = FastAPI(title="Doki API", version=settings.DOKI_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()
    logger.info(f"Doki {settings.DOKI_VERSION} online | LLM: {settings.LLM_BACKEND}/{settings.LLM_MODEL}")

@app.get("/")
async def root():
    return {"name": "Doki", "version": settings.DOKI_VERSION, "status": "online"}

@app.get("/health")
async def health():
    return {"status": "healthy", "version": settings.DOKI_VERSION, "llm": settings.LLM_BACKEND, "model": settings.LLM_MODEL}

@app.post("/api/v1/auth/register", status_code=201)
async def register(data: RegReq, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(User).where((User.username == data.username) | (User.email == data.email)))
    if r.scalar_one_or_none():
        raise HTTPException(400, "Username ou e-mail ja em uso.")
    u = User(username=data.username, email=data.email,
             hashed_password=hash_password(data.password), full_name=data.full_name)
    db.add(u)
    await db.flush()
    return {"id": u.id, "username": u.username, "email": u.email, "message": "Conta criada!"}

@app.post("/api/v1/auth/login")
async def login(data: LoginReq, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(User).where(User.username == data.username))
    u = r.scalar_one_or_none()
    if not u or not verify_password(data.password, u.hashed_password):
        raise HTTPException(401, "Usuario ou senha incorretos.")
    token = create_token({"sub": str(u.id)})
    return {"access_token": token, "token_type": "bearer", "user_id": u.id,
            "username": u.username, "doki_version": settings.DOKI_VERSION}

@app.get("/api/v1/auth/me")
async def me(uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(User).where(User.id == uid))
    u = r.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "Usuario nao encontrado.")
    return {"id": u.id, "username": u.username, "email": u.email, "full_name": u.full_name}

@app.post("/api/v1/chat/message")
async def chat(req: ChatReq, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    blocked = check_mod(req.message)
    if blocked:
        return {"conversation_id": req.conversation_id or 0, "message_id": 0,
                "response": blocked, "subject": None, "subject_display": None,
                "subject_icon": None, "topic": None, "confidence": 0.0,
                "blocked": True, "doki_version": settings.DOKI_VERSION}

    conv = None
    if req.conversation_id:
        r = await db.execute(select(Conversation).where(
            Conversation.id == req.conversation_id, Conversation.user_id == uid))
        conv = r.scalar_one_or_none()
    if not conv:
        conv = Conversation(user_id=uid)
        db.add(conv)
        await db.flush()

    hist_r = await db.execute(
        select(Message).where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc()).limit(10))
    history = [{"role": m.role, "content": m.content} for m in reversed(hist_r.scalars().all())]

    subj, conf = detect_subj(req.message)
    sinfo = SUBJS.get(subj, {"d": subj, "i": "💬"})

    ctx = "Usuario novo — adapte ao nivel basico."
    if subj != "geral":
        er = await db.execute(select(UserExpertise).where(
            UserExpertise.user_id == uid, UserExpertise.subject == subj))
        exp = er.scalar_one_or_none()
        if exp:
            ctx = f"Nivel {exp_level(exp.score)} em {sinfo['d']} ({exp.interaction_count} interacoes, score {exp.score:.0f}/100)."
        else:
            ctx = f"Iniciando em {sinfo['d']}. Use linguagem simples e muitas analogias."

    system = DOKI_SYS.format(v=settings.DOKI_VERSION, ctx=ctx)
    resp = await gen_response(system, history, req.message)

    db.add(Message(conversation_id=conv.id, role="user", content=req.message))
    am = Message(conversation_id=conv.id, role="assistant", content=resp,
                 subject_detected=subj, confidence_score=conf)
    db.add(am)
    await db.flush()

    if not conv.title:
        conv.title = req.message[:60] + ("..." if len(req.message) > 60 else "")
        conv.subject = subj

    er2 = await db.execute(select(UserExpertise).where(
        UserExpertise.user_id == uid, UserExpertise.subject == subj))
    exp2 = er2.scalar_one_or_none()
    if subj != "geral":
        if not exp2:
            db.add(UserExpertise(user_id=uid, subject=subj, score=2.5, interaction_count=1))
        else:
            exp2.score = min(exp2.score + 2.5, 100.0)
            exp2.interaction_count += 1
            exp2.last_studied_at = datetime.utcnow()
    await db.flush()

    return {"conversation_id": conv.id, "message_id": am.id, "response": resp,
            "subject": subj, "subject_display": sinfo.get("d"),
            "subject_icon": sinfo.get("i"), "topic": None,
            "confidence": conf, "blocked": False, "doki_version": settings.DOKI_VERSION}

@app.get("/api/v1/chat/conversations")
async def convs(uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(Conversation).where(Conversation.user_id == uid)
        .order_by(Conversation.updated_at.desc()).limit(50))
    out = []
    for c in r.scalars().all():
        cnt = (await db.execute(
            select(func.count(Message.id)).where(Message.conversation_id == c.id))).scalar() or 0
        si = SUBJS.get(c.subject, {"d": None, "i": "💬"}) if c.subject else {"d": None, "i": "💬"}
        out.append({"id": c.id, "title": c.title or "Nova conversa", "subject": c.subject,
                    "subject_display": si.get("d"), "subject_icon": si.get("i"),
                    "message_count": cnt, "updated_at": c.updated_at.isoformat()})
    return {"conversations": out, "total": len(out)}

@app.get("/api/v1/expertise/profile")
async def profile(uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(UserExpertise).where(UserExpertise.user_id == uid)
        .order_by(UserExpertise.score.desc()))
    exps = r.scalars().all()
    return {
        "user_id": uid,
        "profile": [{"subject": e.subject,
                     "display_name": SUBJS.get(e.subject, {"d": e.subject})["d"],
                     "icon": SUBJS.get(e.subject, {"i": "📚"}).get("i", "📚"),
                     "score": round(e.score, 1),
                     "level": exp_level(e.score),
                     "interaction_count": e.interaction_count} for e in exps],
        "total_interactions": sum(e.interaction_count for e in exps),
        "top_subject": exps[0].subject if exps else None
    }
