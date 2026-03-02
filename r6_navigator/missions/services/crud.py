from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
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

def create_mission(
    session: Session,
    client_name: str,
    description: str | None = None,
    status: str = "active",
) -> Mission:
    if not client_name or not client_name.strip():
        raise ValueError("client_name is required")
    mission = Mission(
        mission_id=str(uuid.uuid4()),
        client_name=client_name,
        description=description,
        status=status,
    )
    session.add(mission)
    session.commit()
    session.refresh(mission)
    return mission


def get_mission(session: Session, mission_id: str) -> Mission | None:
    return session.get(Mission, mission_id)


def list_missions(session: Session) -> list[Mission]:
    stmt = select(Mission).order_by(Mission.created_at.desc())
    return list(session.scalars(stmt).all())


def update_mission(session: Session, mission_id: str, **fields) -> Mission:
    mission = session.get(Mission, mission_id)
    if mission is None:
        raise ValueError(f"Mission '{mission_id}' not found")
    for key, value in fields.items():
        setattr(mission, key, value)
    session.commit()
    session.refresh(mission)
    return mission


def delete_mission(session: Session, mission_id: str) -> None:
    mission = session.get(Mission, mission_id)
    if mission is not None:
        session.delete(mission)
        session.commit()


# ---------------------------------------------------------------------------
# Interview
# ---------------------------------------------------------------------------

def create_interview(
    session: Session,
    mission_id: str,
    interviewee_name: str,
    interviewee_role: str | None = None,
    interviewee_level: str | None = None,
    interview_date: str | None = None,
    notes: str | None = None,
) -> Interview:
    if not interviewee_name or not interviewee_name.strip():
        raise ValueError("interviewee_name is required")
    interview = Interview(
        mission_id=mission_id,
        interviewee_name=interviewee_name,
        interviewee_role=interviewee_role,
        interviewee_level=interviewee_level,
        interview_date=interview_date,
        notes=notes,
    )
    session.add(interview)
    session.commit()
    session.refresh(interview)
    return interview


def get_interview(session: Session, interview_id: int) -> Interview | None:
    return session.get(Interview, interview_id)


def list_interviews(session: Session, mission_id: str) -> list[Interview]:
    stmt = select(Interview).where(Interview.mission_id == mission_id)
    return list(session.scalars(stmt).all())


def update_interview(session: Session, interview_id: int, **fields) -> Interview:
    interview = session.get(Interview, interview_id)
    if interview is None:
        raise ValueError(f"Interview '{interview_id}' not found")
    for key, value in fields.items():
        setattr(interview, key, value)
    session.commit()
    session.refresh(interview)
    return interview


def delete_interview(session: Session, interview_id: int) -> None:
    interview = session.get(Interview, interview_id)
    if interview is not None:
        session.delete(interview)
        session.commit()


# ---------------------------------------------------------------------------
# Verbatim
# ---------------------------------------------------------------------------

def create_verbatim(
    session: Session,
    interview_id: int,
    raw_text: str,
    title: str | None = None,
    source_file: str | None = None,
) -> Verbatim:
    verbatim = Verbatim(
        interview_id=interview_id,
        raw_text=raw_text,
        title=title,
        source_file=source_file,
        status="pending",
    )
    session.add(verbatim)
    session.commit()
    session.refresh(verbatim)
    return verbatim


def get_verbatim(session: Session, verbatim_id: int) -> Verbatim | None:
    return session.get(Verbatim, verbatim_id)


def list_verbatims(session: Session, interview_id: int) -> list[Verbatim]:
    stmt = (
        select(Verbatim)
        .where(Verbatim.interview_id == interview_id)
        .order_by(Verbatim.created_at)
    )
    return list(session.scalars(stmt).all())


def list_verbatims_for_mission(session: Session, mission_id: str) -> list[Verbatim]:
    stmt = (
        select(Verbatim)
        .join(Interview, Verbatim.interview_id == Interview.interview_id)
        .where(Interview.mission_id == mission_id)
        .order_by(Verbatim.created_at)
    )
    return list(session.scalars(stmt).all())


def update_verbatim_status(session: Session, verbatim_id: int, status: str) -> Verbatim:
    verbatim = session.get(Verbatim, verbatim_id)
    if verbatim is None:
        raise ValueError(f"Verbatim '{verbatim_id}' not found")
    verbatim.status = status
    session.commit()
    session.refresh(verbatim)
    return verbatim


def update_verbatim(session: Session, verbatim_id: int, **fields) -> Verbatim:
    verbatim = session.get(Verbatim, verbatim_id)
    if verbatim is None:
        raise ValueError(f"Verbatim '{verbatim_id}' not found")
    for key, value in fields.items():
        setattr(verbatim, key, value)
    session.commit()
    session.refresh(verbatim)
    return verbatim


