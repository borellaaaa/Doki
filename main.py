"""
╔══════════════════════════════════════════════╗
║          DOKI 1.0 — IA de Estudos            ║
║     Backend API — FastAPI + RAG + Expertise  ║
╚══════════════════════════════════════════════╝
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import time

from app.core.config import settings
from app.db.database import init_db
from app.routers import auth, chat, expertise
from app.services.doki_generator import doki_generator

# ─── Logging ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("doki")

# ─── Rate Limiter ────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ─── App ─────────────────────────────────────────────────────
app = FastAPI(
    title="Doki API",
    description=(
        "🎓 **Doki** — Sua IA de Estudos Adaptativa\n\n"
        "A Doki aprende junto com você. Quanto mais você estuda um tema, "
        "mais ela se especializa nas suas necessidades.\n\n"
        f"**Versão:** {settings.DOKI_VERSION}  |  **Ambiente:** {settings.ENVIRONMENT}"
    ),
    version=settings.DOKI_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Rate limiting ────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else ["https://seu-frontend.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Request timing middleware ────────────────────────────────
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(process_time)
    response.headers["X-Doki-Version"] = settings.DOKI_VERSION
    return response


# ─── Startup ─────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    logger.info(f"🎓 Doki {settings.DOKI_VERSION} iniciando...")
    await init_db()
    logger.info("✅ Banco de dados inicializado.")
    logger.info(f"🤖 Backend LLM: {settings.LLM_BACKEND} ({settings.LLM_MODEL})")
    logger.info(f"🧠 Banco vetorial: ChromaDB em {settings.CHROMA_PATH}")
    logger.info("🚀 Doki pronta para receber conexões!")


# ─── Routers ─────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(expertise.router, prefix="/api/v1")


# ─── Health Check ────────────────────────────────────────────
@app.get("/", tags=["Status"])
async def root():
    return {
        "name": "Doki API",
        "version": settings.DOKI_VERSION,
        "status": "online",
        "message": "🎓 A Doki está pronta para te ajudar a estudar!",
    }


@app.get("/health", tags=["Status"])
async def health_check():
    llm_health = await doki_generator.health_check()

    return {
        "status": "healthy",
        "doki_version": settings.DOKI_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "ok",
        "vector_store": "chromadb",
        "llm": llm_health,
    }


# ─── Global error handler ─────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Erro não tratado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor. Por favor, tente novamente."},
    )
