"""Tests for the mission module CRUD operations."""
from __future__ import annotations

from pathlib import Path

import pytest

from r6_navigator.db.database import get_engine, get_session_factory, init_db
from r6_navigator.db.models import Capacity, CapacityTranslation
from r6_navigator.missions.services import crud


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def session_with_mission():
    """In-memory DB with one Mission, one Interview, and one Verbatim."""
    engine = get_engine(Path(":memory:"))
    init_db(engine, seed_capacities=False)
    factory = get_session_factory(engine)
    with factory() as s:
        # Create a mission
        mission = crud.create_mission(s, client_name="Acme Corp", description="Test mission")
        # Create an interview
        interview = crud.create_interview(
            s,
            mission_id=mission.mission_id,
            interviewee_name="Alice",
            interviewee_role="CEO",
            interviewee_level="executive",
        )
        # Create a verbatim
        verbatim = crud.create_verbatim(
            s,
            interview_id=interview.interview_id,
            raw_text="Nous avons transformé notre organisation.",
            title="Verbatim 1",
        )
        yield s, mission, interview, verbatim


# ---------------------------------------------------------------------------
# Mission CRUD
# ---------------------------------------------------------------------------

def test_create_mission(session_with_mission):
    session, mission, _, _ = session_with_mission
    assert mission.mission_id is not None
    assert mission.client_name == "Acme Corp"
    assert mission.status == "active"


def test_get_mission(session_with_mission):
    session, mission, _, _ = session_with_mission
    fetched = crud.get_mission(session, mission.mission_id)
    assert fetched is not None
    assert fetched.client_name == "Acme Corp"


def test_list_missions(session_with_mission):
    session, mission, _, _ = session_with_mission
    crud.create_mission(session, client_name="BetaCo")
    missions = crud.list_missions(session)
    assert len(missions) == 2


def test_update_mission(session_with_mission):
    session, mission, _, _ = session_with_mission
    updated = crud.update_mission(session, mission.mission_id, client_name="Acme Ltd", status="complete")
    assert updated.client_name == "Acme Ltd"
    assert updated.status == "complete"


def test_delete_mission(session_with_mission):
    session, mission, _, _ = session_with_mission
    mission_id = mission.mission_id
    crud.delete_mission(session, mission_id)
    assert crud.get_mission(session, mission_id) is None


def test_create_mission_missing_name():
    """create_mission raises ValueError when client_name is empty."""
    engine = get_engine(Path(":memory:"))
    init_db(engine, seed_capacities=False)
    factory = get_session_factory(engine)
    with factory() as s:
        with pytest.raises(ValueError, match="client_name"):
            crud.create_mission(s, client_name="")


# ---------------------------------------------------------------------------
# Interview CRUD
# ---------------------------------------------------------------------------

def test_create_interview(session_with_mission):
    session, mission, interview, _ = session_with_mission
    assert interview.interview_id is not None
    assert interview.interviewee_name == "Alice"
    assert interview.mission_id == mission.mission_id


def test_list_interviews(session_with_mission):
    session, mission, interview, _ = session_with_mission
    crud.create_interview(session, mission_id=mission.mission_id, interviewee_name="Bob")
    interviews = crud.list_interviews(session, mission.mission_id)
    assert len(interviews) == 2


def test_delete_interview_cascades_verbatims(session_with_mission):
    session, mission, interview, verbatim = session_with_mission
    verbatim_id = verbatim.verbatim_id
    crud.delete_interview(session, interview.interview_id)
    assert crud.get_verbatim(session, verbatim_id) is None


# ---------------------------------------------------------------------------
# Verbatim CRUD
# ---------------------------------------------------------------------------

def test_create_verbatim(session_with_mission):
    session, _, interview, verbatim = session_with_mission
    assert verbatim.verbatim_id is not None
    assert verbatim.raw_text == "Nous avons transformé notre organisation."
    assert verbatim.status == "pending"


def test_update_verbatim_status(session_with_mission):
    session, _, _, verbatim = session_with_mission
    updated = crud.update_verbatim_status(session, verbatim.verbatim_id, "analyzed")
    assert updated.status == "analyzed"


def test_list_verbatims(session_with_mission):
    session, _, interview, verbatim = session_with_mission
    crud.create_verbatim(session, interview_id=interview.interview_id, raw_text="Second verbatim")
    verbatims = crud.list_verbatims(session, interview.interview_id)
    assert len(verbatims) == 2


def test_list_verbatims_for_mission(session_with_mission):
    session, mission, interview, verbatim = session_with_mission
    verbatims = crud.list_verbatims_for_mission(session, mission.mission_id)
    assert len(verbatims) == 1
    assert verbatims[0].verbatim_id == verbatim.verbatim_id


