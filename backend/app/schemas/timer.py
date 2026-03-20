from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.timer import TimerEventType, TimerStatus


class TimerCreate(BaseModel):
    competition_id: int
    category_id: int | None = None
    user_id: int | None = None
    team_id: int | None = None

    @model_validator(mode="after")
    def validate_subject(self) -> "TimerCreate":
        if self.user_id is None and self.team_id is None:
            raise ValueError("Informe user_id (individual) ou team_id (equipe)")
        if self.user_id is not None and self.team_id is not None:
            raise ValueError("Informe apenas user_id ou team_id, não ambos")
        return self


class TimerActionRequest(BaseModel):
    note: str | None = Field(None, max_length=500)


class PenaltyTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    kind: str = Field("time_increment", pattern="^(time_increment|mandatory_stop)$")
    seconds: int = Field(0, ge=0)
    description: str | None = None


class PenaltyTypeResponse(BaseModel):
    id: int
    competition_id: int
    name: str
    kind: str
    seconds: int
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PenaltyApply(BaseModel):
    penalty_type_id: int
    justification: str = Field(..., min_length=1, max_length=1000)


class PenaltyResponse(BaseModel):
    id: int
    timer_id: int
    penalty_type_id: int
    penalty_type_name: str
    applied_by_id: int | None
    justification: str
    seconds_added: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_type(cls, penalty: object) -> "PenaltyResponse":
        return cls(
            id=penalty.id,  # type: ignore[attr-defined]
            timer_id=penalty.timer_id,  # type: ignore[attr-defined]
            penalty_type_id=penalty.penalty_type_id,  # type: ignore[attr-defined]
            penalty_type_name=penalty.penalty_type.name,  # type: ignore[attr-defined]
            applied_by_id=penalty.applied_by_id,  # type: ignore[attr-defined]
            justification=penalty.justification,  # type: ignore[attr-defined]
            seconds_added=penalty.seconds_added,  # type: ignore[attr-defined]
            created_at=penalty.created_at,  # type: ignore[attr-defined]
        )


class TimerEventResponse(BaseModel):
    id: int
    timer_id: int
    event_type: TimerEventType
    event_at: datetime
    accumulated_ms: int
    triggered_by_id: int | None
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OfficialResultResponse(BaseModel):
    id: int
    timer_id: int
    final_time_ms: int
    finished_by_user_id: int | None
    finished_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class TimerResponse(BaseModel):
    id: int
    competition_id: int
    category_id: int | None
    user_id: int | None
    team_id: int | None
    heat_id: int | None
    status: TimerStatus
    accumulated_ms: int
    # started_at_ms: epoch ms de quando o segmento atual de execução iniciou.
    # Presente apenas quando status=running (necessário para o contador ao vivo no frontend).
    started_at_ms: int | None = None
    # elapsed_seconds é calculado a partir de accumulated_ms para compatibilidade
    elapsed_seconds: int
    total_penalty_seconds: int
    final_seconds: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, timer: object, redis_state: dict | None = None) -> "TimerResponse":
        """Constrói resposta calculando tempo acumulado.

        Para timers `running`, usa o estado Redis (sub-segundo de precisão).
        Fallback para cálculo por eventos quando Redis não disponível.

        Args:
            timer: Instância ORM Timer com events e penalties carregados.
            redis_state: Estado Redis do timer (opcional). Chaves esperadas:
                ``accumulated_ms`` e ``started_at_ms`` quando em execução.
        """
        t = timer  # type: ignore[assignment]

        if redis_state and t.status == TimerStatus.running:
            # Retorna o baseline e o anchor separados — o frontend calcula o tempo
            # vivo com: accumulated_ms + (Date.now() - started_at_ms).
            # NÃO pré-computar o elapsed aqui, pois isso causaria double-counting:
            # o frontend somaria (T_agora - T_start) sobre um valor que já inclui
            # (T_resposta - T_start), inflando o display progressivamente.
            accumulated_ms = redis_state["accumulated_ms"]
            started_at_ms: int | None = redis_state.get("started_at_ms")
        else:
            accumulated_ms = _compute_accumulated_ms(t)
            started_at_ms = None

        elapsed_seconds = accumulated_ms // 1000
        penalty_seconds = sum(p.seconds_added for p in t.penalties)

        return cls(
            id=t.id,
            competition_id=t.competition_id,
            category_id=t.category_id,
            user_id=t.user_id,
            team_id=t.team_id,
            heat_id=t.heat_id,
            status=t.status,
            accumulated_ms=accumulated_ms,
            started_at_ms=started_at_ms,
            elapsed_seconds=elapsed_seconds,
            total_penalty_seconds=penalty_seconds,
            final_seconds=elapsed_seconds + penalty_seconds,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )


class RankingEntry(BaseModel):
    position: int
    timer_id: int
    user_id: int | None
    team_id: int | None
    athlete_name: str
    team_name: str | None
    category_name: str | None
    accumulated_ms: int
    elapsed_seconds: int
    total_penalty_seconds: int
    final_seconds: int
    infractions_count: int
    remaining_seconds: int | None
    status: TimerStatus


# ---------------------------------------------------------------------------
# Helpers: cálculo de tempo acumulado (Redis e DB-events)
# ---------------------------------------------------------------------------


def _compute_accumulated_ms_from_redis(redis_state: dict) -> int:
    """Calcula tempo acumulado atual a partir do estado Redis de um timer running.

    Args:
        redis_state: Dict com ``accumulated_ms`` (baseline) e ``started_at_ms``
            (epoch ms de quando o segmento de execução começou).

    Returns:
        Tempo acumulado total em milissegundos.
    """
    import time

    now_ms = int(time.time() * 1000)
    return redis_state["accumulated_ms"] + (now_ms - redis_state["started_at_ms"])


def _compute_accumulated_ms(timer: object) -> int:
    """Calcula o tempo acumulado em ms a partir do histórico de eventos.

    Estratégia (DB-based, pré-Redis):
    - Percorre eventos em ordem cronológica reversa.
    - Para `paused`, `finished`, `reset`, `cancelled`: retorna accumulated_ms gravado.
    - Para `started`, `resumed`: timer está rodando — calcula elapsed desde event_at.
    - Sem eventos relevantes (created/ready): retorna 0.

    Em Etapa 3, para timers `running`, esta função será substituída por leitura
    direta do Redis (sem hit no banco), mas o resultado será idêntico.

    Args:
        timer: Instância ORM Timer com events carregados.

    Returns:
        Tempo acumulado em milissegundos.
    """
    from datetime import timezone

    from app.models.timer import TimerEventType as ET

    events = sorted(timer.events, key=lambda e: e.id)  # type: ignore[attr-defined]

    for event in reversed(events):
        if event.event_type in (ET.paused, ET.finished, ET.reset, ET.cancelled, ET.adjusted):
            return event.accumulated_ms
        if event.event_type in (ET.started, ET.resumed):
            # Timer está rodando desde este evento — adiciona tempo decorrido
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            event_at = (
                event.event_at.replace(tzinfo=None)
                if event.event_at.tzinfo
                else event.event_at
            )
            elapsed_since_ms = int((now - event_at).total_seconds() * 1000)
            return event.accumulated_ms + elapsed_since_ms

    return 0  # created / ready — nunca iniciado


# Importação local para evitar circular no módulo de schemas
from datetime import datetime  # noqa: E402 (reexported for _compute_accumulated_ms)
