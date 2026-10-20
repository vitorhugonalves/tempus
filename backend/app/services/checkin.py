"""Serviço de check-in — unifica Athlete (import em massa) e CompetitorRegistration
(auto-inscrição online) num único ponto de busca e garante que a pessoa tenha um
registro Athlete antes do credenciamento físico (pareamento de tag RFID)."""

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.repositories.athlete import AthleteRepository
from app.repositories.competitor_registration import CompetitorRegistrationRepository
from app.repositories.team import TeamRepository
from app.schemas.checkin import CheckinCandidate, CheckinEnsureRequest

_MAX_ATHLETE_DOCUMENT_LENGTH = 20
_MAX_ATHLETE_EMAIL_LENGTH = 200


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
        athletes_by_email = {a.email.lower(): a for a in athletes if a.email}

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
            if reg.user.email.lower() in athletes_by_email:
                continue  # mesma pessoa já tem Athlete com este e-mail — evita duplicar
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

        # Capturado antes de qualquer flush/rollback: após um rollback (corrida
        # de duplo-clique, abaixo) o objeto `registration` fica expirado e um
        # acesso a `.user_id` dispararia um reload síncrono inválido em sessão
        # assíncrona.
        registration_user_id = registration.user_id

        existing = await AthleteRepository.list_by_competition(db, competition_id)
        already = next((a for a in existing if a.user_id == registration_user_id), None)
        if already:
            return already

        # Mesma pessoa pode já existir como Athlete importado em massa (mesmo
        # e-mail, sem user_id ainda) — vincula em vez de duplicar o cadastro.
        registration_email = registration.user.email.lower()
        matched_by_email = next(
            (a for a in existing if a.email and a.email.lower() == registration_email),
            None,
        )
        if matched_by_email:
            matched_by_email.user_id = registration_user_id
            return await AthleteRepository.update(db, matched_by_email)

        if (
            registration.document is not None
            and len(registration.document) > _MAX_ATHLETE_DOCUMENT_LENGTH
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Documento excede o tamanho máximo permitido para o "
                    "registro de atleta (20 caracteres)"
                ),
            )
        if len(registration.user.email) > _MAX_ATHLETE_EMAIL_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "E-mail excede o tamanho máximo permitido para o "
                    "registro de atleta (200 caracteres)"
                ),
            )

        team_member = await TeamRepository.get_member_in_competition(
            db, competition_id, registration_user_id
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
            user_id=registration_user_id,
            name=registration.user.full_name,
            email=registration.user.email,
            document=registration.document,
        )
        try:
            return await AthleteRepository.create(db, new_athlete)
        except IntegrityError:
            # Corrida de duplo-clique: outra requisição já criou o Athlete
            # para este user_id entre nossa checagem e o insert. Não é erro
            # do usuário — devolve o registro vencedor em vez de propagar 500.
            await db.rollback()
            existing_after = await AthleteRepository.list_by_competition(
                db, competition_id
            )
            winner = next(
                (a for a in existing_after if a.user_id == registration_user_id), None
            )
            if winner:
                return winner
            raise
