# Design: Cronometragem por Estações via RFID (Hyrox)

**Data:** 2026-09-08
**Status:** Aprovado — pronto para plano de implementação

---

## Escopo

Evoluir o cronômetro por atleta/equipe (`Timer`/`TimerEvent`, RF-26 a RF-31) para suportar
leitura automática de tags RFID em múltiplas estações, via um serviço gateway externo
(Raspberry Pi + leitor LLRP) que traduz leituras físicas em chamadas HTTP para uma nova
API de ingestão do Tempus. A captura manual (start/pause/resume/finish em `TimersPage`)
continua existindo como backup do juiz, e ganha uma capacidade que nunca existiu: correção
com horário customizado.

**Só se aplica a competições Hyrox com a feature habilitada** — nunca a CrossFit. Não
altera o fluxo de `WodResult`/leaderboard do CrossFit.

Este documento cobre apenas o lado Tempus (API receptora, modelo de dados, autenticação,
frontend). O software do gateway (Raspberry Pi/LLRP) é um projeto separado — a
especificação inicial dele está em
`docs/superpowers/specs/2026-09-08-rfid-gateway-service-prompt.md`.

---

## 1. Feature flag por competição

`Competition` ganha `rfid_enabled: bool` (default `False`).

Regra de negócio (`CompetitionService`): só pode ser `True` quando `event_type == EventType.hyrox`.
Tentar habilitar em uma competição CrossFit (ou sem `event_type` definido) retorna 422.
Desabilitar depois de já ter leituras registradas é permitido (não apaga histórico) — só
impede novas leituras via `/gateway/readings` e esconde a UI de estações/tags.

Toda a superfície nova (endpoints de estação, ingestão do gateway, telas de pareamento de
tag) checa essa flag antes de agir.

---

## 2. Atleta sempre pertence a uma equipe (mudança global)

Hoje `Athlete.team_id` é opcional. Passa a ser **obrigatório em todas as competições**,
inclusive CrossFit — atleta individual vira equipe de 1. `Team.category_id` continua
obrigatório, então criar uma equipe nova exige categoria conhecida (mesma regra que já
existe no import CSV: *"Equipe não pode ser criada sem categoria válida"* —
`services/athlete.py:171-178`).

### Mudanças

- `models/athlete.py`: `team_id` vira `nullable=False`.
- `schemas/athlete.py` (`AthleteCreate`): validação (`model_validator`, mesmo padrão de
  `TimerCreate.validate_subject`) exigindo `team_id` **ou** (`category_id` + criação
  implícita de equipe nova com o nome do atleta, se nenhum nome de equipe for informado).
- `services/athlete.py`: `AthleteService.create` ganha a mesma lógica de resolução de
  equipe que `import_csv` já tem (busca por nome, cria se não existir) — hoje só existe no
  caminho CSV, precisa também no create individual.
- **Migração de dados — requer auditoria antes de decidir a estratégia.** Atletas
  existentes com `team_id IS NULL` precisam de uma equipe solo criada por
  `downgrade`/`upgrade`. Se algum desses atletas também não tiver `category_id`, não há
  como criar a equipe (constraint `NOT NULL`) sem uma decisão de negócio (categoria
  "avulsos"? bloquear a migração e pedir correção manual antes?). **Não decidir isso no
  código sem antes rodar uma contagem em produção** (`SELECT count(*) FROM athletes WHERE
  team_id IS NULL AND category_id IS NULL`) — é alteração de dados existentes, não só de
  schema.

### Fora de escopo desta mudança

`Timer.user_id` continua existindo para o que já usa (não estamos depreciando o caminho de
timer individual por `User`). Só estamos garantindo que **toda linha de `Athlete`** tenha
equipe — o que é o sujeito relevante para RFID.

---

## 3. Unificação Athlete ↔ User (check-in no dia do evento)

Hoje existem dois caminhos independentes pra alguém entrar numa competição:

- **Import em massa** → `Athlete` (sem login), com `team_id`.
- **Auto-inscrição** → `User` + `CompetitorRegistration` + `Team` (via `TeamMember`), com login.

RFID pareia tag sempre em `Athlete` — inclusive para quem veio da auto-inscrição. O ponto
de unificação é o **check-in presencial**: o atleta chega no estande antes da bateria,
recebe a pulseira, e é aí que a tag vira `Athlete`.

