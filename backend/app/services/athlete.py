"""Serviço de atletas — CRUD e importação CSV."""

import csv
import io
import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete, TshirtSize
from app.models.category import Category
from app.models.team import Team
from app.repositories.athlete import AthleteRepository
from app.repositories.category import CategoryRepository
from app.repositories.team import TeamRepository
from app.schemas.athlete import (
    AthleteBulkError,
    AthleteBulkResult,
    AthleteCreate,
    AthleteUpdate,
)

logger = logging.getLogger(__name__)

_TSHIRT_SIZES = {s.value for s in TshirtSize}
_CSV_REQUIRED = {"nome"}


class AthleteService:
    """Lógica de negócio para atletas."""

    @staticmethod
    async def list_by_competition(
        db: AsyncSession,
        competition_id: int,
        category_id: int | None = None,
        team_id: int | None = None,
    ) -> list[Athlete]:
        """Lista atletas de uma competição com filtros opcionais.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            category_id: Filtro por categoria (opcional).
            team_id: Filtro por equipe (opcional).

        Returns:
            Lista de atletas.
        """
        return await AthleteRepository.list_by_competition(
            db, competition_id, category_id=category_id, team_id=team_id
        )

    @staticmethod
    async def get_or_404(db: AsyncSession, athlete_id: int) -> Athlete:
        """Busca atleta ou lança 404.

        Args:
            db: Sessão assíncrona.
            athlete_id: ID do atleta.

        Returns:
            Objeto Athlete.

        Raises:
            HTTPException 404: se não encontrado.
        """
        athlete = await AthleteRepository.get_by_id(db, athlete_id)
        if athlete is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Atleta não encontrado"
            )
        return athlete

    @staticmethod
    async def _resolve_team(
        db: AsyncSession,
        competition_id: int,
        *,
        athlete_name: str,
        team_id: int | None,
        team_name: str | None,
        category_id: int | None,
    ) -> int:
        """Resolve team_id: usa o informado, busca por nome ou cria um novo.

        Todo atleta pertence a uma equipe (mesmo que solo). Se `team_id` for informado,
        é usado diretamente. Caso contrário, tenta localizar uma equipe existente pelo
        nome; se não encontrar, cria uma equipe nova — o que exige `category_id`.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            athlete_name: Nome do atleta (usado para equipe solo).
            team_id: ID de equipe existente, se já escolhida explicitamente.
            team_name: Nome de equipe pra buscar/criar quando `team_id` não é informado.
            category_id: Categoria do atleta — obrigatória pra criar equipe nova.

        Returns:
            ID da equipe resolvida ou criada.

        Raises:
            HTTPException 404: `team_id` informado não existe na competição.
            HTTPException 422: Nenhuma equipe pôde ser resolvida (sem team_id, sem nome
                de equipe existente e sem categoria pra criar uma nova).
        """
        if team_id is not None:
            team = await TeamRepository.get_by_id(db, team_id)
            if not team or team.competition_id != competition_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Equipe não encontrada nesta competição",
                )
            return team_id

        if team_name:
            existing = await TeamRepository.get_by_name_in_competition(
                db, competition_id, team_name
            )
            if existing:
                return existing.id
            if category_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Equipe '{team_name}' não pode ser criada sem categoria válida"
                    ),
                )
            category = await CategoryRepository.get_by_id(db, category_id)
            if not category or category.competition_id != competition_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Categoria não encontrada nesta competição",
                )
            new_team = Team(
                competition_id=competition_id, name=team_name, category_id=category_id
            )
            db.add(new_team)
            await db.flush()
            await db.refresh(new_team)
            return new_team.id

        # Sem team_id nem nome de equipe: cria equipe solo a partir da categoria
        if category_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Todo atleta precisa de uma equipe. Informe 'team_id' de "
                    "uma equipe existente ou 'category_id' para criar uma "
                    "equipe solo automaticamente."
                ),
            )
        category = await CategoryRepository.get_by_id(db, category_id)
        if not category or category.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria não encontrada nesta competição",
            )
        solo_team = Team(
            competition_id=competition_id,
            name=f"Equipe {athlete_name}",
            category_id=category_id,
        )
        db.add(solo_team)
        await db.flush()
        await db.refresh(solo_team)
        return solo_team.id

    @staticmethod
    async def create(
        db: AsyncSession, competition_id: int, data: AthleteCreate
    ) -> Athlete:
        """Cria um novo atleta, resolvendo (ou criando) a equipe à qual ele pertence.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição à qual o atleta pertence.
            data: Dados do atleta.

        Returns:
            Objeto Athlete criado, sempre com team_id preenchido.
        """
        team_id = await AthleteService._resolve_team(
            db,
            competition_id,
            athlete_name=data.name,
            team_id=data.team_id,
            team_name=None,
            category_id=data.category_id,
        )
        payload = data.model_dump()
        payload["team_id"] = team_id
        athlete = Athlete(competition_id=competition_id, **payload)
        return await AthleteRepository.create(db, athlete)

    @staticmethod
    async def update(
        db: AsyncSession, athlete: Athlete, data: AthleteUpdate
    ) -> Athlete:
        """Atualiza dados de um atleta, validando reatribuição de equipe.

        Args:
            db: Sessão assíncrona.
            athlete: Objeto Athlete a atualizar.
            data: Dados de atualização (parcial).

        Returns:
            Objeto Athlete atualizado.

        Raises:
            HTTPException 422: `team_id` informado explicitamente como nulo —
                todo atleta precisa pertencer a uma equipe.
            HTTPException 404: `team_id` informado não pertence à mesma competição.
        """
        updates = data.model_dump(exclude_unset=True)
        if "team_id" in updates and updates["team_id"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="team_id não pode ser nulo — todo atleta pertence a uma equipe",
            )
        if "team_id" in updates and updates["team_id"] is not None:
            team = await TeamRepository.get_by_id(db, updates["team_id"])
            if not team or team.competition_id != athlete.competition_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Equipe não encontrada nesta competição",
                )
        for field, value in updates.items():
            setattr(athlete, field, value)
        return await AthleteRepository.update(db, athlete)

    @staticmethod
    async def delete(db: AsyncSession, athlete: Athlete) -> None:
        """Remove um atleta.

        Args:
            db: Sessão assíncrona.
            athlete: Objeto Athlete a remover.
        """
        await AthleteRepository.delete(db, athlete)

    @staticmethod
    async def import_csv(
        db: AsyncSession,
        competition_id: int,
        content: bytes,
        categories: list[Category],
    ) -> AthleteBulkResult:
        """Importa atletas de um arquivo CSV.

        Colunas (separador ponto-e-vírgula):
            nome;categoria;equipe;email;documento;telefone;tamanho_camiseta

        Apenas 'nome' é obrigatório. Se 'equipe' for informada e a equipe não existir,
        ela será criada automaticamente usando a mesma categoria do atleta.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            content: Conteúdo do CSV em bytes.
            categories: Categorias da competição para resolução de nomes.

        Returns:
            AthleteBulkResult com contagens e erros por linha.
        """
        category_by_name = {c.name.lower(): c for c in categories}

        created_count = 0
        errors: list[AthleteBulkError] = []

        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        for row_num, row in enumerate(reader, start=1):
            name = (row.get("nome") or "").strip()
            if not name:
                errors.append(
                    AthleteBulkError(
                        row=row_num, name="", error="Campo 'nome' obrigatório"
                    )
                )
                continue

            cat_name = (row.get("categoria") or "").strip().lower()
            category = category_by_name.get(cat_name) if cat_name else None
            category_id = category.id if category else None

            raw_size = (row.get("tamanho_camiseta") or "").strip().upper()
            tshirt_size = TshirtSize(raw_size) if raw_size in _TSHIRT_SIZES else None

            team_name = (row.get("equipe") or "").strip() or None

            try:
                resolved_team_id = await AthleteService._resolve_team(
                    db,
                    competition_id,
                    athlete_name=name,
                    team_id=None,
                    team_name=team_name,
                    category_id=category_id,
                )
            except HTTPException as exc:
                errors.append(
                    AthleteBulkError(row=row_num, name=name, error=str(exc.detail))
                )
                continue

            athlete = Athlete(
                competition_id=competition_id,
                name=name,
                email=(row.get("email") or "").strip() or None,
                document=(row.get("documento") or "").strip() or None,
                phone=(row.get("telefone") or "").strip() or None,
                category_id=category_id,
                tshirt_size=tshirt_size,
                team_id=resolved_team_id,
            )
            db.add(athlete)
            created_count += 1

        if created_count:
            await db.flush()

        return AthleteBulkResult(created=created_count, errors=errors)
