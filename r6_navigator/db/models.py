from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Reference tables (read-only at runtime, seeded by init_db)
# ---------------------------------------------------------------------------

class Level(Base):
    __tablename__ = "level"

    level_code: Mapped[str] = mapped_column(String, primary_key=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str | None] = mapped_column(Text)
    measurement_scale: Mapped[str | None] = mapped_column(Text)

    capacities: Mapped[list[Capacity]] = relationship(back_populates="level")


class Axis(Base):
    __tablename__ = "axis"

    axis_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    tension_pole_a: Mapped[str | None] = mapped_column(Text)
    tension_pole_b: Mapped[str | None] = mapped_column(Text)

    capacities: Mapped[list[Capacity]] = relationship(back_populates="axis")


class Pole(Base):
    __tablename__ = "pole"

    pole_code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    characteristics: Mapped[str | None] = mapped_column(Text)

    capacities: Mapped[list[Capacity]] = relationship(back_populates="pole")


class ObservableCategory(Base):
    __tablename__ = "observable_category"

    category_code: Mapped[str] = mapped_column(String, primary_key=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    items: Mapped[list[ObservableItem]] = relationship(back_populates="category")


class AppSetting(Base):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


# ---------------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------------

class Capacity(Base):
    __tablename__ = "capacity"
    __table_args__ = (UniqueConstraint("level_code", "axis_number", "pole_code"),)

    capacity_id: Mapped[str] = mapped_column(String, primary_key=True)
    level_code: Mapped[str] = mapped_column(
        String, ForeignKey("level.level_code"), nullable=False
    )
    axis_number: Mapped[int] = mapped_column(
        Integer, ForeignKey("axis.axis_number"), nullable=False
    )
    pole_code: Mapped[str] = mapped_column(
        String, ForeignKey("pole.pole_code"), nullable=False
    )
    is_canonical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    level: Mapped[Level] = relationship(back_populates="capacities")
    axis: Mapped[Axis] = relationship(back_populates="capacities")
    pole: Mapped[Pole] = relationship(back_populates="capacities")
    translations: Mapped[list[CapacityTranslation]] = relationship(
        back_populates="capacity", cascade="all, delete-orphan"
    )
    questions: Mapped[list[Question]] = relationship(
        back_populates="capacity",
        cascade="all, delete-orphan",
        order_by="Question.display_order",
    )
    observable_items: Mapped[list[ObservableItem]] = relationship(
        back_populates="capacity", cascade="all, delete-orphan"
    )
    coaching: Mapped[Coaching | None] = relationship(
        back_populates="capacity", cascade="all, delete-orphan", uselist=False
    )


class CapacityTranslation(Base):
    __tablename__ = "capacity_translation"

    capacity_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("capacity.capacity_id", ondelete="CASCADE"),
        primary_key=True,
    )
    lang: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    definition: Mapped[str | None] = mapped_column(Text)
    central_function: Mapped[str | None] = mapped_column(Text)
    risk_insufficient: Mapped[str | None] = mapped_column(Text)
    risk_excessive: Mapped[str | None] = mapped_column(Text)

    capacity: Mapped[Capacity] = relationship(back_populates="translations")


