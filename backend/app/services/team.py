"""Serviço de equipes."""

import csv
import io

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.competitor import CompetitorRegistration
from app.models.team import Team, TeamMember
from app.repositories.competition import CompetitionRepository
from app.repositories.team import TeamRepository
from app.repositories.user import UserRepository
from app.schemas.team import TeamCreate, TeamMemberAdd, TeamUpdate


class TeamService:
    """Regras de negócio para equipes (RF-23 a RF-25)."""

    @staticmethod
    async def get_or_404(db: AsyncSession, team_id: int) -> Team:
        """Retorna equipe ou lança 404.

        Args:
            db: Sessão assíncrona.
            team_id: ID da equipe.

        Returns:
            Team.

        Raises:
            HTTPException 404.
        """
        team = await TeamRepository.get_by_id(db, team_id)
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Equipe não encontrada"
            )
        return team

    @staticmethod
    async def list_by_competition(db: AsyncSession, competition_id: int) -> list[Team]:
        """Lista equipes da competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            Lista de Team.
        """
        return await TeamRepository.get_by_competition(db, competition_id)

    @staticmethod
    async def create(db: AsyncSession, competition_id: int, data: TeamCreate) -> Team:
        """Cria equipe em uma competição (RF-23).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            data: Dados validados.

        Returns:
            Team criada.

        Raises:
            HTTPException 404: Competição não encontrada.
        """
        competition = await CompetitionRepository.get_by_id(db, competition_id)
        if not competition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
            )
        team = Team(competition_id=competition_id, **data.model_dump())
        return await TeamRepository.create(db, team)

    @staticmethod
    async def update(db: AsyncSession, team_id: int, data: TeamUpdate) -> Team:
        """Atualiza dados de uma equipe.

        Args:
            db: Sessão assíncrona.
            team_id: ID da equipe.
            data: Campos a atualizar.

        Returns:
            Team atualizada.
        """
        team = await TeamService.get_or_404(db, team_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(team, field, value)
        return await TeamRepository.save(db, team)

    @staticmethod
    async def delete(db: AsyncSession, team_id: int) -> None:
        """Remove equipe e cancela as inscrições de todos os seus membros.

        Para cada membro da equipe, apaga o registro em `CompetitorRegistration`
        para a competição desta equipe, cancelando a inscrição do competidor.

        Args:
            db: Sessão assíncrona.
            team_id: ID da equipe.
        """
        team = await TeamService.get_or_404(db, team_id)

        # Cancela inscrições de todos os membros nesta competição
        member_ids = [m.user_id for m in team.members]
        if member_ids:
            regs = await db.execute(
                select(CompetitorRegistration).where(
                    CompetitorRegistration.user_id.in_(member_ids),
                    CompetitorRegistration.competition_id == team.competition_id,
                )
            )
            for reg in regs.scalars().all():
                await db.delete(reg)
            await db.flush()

        await TeamRepository.delete(db, team)

    @staticmethod
    async def add_member(
        db: AsyncSession, team_id: int, data: TeamMemberAdd
    ) -> TeamMember:
        """Adiciona membro à equipe (RF-25).

        Args:
            db: Sessão assíncrona.
            team_id: ID da equipe.
            data: user_id a adicionar.

        Returns:
            TeamMember criado.

        Raises:
            HTTPException 404: Equipe ou usuário não encontrado.
            HTTPException 409: Membro já pertence à equipe.
        """
        team = await TeamService.get_or_404(db, team_id)
        user = await UserRepository.get_by_id(db, data.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado"
            )
        existing = await TeamRepository.get_member(db, team_id, data.user_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Usuário já é membro desta equipe",
            )
        # RN-17: um competidor não pode estar em mais de uma equipe na mesma competição
        existing_in_competition = await TeamRepository.get_member_in_competition(
            db, team.competition_id, data.user_id
        )
        if existing_in_competition:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Usuário já pertence a uma equipe nesta competição",
            )
        # Validação de capacidade: respeita max_team_size da categoria
        category_result = await db.execute(
            select(Category).where(Category.id == team.category_id)
        )
        category = category_result.scalar_one_or_none()
        if category and category.max_team_size is not None:
            if len(team.members) >= category.max_team_size:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"A equipe já atingiu o limite de {category.max_team_size} "
                        f"membro(s) para a categoria '{category.name}'"
                    ),
                )
        member = TeamMember(team_id=team_id, user_id=data.user_id)
        return await TeamRepository.add_member(db, member)

    @staticmethod
    async def remove_member(db: AsyncSession, team_id: int, user_id: int) -> None:
        """Remove membro da equipe.

        Args:
            db: Sessão assíncrona.
            team_id: ID da equipe.
            user_id: ID do usuário a remover.

        Raises:
            HTTPException 404: Membro não encontrado.
        """
        member = await TeamRepository.get_member(db, team_id, user_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Membro não encontrado nesta equipe",
            )
        await TeamRepository.remove_member(db, member)

    @staticmethod
    async def import_csv(
        db: AsyncSession,
        competition_id: int,
        content: bytes,
        categories: list[Category],
    ) -> "TeamBulkResult":
        """Importa equipes de um arquivo CSV.

        Colunas (separador ponto-e-vírgula):
            nome_equipe;categoria

        Equipes com nome já existente na competição são puladas silenciosamente.
        Linhas com categoria inválida geram erro e não são criadas.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            content: Conteúdo do CSV em bytes.
            categories: Categorias da competição para resolução de nomes.

        Returns:
            TeamBulkResult com contagem de criadas e erros por linha.
        """
        from app.schemas.team import TeamBulkError, TeamBulkResult

        category_by_name = {c.name.lower(): c for c in categories}
        existing = await TeamRepository.get_by_competition(db, competition_id)
        existing_names = {t.name.lower() for t in existing}

        created_count = 0
        errors: list[TeamBulkError] = []

        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        for row_num, row in enumerate(reader, start=1):
            name = (row.get("nome_equipe") or "").strip()
            if not name:
                errors.append(
                    TeamBulkError(row=row_num, name="", error="Campo 'nome_equipe' obrigatório")
                )
                continue

            if name.lower() in existing_names:
                continue

            cat_name = (row.get("categoria") or "").strip().lower()
            category = category_by_name.get(cat_name)
            if not category:
                errors.append(
                    TeamBulkError(
                        row=row_num,
                        name=name,
                        error=f"Categoria '{cat_name}' não encontrada na competição",
                    )
                )
                continue

            team = Team(
                competition_id=competition_id,
                name=name,
                category_id=category.id,
            )
            db.add(team)
            existing_names.add(name.lower())
            created_count += 1

        if created_count:
            await db.flush()

        return TeamBulkResult(created=created_count, errors=errors)
