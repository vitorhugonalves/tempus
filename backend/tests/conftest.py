import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Desabilita rate limiting em testes (RNF-06 é validado separadamente)
app.state.limiter.enabled = False

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """Fornece uma sessão de banco de dados em memória isolada por teste.

    Usa StaticPool para garantir que create_all e a session compartilhem
    a mesma conexão (obrigatório para SQLite :memory:).
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncClient:
    """Fornece um AsyncClient configurado com a app FastAPI e banco de testes."""

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession):
    """Cria um usuário admin para uso nos testes."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        full_name="Admin Teste",
        email="admin@example.com",
        hashed_password=hash_password("senha-admin-123"),
        role=UserRole.admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def judge_user(db: AsyncSession):
    """Cria um usuário judge para uso nos testes."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        full_name="Judge Teste",
        email="judge@example.com",
        hashed_password=hash_password("senha-judge-123"),
        role=UserRole.judge,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def competitor_user(db: AsyncSession):
    """Cria um usuário competidor para uso nos testes."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        full_name="Competidor Teste",
        email="competidor@example.com",
        hashed_password=hash_password("senha-competidor-123"),
        role=UserRole.competitor,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, admin_user) -> str:
    """Autentica o admin e retorna o token de sessão."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "senha-admin-123"},
    )
    assert response.status_code == 200
    return response.cookies["session_id"]


@pytest_asyncio.fixture
async def judge_token(client: AsyncClient, judge_user) -> str:
    """Autentica o judge e retorna o token de sessão."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "judge@example.com", "password": "senha-judge-123"},
    )
    assert response.status_code == 200
    return response.cookies["session_id"]


@pytest_asyncio.fixture
async def competitor_token(client: AsyncClient, competitor_user) -> str:
    """Autentica o competidor e retorna o token de sessão."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "competidor@example.com", "password": "senha-competidor-123"},
    )
    assert response.status_code == 200
    return response.cookies["session_id"]
