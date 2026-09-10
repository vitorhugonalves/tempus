"""Serviço de check-in — unifica Athlete (import em massa) e CompetitorRegistration
(auto-inscrição online) num único ponto de busca e garante que a pessoa tenha um
registro Athlete antes do credenciamento físico (pareamento de tag RFID)."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.repositories.athlete import AthleteRepository
from app.repositories.competitor_registration import CompetitorRegistrationRepository
from app.repositories.team import TeamRepository
from app.schemas.checkin import CheckinCandidate, CheckinEnsureRequest


class CheckinService:
    """Regras de negócio para o check-in presencial de atletas."""

    @staticmethod
    async def search(
        db: AsyncSession, competition_id: int, query: str
    ) -> list[CheckinCandidate]:
        """Busca candidatos ao check-in cruzando Athlete e CompetitorRegistration.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            query: Termo de busca (nome ou e-mail).

        Returns:
            Lista de CheckinCandidate — atletas já existentes e inscrições online
            sem Athlete correspondente ainda.
        """
        athletes = await AthleteRepository.list_by_competition(db, competition_id)
        matched_athletes = [
            a
            for a in athletes
            if query.lower() in a.name.lower()
            or (a.email and query.lower() in a.email.lower())
        ]
        linked_user_ids = {a.user_id for a in athletes if a.user_id is not None}

        registrations = await CompetitorRegistrationRepository.search(
            db, competition_id, query
        )

        candidates = [
            CheckinCandidate(
                kind="athlete",
                source_id=a.id,
                name=a.name,
                email=a.email,
                team_name=a.team.name if a.team else None,
                has_athlete_record=True,
            )
            for a in matched_athletes
        ]
        for reg in registrations:
            if reg.user_id in linked_user_ids:
                continue  # já tem Athlete vinculado — evita duplicar na lista
            candidates.append(
                CheckinCandidate(
                    kind="registration",
                    source_id=reg.id,
                    name=reg.user.full_name,
                    email=reg.user.email,
                    team_name=None,
                    has_athlete_record=False,
                )
            )
        return candidates

    @staticmethod
    async def ensure_athlete(
        db: AsyncSession, competition_id: int, data: CheckinEnsureRequest
    ) -> Athlete:
        """Garante que existe um Athlete para o candidato — cria se necessário.

        Idempotente: se o CompetitorRegistration já tiver um Athlete vinculado
        (mesmo user_id na competição), retorna o existente em vez de duplicar.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            data: kind ("athlete" ou "registration") + source_id.

        Returns:
            Athlete garantido (existente ou recém-criado).

        Raises:
            HTTPException 404: fonte não encontrada nesta competição.
            HTTPException 422: inscrição sem equipe (não deveria acontecer, dado que
                toda auto-inscrição cria equipe — guarda defensiva).
        """
        if data.kind == "athlete":
            athlete = await AthleteRepository.get_by_id(db, data.source_id)
            if not athlete or athlete.competition_id != competition_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Atleta não encontrado",
                )
            return athlete

        registration = await CompetitorRegistrationRepository.get_by_id(
            db, data.source_id
        )
        if not registration or registration.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inscrição não encontrada"
            )

        existing = await AthleteRepository.list_by_competition(db, competition_id)
        already = next((a for a in existing if a.user_id == registration.user_id), None)
        if already:
            return already

        team_member = await TeamRepository.get_member_in_competition(
            db, competition_id, registration.user_id
        )
        if not team_member:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Inscrição sem equipe vinculada — não é possível criar o atleta",
            )

        new_athlete = Athlete(
            competition_id=competition_id,
            category_id=registration.category_id,
            team_id=team_member.team_id,
            user_id=registration.user_id,
            name=registration.user.full_name,
            email=registration.user.email,
            document=registration.document,
        )
        return await AthleteRepository.create(db, new_athlete)
