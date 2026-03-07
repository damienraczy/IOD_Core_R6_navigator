from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import sessionmaker

from r6_navigator.db.models import (
    AppSetting,
    Axis,
    Base,
    Capacity,
    CapacityTranslation,
    Coaching,
    Level,
    ObservableCategory,
    Pole,
)


# ---------------------------------------------------------------------------
# Engine / session factory
# ---------------------------------------------------------------------------

def get_engine(db_path: Path) -> Engine:
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return engine


def get_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# DB initialisation
# ---------------------------------------------------------------------------

def init_db(engine: Engine, seed_capacities: bool = True) -> None:
    Base.metadata.create_all(engine)
    _migrate_to_translation_tables(engine)
    _migrate_drop_observable_column(engine)
    _migrate_add_mission_tables(engine)
    _migrate_add_halliday_columns(engine)
    _migrate_drop_interview_level_code(engine)
    _seed_reference_data(engine)
    if seed_capacities:
        _seed_capacities(engine)


# ---------------------------------------------------------------------------
# Migration — legacy _fr/_en bilingual columns → *_translation tables
# ---------------------------------------------------------------------------

def _migrate_to_translation_tables(engine: Engine) -> None:
    """Migrates legacy bilingual columns to *_translation tables. No-op on fresh DB."""
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(capacity)")).fetchall()
        if not any(r[1] == "label_fr" for r in rows):
            return  # Fresh v2 DB or already migrated

    # Legacy schema detected — use raw DBAPI connection to allow PRAGMA outside transaction
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("PRAGMA foreign_keys = OFF")

        # Copy capacity text content into capacity_translation
        for lang in ("fr", "en"):
            cur.execute(
                "INSERT OR IGNORE INTO capacity_translation "
                "(capacity_id, lang, label, definition, central_function, "
                " observable, risk_insufficient, risk_excessive) "
                f"SELECT capacity_id, ?, "
                f"  COALESCE(label_{lang}, ''), definition_{lang}, central_function_{lang}, "
                f"  observable_behaviors_{lang}, risk_insufficient_{lang}, risk_excessive_{lang} "
                "FROM capacity",
                (lang,),
            )

        # Rebuild capacity without legacy columns (SQLite requires full table rebuild)
        cur.execute("""
            CREATE TABLE capacity_v2 (
                capacity_id  TEXT PRIMARY KEY,
                level_code   TEXT NOT NULL REFERENCES level(level_code),
                axis_number  INTEGER NOT NULL REFERENCES axis(axis_number),
                pole_code    TEXT NOT NULL REFERENCES pole(pole_code),
                is_canonical INTEGER NOT NULL DEFAULT 1
                                 CHECK (is_canonical IN (0, 1)),
                created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (level_code, axis_number, pole_code)
            )
        """)
        cur.execute(
            "INSERT INTO capacity_v2 "
            "  SELECT capacity_id, level_code, axis_number, pole_code, "
            "         is_canonical, created_at, updated_at FROM capacity"
        )
        cur.execute("DROP TABLE capacity")
        cur.execute("ALTER TABLE capacity_v2 RENAME TO capacity")

        cur.execute("PRAGMA foreign_keys = ON")
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


# ---------------------------------------------------------------------------
# Migration — drop legacy observable column from capacity_translation
# ---------------------------------------------------------------------------

def _migrate_drop_observable_column(engine: Engine) -> None:
    """Drops the observable column from capacity_translation if it exists. No-op otherwise."""
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(capacity_translation)")).fetchall()
        if not any(r[1] == "observable" for r in rows):
            return  # Already migrated or fresh DB

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("PRAGMA foreign_keys = OFF")
        cur.execute("""
            CREATE TABLE capacity_translation_v2 (
                capacity_id TEXT NOT NULL
                    REFERENCES capacity(capacity_id) ON DELETE CASCADE,
                lang TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                definition TEXT,
                central_function TEXT,
                risk_insufficient TEXT,
                risk_excessive TEXT,
                PRIMARY KEY (capacity_id, lang)
            )
        """)
        cur.execute("""
            INSERT INTO capacity_translation_v2
                (capacity_id, lang, label, definition, central_function,
                 risk_insufficient, risk_excessive)
            SELECT capacity_id, lang, label, definition, central_function,
                   risk_insufficient, risk_excessive
            FROM capacity_translation
        """)
        cur.execute("DROP TABLE capacity_translation")
        cur.execute("ALTER TABLE capacity_translation_v2 RENAME TO capacity_translation")
        cur.execute("PRAGMA foreign_keys = ON")
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


# ---------------------------------------------------------------------------
# Migration — add mission tables if absent
# ---------------------------------------------------------------------------

def _migrate_add_mission_tables(engine: Engine) -> None:
    """Rebuilds mission tables if they have an incompatible legacy schema.

    The previous schema used ``mission_id`` (string PK); the current schema
    uses ``id`` (integer PK). If the old schema is detected, all six mission
    tables are dropped and recreated via ``create_all``.
    No-op if the current schema is already in place.
    """
    _MISSION_TABLES = [
        "interpretation", "extract", "verbatim", "interview",
        "mission_report", "mission",
    ]

    with engine.connect() as conn:
        existing = {row[0] for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )}
        if "mission" not in existing:
            return  # create_all already ran — tables were just created

        # Check if the schema is current (has integer `id` column)
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(mission)"))}
        if "id" in cols:
            return  # Already on new schema — nothing to do

    # Legacy schema detected — drop all mission-related tables and recreate
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("PRAGMA foreign_keys = OFF")
        for tbl in _MISSION_TABLES:
            cur.execute(f"DROP TABLE IF EXISTS {tbl}")
        cur.execute("PRAGMA foreign_keys = ON")
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()

    # Recreate with current schema
    from r6_navigator.db.models import Base, Extract, Interpretation, Interview, Mission, MissionReport, Verbatim
    tables = [
        Base.metadata.tables[t] for t in
        ("mission", "interview", "verbatim", "extract", "interpretation", "mission_report")
    ]
    Base.metadata.create_all(engine, tables=tables)


