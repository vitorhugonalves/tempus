import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, competitions, judges, reports, timers, users
from app.core.config import settings
from app.core.logging_config import setup_logging

setup_logging(settings.APP_ENV)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tempus API",
    description="API para gerenciamento de timers em competições esportivas",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

_cors_origins = (
    ["http://localhost:5173", "http://localhost:3000"]
    if settings.APP_ENV == "development"
    else []
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(users.router, prefix="/api/v1", tags=["users"])
app.include_router(competitions.router, prefix="/api/v1", tags=["competitions"])
app.include_router(timers.router, prefix="/api/v1", tags=["timers"])
app.include_router(judges.router, prefix="/api/v1", tags=["judges"])
app.include_router(reports.router, prefix="/api/v1", tags=["reports"])


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Verifica o status da aplicação."""
    return {"status": "ok", "env": settings.APP_ENV}
