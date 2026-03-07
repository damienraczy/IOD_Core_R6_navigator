from __future__ import annotations

from sqlalchemy.orm import Session

from r6_navigator.db.models import (
    Extract,
    Interpretation,
    Interview,
    Mission,
    MissionReport,
    Verbatim,
)


# ---------------------------------------------------------------------------
# Mission
# ---------------------------------------------------------------------------

def get_all_missions(session: Session) -> list[Mission]:
    return session.query(Mission).order_by(Mission.created_at.desc()).all()


def get_mission(session: Session, mission_id: int) -> Mission | None:
    return session.get(Mission, mission_id)


def create_mission(
    session: Session,
    name: str,
    client: str | None = None,
    consultant: str | None = None,
    start_date: str | None = None,
    objective: str | None = None,
) -> Mission:
    mission = Mission(
        name=name,
        client=client,
        consultant=consultant,
        start_date=start_date,
        objective=objective,
    )
    session.add(mission)
    session.commit()
    return mission


def update_mission(session: Session, mission_id: int, **kwargs) -> Mission:
    mission = session.get(Mission, mission_id)
    if mission is None:
        raise ValueError(f"Mission {mission_id} not found")
    for key, value in kwargs.items():
        setattr(mission, key, value)
    session.commit()
    return mission


def delete_mission(session: Session, mission_id: int) -> None:
    mission = session.get(Mission, mission_id)
    if mission is not None:
        session.delete(mission)
        session.commit()


# ---------------------------------------------------------------------------
# Interview
# ---------------------------------------------------------------------------

def get_interviews(session: Session, mission_id: int) -> list[Interview]:
    return (
        session.query(Interview)
        .filter_by(mission_id=mission_id)
        .order_by(Interview.id)
        .all()
    )


def create_interview(
    session: Session,
    mission_id: int,
    subject_name: str,
    subject_role: str | None = None,
    interview_date: str | None = None,
    notes: str | None = None,
) -> Interview:
    interview = Interview(
        mission_id=mission_id,
        subject_name=subject_name,
        subject_role=subject_role,
        interview_date=interview_date,
        notes=notes,
    )
    session.add(interview)
    session.commit()
    return interview


def update_interview(session: Session, interview_id: int, **kwargs) -> Interview:
    interview = session.get(Interview, interview_id)
    if interview is None:
        raise ValueError(f"Interview {interview_id} not found")
    for key, value in kwargs.items():
        setattr(interview, key, value)
    session.commit()
    return interview


def delete_interview(session: Session, interview_id: int) -> None:
    interview = session.get(Interview, interview_id)
    if interview is not None:
        session.delete(interview)
        session.commit()


# ---------------------------------------------------------------------------
# Verbatim
# ---------------------------------------------------------------------------

def get_verbatims(session: Session, interview_id: int) -> list[Verbatim]:
    return (
        session.query(Verbatim)
        .filter_by(interview_id=interview_id)
        .order_by(Verbatim.id)
        .all()
    )


def create_verbatim(session: Session, interview_id: int, text: str = "") -> Verbatim:
    verbatim = Verbatim(interview_id=interview_id, text=text)
    session.add(verbatim)
    session.commit()
    return verbatim


def update_verbatim(session: Session, verbatim_id: int, text: str) -> Verbatim:
    verbatim = session.get(Verbatim, verbatim_id)
    if verbatim is None:
        raise ValueError(f"Verbatim {verbatim_id} not found")
    verbatim.text = text
    session.commit()
    return verbatim


def delete_verbatim(session: Session, verbatim_id: int) -> None:
    verbatim = session.get(Verbatim, verbatim_id)
    if verbatim is not None:
        session.delete(verbatim)
        session.commit()


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def get_extracts(session: Session, verbatim_id: int) -> list[Extract]:
    return (
        session.query(Extract)
        .filter_by(verbatim_id=verbatim_id)
        .order_by(Extract.display_order, Extract.id)
        .all()
    )


