from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.team import Team, TeamMember


class TeamRepository:
    """Acesso ao banco para equipes."""

    @staticmethod
    async def get_by_id(db: AsyncSession, team_id: int) -> Team | None:
        """Retorna equipe pelo ID com membros carregados.

        Args:
            db: Sessão assíncrona.
            team_id: ID da equipe.

        Returns:
            Team ou None.
        """
        result = await db.execute(
            select(Team)
            .options(selectinload(Team.members).selectinload(TeamMember.user))
            .where(Team.id == team_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_competition(db: AsyncSession, competition_id: int) -> list[Team]:
        """Lista equipes de uma competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            Lista de Team.
        """
        result = await db.execute(
            select(Team)
            .options(selectinload(Team.members).selectinload(TeamMember.user))
            .where(Team.competition_id == competition_id)
            .order_by(Team.name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, team: Team) -> Team:
        """Persiste uma nova equipe.

        Args:
            db: Sessão assíncrona.
            team: Instância ORM não persistida.

        Returns:
            Team criada.
        """
        db.add(team)
        await db.flush()
        return await TeamRepository.get_by_id(db, team.id)  # type: ignore[return-value]

    @staticmethod
    async def save(db: AsyncSession, team: Team) -> Team:
        """Persiste alterações em uma equipe.

        Args:
            db: Sessão assíncrona.
            team: Instância ORM modificada.

        Returns:
            Team atualizada (com membros carregados).
        """
        await db.flush()
        return await TeamRepository.get_by_id(db, team.id)  # type: ignore[return-value]

    @staticmethod
    async def delete(db: AsyncSession, team: Team) -> None:
        """Remove uma equipe e seus membros (cascade).

        Args:
            db: Sessão assíncrona.
            team: Instância ORM a remover.
        """
        await db.delete(team)
        await db.flush()

    @staticmethod
    async def add_member(db: AsyncSession, member: TeamMember) -> TeamMember:
        """Adiciona membro a uma equipe.

        Args:
            db: Sessão assíncrona.
            member: Instância TeamMember não persistida.

        Returns:
            TeamMember criado.
        """
        db.add(member)
        await db.flush()
        await db.refresh(member)
        return member

    @staticmethod
    async def get_member(db: AsyncSession, team_id: int, user_id: int) -> TeamMember | None:
        """Retorna membro de equipe pelo par (team_id, user_id).

        Args:
            db: Sessão assíncrona.
            team_id: ID da equipe.
            user_id: ID do usuário.

        Returns:
            TeamMember ou None.
        """
        result = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id, TeamMember.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def remove_member(db: AsyncSession, member: TeamMember) -> None:
        """Remove membro de uma equipe.

        Args:
            db: Sessão assíncrona.
            member: Instância TeamMember a remover.
        """
        await db.delete(member)
        await db.flush()
