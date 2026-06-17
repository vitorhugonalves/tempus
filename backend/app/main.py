import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import admin, athletes, auth, bulk, cep, competitions, judges, modalities, reports, timers, users, websocket
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging_config import setup_logging
from app.core.redis import close_redis_pool, get_redis_pool

setup_logging(settings.APP_ENV)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida da aplicação — inicializa e encerra recursos."""
    # Startup
    logger.info("Inicializando conexão Redis em %s...", settings.REDIS_URL)
    await get_redis_pool()
    logger.info("Redis conectado.")
    yield
    # Shutdown
    await close_redis_pool()


app = FastAPI(
    title="Tempus API",
    description="API para gerenciamento de timers em competições esportivas",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

_cors_origins = [settings.FRONTEND_URL] if settings.APP_ENV == "development" else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
app.include_router(bulk.router, prefix="/api/v1", tags=["admin"])
app.include_router(athletes.router, prefix="/api/v1", tags=["athletes"])
app.include_router(cep.router, prefix="/api/v1", tags=["cep"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(users.router, prefix="/api/v1", tags=["users"])
app.include_router(modalities.router, prefix="/api/v1", tags=["modalities"])
app.include_router(competitions.router, prefix="/api/v1", tags=["competitions"])
app.include_router(timers.router, prefix="/api/v1", tags=["timers"])
app.include_router(judges.router, prefix="/api/v1", tags=["judges"])
app.include_router(reports.router, prefix="/api/v1", tags=["reports"])
app.include_router(websocket.router, tags=["websocket"])


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Verifica o status da aplicação."""
    return {"status": "ok", "env": settings.APP_ENV}
