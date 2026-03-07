"""Tests for mission CRUD operations."""

import pytest
from pathlib import Path

from r6_navigator.db.database import get_engine, get_session_factory, init_db
from r6_navigator.services.crud_mission import (
    create_extract,
    create_interpretation,
    create_interview,
    create_mission,
    create_verbatim,
    delete_extract,
    delete_interpretation,
    delete_interview,
    delete_mission,
    delete_verbatim,
    get_all_mission_interpretations,
    get_all_missions,
    get_extracts,
    get_interpretations,
    get_interviews,
    get_mission,
    get_mission_report,
    get_verbatims,
    update_interpretation_status,
    update_interview,
    update_mission,
    update_verbatim,
    upsert_mission_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def session():
    engine = get_engine(Path(":memory:"))
    init_db(engine, seed_capacities=False)
    factory = get_session_factory(engine)
    with factory() as s:
        yield s


@pytest.fixture
def mission(session):
    return create_mission(session, "Test Mission", client="Acme", consultant="Alice")


@pytest.fixture
def interview(session, mission):
    return create_interview(session, mission.id, "Bob Smith", subject_role="Manager")


@pytest.fixture
def verbatim(session, interview):
    return create_verbatim(session, interview.id, "Sample verbatim text for testing.")


@pytest.fixture
def extract(session, verbatim):
    return create_extract(session, verbatim.id, "Extract text", tag="I3a", display_order=0)


@pytest.fixture
def interpretation(session, extract):
    return create_interpretation(
        session, extract.id,
        capacity_id=None,  # no capacity seeded in test DB
        maturity_level="insuffisant",
        confidence=0.8,
        text="This is an interpretation.",
    )


# ---------------------------------------------------------------------------
# Mission CRUD
# ---------------------------------------------------------------------------

def test_create_mission(session):
    m = create_mission(session, "My Mission", client="ClientX")
    assert m.id is not None
    assert m.name == "My Mission"
    assert m.client == "ClientX"


def test_get_all_missions(session):
    create_mission(session, "Mission A")
    create_mission(session, "Mission B")
    missions = get_all_missions(session)
    assert len(missions) == 2


def test_get_mission(session, mission):
    found = get_mission(session, mission.id)
    assert found is not None
    assert found.name == "Test Mission"


def test_get_mission_not_found(session):
    assert get_mission(session, 9999) is None


def test_update_mission(session, mission):
    updated = update_mission(session, mission.id, name="Updated Name", client="NewClient")
    assert updated.name == "Updated Name"
    assert updated.client == "NewClient"


def test_delete_mission_cascades(session, mission):
    iv = create_interview(session, mission.id, "Alice")
    v = create_verbatim(session, iv.id, "text")
    ex = create_extract(session, v.id, "extract")
    create_interpretation(session, ex.id, text="interp")

    delete_mission(session, mission.id)
    assert get_mission(session, mission.id) is None
    assert get_interviews(session, mission.id) == []


# ---------------------------------------------------------------------------
# Interview CRUD
# ---------------------------------------------------------------------------

def test_create_interview(session, mission):
    iv = create_interview(session, mission.id, "Jane Doe", subject_role="CEO")
    assert iv.id is not None
    assert iv.subject_name == "Jane Doe"
    assert iv.subject_role == "CEO"


def test_get_interviews_by_mission(session, mission):
    create_interview(session, mission.id, "Alice")
    create_interview(session, mission.id, "Bob")
    ivs = get_interviews(session, mission.id)
    assert len(ivs) == 2


def test_update_interview(session, interview):
    updated = update_interview(session, interview.id, subject_role="Director")
    assert updated.subject_role == "Director"


def test_delete_interview_cascades(session, interview, verbatim, extract, interpretation):
    delete_interview(session, interview.id)
    assert get_verbatims(session, interview.id) == []


# ---------------------------------------------------------------------------
# Verbatim CRUD
# ---------------------------------------------------------------------------

def test_create_verbatim(session, interview):
    v = create_verbatim(session, interview.id, "Some text here.")
    assert v.id is not None
    assert v.text == "Some text here."


def test_update_verbatim(session, verbatim):
    updated = update_verbatim(session, verbatim.id, "New text content.")
    assert updated.text == "New text content."


def test_delete_verbatim_cascades(session, verbatim, extract, interpretation):
    delete_verbatim(session, verbatim.id)
    assert get_extracts(session, verbatim.id) == []


# ---------------------------------------------------------------------------
# Extract CRUD
# ---------------------------------------------------------------------------

def test_create_extract(session, verbatim):
    ex = create_extract(session, verbatim.id, "Extract text", tag="O2b", display_order=1)
    assert ex.id is not None
    assert ex.tag == "O2b"
    assert ex.display_order == 1


def test_get_extracts_ordered_by_display_order(session, verbatim):
    create_extract(session, verbatim.id, "Second", display_order=2)
    create_extract(session, verbatim.id, "First", display_order=1)
    extracts = get_extracts(session, verbatim.id)
    assert extracts[0].display_order == 1
    assert extracts[1].display_order == 2


def test_delete_extract_cascades(session, extract, interpretation):
    delete_extract(session, extract.id)
    assert get_interpretations(session, extract.id) == []


# ---------------------------------------------------------------------------
# Interpretation CRUD
# ---------------------------------------------------------------------------

def test_create_interpretation_default_status(session, extract):
    interp = create_interpretation(session, extract.id, capacity_id=None, text="My interpretation")
    assert interp.status == "pending"


def test_get_interpretations(session, extract, interpretation):
    interps = get_interpretations(session, extract.id)
    assert len(interps) == 1
    assert interps[0].id == interpretation.id


def test_update_interpretation_status_validate(session, interpretation):
    updated = update_interpretation_status(session, interpretation.id, "validated")
    assert updated.status == "validated"


def test_update_interpretation_status_reject(session, interpretation):
    updated = update_interpretation_status(session, interpretation.id, "rejected")
    assert updated.status == "rejected"


def test_update_interpretation_status_correct(session, interpretation):
    updated = update_interpretation_status(
        session, interpretation.id, "corrected", corrected_text="Corrected text."
    )
    assert updated.status == "corrected"
    assert updated.text == "Corrected text."


def test_get_all_mission_interpretations(session, mission, interview, verbatim, extract, interpretation):
    interps = get_all_mission_interpretations(session, mission.id)
    assert len(interps) == 1
    assert interps[0].id == interpretation.id


def test_delete_interpretation(session, extract, interpretation):
    delete_interpretation(session, interpretation.id)
    assert get_interpretations(session, extract.id) == []


# ---------------------------------------------------------------------------
# MissionReport CRUD
# ---------------------------------------------------------------------------

def test_upsert_mission_report_insert(session, mission):
    report = upsert_mission_report(session, mission.id, "fr", "## Rapport\nContenu.")
    assert report.id is not None
    assert report.lang == "fr"
    assert "Rapport" in report.text


def test_upsert_mission_report_update(session, mission):
    upsert_mission_report(session, mission.id, "fr", "First version.")
    updated = upsert_mission_report(session, mission.id, "fr", "Second version.")
    assert updated.text == "Second version."


def test_get_mission_report(session, mission):
    upsert_mission_report(session, mission.id, "fr", "Rapport FR")
    upsert_mission_report(session, mission.id, "en", "Report EN")
    fr = get_mission_report(session, mission.id, "fr")
    en = get_mission_report(session, mission.id, "en")
    assert fr.text == "Rapport FR"
    assert en.text == "Report EN"


def test_get_mission_report_not_found(session, mission):
    assert get_mission_report(session, mission.id, "fr") is None


def test_mission_report_deleted_with_mission(session, mission):
    upsert_mission_report(session, mission.id, "fr", "Will be deleted.")
    delete_mission(session, mission.id)
    assert get_mission_report(session, mission.id, "fr") is None
