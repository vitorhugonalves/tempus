"""Testes unitários para a lógica de leaderboard de WOD results."""
from unittest.mock import MagicMock

from app.models.wod import WodType
from app.services.wod_result import _compute_leaderboard


def _make_wod(id: int, wod_type: str, category_ids: list[int] | None = None) -> MagicMock:
    w = MagicMock()
    w.id = id
    w.name = f"WOD {id}"
    w.wod_type = WodType(wod_type)
    cats = [MagicMock(id=cid) for cid in (category_ids or [])]
    w.categories = cats
    return w


def _make_team(id: int, name: str, category_id: int = 0) -> MagicMock:
    t = MagicMock()
    t.id = id
    t.name = name
    t.category_id = category_id
    return t


def _make_result(wod_id: int, team_id: int, time_seconds=None, reps=None, walkover=False) -> MagicMock:
    r = MagicMock()
    r.wod_id = wod_id
    r.team_id = team_id
    r.time_seconds = time_seconds
    r.reps = reps
    r.walkover = walkover
    return r


def test_leaderboard_vazio_sem_wods():
    lb = _compute_leaderboard("most_points", [], [], [])
    assert lb.entries == []


def test_leaderboard_vazio_sem_equipes():
    wod = _make_wod(1, "for_time")
    lb = _compute_leaderboard("most_points", [wod], [], [])
    assert lb.entries == []


def test_leaderboard_for_time_menor_tempo_em_primeiro():
    """Equipe mais rápida recebe bônus maior e fica em 1º."""
    wod = _make_wod(1, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, time_seconds=600),  # Alpha: 10 min (rank 2)
        _make_result(1, 2, time_seconds=480),  # Beta: 8 min  (rank 1 → 500 pts)
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    assert lb.entries[0].team_id == 2   # Beta em 1º
    assert lb.entries[0].position == 1
    assert lb.entries[0].total_points == 500  # rank1 → 500 pts, sem reps
    assert lb.entries[1].team_id == 1   # Alpha em 2º
    assert lb.entries[1].total_points == 490  # rank2 → 490 pts


def test_leaderboard_for_time_pontos_reps_mais_bonus_tempo():
    """FOR_TIME: pontuação = reps×10 + bônus de tempo."""
    wod = _make_wod(1, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, time_seconds=300, reps=5),   # Alpha: rank2 → 490 + 50 = 540
        _make_result(1, 2, time_seconds=200, reps=10),  # Beta:  rank1 → 500 + 100 = 600
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    assert lb.entries[0].team_id == 2   # Beta em 1º
    assert lb.entries[0].total_points == 600
    assert lb.entries[1].total_points == 540


def test_leaderboard_amrap_mais_reps_em_primeiro():
    """AMRAP: pontuação = reps × 10; mais reps = melhor posição."""
    wod = _make_wod(1, "amrap")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, reps=120),  # Alpha: 1200 pts
        _make_result(1, 2, reps=90),   # Beta:   900 pts
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    assert lb.entries[0].team_id == 1   # Alpha em 1º
    assert lb.entries[0].total_points == 1200
    assert lb.entries[1].total_points == 900


def test_leaderboard_amrap_pontuacao_absoluta_10_por_rep():
    """10 pontos por repetição exatos."""
    wod = _make_wod(1, "amrap")
    team_a = _make_team(1, "Alpha")
    results = [_make_result(1, 1, reps=37)]

    lb = _compute_leaderboard("most_points", [wod], [team_a], results)

    assert lb.entries[0].total_points == 370
    assert lb.entries[0].wod_entries[0].points == 370