# ---------------------------------------------------------------------------
# Migration — add halliday columns to extract table
# ---------------------------------------------------------------------------

def _migrate_add_halliday_columns(engine: Engine) -> None:
    """Adds halliday_note and halliday_ok columns to extract table if absent. No-op if present."""
    with engine.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(extract)")).fetchall()}
        if "halliday_note" not in cols:
            conn.execute(text("ALTER TABLE extract ADD COLUMN halliday_note TEXT"))
        if "halliday_ok" not in cols:
            conn.execute(text("ALTER TABLE extract ADD COLUMN halliday_ok BOOLEAN"))
        conn.commit()


# ---------------------------------------------------------------------------
# Migration — drop level_code column from interview table
# ---------------------------------------------------------------------------

def _migrate_drop_interview_level_code(engine: Engine) -> None:
    """Drops the level_code column from the interview table if present. No-op if absent."""
    with engine.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(interview)")).fetchall()}
        if "level_code" not in cols:
            return
        conn.execute(text("ALTER TABLE interview DROP COLUMN level_code"))
        conn.commit()


# ---------------------------------------------------------------------------
# Reference data seeding
# ---------------------------------------------------------------------------

_LEVELS = [
    Level(
        level_code="S",
        display_order=1,
        unit="Strategic Pivot Logics",
        measurement_scale="S6_Maturity_Levels_and_Learning_Loops.md",
    ),
    Level(
        level_code="O",
        display_order=2,
        unit="Organizational Capabilities",
        measurement_scale="O6_Maturity_Levels.md",
    ),
    Level(
        level_code="I",
        display_order=3,
        unit="Individual Competencies",
        measurement_scale="I6_EQF_Proficiency_Levels.md",
    ),
]

_AXES = [
    Axis(axis_number=1, name="Direction", tension_pole_a="Stability", tension_pole_b="Change"),
    Axis(axis_number=2, name="Coordination", tension_pole_a="Autonomy", tension_pole_b="Interdependence"),
    Axis(axis_number=3, name="Realization", tension_pole_a="Direct", tension_pole_b="Mediated"),
]

_POLES = [
    Pole(pole_code="a", name="Agentive", characteristics="Stabilizing / Individualizing / Direct"),
    Pole(pole_code="b", name="Instrumental", characteristics="Transforming / Collectivizing / Mediated"),
]

_OBSERVABLE_CATEGORIES = [
    ObservableCategory(category_code="OK", display_order=1),
    ObservableCategory(category_code="EXC", display_order=2),
    ObservableCategory(category_code="DEP", display_order=3),
    ObservableCategory(category_code="INS", display_order=4),
]

_DEFAULT_SETTINGS = [
    ("active_language", "fr"),
    ("last_capacity_id", ""),
]

# 18 canonical capacities: (level_code, axis_number, pole_code)
_CANONICAL_CAPACITIES: list[tuple[str, int, str]] = [
    ("S", 1, "a"), ("S", 1, "b"),
    ("S", 2, "a"), ("S", 2, "b"),
    ("S", 3, "a"), ("S", 3, "b"),
    ("O", 1, "a"), ("O", 1, "b"),
    ("O", 2, "a"), ("O", 2, "b"),
    ("O", 3, "a"), ("O", 3, "b"),
    ("I", 1, "a"), ("I", 1, "b"),
    ("I", 2, "a"), ("I", 2, "b"),
    ("I", 3, "a"), ("I", 3, "b"),
]


def _seed_reference_data(engine: Engine) -> None:
    factory = get_session_factory(engine)
    with factory() as session:
        for obj in [*_LEVELS, *_AXES, *_POLES, *_OBSERVABLE_CATEGORIES]:
            session.merge(obj)

        # AppSetting: only insert defaults — never overwrite user-changed values
        for key, default_value in _DEFAULT_SETTINGS:
            if session.get(AppSetting, key) is None:
                session.add(AppSetting(key=key, value=default_value))

        session.commit()


def _seed_capacities(engine: Engine) -> None:
    """Seeds the 18 canonical Capacity rows with a stub FR translation and empty Coaching."""
    factory = get_session_factory(engine)
    with factory() as session:
        for level_code, axis_number, pole_code in _CANONICAL_CAPACITIES:
            capacity_id = f"{level_code}{axis_number}{pole_code}"
            if session.get(Capacity, capacity_id) is not None:
                continue  # Already seeded — idempotent

            session.add(Capacity(
                capacity_id=capacity_id,
                level_code=level_code,
                axis_number=axis_number,
                pole_code=pole_code,
                is_canonical=True,
            ))
            session.add(CapacityTranslation(
                capacity_id=capacity_id,
                lang="fr",
                label=capacity_id,
            ))
            session.add(Coaching(capacity_id=capacity_id))

        session.commit()