def delete_verbatim(session: Session, verbatim_id: int) -> None:
    verbatim = session.get(Verbatim, verbatim_id)
    if verbatim is not None:
        session.delete(verbatim)
        session.commit()


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def create_extract(
    session: Session,
    verbatim_id: int,
    raw_text: str,
    created_by: str = "AI",
) -> Extract:
    extract = Extract(
        verbatim_id=verbatim_id,
        raw_text=raw_text,
        created_by=created_by,
    )
    session.add(extract)
    session.commit()
    session.refresh(extract)
    return extract


def get_extract(session: Session, extract_id: int) -> Extract | None:
    return session.get(Extract, extract_id)


def list_extracts(session: Session, verbatim_id: int) -> list[Extract]:
    stmt = (
        select(Extract)
        .where(Extract.verbatim_id == verbatim_id)
        .order_by(Extract.created_at)
    )
    return list(session.scalars(stmt).all())


def delete_extract(session: Session, extract_id: int) -> None:
    extract = session.get(Extract, extract_id)
    if extract is not None:
        session.delete(extract)
        session.commit()


# ---------------------------------------------------------------------------
# Interpretation
# ---------------------------------------------------------------------------

def create_interpretation(
    session: Session,
    extract_id: int,
    capacity_id: str | None = None,
    maturity_score: int | None = None,
    direction: str | None = None,
    justification: str | None = None,
) -> Interpretation:
    interp = Interpretation(
        extract_id=extract_id,
        capacity_id=capacity_id,
        maturity_score=maturity_score,
        direction=direction,
        justification=justification,
        status="pending",
    )
    session.add(interp)
    session.commit()
    session.refresh(interp)
    return interp


def get_interpretation(session: Session, interpretation_id: int) -> Interpretation | None:
    return session.get(Interpretation, interpretation_id)


def list_interpretations(session: Session, extract_id: int) -> list[Interpretation]:
    stmt = (
        select(Interpretation)
        .where(Interpretation.extract_id == extract_id)
        .order_by(Interpretation.created_at)
    )
    return list(session.scalars(stmt).all())


def list_interpretations_for_mission(
    session: Session, mission_id: str, status_filter: str | None = None
) -> list[Interpretation]:
    stmt = (
        select(Interpretation)
        .join(Extract, Interpretation.extract_id == Extract.extract_id)
        .join(Verbatim, Extract.verbatim_id == Verbatim.verbatim_id)
        .join(Interview, Verbatim.interview_id == Interview.interview_id)
        .where(Interview.mission_id == mission_id)
    )
    if status_filter:
        stmt = stmt.where(Interpretation.status == status_filter)
    return list(session.scalars(stmt).all())


def validate_interpretation(session: Session, interpretation_id: int) -> Interpretation:
    interp = session.get(Interpretation, interpretation_id)
    if interp is None:
        raise ValueError(f"Interpretation '{interpretation_id}' not found")
    interp.status = "validated"
    interp.validated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(interp)
    return interp


def reject_interpretation(session: Session, interpretation_id: int) -> Interpretation:
    interp = session.get(Interpretation, interpretation_id)
    if interp is None:
        raise ValueError(f"Interpretation '{interpretation_id}' not found")
    interp.status = "rejected"
    interp.validated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(interp)
    return interp


def correct_interpretation(
    session: Session,
    interpretation_id: int,
    corrected_capacity_id: str | None = None,
    corrected_maturity_score: int | None = None,
    corrected_direction: str | None = None,
    corrected_justification: str | None = None,
) -> Interpretation:
    interp = session.get(Interpretation, interpretation_id)
    if interp is None:
        raise ValueError(f"Interpretation '{interpretation_id}' not found")
    interp.status = "corrected"
    interp.corrected_capacity_id = corrected_capacity_id
    interp.corrected_maturity_score = corrected_maturity_score
    interp.corrected_direction = corrected_direction
    interp.corrected_justification = corrected_justification
    interp.validated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(interp)
    return interp


# ---------------------------------------------------------------------------
# MissionReport
# ---------------------------------------------------------------------------

def create_mission_report(
    session: Session,
    mission_id: str,
    content: str | None = None,
    status: str = "draft",
) -> MissionReport:
    report = MissionReport(
        mission_id=mission_id,
        content=content,
        status=status,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def get_mission_report(session: Session, report_id: int) -> MissionReport | None:
    return session.get(MissionReport, report_id)


def get_latest_report(session: Session, mission_id: str) -> MissionReport | None:
    stmt = (
        select(MissionReport)
        .where(MissionReport.mission_id == mission_id)
        .order_by(MissionReport.generated_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def update_mission_report(session: Session, report_id: int, **fields) -> MissionReport:
    report = session.get(MissionReport, report_id)
    if report is None:
        raise ValueError(f"MissionReport '{report_id}' not found")
    for key, value in fields.items():
        setattr(report, key, value)
    session.commit()
    session.refresh(report)
    return report