def test_leaderboard_sem_resultado_recebe_zero_pontos():
    """Equipe sem resultado recebe 0 pontos e rank None."""
    wod = _make_wod(1, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [_make_result(1, 1, time_seconds=300)]  # Beta sem resultado

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    beta_entry = next(e for e in lb.entries if e.team_id == 2)
    assert beta_entry.total_points == 0
    assert beta_entry.wod_entries[0].rank is None
    assert beta_entry.wod_entries[0].points == 0


def test_leaderboard_for_time_bonus_tempo_escala_500_a_0():
    """Bônus de tempo: rank1=500, rank2=490, ..., rank50=10, rank51=0."""
    wod = _make_wod(1, "for_time")
    # 51 equipes para testar o limite
    teams = [_make_team(i, f"T{i}") for i in range(1, 53)]
    results = [_make_result(1, i, time_seconds=i * 10) for i in range(1, 53)]

    lb = _compute_leaderboard("most_points", [wod], teams, results)

    entries_by_team = {e.team_id: e for e in lb.entries}
    assert entries_by_team[1].total_points == 500   # rank 1
    assert entries_by_team[2].total_points == 490   # rank 2
    assert entries_by_team[50].total_points == 10   # rank 50
    assert entries_by_team[51].total_points == 0    # rank 51
    assert entries_by_team[52].total_points == 0    # rank 52


def test_leaderboard_multiwod_soma_pontos():
    """Total é a soma dos pontos de todos os WODs participados."""
    wod1 = _make_wod(1, "amrap")
    wod2 = _make_wod(2, "for_time")
    team_a = _make_team(1, "Alpha")
    results = [
        _make_result(1, 1, reps=10),           # AMRAP: 100 pts
        _make_result(2, 1, time_seconds=100),   # FOR_TIME rank1: 500 pts
    ]

    lb = _compute_leaderboard("most_points", [wod1, wod2], [team_a], results)

    assert lb.entries[0].total_points == 600


def test_leaderboard_empate_mesma_posicao():
    """Equipes empatadas em pontos recebem a mesma posição."""
    wod = _make_wod(1, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    team_c = _make_team(3, "Gamma")
    results = [
        _make_result(1, 1, time_seconds=300),   # Alpha e Beta empatadas → 500 pts cada
        _make_result(1, 2, time_seconds=300),
        _make_result(1, 3, time_seconds=600),   # Gamma rank3 → 480 pts
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b, team_c], results)

    positions = {e.team_id: e.position for e in lb.entries}
    assert positions[1] == positions[2]  # Empate em 1º
    assert positions[3] == 3             # Gamma em 3º (não em 2º)


def test_leaderboard_wod_type_presente_em_cada_entrada():
    """wod_type deve estar em cada LeaderboardWodEntry."""
    wod = _make_wod(1, "amrap")
    team_a = _make_team(1, "Alpha")
    results = [_make_result(1, 1, reps=50)]

    lb = _compute_leaderboard("most_points", [wod], [team_a], results)

    assert lb.entries[0].wod_entries[0].wod_type == "amrap"


def test_leaderboard_emom_sem_pontuacao():
    """EMOM e MAX_LOAD ainda não têm pontuação definida → 0 pts."""
    wod = _make_wod(1, "emom")
    team_a = _make_team(1, "Alpha")
    results = [_make_result(1, 1, reps=20)]

    lb = _compute_leaderboard("most_points", [wod], [team_a], results)

    assert lb.entries[0].total_points == 0
    assert lb.entries[0].wod_entries[0].points == 0


def test_leaderboard_filtra_equipes_por_categoria_do_wod():
    """WOD com category_ids só inclui equipes daquela categoria."""
    wod = _make_wod(1, "amrap", category_ids=[1])  # só categoria 1
    team_a = _make_team(1, "Alpha", category_id=1)  # participa
    team_b = _make_team(2, "Beta", category_id=2)   # NÃO participa
    results = [
        _make_result(1, 1, reps=50),  # Alpha: 500 pts
        _make_result(1, 2, reps=80),  # Beta: não deve contar
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    alpha = next(e for e in lb.entries if e.team_id == 1)
    beta = next(e for e in lb.entries if e.team_id == 2)
    assert alpha.position == 1
    assert alpha.total_points == 500   # 50 reps × 10
    # Beta não participa: rank=None, points=0
    assert beta.wod_entries[0].rank is None
    assert beta.wod_entries[0].points == 0


def test_leaderboard_walkover_recebe_zero_pontos_e_nao_entra_no_rank():
    """Equipe com W.O. recebe 0 pts e não entra no rank de tempo."""
    wod = _make_wod(1, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, time_seconds=300),  # Alpha: rank1 → 500 pts
        _make_result(1, 2, walkover=True),      # Beta: W.O. → 0 pts, não rankeia
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    alpha = next(e for e in lb.entries if e.team_id == 1)
    beta = next(e for e in lb.entries if e.team_id == 2)

    assert alpha.total_points == 500         # Alpha é rank 1 (única com tempo)
    assert alpha.wod_entries[0].rank == 1
    assert beta.total_points == 0
    assert beta.wod_entries[0].walkover is True
    assert beta.wod_entries[0].rank is None
    assert beta.position > alpha.position    # Beta fica após Alpha


def test_leaderboard_walkover_exibe_flag_no_entry():
    """Flag walkover=True aparece no LeaderboardWodEntry e walkover=False no demais."""
    wod = _make_wod(1, "amrap")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, reps=10),      # Alpha: normal
        _make_result(1, 2, walkover=True), # Beta: W.O.
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    alpha = next(e for e in lb.entries if e.team_id == 1)
    beta = next(e for e in lb.entries if e.team_id == 2)

    assert alpha.wod_entries[0].walkover is False
    assert beta.wod_entries[0].walkover is True