def create_extract(
    session: Session,
    verbatim_id: int,
    text: str,
    tag: str | None = None,
    display_order: int = 0,
    halliday_ok: bool | None = None,
    halliday_note: str | None = None,
) -> Extract:
    extract = Extract(
        verbatim_id=verbatim_id,
        text=text,
        tag=tag,
        display_order=display_order,
        halliday_ok=halliday_ok,
        halliday_note=halliday_note,
    )
    session.add(extract)
    session.commit()
    return extract


def delete_extract(session: Session, extract_id: int) -> None:
    extract = session.get(Extract, extract_id)
    if extract is not None:
        session.delete(extract)
        session.commit()


# ---------------------------------------------------------------------------
# Interpretation
# ---------------------------------------------------------------------------

def get_interpretations(session: Session, extract_id: int) -> list[Interpretation]:
    return (
        session.query(Interpretation)
        .filter_by(extract_id=extract_id)
        .order_by(Interpretation.id)
        .all()
    )


def get_all_mission_interpretations(
    session: Session, mission_id: int
) -> list[Interpretation]:
    return (
        session.query(Interpretation)
        .join(Extract)
        .join(Verbatim)
        .join(Interview)
        .filter(Interview.mission_id == mission_id)
        .order_by(Interpretation.id)
        .all()
    )


def create_interpretation(
    session: Session,
    extract_id: int,
    capacity_id: str | None = None,
    maturity_level: str | None = None,
    confidence: float | None = None,
    text: str = "",
) -> Interpretation:
    interp = Interpretation(
        extract_id=extract_id,
        capacity_id=capacity_id,
        maturity_level=maturity_level,
        confidence=confidence,
        text=text,
        status="pending",
    )
    session.add(interp)
    session.commit()
    return interp


def update_interpretation_status(
    session: Session,
    interp_id: int,
    status: str,
    corrected_text: str | None = None,
) -> Interpretation:
    interp = session.get(Interpretation, interp_id)
    if interp is None:
        raise ValueError(f"Interpretation {interp_id} not found")
    interp.status = status
    if corrected_text is not None:
        interp.text = corrected_text
    session.commit()
    return interp


def delete_interpretation(session: Session, interp_id: int) -> None:
    interp = session.get(Interpretation, interp_id)
    if interp is not None:
        session.delete(interp)
        session.commit()


def delete_all_mission_interpretations(session: Session, mission_id: int) -> int:
    """Supprime toutes les interprétations d'une mission. Retourne le nombre supprimé."""
    interps = (
        session.query(Interpretation)
        .join(Extract, Interpretation.extract_id == Extract.id)
        .join(Verbatim, Extract.verbatim_id == Verbatim.id)
        .join(Interview, Verbatim.interview_id == Interview.id)
        .filter(Interview.mission_id == mission_id)
        .all()
    )
    count = len(interps)
    for interp in interps:
        session.delete(interp)
    session.commit()
    return count


def delete_interview_interpretations(session: Session, interview_id: int) -> int:
    """Supprime toutes les interprétations d'un entretien. Retourne le nombre supprimé."""
    interps = (
        session.query(Interpretation)
        .join(Extract, Interpretation.extract_id == Extract.id)
        .join(Verbatim, Extract.verbatim_id == Verbatim.id)
        .filter(Verbatim.interview_id == interview_id)
        .all()
    )
    count = len(interps)
    for interp in interps:
        session.delete(interp)
    session.commit()
    return count


# ---------------------------------------------------------------------------
# MissionReport
# ---------------------------------------------------------------------------

def get_mission_report(
    session: Session, mission_id: int, lang: str
) -> MissionReport | None:
    return (
        session.query(MissionReport)
        .filter_by(mission_id=mission_id, lang=lang)
        .first()
    )


def upsert_mission_report(
    session: Session, mission_id: int, lang: str, text: str
) -> MissionReport:
    from datetime import datetime, timezone

    report = get_mission_report(session, mission_id, lang)
    if report is None:
        report = MissionReport(mission_id=mission_id, lang=lang, text=text)
        session.add(report)
    else:
        report.text = text
        report.generated_at = datetime.now(timezone.utc)
    session.commit()
    return report
