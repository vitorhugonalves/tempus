"""Serviço de auto-inscrição de competidores."""

import logging
import secrets

from fastapi import HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.category import Category, CategoryType
from app.models.competition import Competition, CompetitionStatus
from app.models.competitor import CompetitorRegistration
from app.models.team import Team, TeamMember
from app.models.user import User, UserRole
from app.repositories.team import TeamRepository
from app.repositories.user import UserRepository
from app.services.email import send_registration_welcome

logger = logging.getLogger(__name__)


# ── Schemas de entrada/saída ──────────────────────────────────────────────────


class MemberInput(BaseModel):
    """Dados de um membro adicional na inscrição de equipe."""

    full_name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr


class CompetitorRegisterRequest(BaseModel):
    """Payload para auto-inscrição do competidor em uma competição ativa."""

    category_id: int
    document: str | None = Field(None, max_length=30)
    box_name: str | None = Field(None, max_length=200)
    # Campos para categoria do tipo equipe
    team_name: str | None = Field(None, min_length=1, max_length=200)
    additional_members: list[MemberInput] = []


class CompetitorRegisterResponse(BaseModel):
    """Resposta da inscrição."""

    registration_id: int
    team_id: int
    team_name: str
    accounts_created: int


# ── Service ───────────────────────────────────────────────────────────────────


class RegistrationService:
    """Regras de negócio para auto-inscrição de competidores."""

    @staticmethod
    async def register(
        db: AsyncSession,
        current_user: User,
        competition_id: int,
        data: CompetitorRegisterRequest,
        login_url: str,
    ) -> CompetitorRegisterResponse:
        """Inscreve o competidor autenticado em uma competição ativa.

        Para categorias individuais, cria uma equipe solo automaticamente.
        Para categorias de equipe, cria a equipe com os membros informados,
        gerando novas contas para membros inexistentes e enviando e-mail de boas-vindas.

        Args:
            db: Sessão assíncrona.
            current_user: Usuário autenticado que está se inscrevendo.
            competition_id: ID da competição de destino.
            data: Dados da inscrição (categoria, documento, membros).
            login_url: URL de login para incluir no e-mail de boas-vindas.

        Returns:
            CompetitorRegisterResponse com detalhes da inscrição criada.

        Raises:
            HTTPException 404: Competição ou categoria não encontrada.
            HTTPException 409: Competidor já inscrito ou equipe lotada.
            HTTPException 422: Campos obrigatórios ausentes para categoria equipe.
        """
        # 1. Verifica competição existe e está ativa
        comp_result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = comp_result.scalar_one_or_none()
        if not competition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competição não encontrada",
            )
        if competition.status != CompetitionStatus.active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Inscrições só são permitidas em competições ativas",
            )

        # 2. Verifica categoria pertence à competição e está ativa
        cat_result = await db.execute(
            select(Category).where(
                Category.id == data.category_id,
                Category.competition_id == competition_id,
                Category.is_active.is_(True),
            )
        )
        category = cat_result.scalar_one_or_none()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria não encontrada ou inativa nesta competição",
            )

        # 3. Verifica se o competidor já está inscrito nesta competição (RN-02)
        existing_reg = await db.execute(
            select(CompetitorRegistration).where(
                CompetitorRegistration.user_id == current_user.id,
                CompetitorRegistration.competition_id == competition_id,
            )
        )
        if existing_reg.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Você já está inscrito nesta competição",
            )

        # 4. Validação específica para categoria equipe
        if category.category_type == CategoryType.team:
            if not data.team_name:
                raise HTTPException(
                    status_code=422,
                    detail="Nome da equipe é obrigatório para categorias de equipe",
                )
            total_members = 1 + len(data.additional_members)
            if category.max_team_size and total_members > category.max_team_size:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"A categoria '{category.name}' permite no máximo "
                        f"{category.max_team_size} membro(s) por equipe"
                    ),
                )

        # 5. Cria inscrição do competidor principal
        registration = CompetitorRegistration(
            user_id=current_user.id,
            competition_id=competition_id,
            category_id=data.category_id,
            document=data.document,
        )
        db.add(registration)
        await db.flush()
        await db.refresh(registration)

        # 6. Cria a equipe
        if category.category_type == CategoryType.individual:
            team_name = current_user.email
        else:
            team_name = data.team_name  # type: ignore[assignment]

        team = Team(
            competition_id=competition_id,
            category_id=data.category_id,
            name=team_name,
            captain_id=current_user.id,
            box_name=data.box_name,
        )
        db.add(team)
        await db.flush()
        await db.refresh(team)

        # 7. Adiciona o competidor principal à equipe
        captain_member = TeamMember(team_id=team.id, user_id=current_user.id)
        db.add(captain_member)
        await db.flush()

        # 8. Processa membros adicionais (apenas para equipes)
        accounts_created = 0
        if category.category_type == CategoryType.team:
            for member_input in data.additional_members:
                member_user = await UserRepository.get_by_email(db, member_input.email)
                temp_password: str | None = None

                if not member_user:
                    # Cria conta automaticamente com senha temporária
                    temp_password = secrets.token_urlsafe(10)
                    member_user = User(
                        full_name=member_input.full_name,
                        email=member_input.email,
                        hashed_password=hash_password(temp_password),
                        role=UserRole.competitor,
                    )
                    db.add(member_user)
                    await db.flush()
                    await db.refresh(member_user)
                    accounts_created += 1
                    logger.info(
                        "Conta criada automaticamente para membro: email=%s por registration=%s",
                        member_input.email,
                        registration.id,
                    )

                # Verifica se já está inscrito nesta competição
                existing_member_reg = await db.execute(
                    select(CompetitorRegistration).where(
                        CompetitorRegistration.user_id == member_user.id,
                        CompetitorRegistration.competition_id == competition_id,
                    )
                )
                if not existing_member_reg.scalar_one_or_none():
                    member_reg = CompetitorRegistration(
                        user_id=member_user.id,
                        competition_id=competition_id,
                        category_id=data.category_id,
                    )
                    db.add(member_reg)
                    await db.flush()

                # Verifica RN-17: usuário não pode estar em outra equipe da mesma competição
                already_in_team = await TeamRepository.get_member_in_competition(
                    db, competition_id, member_user.id
                )
                if already_in_team:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"O usuário '{member_input.email}' já pertence a uma "
                            "equipe nesta competição"
                        ),
                    )

                team_member = TeamMember(team_id=team.id, user_id=member_user.id)
                db.add(team_member)
                await db.flush()

                # Envia e-mail apenas para contas criadas automaticamente
                if temp_password and _smtp_configured():
                    try:
                        await send_registration_welcome(
                            to_email=member_input.email,
                            full_name=member_input.full_name,
                            competition_name=competition.name,
                            temporary_password=temp_password,
                            login_url=login_url,
                        )
                    except Exception:
                        logger.warning(
                            "Falha ao enviar e-mail de boas-vindas para %s",
                            member_input.email,
                        )

        logger.info(
            "Inscrição criada: user_id=%s competition_id=%s category_id=%s team_id=%s",
            current_user.id,
            competition_id,
            data.category_id,
            team.id,
        )

        return CompetitorRegisterResponse(
            registration_id=registration.id,
            team_id=team.id,
            team_name=team_name,
            accounts_created=accounts_created,
        )


def _smtp_configured() -> bool:
    """Verifica se o SMTP está configurado para envio de e-mails."""
    from app.core.config import settings  # noqa: PLC0415 (import lazy to avoid circular)

    return bool(settings.SMTP_HOST and settings.SMTP_USER)