### Mudanças

- `models/athlete.py`: novo campo `user_id: Mapped[int | None]` (FK `users.id`,
  `ondelete=SET NULL`, nullable, índice único junto com `competition_id`) — link opcional
  de volta ao usuário quando o atleta veio de auto-inscrição.
- Nova tela/fluxo de **check-in** (`app/services/checkin.py`, novo):
  - Busca por nome/documento/e-mail cruzando `Athlete` e `CompetitorRegistration` da
    competição.
  - Se encontrar um `CompetitorRegistration` sem `Athlete` correspondente: cria o
    `Athlete` reaproveitando `team_id` (via `TeamMember`), `category_id` e dados do
    `User`, setando `user_id`.
  - Se encontrar um `Athlete` já existente (import em massa): usa direto.
  - Se não encontrar nada (walk-in sem pré-cadastro): cria `Athlete` novo na hora,
    exigindo equipe (regra da seção 2).
  - Ao final, sempre existe um `Athlete` — aí sim entra o pareamento de tag (seção 5).

---

## 4. Estações e eventos de timer

### `models/station.py` (novo)

```python
class StationKind(str, enum.Enum):
    checkpoint = "checkpoint"
    finish = "finish"

class Station(Base):
    __tablename__ = "stations"
    id, competition_id (FK), name, kind (StationKind), sort_order
    created_at, updated_at
```

Sem "estação de largada" por enquanto — a largada continua via `Heat.start_all` /
`Heat.start_team` (já fazem exatamente "em massa" e "individual", RF-27). Se um pórtico de
largada for necessário no futuro, adiciona-se `StationKind.start` depois — YAGNI por ora.

### `models/timer.py`

- `TimerEvent` ganha `station_id` (FK `stations.id`, nullable) e `subject_athlete_id`
  (FK `athletes.id`, nullable) — necessário porque `Timer.team_id` é um cronômetro
  compartilhado, mas cada leitura de tag pertence a um atleta específico da equipe.
- Novos `TimerEventType`: `station_in`, `station_out`. (`split` permanece definido mas não
  usado — não há necessidade de reaproveitá-lo, os dois novos tipos são mais explícitos.)
- `finish`/`start`/`pause`/`resume`/`reset` ganham parâmetro opcional `event_at: datetime
  | None` (default: agora) — hoje todos usam `_utcnow()` fixo no momento da requisição;
  leituras do gateway chegam com atraso de rede e precisam registrar o instante real da
  leitura, não o instante em que a API processou o POST.

---

## 5. Pareamento de tag (pool reaproveitável)

### `models/rfid.py` (novo)

```python
class RfidTagAssignment(Base):
    __tablename__ = "rfid_tag_assignments"
    id, competition_id (FK), tag_code (str, indexed),
    athlete_id (FK athletes.id), assigned_at, released_at (nullable = ativo)
```

Mesma pulseira física é reatribuída entre atletas/eventos — por isso o vínculo é por
competição, não permanente no cadastro do atleta. `RfidTagService`:

- `assign(competition_id, tag_code, athlete_id)`: libera qualquer atribuição ativa
  anterior da mesma tag (mesma competição) e do mesmo atleta antes de criar a nova —
  1 tag ativa por atleta, 1 atleta ativo por tag, dentro da competição. Validado em
  serviço (não em constraint parcial de banco — suporte a índice único parcial é
  inconsistente entre SQLite/Postgres; ver Riscos).
- `release(assignment_id)`.

---

## 6. Ingestão de leituras (`StationEventService`)

`POST /gateway/readings` — autenticado por token de gateway (seção 8), não por sessão.

**Payload:** `{tag_code, station_id, direction: "in"|"out", read_at, read_id}`

`read_id` é um UUID gerado pelo gateway por leitura física (não por retry) — chave de
idempotência.

Pipeline, em ordem:

1. **Guarda de relógio** — rejeita (422) se `read_at` estiver fora de uma janela
   razoável em relação ao relógio do servidor (constante `CLOCK_SKEW_TOLERANCE_SECONDS`
   em `core/constants.py`) — não confia cegamente no relógio do dispositivo de campo.
