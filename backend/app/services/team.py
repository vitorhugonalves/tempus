"""Serviço de equipes."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team, TeamMember
from app.repositories.competition import CompetitionRepository
from app.repositories.team import TeamRepository
from app.repositories.user import UserRepository
from app.schemas.team import TeamCreate, TeamMemberAdd, TeamUpdate


class TeamService:
    """Regras de negócio para equipes (RF-23 a RF-25)."""

    @staticmethod
    async def get_or_404(db: AsyncSession, team_id: int) -> Team:
        """Retorna equipe ou lança 404.

        Args:
            db: Sessão assíncrona.
            team_id: ID da equipe.

        Returns:
            Team.

        Raises:
            HTTPException 404.
        """
        team = await TeamRepository.get_by_id(db, team_id)
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Equipe não encontrada"
            )
        return team

    @staticmethod
    async def list_by_competition(db: AsyncSession, competition_id: int) -> list[Team]:
        """Lista equipes da competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            Lista de Team.
        """
        return await TeamRepository.get_by_competition(db, competition_id)

    @staticmethod
    async def create(db: AsyncSession, competition_id: int, data: TeamCreate) -> Team:
        """Cria equipe em uma competição (RF-23).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            data: Dados validados.

        Returns:
            Team criada.

        Raises:
            HTTPException 404: Competição não encontrada.
        """
        competition = await CompetitionRepository.get_by_id(db, competition_id)
        if not competition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
            )
        team = Team(competition_id=competition_id, **data.model_dump())
        return await TeamRepository.create(db, team)

    @staticmethod
    async def update(db: AsyncSession, team_id: int, data: TeamUpdate) -> Team:
        """Atualiza dados de uma equipe.

        Args:
            db: Sessão assíncrona.
            team_id: ID da equipe.
            data: Campos a atualizar.

        Returns:
            Team atualizada.
        """
        team = await TeamService.get_or_404(db, team_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(team, field, value)
        return await TeamRepository.save(db, team)

    @staticmethod
    async def delete(db: AsyncSession, team_id: int) -> None:
        """Remove equipe.

        Args:
            db: Sessão assíncrona.
            team_id: ID da equipe.
        """
        team = await TeamService.get_or_404(db, team_id)
        await TeamRepository.delete(db, team)

    @staticmethod
    async def add_member(
        db: AsyncSession, team_id: int, data: TeamMemberAdd
    ) -> TeamMember:
        """Adiciona membro à equipe (RF-25).

        Args:
            db: Sessão assíncrona.
            team_id: ID da equipe.
            data: user_id a adicionar.

        Returns:
            TeamMember criado.

        Raises:
            HTTPException 404: Equipe ou usuário não encontrado.
            HTTPException 409: Membro já pertence à equipe.
        """
        team = await TeamService.get_or_404(db, team_id)
        user = await UserRepository.get_by_id(db, data.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado"
            )
        existing = await TeamRepository.get_member(db, team_id, data.user_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Usuário já é membro desta equipe",
            )
        member = TeamMember(team_id=team_id, user_id=data.user_id)
        return await TeamRepository.add_member(db, member)

    @staticmethod
    async def remove_member(db: AsyncSession, team_id: int, user_id: int) -> None:
        """Remove membro da equipe.

        Args:
            db: Sessão assíncrona.
            team_id: ID da equipe.
            user_id: ID do usuário a remover.

        Raises:
            HTTPException 404: Membro não encontrado.
        """
        member = await TeamRepository.get_member(db, team_id, user_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Membro não encontrado nesta equipe",
            )
        await TeamRepository.remove_member(db, member)
