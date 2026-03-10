"""Serviço de tokens de reset de senha e convite (RF-05, RF-06, RNF-07)."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_invite_token, generate_password_reset_token, hash_password
from app.models.token import InviteToken, PasswordResetToken
from app.models.user import User, UserRole
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)

_TOKEN_TTL_HOURS = 72  # RNF-07


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PasswordResetService:
    """Recuperação de senha via token de uso único (RF-05)."""

    @staticmethod
    async def create_token(db: AsyncSession, email: str) -> PasswordResetToken | None:
        """Cria token de reset para o e-mail fornecido.

        Não lança erro se o e-mail não existir (evita enumeração de usuários).

        Args:
            db: Sessão assíncrona.
            email: E-mail do usuário.

        Returns:
            PasswordResetToken ou None se o usuário não existir.
        """
        user = await UserRepository.get_by_email(db, email)
        if not user or not user.is_active:
            return None

        # Invalida tokens anteriores pendentes
        result = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
        )
        for old in result.scalars().all():
            old.used_at = _utcnow()

        token = PasswordResetToken(
            token=generate_password_reset_token(),
            user_id=user.id,
            expires_at=_utcnow() + timedelta(hours=_TOKEN_TTL_HOURS),
        )
        db.add(token)
        await db.flush()
        await db.refresh(token)
        return token

    @staticmethod
    async def consume_token(
        db: AsyncSession, token_str: str, new_password: str
    ) -> User:
        """Consome o token e redefine a senha.

        Args:
            db: Sessão assíncrona.
            token_str: Token recebido por e-mail.
            new_password: Nova senha em texto puro.

        Returns:
            User com senha atualizada.

        Raises:
            HTTPException 400: Token inválido, expirado ou já usado.
        """
        result = await db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token == token_str)
        )
        token = result.scalar_one_or_none()

        if not token or token.used_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido ou já utilizado")
        if token.expires_at < _utcnow():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token expirado")

        token.used_at = _utcnow()

        user = await UserRepository.get_by_id(db, token.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário não encontrado")

        user.hashed_password = hash_password(new_password)
        await db.flush()
        logger.info("Senha redefinida via token para user_id=%s", user.id)
        return user


class InviteService:
    """Convite e auto-cadastro de competidores (RF-06, RF-13, RN-07)."""

    @staticmethod
    async def create_invite(
        db: AsyncSession,
        email: str,
        competition_id: int | None,
        category_id: int | None,
        invited_by: User,
        team_id: int | None = None,
    ) -> InviteToken:
        """Cria token de convite para um e-mail (RF-13).

        Se team_id for None e category_id apontar para uma categoria individual,
        uma equipe com o e-mail como nome é criada automaticamente no registro.

        Args:
            db: Sessão assíncrona.
            email: E-mail do convidado.
            competition_id: Competição associada (opcional).
            category_id: Categoria sugerida (opcional).
            invited_by: Usuário que está convidando.
            team_id: Equipe a que o competidor será automaticamente adicionado (opcional).

        Returns:
            InviteToken criado.

        Raises:
            HTTPException 409: Usuário com este e-mail já existe.
        """
        existing = await UserRepository.get_by_email(db, email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe um usuário com este e-mail",
            )

        # Invalida convites anteriores para o mesmo e-mail
        result = await db.execute(
            select(InviteToken).where(
                InviteToken.email == email,
                InviteToken.used_at.is_(None),
            )
        )
        for old in result.scalars().all():
            old.used_at = _utcnow()

        invite = InviteToken(
            token=generate_invite_token(),
            email=email,
            competition_id=competition_id,
            category_id=category_id,
            team_id=team_id,
            invited_by_id=invited_by.id,
            expires_at=_utcnow() + timedelta(hours=_TOKEN_TTL_HOURS),
        )
        db.add(invite)
        await db.flush()
        await db.refresh(invite)
        return invite

    @staticmethod
    async def get_invite(db: AsyncSession, token_str: str) -> InviteToken:
        """Retorna convite válido pelo token.

        Args:
            db: Sessão assíncrona.
            token_str: Token do convite.

        Returns:
            InviteToken válido.

        Raises:
            HTTPException 400: Token inválido, expirado ou já usado.
        """
        result = await db.execute(
            select(InviteToken).where(InviteToken.token == token_str)
        )
        invite = result.scalar_one_or_none()

        if not invite or invite.used_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Convite inválido ou já utilizado")
        if invite.expires_at < _utcnow():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Convite expirado")

        return invite

    @staticmethod
    async def register_via_invite(
        db: AsyncSession,
        token_str: str,
        full_name: str,
        password: str,
        email: str,
    ) -> User:
        """Registra competidor via token de convite (RF-06, RN-07).

        Args:
            db: Sessão assíncrona.
            token_str: Token do convite.
            full_name: Nome completo.
            password: Senha em texto puro.
            email: E-mail informado pelo usuário.

        Returns:
            User criado com role=competitor.

        Raises:
            HTTPException 400: Token inválido/expirado ou e-mail não confere (RN-07).
            HTTPException 409: E-mail já cadastrado.
        """
        invite = await InviteService.get_invite(db, token_str)

        # RN-07: link de convite é pessoal
        if invite.email.lower() != email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este convite foi enviado para outro e-mail (RN-07)",
            )

        existing = await UserRepository.get_by_email(db, email)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")

        user = User(
            full_name=full_name,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.competitor,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

        invite.used_at = _utcnow()

        # Auto-registrar na competição/categoria do convite
        if invite.competition_id and invite.category_id:
            from app.models.competitor import CompetitorRegistration
            reg = CompetitorRegistration(
                user_id=user.id,
                competition_id=invite.competition_id,
                category_id=invite.category_id,
            )
            db.add(reg)

            # Associar à equipe do convite (ou auto-criar para categoria individual)
            await InviteService._handle_team_assignment(db, user, invite)

        await db.flush()
        logger.info("Competidor registrado via convite: user_id=%s", user.id)
        return user

    @staticmethod
    async def _handle_team_assignment(
        db: AsyncSession, user: "User", invite: "InviteToken"
    ) -> None:
        """Associa o competidor a uma equipe conforme o convite.

        Se o convite tiver team_id: adiciona o usuário como membro.
        Se a categoria for individual e sem team_id: cria equipe com o e-mail como nome.

        Args:
            db: Sessão assíncrona.
            user: Usuário recém-criado.
            invite: InviteToken consumido.
        """
        from app.models.category import Category, CategoryType
        from app.models.team import Team, TeamMember

        if invite.team_id:
            # Adiciona à equipe especificada no convite
            member = TeamMember(team_id=invite.team_id, user_id=user.id)
            db.add(member)
            await db.flush()
            return

        if not invite.category_id:
            return

        # Verifica o tipo da categoria
        cat_result = await db.execute(
            select(Category).where(Category.id == invite.category_id)
        )
        category = cat_result.scalar_one_or_none()
        if not category or category.category_type != CategoryType.individual:
            return

        # Categoria individual: cria equipe com e-mail como nome (RN: atleta individual = equipe solo)
        team = Team(
            name=user.email,
            competition_id=invite.competition_id,
            category_id=invite.category_id,
            captain_id=user.id,
        )
        db.add(team)
        await db.flush()
        await db.refresh(team)

        member = TeamMember(team_id=team.id, user_id=user.id)
        db.add(member)
        await db.flush()
