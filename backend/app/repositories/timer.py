from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.timer import Penalty, PenaltyType, Timer, TimerEvent


class TimerRepository:
    """Acesso ao banco para timers."""

    @staticmethod
    async def get_by_id(db: AsyncSession, timer_id: int) -> Timer | None:
        """Retorna timer com penalidades e eventos carregados.

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.

        Returns:
            Timer com relacionamentos ou None.
        """
        result = await db.execute(
            select(Timer)
            .options(
                selectinload(Timer.penalties).selectinload(Penalty.penalty_type),
                selectinload(Timer.events),
            )
            .where(Timer.id == timer_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_competition(
        db: AsyncSession,
        competition_id: int,
    ) -> list[Timer]:
        """Lista timers de uma competição com penalidades.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            Lista de timers.
        """
        result = await db.execute(
            select(Timer)
            .options(
                selectinload(Timer.penalties).selectinload(Penalty.penalty_type),
                selectinload(Timer.events),
            )
            .where(Timer.competition_id == competition_id)
            .order_by(Timer.id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, timer: Timer) -> Timer:
        """Persiste um novo timer.

        Args:
            db: Sessão assíncrona.
            timer: Instância ORM não persistida.

        Returns:
            Timer persistido.
        """
        db.add(timer)
        await db.flush()
        return await TimerRepository.get_by_id(db, timer.id)  # type: ignore[return-value]

    @staticmethod
    async def save(db: AsyncSession, timer: Timer) -> Timer:
        """Persiste alterações em um timer existente.

        Args:
            db: Sessão assíncrona.
            timer: Instância ORM modificada.

        Returns:
            Timer atualizado com relacionamentos.
        """
        await db.flush()
        return await TimerRepository.get_by_id(db, timer.id)  # type: ignore[return-value]

    @staticmethod
    async def add_event(
        db: AsyncSession,
        event: TimerEvent,
    ) -> TimerEvent:
        """Registra um evento de timer.

        Args:
            db: Sessão assíncrona.
            event: Instância de TimerEvent.

        Returns:
            TimerEvent persistido.
        """
        db.add(event)
        await db.flush()
        await db.refresh(event)
        return event


class PenaltyTypeRepository:
    """Acesso ao banco para tipos de penalidade."""

    @staticmethod
    async def get_by_id(db: AsyncSession, penalty_type_id: int) -> PenaltyType | None:
        """Retorna tipo de penalidade pelo ID.

        Args:
            db: Sessão assíncrona.
            penalty_type_id: ID do tipo.

        Returns:
            PenaltyType ou None.
        """
        result = await db.execute(
            select(PenaltyType).where(PenaltyType.id == penalty_type_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_competition(
        db: AsyncSession, competition_id: int
    ) -> list[PenaltyType]:
        """Lista tipos de penalidade de uma competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            Lista de PenaltyType.
        """
        result = await db.execute(
            select(PenaltyType)
            .where(PenaltyType.competition_id == competition_id)
            .order_by(PenaltyType.name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, penalty_type: PenaltyType) -> PenaltyType:
        """Persiste um tipo de penalidade.

        Args:
            db: Sessão assíncrona.
            penalty_type: Instância ORM não persistida.

        Returns:
            PenaltyType persistido.
        """
        db.add(penalty_type)
        await db.flush()
        await db.refresh(penalty_type)
        return penalty_type
