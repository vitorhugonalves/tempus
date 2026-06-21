# Sistema de Pontuação de WODs

**Versão:** Junho 2026  
**Código de referência:** `backend/app/services/wod_result.py` → `_compute_leaderboard()`

---

## Tipos de WOD

| Tipo | Sigla | Como pontua |
|------|-------|-------------|
| `amrap` | As Many Rounds/Reps As Possible | `reps × 10` |
| `for_time` | Completar o circuito no menor tempo | `reps × 10 + bônus de tempo` |
| `emom` | Every Minute on the Minute | Sem pontuação definida (0 pts) |
| `max_load` | Carga máxima | Sem pontuação definida (0 pts) |

---

## Regras de Pontuação

### AMRAP

Pontos = **reps × 10** — sem ranking por tempo.

### FOR_TIME

Pontos = **reps × 10 + bônus de tempo**

O bônus de tempo é calculado pelo **rank de chegada** (menor tempo = melhor rank):

```
bônus = max(0, 500 − (rank − 1) × 10)
```

| Rank de chegada | Bônus de tempo |
|-----------------|----------------|
| 1º | 500 pts |
| 2º | 490 pts |
| 3º | 480 pts |
| … | … |
| 50º | 10 pts |
| 51º ou além | 0 pts |

**Empate em tempo** (duas equipes chegam com o mesmo `time_seconds`) → ambas recebem o mesmo rank e o mesmo bônus.

### W.O. (Walkover)

Equipe que recebe W.O. **não participou** daquele WOD:
- `points = 0`
- `rank = null` (não entra no cálculo de rank de tempo das demais)
- Flag `walkover = true` aparece no leaderboard

### WOD restrito a categorias

Um WOD pode ter categorias associadas. Equipes de outras categorias recebem `points = 0` e `rank = null` — mas continuam listadas no leaderboard geral.

### Leaderboard final

1. Soma os pontos de todos os WODs participados.
2. Ordena por total decrescente.
3. Empate em total → mesma posição; desempate por nome (alfabético).

---

## Exemplos com três equipes

### Cenário 1 — Apenas AMRAP

> **WOD 1** — AMRAP 12 min

| Equipe | Reps | Cálculo | Pontos |
|--------|------|---------|--------|
| Alpha | 95 | 95 × 10 | **950** |
| Beta | 82 | 82 × 10 | **820** |
| Gamma | 60 | 60 × 10 | **600** |

**Leaderboard:**

| Pos | Equipe | Total |
|-----|--------|-------|
| 1º | Alpha | 950 |
| 2º | Beta | 820 |
| 3º | Gamma | 600 |

---

### Cenário 2 — Apenas FOR_TIME

> **WOD 1** — FOR_TIME (sem reps parciais)

| Equipe | Tempo | Rank | Bônus de tempo | Reps extras | Total |
|--------|-------|------|----------------|-------------|-------|
| Beta | 7 min 20 s (440 s) | 1º | 500 | 0 | **500** |
| Alpha | 8 min 15 s (495 s) | 2º | 490 | 0 | **490** |
| Gamma | 11 min 00 s (660 s) | 3º | 480 | 0 | **480** |

**Leaderboard:**

| Pos | Equipe | Total |
|-----|--------|-------|
| 1º | Beta | 500 |
| 2º | Alpha | 490 |
| 3º | Gamma | 480 |

---

### Cenário 3 — Dois WODs combinados (AMRAP + FOR_TIME) com W.O.

> **WOD 1** — AMRAP 20 min  
> **WOD 2** — FOR_TIME (inclui reps parciais para quem não terminou)

#### WOD 1 — AMRAP

| Equipe | Reps | Pontos WOD 1 |
|--------|------|--------------|
| Alpha | 110 | 1100 |
| Beta | 95 | 950 |
| Gamma | W.O. | 0 |

#### WOD 2 — FOR_TIME

Gamma terminou o circuito mas Alpha e Beta não concluíram dentro do tempo — registrou-se apenas as reps parciais.

| Equipe | Tempo | Reps parciais | Rank | Bônus de tempo | Reps pts | Pontos WOD 2 |
|--------|-------|---------------|------|----------------|----------|--------------|
| Gamma | 14 min 30 s | 0 | 1º | 500 | 0 | **500** |
| Alpha | DNF (tempo) | 7 | 2º | 490 | 70 | **560** |
| Beta | DNF (tempo) | 3 | 3º | 480 | 30 | **510** |

> **DNF (Did Not Finish):** o WOD atingiu o limite de tempo com a equipe ainda em execução. O juiz registra o tempo limite + as reps completadas até aquele momento. O rank de tempo segue normal — quem avançou mais no circuito chega primeiro.

#### Leaderboard final

| Pos | Equipe | WOD 1 | WOD 2 | Total |
|-----|--------|-------|-------|-------|
| 1º | Alpha | 1100 | 560 | **1660** |
| 2º | Beta | 950 | 510 | **1460** |
| 3º | Gamma | 0 (W.O.) | 500 | **500** |

---

## Fluxo de dados (resumido)

```mermaid
flowchart TD
    A[Juiz registra resultado via ResultsPage] --> B[POST /competitions/{id}/wod-results]
    B --> C[WodResultService.upsert]
    C --> D[(wod_results)]

    E[Leaderboard solicitado] --> F[GET /competitions/{id}/wod-leaderboard]
    F --> G[WodResultService.compute_leaderboard]
    G --> H[_compute_leaderboard]
    H --> I{tipo do WOD}
    I -->|amrap| J[reps × 10]
    I -->|for_time| K[reps × 10 + bônus de tempo]
    I -->|emom / max_load| L[0 pts]
    J --> M[Soma total por equipe]
    K --> M
    L --> M
    M --> N[Ordena decrescente]
    N --> O[Atribui posições com suporte a empate]
    O --> P[WodLeaderboard]
```
