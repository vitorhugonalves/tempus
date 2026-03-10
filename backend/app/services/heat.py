"""Serviço de baterias (heats)."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.heat import Heat, HeatStatus
from app.models.timer import Timer, TimerEvent, TimerEventType, TimerStatus
from app.models.user import User
from app.repositories.competition import CompetitionRepository
from app.repositories.heat import HeatRepository
from app.repositories.timer import TimerRepository
from app.schemas.heat import HeatCreate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class HeatService:
    """Regras de negócio para baterias."""

    @staticmethod
    async def get_or_404(db: AsyncSession, heat_id: int) -> Heat:
        """Retorna bateria ou lança 404.

        Args:
            db: Sessão assíncrona.
            heat_id: ID da bateria.

        Returns:
            Heat.

        Raises:
            HTTPException 404.
        """
        heat = await HeatRepository.get_by_id(db, heat_id)
        if not heat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Bateria não encontrada"
            )
        return heat

    @staticmethod
    async def list_by_competition(db: AsyncSession, competition_id: int) -> list[Heat]:
        """Lista baterias da competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            Lista de Heat.
        """
        return await HeatRepository.get_by_competition(db, competition_id)

    @staticmethod
    async def create(
        db: AsyncSession, competition_id: int, data: HeatCreate
    ) -> Heat:
        """Cria bateria em uma competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            data: Dados validados.

        Returns:
            Heat criada.

        Raises:
            HTTPException 404: Competição não encontrada.
        """
        competition = await CompetitionRepository.get_by_id(db, competition_id)
        if not competition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
            )
        heat = Heat(
            competition_id=competition_id,
            name=data.name,
            scheduled_at=data.scheduled_at,
            max_participants=data.max_participants,
        )
        return await HeatRepository.create(db, heat)

    @staticmethod
    async def add_team(db: AsyncSession, heat_id: int, team_id: int) -> Heat:
        """Vincula equipe a uma bateria com validação de capacidade.

        A soma do tamanho de todas as equipes vinculadas não pode ultrapassar
        max_participants da bateria (quando definido).

        Args:
            db: Sessão assíncrona.
            heat_id: ID da bateria.
            team_id: ID da equipe.

        Returns:
            Heat atualizada.

        Raises:
            HTTPException 404: Bateria ou equipe não encontrada.
            HTTPException 409: Equipe já está na bateria.
            HTTPException 422: Capacidade da bateria excedida.
        """
        from app.repositories.team import TeamRepository

        heat = await HeatService.get_or_404(db, heat_id)
        team = await TeamRepository.get_by_id(db, team_id)
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Equipe não encontrada"
            )
        if team.competition_id != heat.competition_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Equipe não pertence à mesma competição da bateria",
            )

        # Verifica se já está vinculada
        existing = await HeatRepository.get_heat_team(db, heat_id, team_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Equipe já está vinculada a esta bateria",
            )

        # Validação de capacidade
        if heat.max_participants is not None:
            # Soma de membros das equipes já na bateria (usa len(members) — member_count é campo de response, não ORM)
            current_count = sum(len(ht.team.members) for ht in heat.heat_teams)
            team_size = max(len(team.members), 1)  # mínimo 1 para equipes sem membros ainda
            if current_count + team_size > heat.max_participants:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Capacidade excedida: a bateria suporta {heat.max_participants} pessoa(s), "
                        f"atualmente com {current_count} e equipe '{team.name}' tem {team_size} membro(s)."
                    ),
                )

        await HeatRepository.add_team(db, heat_id, team_id)
        return await HeatRepository.get_by_id(db, heat_id)  # type: ignore[return-value]

    @staticmethod
    async def remove_team(db: AsyncSession, heat_id: int, team_id: int) -> Heat:
        """Desvincula equipe de uma bateria.

        Args:
            db: Sessão assíncrona.
            heat_id: ID da bateria.
            team_id: ID da equipe.

        Returns:
            Heat atualizada.

        Raises:
            HTTPException 404: Associação não encontrada.
        """
        await HeatService.get_or_404(db, heat_id)
        ht = await HeatRepository.get_heat_team(db, heat_id, team_id)
        if not ht:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipe não está vinculada a esta bateria",
            )
        await HeatRepository.remove_team(db, ht)
        return await HeatRepository.get_by_id(db, heat_id)  # type: ignore[return-value]

    @staticmethod
    async def add_timer(db: AsyncSession, heat_id: int, timer_id: int) -> Heat:
        """Vincula timer a uma bateria.

        Args:
            db: Sessão assíncrona.
            heat_id: ID da bateria.
            timer_id: ID do timer.

        Returns:
            Heat atualizada.

        Raises:
            HTTPException 404: Bateria ou timer não encontrado.
            HTTPException 409: Timer já pertence a outra bateria.
        """
        heat = await HeatService.get_or_404(db, heat_id)
        timer = await TimerRepository.get_by_id(db, timer_id)
        if not timer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado"
            )
        if timer.competition_id != heat.competition_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Timer não pertence à mesma competição da bateria",
            )
        if timer.heat_id is not None and timer.heat_id != heat_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Timer já está vinculado a outra bateria",
            )
        timer.heat_id = heat_id
        await TimerRepository.save(db, timer)
        return await HeatRepository.get_by_id(db, heat_id)  # type: ignore[return-value]

    @staticmethod
    async def remove_timer(db: AsyncSession, heat_id: int, timer_id: int) -> Heat:
        """Desvincula timer de uma bateria.

        Args:
            db: Sessão assíncrona.
            heat_id: ID da bateria.
            timer_id: ID do timer.

        Returns:
            Heat atualizada.
        """
        await HeatService.get_or_404(db, heat_id)
        timer = await TimerRepository.get_by_id(db, timer_id)
        if not timer or timer.heat_id != heat_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Timer não encontrado nesta bateria",
            )
        timer.heat_id = None
        await TimerRepository.save(db, timer)
        return await HeatRepository.get_by_id(db, heat_id)  # type: ignore[return-value]

    @staticmethod
    async def start_all(
        db: AsyncSession, heat_id: int, current_user: User
    ) -> Heat:
        """Inicia todos os timers da bateria simultaneamente.

        RN-01: competição deve estar ativa.
        Apenas timers em estado idle ou stopped são iniciados.

        Args:
            db: Sessão assíncrona.
            heat_id: ID da bateria.
            current_user: Usuário autenticado (judge/operator/admin).

        Returns:
            Heat com status atualizado.

        Raises:
            HTTPException 403: Competição não está ativa.
            HTTPException 409: Bateria já foi finalizada.
        """
        from app.models.competition import CompetitionStatus

        heat = await HeatService.get_or_404(db, heat_id)

        if heat.status == HeatStatus.finished:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bateria já foi finalizada",
            )

        competition = await CompetitionRepository.get_by_id(db, heat.competition_id)
        if not competition or competition.status != CompetitionStatus.active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A competição deve estar ativa para iniciar uma bateria (RN-01)",
            )

        now = _utcnow()
        started_count = 0

        for timer in heat.timers:
            if timer.status in (TimerStatus.idle, TimerStatus.stopped):
                timer.status = TimerStatus.running
                timer.started_at = now
                timer.stopped_at = None
                await TimerRepository.add_event(
                    db,
                    TimerEvent(
                        timer_id=timer.id,
                        event_type=TimerEventType.start,
                        triggered_by_id=current_user.id,
                        note=f"Iniciado via bateria '{heat.name}'",
                    ),
                )
                await TimerRepository.save(db, timer)
                started_count += 1

        if started_count == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nenhum timer disponível para iniciar nesta bateria",
            )

        heat.status = HeatStatus.running
        return await HeatRepository.save(db, heat)

    @staticmethod
    async def delete(db: AsyncSession, heat_id: int) -> None:
        """Remove bateria (desvincula timers).

        Args:
            db: Sessão assíncrona.
            heat_id: ID da bateria.
        """
        heat = await HeatService.get_or_404(db, heat_id)
        await HeatRepository.delete(db, heat)
