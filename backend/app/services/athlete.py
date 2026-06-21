"""Serviço de atletas — CRUD e importação CSV."""
import csv
import io
import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete, TshirtSize
from app.models.category import Category
from app.repositories.athlete import AthleteRepository
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
    async def create(db: AsyncSession, competition_id: int, data: AthleteCreate) -> Athlete:
        """Cria um novo atleta.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição à qual o atleta pertence.
            data: Dados do atleta.

        Returns:
            Objeto Athlete criado.
        """
        athlete = Athlete(competition_id=competition_id, **data.model_dump())
        return await AthleteRepository.create(db, athlete)

    @staticmethod
    async def update(db: AsyncSession, athlete: Athlete, data: AthleteUpdate) -> Athlete:
        """Atualiza dados de um atleta.

        Args:
            db: Sessão assíncrona.
            athlete: Objeto Athlete a atualizar.
            data: Dados de atualização (parcial).

        Returns:
            Objeto Athlete atualizado.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
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
        db: AsyncSession, competition_id: int, content: bytes, categories: list[Category]
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
        from app.models.team import Team
        from app.repositories.team import TeamRepository

        category_by_name = {c.name.lower(): c for c in categories}

        existing_teams = await TeamRepository.get_by_competition(db, competition_id)
        teams_by_name: dict[str, Team] = {t.name.lower(): t for t in existing_teams}

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
                    AthleteBulkError(row=row_num, name="", error="Campo 'nome' obrigatório")
                )
                continue

            cat_name = (row.get("categoria") or "").strip().lower()
            category = category_by_name.get(cat_name) if cat_name else None
            category_id = category.id if category else None

            raw_size = (row.get("tamanho_camiseta") or "").strip().upper()
            tshirt_size = TshirtSize(raw_size) if raw_size in _TSHIRT_SIZES else None

            team_name = (row.get("equipe") or "").strip()
            team_id: int | None = None
            if team_name:
                team_key = team_name.lower()
                if team_key in teams_by_name:
                    team_id = teams_by_name[team_key].id
                elif category_id is None:
                    errors.append(
                        AthleteBulkError(
                            row=row_num,
                            name=name,
                            error=f"Equipe '{team_name}' não pode ser criada sem categoria válida",
                        )
                    )
                else:
                    new_team = Team(
                        competition_id=competition_id,
                        name=team_name,
                        category_id=category_id,
                    )
                    db.add(new_team)
                    await db.flush()
                    await db.refresh(new_team)
                    teams_by_name[team_key] = new_team
                    team_id = new_team.id

            athlete = Athlete(
                competition_id=competition_id,
                name=name,
                email=(row.get("email") or "").strip() or None,
                document=(row.get("documento") or "").strip() or None,
                phone=(row.get("telefone") or "").strip() or None,
                category_id=category_id,
                tshirt_size=tshirt_size,
                team_id=team_id,
            )
            db.add(athlete)
            created_count += 1

        if created_count:
            await db.flush()

        return AthleteBulkResult(created=created_count, errors=errors)
