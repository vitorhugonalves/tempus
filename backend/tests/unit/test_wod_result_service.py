"""Testes unitários para a lógica de leaderboard de WOD results."""
from unittest.mock import MagicMock

from app.models.wod import WodType
from app.services.wod_result import _compute_leaderboard


def _make_wod(id: int, wod_type: str) -> MagicMock:
    w = MagicMock()
    w.id = id
    w.name = f"WOD {id}"
    w.wod_type = WodType(wod_type)
    return w


def _make_team(id: int, name: str) -> MagicMock:
    t = MagicMock()
    t.id = id
    t.name = name
    return t


def _make_result(wod_id: int, team_id: int, time_seconds=None, reps=None) -> MagicMock:
    r = MagicMock()
    r.wod_id = wod_id
    r.team_id = team_id
    r.time_seconds = time_seconds
    r.reps = reps
    return r


def test_leaderboard_vazio_sem_wods():
    lb = _compute_leaderboard("most_points", [], [], [])
    assert lb.entries == []


def test_leaderboard_vazio_sem_equipes():
    wod = _make_wod(1, "for_time")
    lb = _compute_leaderboard("most_points", [wod], [], [])
    assert lb.entries == []


def test_leaderboard_most_points_for_time_ordena_por_tempo_asc():
    """Equipe com menor tempo recebe mais pontos e fica em 1º."""
    wod = _make_wod(1, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, time_seconds=600),   # Alpha: 10 min
        _make_result(1, 2, time_seconds=480),   # Beta: 8 min (melhor)
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    assert lb.entries[0].team_id == 2  # Beta em 1º
    assert lb.entries[0].position == 1
    assert lb.entries[0].total_points == 2  # 2 equipes, 1º = 2 pts
    assert lb.entries[1].team_id == 1  # Alpha em 2º
    assert lb.entries[1].total_points == 1


def test_leaderboard_most_points_amrap_ordena_por_reps_desc():
    """Equipe com mais reps recebe mais pontos e fica em 1º."""
    wod = _make_wod(1, "amrap")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, reps=120),  # Alpha: 120 reps (melhor)
        _make_result(1, 2, reps=90),   # Beta: 90 reps
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    assert lb.entries[0].team_id == 1  # Alpha em 1º
    assert lb.entries[0].total_points == 2


def test_leaderboard_sem_resultado_recebe_zero_pontos():
    wod = _make_wod(1, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [_make_result(1, 1, time_seconds=300)]  # Beta sem resultado

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    beta_entry = next(e for e in lb.entries if e.team_id == 2)
    assert beta_entry.total_points == 0
    assert beta_entry.wod_entries[0].rank is None


def test_leaderboard_lowest_time_soma_tempos():
    wod1 = _make_wod(1, "for_time")
    wod2 = _make_wod(2, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, time_seconds=300),
        _make_result(2, 1, time_seconds=240),   # Alpha total: 540
        _make_result(1, 2, time_seconds=200),
        _make_result(2, 2, time_seconds=200),   # Beta total: 400 (melhor)
    ]

    lb = _compute_leaderboard("lowest_time", [wod1, wod2], [team_a, team_b], results)

    assert lb.entries[0].team_id == 2  # Beta com menor tempo total
    assert lb.entries[0].total_points == 400  # total_points = total_seconds aqui
    assert lb.entries[1].total_points == 540


def test_leaderboard_lowest_time_incompleto_vai_ao_fim():
    """Equipe sem resultado em algum WOD vai para o final do leaderboard."""
    wod1 = _make_wod(1, "for_time")
    wod2 = _make_wod(2, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, time_seconds=300),
        _make_result(2, 1, time_seconds=240),  # Alpha completo: 540
        _make_result(1, 2, time_seconds=100),  # Beta só tem WOD1
    ]

    lb = _compute_leaderboard("lowest_time", [wod1, wod2], [team_a, team_b], results)

    assert lb.entries[0].team_id == 1   # Alpha em 1º (completo)
    assert lb.entries[1].team_id == 2   # Beta ao fim (incompleto)


def test_leaderboard_empate_mesma_posicao():
    """Equipes empatadas em pontos recebem a mesma posição."""
    wod = _make_wod(1, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    team_c = _make_team(3, "Gamma")
    results = [
        _make_result(1, 1, time_seconds=300),
        _make_result(1, 2, time_seconds=300),  # Empate com Alpha
        _make_result(1, 3, time_seconds=600),
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b, team_c], results)

    positions = {e.team_id: e.position for e in lb.entries}
    assert positions[1] == positions[2]   # Empate em 1º
    assert positions[3] == 3             # Gamma em 3º (não em 2º)
