"""Serviço de importação em lote de usuários e equipes via CSV."""

import csv
import io
import logging
import secrets

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.team import Team, TeamMember
from app.models.user import User, UserRole
from app.repositories.category import CategoryRepository
from app.repositories.competition import CompetitionRepository
from app.repositories.team import TeamRepository
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)

# Roles válidos para importação
_VALID_ROLES = {r.value for r in UserRole}


# ── Schemas de resposta ────────────────────────────────────────────────────────


class BulkError(BaseModel):
    """Detalhe de erro em uma linha do CSV."""

    row: int
    identifier: str
    reason: str


class BulkImportResult(BaseModel):
    """Resultado da importação em lote."""

    created_count: int
    errors: list[BulkError]


# ── Serviço ────────────────────────────────────────────────────────────────────


class BulkService:
    """Importação em lote de usuários e equipes via CSV."""

    @staticmethod
    async def import_users(csv_content: str, db: AsyncSession) -> BulkImportResult:
        """Importa usuários em lote a partir de conteúdo CSV.

        Formato esperado: nome_completo;email;perfil (separado por ponto-e-vírgula).
        O cabeçalho é ignorado se a primeira coluna for 'nome_completo' (case-insensitive).

        Args:
            csv_content: Conteúdo do arquivo CSV decodificado como string.
            db: Sessão assíncrona.

        Returns:
            BulkImportResult com contagem de criados e lista de erros por linha.
        """
        errors: list[BulkError] = []
        created_count = 0
        reader = csv.reader(io.StringIO(csv_content.strip()), delimiter=";")
        rows = list(reader)

        for row_num, row in enumerate(rows, start=1):
            # Ignorar cabeçalho
            if row_num == 1 and row and row[0].strip().lower() in ("nome_completo", "nome", "name"):
                continue

            if not row or all(c.strip() == "" for c in row):
                continue

            if len(row) < 3:
                errors.append(
                    BulkError(
                        row=row_num,
                        identifier=row[0].strip() if row else "",
                        reason="Linha incompleta — esperado: nome_completo;email;perfil",
                    )
                )
                continue

            full_name = row[0].strip()
            email = row[1].strip().lower()
            role_str = row[2].strip().lower()

            if not full_name:
                errors.append(BulkError(row=row_num, identifier=email, reason="Nome completo ausente"))
                continue

            if not email:
                errors.append(BulkError(row=row_num, identifier="", reason="E-mail ausente"))
                continue

            if role_str not in _VALID_ROLES:
                errors.append(
                    BulkError(
                        row=row_num,
                        identifier=email,
                        reason=f"Perfil inválido '{role_str}'. Valores aceitos: {', '.join(sorted(_VALID_ROLES))}",
                    )
                )
                continue

            existing = await UserRepository.get_by_email(db, email)
            if existing:
                errors.append(
                    BulkError(row=row_num, identifier=email, reason="E-mail já cadastrado")
                )
                continue

            temp_password = secrets.token_urlsafe(9)
            user = User(
                full_name=full_name,
                email=email,
                hashed_password=hash_password(temp_password),
                role=UserRole(role_str),
            )
            db.add(user)
            try:
                await db.flush()
                await db.refresh(user)
                created_count += 1
                logger.info("Usuário importado em lote: email=%s role=%s", email, role_str)
            except Exception as exc:
                await db.rollback()
                errors.append(
                    BulkError(row=row_num, identifier=email, reason=f"Erro ao salvar: {exc}")
                )

        return BulkImportResult(created_count=created_count, errors=errors)

    @staticmethod
    async def import_teams(csv_content: str, db: AsyncSession) -> BulkImportResult:
        """Importa equipes em lote a partir de conteúdo CSV.

        Formato novo: id_competicao;categoria_equipe;nome_equipe;box_name;email1;email2;...
        Formato legado: id_competicao;categoria_equipe;nome_equipe;email1;email2;...

        O formato é detectado automaticamente: se a coluna de índice 3 contiver '@',
        é tratada como e-mail (formato legado, sem box_name). Caso contrário, é tratada
        como box_name (pode ser vazia) e os e-mails começam a partir do índice 4.

        O número de e-mails de competidores deve ser igual a category.max_team_size.

        Args:
            csv_content: Conteúdo do arquivo CSV decodificado como string.
            db: Sessão assíncrona.

        Returns:
            BulkImportResult com contagem de equipes criadas e lista de erros.
        """
        errors: list[BulkError] = []
        created_count = 0
        reader = csv.reader(io.StringIO(csv_content.strip()), delimiter=";")
        rows = list(reader)

        for row_num, row in enumerate(rows, start=1):
            # Ignorar cabeçalho
            if row_num == 1 and row and row[0].strip().lower() in ("id_competicao", "competition_id"):
                continue

            if not row or all(c.strip() == "" for c in row):
                continue

            if len(row) < 4:
                errors.append(
                    BulkError(
                        row=row_num,
                        identifier=row[2].strip() if len(row) > 2 else "",
                        reason="Linha incompleta — esperado: id_competicao;categoria_equipe;nome_equipe;box_name;email1;...",
                    )
                )
                continue

            competition_id_str = row[0].strip()
            category_name = row[1].strip()
            team_name = row[2].strip()

            # Detecção automática de formato: coluna 3 com '@' → formato legado (sem box_name)
            if "@" in row[3]:
                box_name: str | None = None
                email_columns = [e.strip().lower() for e in row[3:] if e.strip()]
            else:
                box_name = row[3].strip() or None
                email_columns = [e.strip().lower() for e in row[4:] if e.strip()]

            # 1. Valida ID de competição
            try:
                competition_id = int(competition_id_str)
            except ValueError:
                errors.append(
                    BulkError(
                        row=row_num,
                        identifier=team_name,
                        reason=f"ID de competição inválido: '{competition_id_str}'",
                    )
                )
                continue

            # 2. Verifica se competição existe
            competition = await CompetitionRepository.get_by_id(db, competition_id)
            if competition is None:
                errors.append(
                    BulkError(
                        row=row_num,
                        identifier=team_name,
                        reason=f"Competição com ID {competition_id} não encontrada",
                    )
                )
                continue

            # 3. Verifica se categoria existe na competição
            categories = await CategoryRepository.get_by_competition(db, competition_id)
            category = next(
                (c for c in categories if c.name.lower() == category_name.lower()), None
            )
            if category is None:
                errors.append(
                    BulkError(
                        row=row_num,
                        identifier=team_name,
                        reason=f"Categoria '{category_name}' não encontrada na competição {competition_id}",
                    )
                )
                continue

            # 4. Valida quantidade de competidores vs max_team_size
            if category.max_team_size is not None and len(email_columns) != category.max_team_size:
                errors.append(
                    BulkError(
                        row=row_num,
                        identifier=team_name,
                        reason=(
                            f"Quantidade de competidores ({len(email_columns)}) não corresponde ao "
                            f"tamanho da categoria '{category.name}' ({category.max_team_size})"
                        ),
                    )
                )
                continue

            # 5. Verifica unicidade do nome da equipe na competição
            existing_team = await TeamRepository.get_by_name_in_competition(
                db, competition_id, team_name
            )
            if existing_team is not None:
                errors.append(
                    BulkError(
                        row=row_num,
                        identifier=team_name,
                        reason=f"Nome de equipe '{team_name}' já existe nesta competição",
                    )
                )
                continue

            # 6. Valida e-mails dos competidores
            member_users: list[User] = []
            row_has_error = False
            for email in email_columns:
                user = await UserRepository.get_by_email(db, email)
                if user is None:
                    errors.append(
                        BulkError(
                            row=row_num,
                            identifier=team_name,
                            reason=f"Usuário não encontrado: '{email}'",
                        )
                    )
                    row_has_error = True
                    break
                member_users.append(user)

            if row_has_error:
                continue

            # 7. Cria equipe e membros
            team = Team(
                competition_id=competition_id,
                category_id=category.id,
                name=team_name,
                box_name=box_name,
                captain_id=member_users[0].id if member_users else None,
            )
            db.add(team)
            try:
                await db.flush()
                await db.refresh(team)
            except Exception as exc:
                await db.rollback()
                errors.append(
                    BulkError(row=row_num, identifier=team_name, reason=f"Erro ao criar equipe: {exc}")
                )
                continue

            member_error = False
            for member_user in member_users:
                team_member = TeamMember(team_id=team.id, user_id=member_user.id)
                db.add(team_member)
                try:
                    await db.flush()
                except Exception as exc:
                    await db.rollback()
                    errors.append(
                        BulkError(
                            row=row_num,
                            identifier=team_name,
                            reason=f"Erro ao adicionar membro '{member_user.email}': {exc}",
                        )
                    )
                    member_error = True
                    break

            if not member_error:
                created_count += 1
                logger.info(
                    "Equipe importada em lote: name=%s competition_id=%s",
                    team_name,
                    competition_id,
                )

        return BulkImportResult(created_count=created_count, errors=errors)