class Question(Base):
    __tablename__ = "question"

    question_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    capacity_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("capacity.capacity_id", ondelete="CASCADE"),
        nullable=False,
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    capacity: Mapped[Capacity] = relationship(back_populates="questions")
    translations: Mapped[list[QuestionTranslation]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class QuestionTranslation(Base):
    __tablename__ = "question_translation"

    question_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("question.question_id", ondelete="CASCADE"),
        primary_key=True,
    )
    lang: Mapped[str] = mapped_column(String, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    question: Mapped[Question] = relationship(back_populates="translations")


class ObservableItem(Base):
    __tablename__ = "observable_item"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    capacity_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("capacity.capacity_id", ondelete="CASCADE"),
        nullable=False,
    )
    category_code: Mapped[str] = mapped_column(
        String,
        ForeignKey("observable_category.category_code"),
        nullable=False,
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    capacity: Mapped[Capacity] = relationship(back_populates="observable_items")
    category: Mapped[ObservableCategory] = relationship(back_populates="items")
    translations: Mapped[list[ObservableItemTranslation]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class ObservableItemTranslation(Base):
    __tablename__ = "observable_item_translation"

    item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("observable_item.item_id", ondelete="CASCADE"),
        primary_key=True,
    )
    lang: Mapped[str] = mapped_column(String, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    item: Mapped[ObservableItem] = relationship(back_populates="translations")


class Coaching(Base):
    __tablename__ = "coaching"

    capacity_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("capacity.capacity_id", ondelete="CASCADE"),
        primary_key=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    capacity: Mapped[Capacity] = relationship(back_populates="coaching")
    translations: Mapped[list[CoachingTranslation]] = relationship(
        back_populates="coaching", cascade="all, delete-orphan"
    )


class CoachingTranslation(Base):
    __tablename__ = "coaching_translation"

    capacity_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("coaching.capacity_id", ondelete="CASCADE"),
        primary_key=True,
    )
    lang: Mapped[str] = mapped_column(String, primary_key=True)
    reflection_themes: Mapped[str | None] = mapped_column(Text)
    intervention_levers: Mapped[str | None] = mapped_column(Text)
    recommended_missions: Mapped[str | None] = mapped_column(Text)

    coaching: Mapped[Coaching] = relationship(back_populates="translations")


# ---------------------------------------------------------------------------
# Mission module entities
# ---------------------------------------------------------------------------

class Mission(Base):
    __tablename__ = "mission"

    mission_id: Mapped[str] = mapped_column(String, primary_key=True)
    client_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    interviews: Mapped[list[Interview]] = relationship(
        back_populates="mission", cascade="all, delete-orphan"
    )
    reports: Mapped[list[MissionReport]] = relationship(
        back_populates="mission", cascade="all, delete-orphan"
    )


class Interview(Base):
    __tablename__ = "interview"

    interview_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(
        String, ForeignKey("mission.mission_id", ondelete="CASCADE"), nullable=False
    )
    interviewee_name: Mapped[str] = mapped_column(Text, nullable=False)
    interviewee_role: Mapped[str | None] = mapped_column(Text)
    interviewee_level: Mapped[str | None] = mapped_column(String)
    interview_date: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    mission: Mapped[Mission] = relationship(back_populates="interviews")
    verbatims: Mapped[list[Verbatim]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )


class Verbatim(Base):
    __tablename__ = "verbatim"

    verbatim_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interview_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("interview.interview_id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_file: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")

    interview: Mapped[Interview] = relationship(back_populates="verbatims")
    extracts: Mapped[list[Extract]] = relationship(
        back_populates="verbatim", cascade="all, delete-orphan"
    )


class Extract(Base):
    __tablename__ = "extract"

    extract_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verbatim_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("verbatim.verbatim_id", ondelete="CASCADE"), nullable=False
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String, nullable=False, default="AI")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    verbatim: Mapped[Verbatim] = relationship(back_populates="extracts")
    interpretations: Mapped[list[Interpretation]] = relationship(
        back_populates="extract", cascade="all, delete-orphan"
    )


class Interpretation(Base):
    __tablename__ = "interpretation"

    interpretation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    extract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("extract.extract_id", ondelete="CASCADE"), nullable=False
    )
    capacity_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("capacity.capacity_id"), nullable=True
    )
    maturity_score: Mapped[int | None] = mapped_column(Integer)
    direction: Mapped[str | None] = mapped_column(String)
    justification: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    corrected_capacity_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("capacity.capacity_id"), nullable=True
    )
    corrected_maturity_score: Mapped[int | None] = mapped_column(Integer)
    corrected_direction: Mapped[str | None] = mapped_column(String)
    corrected_justification: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime)

    extract: Mapped[Extract] = relationship(back_populates="interpretations")
    capacity: Mapped[Capacity | None] = relationship(foreign_keys=[capacity_id])
    corrected_capacity: Mapped[Capacity | None] = relationship(foreign_keys=[corrected_capacity_id])


class MissionReport(Base):
    __tablename__ = "mission_report"

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(
        String, ForeignKey("mission.mission_id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")

    mission: Mapped[Mission] = relationship(back_populates="reports")
