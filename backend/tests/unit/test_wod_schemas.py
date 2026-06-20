import pytest
from app.schemas.wod import WodCreate, WodResponse
from app.models.wod import WodType
from datetime import datetime


def test_wod_create_valida_campos_obrigatorios():
    wod = WodCreate(name="Grace", wod_type=WodType.for_time)
    assert wod.name == "Grace"
    assert wod.wod_type == WodType.for_time
    assert wod.duration_minutes is None
    assert wod.description is None
    assert wod.order == 0


def test_wod_create_com_todos_campos():
    wod = WodCreate(
        name="Fran",
        wod_type=WodType.for_time,
        duration_minutes=7,
        description="21-15-9 Thrusters + Pull-ups",
        order=1,
    )
    assert wod.duration_minutes == 7
    assert wod.description == "21-15-9 Thrusters + Pull-ups"


def test_wod_response_from_attributes():
    class FakeWod:
        id = 1
        competition_id = 42
        name = "Grace"
        wod_type = WodType.for_time
        duration_minutes = 10
        description = "30 Clean and Jerk"
        order = 0
        created_at = datetime(2026, 6, 20)
        updated_at = datetime(2026, 6, 20)

    resp = WodResponse.model_validate(FakeWod())
    assert resp.id == 1
    assert resp.competition_id == 42
    assert resp.wod_type == WodType.for_time
