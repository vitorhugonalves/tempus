"""Serviço de timers, penalidades e ranking (RF-26 a RF-39)."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import CompetitionStatus
from app.models.timer import Penalty, PenaltyType, Timer, TimerEvent, TimerEventType, TimerStatus
from app.models.user import User
from app.repositories.competition import CompetitionRepository
from app.repositories.timer import PenaltyTypeRepository, TimerRepository
from app.schemas.timer import PenaltyApply, PenaltyTypeCreate, RankingEntry, TimerCreate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimerService:
    """Regras de negócio para timers (RF-26 a RF-31)."""

    @staticmethod
    async def create(db: AsyncSession, data: TimerCreate, current_user: User) -> Timer:
        """Cria um timer para atleta ou equipe em uma competição (RF-26).

        Args:
            db: Sessão assíncrona.
            data: Dados validados.
            current_user: Usuário autenticado.

        Returns:
            Timer criado.

        Raises:
            HTTPException 404: Competição não encontrada.
            HTTPException 409: Timer já existe para este atleta/equipe.
        """
        from sqlalchemy import select

        competition = await CompetitionRepository.get_by_id(db, data.competition_id)
        if not competition:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada")

        # Verifica duplicata
        from sqlalchemy.ext.asyncio import AsyncSession as _AS
        query = select(Timer).where(Timer.competition_id == data.competition_id)
        if data.user_id:
            query = query.where(Timer.user_id == data.user_id)
        else:
            query = query.where(Timer.team_id == data.team_id)
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Timer já existe para este atleta/equipe nesta competição",
            )

        timer = Timer(
            competition_id=data.competition_id,
            category_id=data.category_id,
            user_id=data.user_id,
            team_id=data.team_id,
        )
        return await TimerRepository.create(db, timer)

    @staticmethod
    async def start(
        db: AsyncSession, timer_id: int, note: str | None, current_user: User
    ) -> Timer:
        """Inicia o timer (RF-27).

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.
            note: Observação opcional.
            current_user: Usuário autenticado.

        Returns:
            Timer atualizado.

        Raises:
            HTTPException 404: Timer não encontrado.
            HTTPException 409: Timer já está rodando ou finalizado.
            HTTPException 403: Competição não está ativa (RN-01).
        """
        timer = await TimerRepository.get_by_id(db, timer_id)
        if not timer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")

        # RN-01: competição deve estar ativa
        competition = await CompetitionRepository.get_by_id(db, timer.competition_id)
        if not competition or competition.status != CompetitionStatus.active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="O timer só pode ser iniciado com a competição ativa (RN-01)",
            )

        if timer.status == TimerStatus.running:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Timer já está em execução")
        if timer.status == TimerStatus.finished:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Timer já finalizado")

        timer.status = TimerStatus.running
        timer.started_at = _utcnow()
        timer.stopped_at = None

        await TimerRepository.add_event(
            db,
            TimerEvent(
                timer_id=timer.id,
                event_type=TimerEventType.start,
                triggered_by_id=current_user.id,
                note=note,
            ),
        )
        return await TimerRepository.save(db, timer)

    @staticmethod
    async def stop(
        db: AsyncSession, timer_id: int, note: str | None, current_user: User
    ) -> Timer:
        """Para o timer (RF-28).

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.
            note: Observação opcional.
            current_user: Usuário autenticado.

        Returns:
            Timer atualizado.

        Raises:
            HTTPException 404: Timer não encontrado.
            HTTPException 409: Timer não está em execução.
        """
        timer = await TimerRepository.get_by_id(db, timer_id)
        if not timer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")
        if timer.status != TimerStatus.running:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Timer não está em execução")

        now = _utcnow()
        if timer.started_at:
            started = timer.started_at.replace(tzinfo=None) if timer.started_at.tzinfo else timer.started_at
            timer.elapsed_seconds += int((now - started).total_seconds())

        timer.status = TimerStatus.stopped
        timer.stopped_at = now

        await TimerRepository.add_event(
            db,
            TimerEvent(
                timer_id=timer.id,
                event_type=TimerEventType.stop,
                triggered_by_id=current_user.id,
                note=note,
            ),
        )
        return await TimerRepository.save(db, timer)

    @staticmethod
    async def finish(
        db: AsyncSession, timer_id: int, note: str | None, current_user: User
    ) -> Timer:
        """Finaliza o timer, marcando o tempo definitivo (RF-28, RN-04).

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.
            note: Observação opcional.
            current_user: Usuário autenticado.

        Returns:
            Timer finalizado.
        """
        timer = await TimerRepository.get_by_id(db, timer_id)
        if not timer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")
        if timer.status == TimerStatus.finished:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Timer já finalizado")

        now = _utcnow()
        if timer.status == TimerStatus.running and timer.started_at:
            started = timer.started_at.replace(tzinfo=None) if timer.started_at.tzinfo else timer.started_at
            timer.elapsed_seconds += int((now - started).total_seconds())

        timer.status = TimerStatus.finished
        timer.stopped_at = now

        await TimerRepository.add_event(
            db,
            TimerEvent(
                timer_id=timer.id,
                event_type=TimerEventType.finish,
                triggered_by_id=current_user.id,
                note=note,
            ),
        )
        return await TimerRepository.save(db, timer)

    @staticmethod
    async def restart(
        db: AsyncSession, timer_id: int, note: str | None, current_user: User
    ) -> Timer:
        """Reinicia o timer zerando o tempo acumulado (RF-29).

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.
            note: Motivo do reinício (obrigatório por RF-29).
            current_user: Usuário autenticado.

        Returns:
            Timer reiniciado.
        """
        timer = await TimerRepository.get_by_id(db, timer_id)
        if not timer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")
        if not note:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="O motivo do reinício é obrigatório (RF-29)",
            )
        if timer.status == TimerStatus.finished:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Timer já finalizado")

        # RN-01: competição deve estar ativa
        competition = await CompetitionRepository.get_by_id(db, timer.competition_id)
        if not competition or competition.status != CompetitionStatus.active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Competição não está ativa",
            )

        timer.elapsed_seconds = 0
        timer.status = TimerStatus.idle
        timer.started_at = None
        timer.stopped_at = None

        await TimerRepository.add_event(
            db,
            TimerEvent(
                timer_id=timer.id,
                event_type=TimerEventType.restart,
                triggered_by_id=current_user.id,
                note=note,
            ),
        )
        return await TimerRepository.save(db, timer)

    @staticmethod
    async def get_or_404(db: AsyncSession, timer_id: int) -> Timer:
        """Retorna timer ou lança 404.

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.

        Returns:
            Timer com relacionamentos.

        Raises:
            HTTPException 404.
        """
        timer = await TimerRepository.get_by_id(db, timer_id)
        if not timer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")
        return timer


class PenaltyService:
    """Regras de negócio para penalidades (RF-32 a RF-35)."""

    @staticmethod
    async def create_type(
        db: AsyncSession, competition_id: int, data: PenaltyTypeCreate
    ) -> PenaltyType:
        """Cria tipo de penalidade para uma competição (RF-32).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            data: Dados validados.

        Returns:
            PenaltyType criado.

        Raises:
            HTTPException 404: Competição não encontrada.
        """
        competition = await CompetitionRepository.get_by_id(db, competition_id)
        if not competition:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada")

        penalty_type = PenaltyType(
            competition_id=competition_id,
            **data.model_dump(),
        )
        return await PenaltyTypeRepository.create(db, penalty_type)

    @staticmethod
    async def apply(
        db: AsyncSession, timer_id: int, data: PenaltyApply, current_user: User
    ) -> Penalty:
        """Aplica penalidade a um timer (RF-33, RF-34).

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.
            data: Dados da penalidade.
            current_user: Usuário autenticado (judge/operator/admin).

        Returns:
            Penalty criada.

        Raises:
            HTTPException 404: Timer ou tipo de penalidade não encontrado.
            HTTPException 409: Timer finalizado — competição encerrada, RN-04.
        """
        timer = await TimerRepository.get_by_id(db, timer_id)
        if not timer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")

        # RN-04: tempo final imutável após encerramento
        competition = await CompetitionRepository.get_by_id(db, timer.competition_id)
        if competition and competition.status == CompetitionStatus.finished:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Competição encerrada — penalidades não podem ser adicionadas (RN-04)",
            )

        penalty_type = await PenaltyTypeRepository.get_by_id(db, data.penalty_type_id)
        if not penalty_type or penalty_type.competition_id != timer.competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tipo de penalidade não encontrado nesta competição",
            )

        penalty = Penalty(
            timer_id=timer_id,
            penalty_type_id=data.penalty_type_id,
            applied_by_id=current_user.id,
            justification=data.justification,
            seconds_added=penalty_type.seconds,
        )
        db.add(penalty)
        await db.flush()
        await db.refresh(penalty)
        # Carrega relacionamento para response
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        result = await db.execute(
            select(Penalty)
            .options(selectinload(Penalty.penalty_type))
            .where(Penalty.id == penalty.id)
        )
        return result.scalar_one()


class RankingService:
    """Cálculo de ranking em tempo real (RF-36 a RF-39)."""

    @staticmethod
    async def get_ranking(
        db: AsyncSession,
        competition_id: int,
        category_id: int | None = None,
    ) -> list[RankingEntry]:
        """Retorna ranking ordenado pelo tempo final (RF-36, RF-37).

        Tempo final = elapsed_seconds + total de penalidades.
        Apenas timers com status finished ou stopped entram no ranking principal;
        timers running aparecem no final para visualização ao vivo.
        remaining_seconds = duration_seconds - elapsed (se configurado e > 0).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            category_id: Filtrar por categoria (opcional).

        Returns:
            Lista de RankingEntry ordenada por final_seconds.
        """
        from datetime import timezone

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.competition import Competition

        query = (
            select(Timer)
            .options(
                selectinload(Timer.penalties).selectinload(Penalty.penalty_type),
                selectinload(Timer.user),
                selectinload(Timer.team),
                selectinload(Timer.category),
            )
            .where(Timer.competition_id == competition_id)
        )
        if category_id:
            query = query.where(Timer.category_id == category_id)

        result = await db.execute(query)
        timers = list(result.scalars().all())

        # Duração configurada na competição (para calcular remaining_seconds)
        comp_result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = comp_result.scalar_one_or_none()
        duration_seconds = competition.duration_seconds if competition else None

        entries: list[RankingEntry] = []
        for timer in timers:
            penalty_seconds = sum(p.seconds_added for p in timer.penalties)
            elapsed = timer.elapsed_seconds
            if timer.status == TimerStatus.running and timer.started_at:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                started = timer.started_at.replace(tzinfo=None) if timer.started_at.tzinfo else timer.started_at
                elapsed += int((now - started).total_seconds())

            # Nome do atleta individual
            if timer.user:
                athlete_name = timer.user.full_name
            elif timer.team:
                athlete_name = timer.team.name
            else:
                athlete_name = f"Timer #{timer.id}"

            # Nome da equipe (preenchido mesmo em timers individuais para consistência)
            team_name = timer.team.name if timer.team else None
            category_name = timer.category.name if timer.category else None
            infractions_count = len(timer.penalties)

            # Tempo restante: só calculado se duração configurada e timer ativo
            remaining: int | None = None
            if duration_seconds and timer.status in (TimerStatus.running, TimerStatus.idle):
                remaining = max(0, duration_seconds - elapsed)

            entries.append(
                RankingEntry(
                    position=0,  # será preenchido após ordenação
                    timer_id=timer.id,
                    user_id=timer.user_id,
                    team_id=timer.team_id,
                    athlete_name=athlete_name,
                    team_name=team_name,
                    category_name=category_name,
                    elapsed_seconds=elapsed,
                    total_penalty_seconds=penalty_seconds,
                    final_seconds=elapsed + penalty_seconds,
                    infractions_count=infractions_count,
                    remaining_seconds=remaining,
                    status=timer.status,
                )
            )

        # Ordenar: finished/stopped primeiro (por final_seconds), running depois, idle por último
        def sort_key(e: RankingEntry) -> tuple:
            order = {
                TimerStatus.finished: 0,
                TimerStatus.stopped: 1,
                TimerStatus.running: 2,
                TimerStatus.idle: 3,
            }
            return (order.get(e.status, 9), e.final_seconds)

        entries.sort(key=sort_key)

        # Atribuir posições (apenas finished/stopped recebem posição numerada)
        pos = 1
        for entry in entries:
            if entry.status in (TimerStatus.finished, TimerStatus.stopped):
                entry.position = pos
                pos += 1

        return entries
