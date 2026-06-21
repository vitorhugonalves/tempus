"""Serviço de timers, penalidades e ranking (RF-26 a RF-39)."""

import time
from datetime import datetime, timezone

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import (
    delete_timer_state,
    get_timer_state,
    publish_timer_event,
    set_timer_state,
    timer_lock,
)
from app.models.competition import CompetitionStatus
from app.models.timer import (
    VALID_TRANSITIONS,
    OfficialResult,
    Penalty,
    PenaltyType,
    Timer,
    TimerEvent,
    TimerEventType,
    TimerStatus,
)
from app.models.user import User
from app.repositories.competition import CompetitionRepository
from app.repositories.timer import OfficialResultRepository, PenaltyTypeRepository, TimerRepository
from app.schemas.timer import (
    PenaltyApply,
    PenaltyTypeCreate,
    RankingEntry,
    TimerCreate,
    _compute_accumulated_ms,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _validate_transition(timer: Timer, target: TimerStatus) -> None:
    """Valida transição de estado, lançando 409 em caso de transição inválida.

    Args:
        timer: Timer atual.
        target: Estado destino.

    Raises:
        HTTPException 409: Transição inválida.
    """
    if target not in VALID_TRANSITIONS.get(timer.status, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Transição inválida: {timer.status.value} → {target.value}. "
                f"Permitidas: {[s.value for s in VALID_TRANSITIONS.get(timer.status, set())]}"
            ),
        )


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
            Timer criado com status `created`.

        Raises:
            HTTPException 404: Competição não encontrada.
            HTTPException 409: Timer já existe para este atleta/equipe.
        """
        from sqlalchemy import select

        competition = await CompetitionRepository.get_by_id(db, data.competition_id)
        if not competition:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada")

        # Verifica duplicata
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
    async def mark_ready(
        db: AsyncSession, timer_id: int, note: str | None, current_user: User
    ) -> Timer:
        """Marca o timer como pronto para iniciar (created → ready).

        Usado para preparar timers em lote antes da largada, por exemplo,
        colocando todos os atletas de uma bateria em estado 'ready' antes
        de acionar start_all.

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.
            note: Observação opcional.
            current_user: Usuário autenticado.

        Returns:
            Timer com status `ready`.

        Raises:
            HTTPException 404: Timer não encontrado.
            HTTPException 409: Transição inválida.
        """
        timer = await TimerRepository.get_by_id(db, timer_id)
        if not timer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")

        _validate_transition(timer, TimerStatus.ready)
        timer.status = TimerStatus.ready

        await TimerRepository.add_event(
            db,
            TimerEvent(
                timer_id=timer.id,
                event_type=TimerEventType.ready,
                event_at=_utcnow(),
                accumulated_ms=0,
                triggered_by_id=current_user.id,
                note=note,
            ),
        )
        return await TimerRepository.save(db, timer)

    @staticmethod
    async def start(
        db: AsyncSession, timer_id: int, note: str | None, current_user: User, redis: Redis
    ) -> Timer:
        """Inicia o timer (RF-27).

        Aceita status `created` ou `ready` → `running`.
        RN-01: a competição deve estar ativa.
        Usa lock distribuído Redis para evitar race conditions.

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.
            note: Observação opcional.
            current_user: Usuário autenticado.
            redis: Conexão Redis.

        Returns:
            Timer com status `running`.

        Raises:
            HTTPException 403: Competição não ativa (RN-01).
            HTTPException 404: Timer não encontrado.
            HTTPException 409: Transição inválida.
        """
        async with timer_lock(redis, timer_id):
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

            _validate_transition(timer, TimerStatus.running)

            # accumulated_ms baseline: do último evento de pausa (0 se nunca pausou)
            accumulated_ms = _compute_accumulated_ms_from_stopped_state(timer)
            now = _utcnow()
            now_ms = int(time.time() * 1000)

            timer.status = TimerStatus.running
            await TimerRepository.add_event(
                db,
                TimerEvent(
                    timer_id=timer.id,
                    event_type=TimerEventType.started,
                    event_at=now,
                    accumulated_ms=accumulated_ms,
                    triggered_by_id=current_user.id,
                    note=note,
                ),
            )
            saved = await TimerRepository.save(db, timer)

            # Escreve estado quente no Redis para leitura sub-segundo
            await set_timer_state(redis, timer_id, {
                "status": "running",
                "accumulated_ms": accumulated_ms,
                "started_at_ms": now_ms,
            })
            await publish_timer_event(redis, timer.competition_id, {
                "event_type": "started",
                "timer_id": timer_id,
                "accumulated_ms": accumulated_ms,
                "started_at_ms": now_ms,
            })
            return saved

    @staticmethod
    async def pause(
        db: AsyncSession, timer_id: int, note: str | None, current_user: User, redis: Redis
    ) -> Timer:
        """Pausa o timer (running → paused).

        Lê o accumulated_ms preciso do Redis antes de remover o estado quente.

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.
            note: Observação opcional.
            current_user: Usuário autenticado.
            redis: Conexão Redis.

        Returns:
            Timer com status `paused`.

        Raises:
            HTTPException 404: Timer não encontrado.
            HTTPException 409: Transição inválida.
        """
        async with timer_lock(redis, timer_id):
            timer = await TimerRepository.get_by_id(db, timer_id)
            if not timer:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")

            _validate_transition(timer, TimerStatus.paused)

            # Lê accumulated_ms do Redis para precisão sub-segundo; fallback para eventos DB
            redis_state = await get_timer_state(redis, timer_id)
            if redis_state:
                now_ms = int(time.time() * 1000)
                accumulated_ms = redis_state["accumulated_ms"] + (now_ms - redis_state["started_at_ms"])
            else:
                accumulated_ms = _compute_accumulated_ms(timer)
            now = _utcnow()

            timer.status = TimerStatus.paused
            await TimerRepository.add_event(
                db,
                TimerEvent(
                    timer_id=timer.id,
                    event_type=TimerEventType.paused,
                    event_at=now,
                    accumulated_ms=accumulated_ms,
                    triggered_by_id=current_user.id,
                    note=note,
                ),
            )
            saved = await TimerRepository.save(db, timer)

            # Remove estado quente do Redis (timer não está mais rodando)
            await delete_timer_state(redis, timer_id)
            await publish_timer_event(redis, timer.competition_id, {
                "event_type": "paused",
                "timer_id": timer_id,
                "accumulated_ms": accumulated_ms,
            })
            return saved

    @staticmethod
    async def resume(
        db: AsyncSession, timer_id: int, note: str | None, current_user: User, redis: Redis
    ) -> Timer:
        """Retoma o timer após pausa (paused → running).

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.
            note: Observação opcional.
            current_user: Usuário autenticado.
            redis: Conexão Redis.

        Returns:
            Timer com status `running`.

        Raises:
            HTTPException 404: Timer não encontrado.
            HTTPException 409: Transição inválida.
        """
        async with timer_lock(redis, timer_id):
            timer = await TimerRepository.get_by_id(db, timer_id)
            if not timer:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")

            _validate_transition(timer, TimerStatus.running)

            accumulated_ms = _compute_accumulated_ms_from_stopped_state(timer)
            now = _utcnow()
            now_ms = int(time.time() * 1000)

            timer.status = TimerStatus.running
            await TimerRepository.add_event(
                db,
                TimerEvent(
                    timer_id=timer.id,
                    event_type=TimerEventType.resumed,
                    event_at=now,
                    accumulated_ms=accumulated_ms,
                    triggered_by_id=current_user.id,
                    note=note,
                ),
            )
            saved = await TimerRepository.save(db, timer)

            await set_timer_state(redis, timer_id, {
                "status": "running",
                "accumulated_ms": accumulated_ms,
                "started_at_ms": now_ms,
            })
            await publish_timer_event(redis, timer.competition_id, {
                "event_type": "resumed",
                "timer_id": timer_id,
                "accumulated_ms": accumulated_ms,
                "started_at_ms": now_ms,
            })
            return saved

    @staticmethod
    async def finish(
        db: AsyncSession, timer_id: int, note: str | None, current_user: User, redis: Redis
    ) -> Timer:
        """Finaliza o timer com resultado oficial imediato (RF-28, RN-04).

        Lê o accumulated_ms preciso do Redis, persiste o evento `finished` e
        cria um registro em `official_results` automaticamente.

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.
            note: Observação opcional.
            current_user: Usuário autenticado.
            redis: Conexão Redis.

        Returns:
            Timer com status `finished`.

        Raises:
            HTTPException 404: Timer não encontrado.
            HTTPException 409: Transição inválida.
        """
        async with timer_lock(redis, timer_id):
            timer = await TimerRepository.get_by_id(db, timer_id)
            if not timer:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")

            _validate_transition(timer, TimerStatus.finished)

            # Lê ms preciso do Redis; fallback para cálculo por eventos
            redis_state = await get_timer_state(redis, timer_id)
            if redis_state:
                now_ms = int(time.time() * 1000)
                accumulated_ms = redis_state["accumulated_ms"] + (now_ms - redis_state["started_at_ms"])
            else:
                accumulated_ms = _compute_accumulated_ms(timer)
            now = _utcnow()

            timer.status = TimerStatus.finished
            await TimerRepository.add_event(
                db,
                TimerEvent(
                    timer_id=timer.id,
                    event_type=TimerEventType.finished,
                    event_at=now,
                    accumulated_ms=accumulated_ms,
                    triggered_by_id=current_user.id,
                    note=note,
                ),
            )
            saved = await TimerRepository.save(db, timer)

            # Cria resultado oficial automaticamente (sem fluxo de aprovação)
            await OfficialResultRepository.create(
                db,
                OfficialResult(
                    timer_id=timer_id,
                    final_time_ms=accumulated_ms,
                    finished_by_user_id=current_user.id,
                    finished_at=now,
                ),
            )

            # Remove estado quente do Redis
            await delete_timer_state(redis, timer_id)
            await publish_timer_event(redis, timer.competition_id, {
                "event_type": "finished",
                "timer_id": timer_id,
                "accumulated_ms": accumulated_ms,
            })
            return saved

    @staticmethod
    async def cancel(
        db: AsyncSession, timer_id: int, note: str | None, current_user: User, redis: Redis
    ) -> Timer:
        """Cancela o timer antes de iniciar (created/ready → cancelled).

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.
            note: Observação opcional.
            current_user: Usuário autenticado.
            redis: Conexão Redis.

        Returns:
            Timer com status `cancelled`.

        Raises:
            HTTPException 404: Timer não encontrado.
            HTTPException 409: Transição inválida.
        """
        async with timer_lock(redis, timer_id):
            timer = await TimerRepository.get_by_id(db, timer_id)
            if not timer:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")

            _validate_transition(timer, TimerStatus.cancelled)

            now = _utcnow()
            timer.status = TimerStatus.cancelled
            await TimerRepository.add_event(
                db,
                TimerEvent(
                    timer_id=timer.id,
                    event_type=TimerEventType.cancelled,
                    event_at=now,
                    accumulated_ms=0,
                    triggered_by_id=current_user.id,
                    note=note,
                ),
            )
            saved = await TimerRepository.save(db, timer)
            await delete_timer_state(redis, timer_id)
            await publish_timer_event(redis, timer.competition_id, {
                "event_type": "cancelled",
                "timer_id": timer_id,
            })
            return saved

    @staticmethod
    async def reset(
        db: AsyncSession, timer_id: int, note: str | None, current_user: User, redis: Redis
    ) -> Timer:
        """Reinicia o timer zerando o tempo acumulado (RF-29).

        O timer volta ao estado `created`. Motivo é obrigatório por RF-29.
        RN-01: competição deve estar ativa.

        Args:
            db: Sessão assíncrona.
            timer_id: ID do timer.
            note: Motivo do reinício (obrigatório).
            current_user: Usuário autenticado.
            redis: Conexão Redis.

        Returns:
            Timer com status `created` e accumulated_ms zerado.

        Raises:
            HTTPException 403: Competição não ativa.
            HTTPException 404: Timer não encontrado.
            HTTPException 409: Timer já finalizado.
            HTTPException 422: Motivo não informado.
        """
        async with timer_lock(redis, timer_id):
            timer = await TimerRepository.get_by_id(db, timer_id)
            if not timer:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")
            if not note:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="O motivo do reinício é obrigatório (RF-29)",
                )
            if timer.status in (TimerStatus.finished, TimerStatus.cancelled):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Timer {timer.status.value} não pode ser reiniciado",
                )

            # RN-01: competição deve estar ativa
            competition = await CompetitionRepository.get_by_id(db, timer.competition_id)
            if not competition or competition.status != CompetitionStatus.active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Competição não está ativa",
                )

            timer.status = TimerStatus.created
            await TimerRepository.add_event(
                db,
                TimerEvent(
                    timer_id=timer.id,
                    event_type=TimerEventType.reset,
                    event_at=_utcnow(),
                    accumulated_ms=0,
                    triggered_by_id=current_user.id,
                    note=note,
                ),
            )
            saved = await TimerRepository.save(db, timer)
            await delete_timer_state(redis, timer_id)
            await publish_timer_event(redis, timer.competition_id, {
                "event_type": "reset",
                "timer_id": timer_id,
            })
            return saved

    # Manter backward compat: stop → pause, restart → reset
    stop = pause  # type: ignore[assignment]
    restart = reset  # type: ignore[assignment]

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


def _compute_accumulated_ms_from_stopped_state(timer: Timer) -> int:
    """Retorna accumulated_ms do último evento de estado parado (paused/reset).

    Usado ao iniciar ou retomar: garante que o accumulated_ms do novo evento
    `started`/`resumed` começa do ponto correto.

    Args:
        timer: Timer com events carregados.

    Returns:
        Tempo acumulado em ms (0 se nunca pausou).
    """
    events = sorted(timer.events, key=lambda e: e.id)
    for event in reversed(events):
        if event.event_type in (TimerEventType.paused, TimerEventType.reset):
            return event.accumulated_ms
    return 0


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
            HTTPException 409: Competição encerrada (RN-04).
        """
        timer = await TimerRepository.get_by_id(db, timer_id)
        if not timer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado")

        # RN-04: tempo final imutável após encerramento da competição
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

        Tempo final = accumulated_ms // 1000 + total de penalidades.
        Apenas timers `finished` entram no ranking principal;
        timers `running` e `paused` aparecem depois para visualização ao vivo.
        remaining_seconds = duration_seconds - elapsed (se configurado).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            category_id: Filtrar por categoria (opcional).

        Returns:
            Lista de RankingEntry ordenada por final_seconds.
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        query = (
            select(Timer)
            .options(
                selectinload(Timer.penalties).selectinload(Penalty.penalty_type),
                selectinload(Timer.user),
                selectinload(Timer.team),
                selectinload(Timer.category),
                selectinload(Timer.events),
            )
            .where(Timer.competition_id == competition_id)
        )
        if category_id:
            query = query.where(Timer.category_id == category_id)

        result = await db.execute(query)
        timers = list(result.scalars().all())

        duration_seconds: int | None = None

        entries: list[RankingEntry] = []
        for timer in timers:
            penalty_seconds = sum(p.seconds_added for p in timer.penalties)
            accumulated_ms = _compute_accumulated_ms(timer)
            elapsed_seconds = accumulated_ms // 1000

            if timer.user:
                athlete_name = timer.user.full_name
            elif timer.team:
                athlete_name = timer.team.name
            else:
                athlete_name = f"Timer #{timer.id}"

            team_name = timer.team.name if timer.team else None
            box_name = timer.team.box_name if timer.team else None
            category_name = timer.category.name if timer.category else None
            infractions_count = len(timer.penalties)

            remaining: int | None = None
            if duration_seconds and timer.status in (
                TimerStatus.running, TimerStatus.created, TimerStatus.ready
            ):
                remaining = max(0, duration_seconds - elapsed_seconds)

            entries.append(
                RankingEntry(
                    position=0,
                    timer_id=timer.id,
                    user_id=timer.user_id,
                    team_id=timer.team_id,
                    athlete_name=athlete_name,
                    team_name=team_name,
                    box_name=box_name,
                    category_name=category_name,
                    accumulated_ms=accumulated_ms,
                    elapsed_seconds=elapsed_seconds,
                    total_penalty_seconds=penalty_seconds,
                    final_seconds=elapsed_seconds + penalty_seconds,
                    infractions_count=infractions_count,
                    remaining_seconds=remaining,
                    status=timer.status,
                )
            )

        # Ordenar: finished primeiro (por final_seconds), paused, running, ready, created
        _order = {
            TimerStatus.finished: 0,
            TimerStatus.paused: 1,
            TimerStatus.running: 2,
            TimerStatus.ready: 3,
            TimerStatus.created: 4,
            TimerStatus.cancelled: 5,
        }

        def sort_key(e: RankingEntry) -> tuple:
            return (_order.get(e.status, 9), e.final_seconds)

        entries.sort(key=sort_key)

        # Posições (apenas timers finalizados recebem posição numerada)
        pos = 1
        for entry in entries:
            if entry.status == TimerStatus.finished:
                entry.position = pos
                pos += 1

        return entries

    @staticmethod
    async def get_crossfit_ranking(
        db: AsyncSession,
        competition_id: int,
        category_id: int | None = None,
    ) -> list["CrossfitRankingEntry"]:
        """Ranking agregado para CrossFit — pontos por colocação por WOD (bateria).

        Cada bateria é pontuada individualmente: o 1º colocado recebe N pontos
        (N = total de finalizadores na bateria), o 2º recebe N-1, etc.
        O total de pontos é somado entre todas as baterias.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            category_id: Filtrar por categoria (opcional).

        Returns:
            Lista de CrossfitRankingEntry ordenada por total_points DESC.
        """
        from collections import defaultdict

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.schemas.timer import CrossfitRankingEntry

        # Carrega todos os timers da competição com seus heats
        query = (
            select(Timer)
            .options(
                selectinload(Timer.user),
                selectinload(Timer.team),
                selectinload(Timer.category),
                selectinload(Timer.events),
                selectinload(Timer.penalties),
            )
            .where(Timer.competition_id == competition_id)
        )
        if category_id:
            query = query.where(Timer.category_id == category_id)

        result = await db.execute(query)
        timers = list(result.scalars().all())

        # Agrupa timers por heat para calcular pontos por bateria
        # heat_id None → timers sem bateria (agrupados como um único "WOD" virtual)
        heats: dict[int | None, list[Timer]] = defaultdict(list)
        for timer in timers:
            heats[timer.heat_id].append(timer)

        # Pontos acumulados e métricas por chave única de atleta/equipe
        # chave: (team_id, user_id)
        points_map: dict[tuple, int] = defaultdict(int)
        wods_map: dict[tuple, int] = defaultdict(int)
        status_map: dict[tuple, str] = {}
        meta_map: dict[tuple, dict] = {}

        for heat_timers in heats.values():
            # Filtra apenas os finalizadores desta bateria para calcular posição
            finished = sorted(
                [t for t in heat_timers if t.status == TimerStatus.finished],
                key=lambda t: _compute_accumulated_ms(t)
                + sum(p.seconds_added for p in t.penalties) * 1000,
            )
            n_finishers = len(finished)

            for rank_idx, timer in enumerate(finished):
                key = (timer.team_id, timer.user_id)
                pts = n_finishers - rank_idx  # 1º = N pts, 2º = N-1, ...
                points_map[key] += pts
                wods_map[key] += 1

            # Registra meta e status para todos os timers (não só finished)
            for timer in heat_timers:
                key = (timer.team_id, timer.user_id)

                if timer.user:
                    athlete_name = timer.user.full_name
                elif timer.team:
                    athlete_name = timer.team.name
                else:
                    athlete_name = f"Timer #{timer.id}"

                if key not in meta_map:
                    meta_map[key] = {
                        "team_id": timer.team_id,
                        "user_id": timer.user_id,
                        "athlete_name": athlete_name,
                        "team_name": timer.team.name if timer.team else None,
                        "category_name": timer.category.name if timer.category else None,
                    }

                # Status mais "urgente" vence: running > paused > created > finished
                _priority = {
                    "running": 0, "paused": 1, "created": 2, "ready": 2, "finished": 3, "cancelled": 4,
                }
                new_s = timer.status.value
                cur_s = status_map.get(key, "finished")
                if _priority.get(new_s, 9) < _priority.get(cur_s, 9):
                    status_map[key] = new_s

        # Garante que atletas/equipes sem nenhum timer ainda aparecem
        for timer in timers:
            key = (timer.team_id, timer.user_id)
            if key not in meta_map:
                if timer.user:
                    athlete_name = timer.user.full_name
                elif timer.team:
                    athlete_name = timer.team.name
                else:
                    athlete_name = f"Timer #{timer.id}"
                meta_map[key] = {
                    "team_id": timer.team_id,
                    "user_id": timer.user_id,
                    "athlete_name": athlete_name,
                    "team_name": timer.team.name if timer.team else None,
                    "category_name": timer.category.name if timer.category else None,
                }
            if key not in status_map:
                status_map[key] = timer.status.value

        entries: list[CrossfitRankingEntry] = []
        for key, meta in meta_map.items():
            entries.append(
                CrossfitRankingEntry(
                    position=0,
                    team_id=meta["team_id"],
                    user_id=meta["user_id"],
                    athlete_name=meta["athlete_name"],
                    team_name=meta["team_name"],
                    category_name=meta["category_name"],
                    wods_completed=wods_map[key],
                    total_points=points_map[key],
                    status=status_map.get(key, "pending"),
                )
            )

        # Ordena: mais pontos primeiro; desempate por wods_completed DESC
        entries.sort(key=lambda e: (-e.total_points, -e.wods_completed))

        # Atribui posições
        pos = 1
        for entry in entries:
            entry.position = pos
            pos += 1

        return entries
