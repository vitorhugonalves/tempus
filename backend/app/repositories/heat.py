from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.heat import Heat, HeatTeam
from app.models.team import Team, TeamMember
from app.models.timer import Timer


class HeatRepository:
    """Acesso ao banco para baterias."""

    @staticmethod
    async def get_by_id(db: AsyncSession, heat_id: int) -> Heat | None:
        """Retorna bateria pelo ID com timers e equipes carregadas.

        Args:
            db: Sessão assíncrona.
            heat_id: ID da bateria.

        Returns:
            Heat ou None.
        """
        result = await db.execute(
            select(Heat)
            .options(
                selectinload(Heat.timers),
                selectinload(Heat.heat_teams)
                .selectinload(HeatTeam.team)
                .selectinload(Team.members),
            )
            .where(Heat.id == heat_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_competition(db: AsyncSession, competition_id: int) -> list[Heat]:
        """Lista baterias de uma competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            Lista de Heat.
        """
        result = await db.execute(
            select(Heat)
            .options(
                selectinload(Heat.timers),
                selectinload(Heat.heat_teams)
                .selectinload(HeatTeam.team)
                .selectinload(Team.members),
            )
            .where(Heat.competition_id == competition_id)
            .order_by(Heat.sort_order, Heat.id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, heat: Heat) -> Heat:
        """Persiste uma nova bateria.

        Args:
            db: Sessão assíncrona.
            heat: Instância ORM não persistida.

        Returns:
            Heat criada.
        """
        db.add(heat)
        await db.flush()
        return await HeatRepository.get_by_id(db, heat.id)  # type: ignore[return-value]

    @staticmethod
    async def save(db: AsyncSession, heat: Heat) -> Heat:
        """Persiste alterações em uma bateria.

        Args:
            db: Sessão assíncrona.
            heat: Instância ORM modificada.

        Returns:
            Heat atualizada (com timers e equipes carregadas).
        """
        await db.flush()
        return await HeatRepository.get_by_id(db, heat.id)  # type: ignore[return-value]

    @staticmethod
    async def delete(db: AsyncSession, heat: Heat) -> None:
        """Remove uma bateria (desvincula timers antes).

        Args:
            db: Sessão assíncrona.
            heat: Instância ORM a remover.
        """
        # Desvincular timers da bateria antes de deletar
        await db.execute(
            Timer.__table__.update()  # type: ignore[attr-defined]
            .where(Timer.heat_id == heat.id)
            .values(heat_id=None)
        )
        await db.delete(heat)
        await db.flush()

    @staticmethod
    async def get_heat_team(db: AsyncSession, heat_id: int, team_id: int) -> HeatTeam | None:
        """Retorna associação heat-team pelo par (heat_id, team_id).

        Args:
            db: Sessão assíncrona.
            heat_id: ID da bateria.
            team_id: ID da equipe.

        Returns:
            HeatTeam ou None.
        """
        result = await db.execute(
            select(HeatTeam).where(
                HeatTeam.heat_id == heat_id, HeatTeam.team_id == team_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def add_team(db: AsyncSession, heat_id: int, team_id: int) -> HeatTeam:
        """Vincula equipe a uma bateria.

        Args:
            db: Sessão assíncrona.
            heat_id: ID da bateria.
            team_id: ID da equipe.

        Returns:
            HeatTeam criado.
        """
        ht = HeatTeam(heat_id=heat_id, team_id=team_id)
        db.add(ht)
        await db.flush()
        await db.refresh(ht)
        return ht

    @staticmethod
    async def get_max_sort_order(db: AsyncSession, competition_id: int) -> int:
        """Retorna o maior sort_order das baterias da competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            Maior sort_order ou 0 se não houver baterias.
        """
        result = await db.execute(
            select(func.max(Heat.sort_order)).where(Heat.competition_id == competition_id)
        )
        return result.scalar_one_or_none() or 0

    @staticmethod
    async def remove_team(db: AsyncSession, ht: HeatTeam) -> None:
        """Remove vínculo equipe-bateria.

        Args:
            db: Sessão assíncrona.
            ht: Instância HeatTeam a remover.
        """
        await db.delete(ht)
        await db.flush()