# ---------------------------------------------------------------------------
# Extract CRUD
# ---------------------------------------------------------------------------

def test_create_extract(session_with_mission):
    session, _, _, verbatim = session_with_mission
    extract = crud.create_extract(session, verbatim_id=verbatim.verbatim_id, raw_text="Extrait clé.")
    assert extract.extract_id is not None
    assert extract.raw_text == "Extrait clé."
    assert extract.created_by == "AI"


def test_list_extracts(session_with_mission):
    session, _, _, verbatim = session_with_mission
    crud.create_extract(session, verbatim_id=verbatim.verbatim_id, raw_text="Extrait 1")
    crud.create_extract(session, verbatim_id=verbatim.verbatim_id, raw_text="Extrait 2")
    extracts = crud.list_extracts(session, verbatim.verbatim_id)
    assert len(extracts) == 2


# ---------------------------------------------------------------------------
# Interpretation CRUD
# ---------------------------------------------------------------------------

def test_create_interpretation(session_with_mission):
    session, _, _, verbatim = session_with_mission
    extract = crud.create_extract(session, verbatim_id=verbatim.verbatim_id, raw_text="Extrait.")
    interp = crud.create_interpretation(
        session,
        extract_id=extract.extract_id,
        capacity_id=None,
        maturity_score=3,
        direction="OK",
        justification="Manifeste clairement.",
    )
    assert interp.interpretation_id is not None
    assert interp.status == "pending"
    assert interp.maturity_score == 3


def test_validate_interpretation(session_with_mission):
    session, _, _, verbatim = session_with_mission
    extract = crud.create_extract(session, verbatim_id=verbatim.verbatim_id, raw_text="X")
    interp = crud.create_interpretation(session, extract_id=extract.extract_id)
    validated = crud.validate_interpretation(session, interp.interpretation_id)
    assert validated.status == "validated"
    assert validated.validated_at is not None


def test_reject_interpretation(session_with_mission):
    session, _, _, verbatim = session_with_mission
    extract = crud.create_extract(session, verbatim_id=verbatim.verbatim_id, raw_text="X")
    interp = crud.create_interpretation(session, extract_id=extract.extract_id)
    rejected = crud.reject_interpretation(session, interp.interpretation_id)
    assert rejected.status == "rejected"


def test_correct_interpretation(session_with_mission):
    session, _, _, verbatim = session_with_mission
    extract = crud.create_extract(session, verbatim_id=verbatim.verbatim_id, raw_text="X")
    interp = crud.create_interpretation(session, extract_id=extract.extract_id, direction="OK")
    corrected = crud.correct_interpretation(
        session,
        interp.interpretation_id,
        corrected_direction="INS",
        corrected_justification="Correction.",
    )
    assert corrected.status == "corrected"
    assert corrected.corrected_direction == "INS"


def test_list_interpretations_for_mission(session_with_mission):
    session, mission, _, verbatim = session_with_mission
    extract = crud.create_extract(session, verbatim_id=verbatim.verbatim_id, raw_text="X")
    crud.create_interpretation(session, extract_id=extract.extract_id)
    crud.create_interpretation(session, extract_id=extract.extract_id)
    interps = crud.list_interpretations_for_mission(session, mission.mission_id)
    assert len(interps) == 2


# ---------------------------------------------------------------------------
# MissionReport CRUD
# ---------------------------------------------------------------------------

def test_create_mission_report(session_with_mission):
    session, mission, _, _ = session_with_mission
    report = crud.create_mission_report(session, mission_id=mission.mission_id, content="Rapport initial.")
    assert report.report_id is not None
    assert report.status == "draft"
    assert report.content == "Rapport initial."


def test_get_latest_report(session_with_mission):
    session, mission, _, _ = session_with_mission
    crud.create_mission_report(session, mission_id=mission.mission_id, content="Premier")
    report2 = crud.create_mission_report(session, mission_id=mission.mission_id, content="Deuxième")
    latest = crud.get_latest_report(session, mission.mission_id)
    assert latest is not None
    assert latest.report_id == report2.report_id


def test_cascade_delete_mission_removes_all(session_with_mission):
    """Deleting a mission removes interviews, verbatims, extracts, and interpretations."""
    session, mission, _, verbatim = session_with_mission
    extract = crud.create_extract(session, verbatim_id=verbatim.verbatim_id, raw_text="X")
    interp = crud.create_interpretation(session, extract_id=extract.extract_id)
    interp_id = interp.interpretation_id
    extract_id = extract.extract_id
    verbatim_id = verbatim.verbatim_id

    crud.delete_mission(session, mission.mission_id)

    assert crud.get_extract(session, extract_id) is None
    assert crud.get_verbatim(session, verbatim_id) is None
    assert crud.get_interpretation(session, interp_id) is None