2. **Idempotência** — já existe `TimerEvent` com esse `read_id` (armazenado em
   `payload_json`)? Retorna o evento existente, não duplica. Cobre retry de rede do
   gateway.
3. **Debounce** (~2s, constante nomeada) — mesma tag + estação + direção dentro da
   janela? Ignora. Cobre releituras físicas repetidas da mesma passagem.
4. **Resolve tag → atleta** via `RfidTagAssignment` ativa. Tag não pareada → 422
   explícito (não silencioso) — o operador usa a captura manual como já era o plano.
5. **Resolve atleta → timer** via `Athlete.team_id` → `Timer` da competição.
6. **Fechamento automático da estação anterior** — se o atleta tinha um `station_in`
   sem `station_out` correspondente em outra estação, sintetiza o `station_out` da
   estação anterior no mesmo `event_at` da nova leitura, antes de gravar a nova.
7. Grava o evento novo (`station_in`/`station_out`, com `subject_athlete_id`,
   `station_id`, `event_at` = `read_at` do payload).
8. **Se a estação é `kind=finish`**: qualquer leitura ali conta como cruzamento de
   chegada (não exige par in/out — é só uma linha de chegada, RN nova). Aciona a
   verificação de conclusão de equipe (seção 7).

Dedup/debounce/fechamento automático são **autoridade do servidor**, não do gateway — o
gateway pode (e deve) fazer seu próprio debounce por eficiência de rede, mas a Tempus API
não pode confiar num dispositivo de campo pra garantir consistência (RN de segurança:
nunca confiar em validação só do cliente).

---

## 7. Conclusão de equipe e atleta ausente

**Regra:** o `Timer` da equipe só finaliza (`TimerService.finish`) quando **todos os
atletas não-ausentes** da equipe tiverem cruzado a estação `finish`. O tempo oficial é o
instante do **último** atleta a cruzar (não o primeiro).

- Verificação roda a cada leitura na estação finish (passo 8 acima): busca
  `team.athletes`, filtra `absent_at IS NULL`, confere se cada um tem um evento na
  estação finish para este timer. Se sim → `TimerService.finish(event_at=<instante do
  último>)`.

### Atleta ausente

- `models/athlete.py`: `absent_at: datetime | None`, `absent_reason: str | None`.
- Não é um `TimerEvent` (pode ser marcado antes mesmo do timer existir — ausência é um
  fato de credenciamento, não um evento de cronometragem). Editável nos dois sentidos
  (marcar/desmarcar ausente), consistente com a regra de UI "todo item permite edição".
- Toda marcação de ausência é registrada em `AuditLog` (entidade já existente no projeto)
  — quem marcou, quando, por quê — já que afeta se uma equipe finaliza ou não.

---

## 8. Autenticação do gateway

### `models/gateway_token.py` (novo)

```python
class GatewayToken(Base):
    __tablename__ = "gateway_tokens"
    id, competition_id (FK), label, token_hash, created_by_id,
    revoked_at (nullable), last_used_at (nullable), created_at
```

Token gerado com `secrets.token_urlsafe(32)`, exibido **uma única vez** na criação, salvo
como hash SHA-256. **Diferente** de `InviteToken`/`PasswordResetToken` (que guardam o
token em texto puro) porque esses são de uso único e curta duração (72h); um
`GatewayToken` é credencial de máquina de longa duração e, se vazado, permite injetar
leituras falsas numa competição ao vivo — maior superfície de risco, hash é obrigatório.

`app/api/deps.py`: nova dependência `require_gateway_token(competition_id)` — lê
`Authorization: Bearer <token>`, hasheia, busca `GatewayToken` ativo daquela competição.
Totalmente separada de `get_current_user`/`require_roles` — o gateway não é um `User`, é
uma credencial de máquina; não faz sentido modelar como `UserRole` novo.

---

## 9. Correção manual do juiz

`TimerService.adjust()` (novo — hoje `TimerEventType.adjusted` existe no enum desde a v2
mas nenhum método de serviço o usa; `TimersPage.tsx:53` só tem o label, sem UI por trás).

`POST /timers/{id}/adjust` — roles `judge`/`operator`/`admin` (sessão normal, não token de
gateway). Payload: `{event_type, event_at (customizado), station_id (opcional),
subject_athlete_id (opcional, p/ equipes), note (obrigatório)}`.

Grava evento novo — nunca edita ou apaga histórico (mesmo princípio de imutabilidade de
`Penalty`/RN-03). Cobre dois casos do pedido original:
1. Corrigir uma leitura errada do pórtico.
2. Reconstituir uma leitura que o pórtico perdeu (inserir `station_in`/`station_out` com
   horário customizado retroativo).

---

## 10. Ranking e splits

`RankingEntry` ganha `splits: list[StationSplit]` (`station_id`, `station_name`,
`split_seconds`, `subject_athlete_name` quando aplicável) — computado percorrendo
`station_in`/`station_out` em ordem no `RankingService`, reaproveitando a query que já
carrega `Timer.events`.

"Estação atual" de um atleta (pra exibição ao vivo) = último `station_in` sem
`station_out` correspondente — mesma lógica do passo 6 da ingestão, exposta como leitura.

Nenhuma mudança no `RankingService.get_crossfit_ranking` — CrossFit nunca usa RFID.

---

## 11. Redis / WebSocket

Nenhuma mudança estrutural. `publish_timer_event` já propaga qualquer `event_type` pro
canal da competição (`competition_channel`); `station_in`/`station_out`/`adjusted` passam
a fluir pelo mesmo Pub/Sub que o frontend já assina em `websocket.py`.

---

## 12. Frontend

- **`StationsPage`** (nova) — CRUD de estações por competição, mesmo padrão visual de
  `HeatsPage`. Só visível quando `competition.rfid_enabled`.
- **Check-in / pareamento de tag** (nova tela) — busca de atleta/inscrito (seção 3),
  criação de `Athlete` on-the-fly quando necessário, campo de leitura/digitação de
  `tag_code`, botão parear/liberar. Pensada pro fluxo "atleta chega no estande antes da
  bateria".
- **Gerência de gateway tokens** (nova, em configurações da competição) — criar (mostra
  segredo uma vez), revogar, ver `last_used_at`.
- **`TimersPage`** — badge de "estação atual" por atleta da equipe + splits expansíveis
  por cronômetro (reusa WebSocket existente, sem nova conexão).
- **Modal "Corrigir leitura"** (novo, a peça que hoje é só um label morto) — tipo de
  evento, estação, atleta (se equipe), horário customizado, motivo obrigatório.
- **Marcar atleta ausente** — toggle na tela de equipe/check-in, com campo de motivo.
- **Feature flag** — toggle `rfid_enabled` na edição da competição, desabilitado/oculto
  quando `event_type != hyrox`.
- Fora do MVP do piloto (fase 2): painel de saúde do gateway (`last_used_at` do token,
  última leitura por estação) — o piloto é pequeno e presencial (tem notebook/tablet no
  local), não é crítico ter alerta automático de leitor "morto" ainda.

---

## Riscos e perguntas em aberto

1. **Backfill de `Athlete.team_id` NOT NULL** (seção 2) — precisa de auditoria de dados
   antes da migração, não pode ser decidido só no código.
2. **Unicidade de `RfidTagAssignment` ativa** — não há garantia via constraint parcial de
   banco (suporte inconsistente SQLite/Postgres); a exclusividade é garantida só na
   camada de serviço. Se isso for inaceitável (ex: dois operadores parearem a mesma tag
   simultaneamente em corridas separadas), considerar lock distribuído (Redis, já usado
   pra timers) na hora do pareamento.
3. **Sincronismo de relógio do gateway** — a guarda de clock-skew (seção 6, passo 1) evita
   leituras absurdas, mas a precisão real dos splits depende do Pi estar com NTP
   sincronizado. Isso é operacional, documentado na spec do gateway, fora do código Tempus.
4. **Conectividade de backup do piloto** — se o gateway perder conexão, o buffer/replay
   local é responsabilidade do software do gateway (fora deste repo); o `read_id`
   idempotente aqui já garante que o replay não duplica eventos quando a conexão volta.

---

## Fora de escopo deste documento

Software do gateway (Raspberry Pi, leitura LLRP, debounce client-side, buffer offline) —
ver `docs/superpowers/specs/2026-09-08-rfid-gateway-service-prompt.md`.
