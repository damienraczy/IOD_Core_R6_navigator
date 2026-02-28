-- =============================================================================
-- R6 Navigator — Reference Schema
-- SQLite 3
-- Version : 2.1  /  2026-02-26
--
-- DOCUMENTATION ONLY.
-- The SQLAlchemy ORM (db/models.py) is the authoritative source for table
-- structure. This file is kept for reference and external tooling.
-- Do not run this file to initialize the DB — use db/database.py:init_db().
--
-- Bilingual architecture: text content lives in *_translations tables.
-- One row per (entity_id, lang). Active language resolved at runtime via
-- i18n.current_lang() → 'fr' | 'en'.
--
-- Ontological foundation: r6_navigator/axioms.yml
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Reference tables
-- Populated by init_db(). Never modified by the user through the UI.
-- -----------------------------------------------------------------------------

CREATE TABLE level (
    level_code          TEXT    PRIMARY KEY,    -- 'S' | 'O' | 'I'
    display_order       INTEGER NOT NULL,
    -- [D1] Structural metadata from axioms.yml (non-translatable)
    unit                TEXT,                   -- e.g. 'Individual Competencies'
    measurement_scale   TEXT                    -- e.g. 'I6_EQF_Proficiency_Levels.md'
);

CREATE TABLE axis (
    axis_number         INTEGER PRIMARY KEY,    -- 1 | 2 | 3
    -- [D2] Structural metadata from axioms.yml
    name                TEXT,                   -- 'Direction' | 'Coordination' | 'Realization'
    tension_pole_a      TEXT,                   -- e.g. 'Stability'
    tension_pole_b      TEXT                    -- e.g. 'Change'
);

CREATE TABLE poles (
    pole_code           TEXT    PRIMARY KEY,    -- 'a' | 'b'
    -- [D3] Structural metadata from axioms.yml
    name                TEXT,                   -- 'Agentive' | 'Instrumental'
    characteristics     TEXT                    -- e.g. 'Stabilizing / Individualizing / Direct'
);

-- [E1] observable_category: applicative extension, not part of the R6 ontological model
-- (axioms.yml). Defines display categories for observable behaviors collected per capacity.
--   OK  = effective observable behaviors
--   EXC = excess-risk observable behaviors
--   DEP = insufficiency-risk observable behaviors
--   INS = coaching indicators
CREATE TABLE observable_category (
    category_code   TEXT PRIMARY KEY,   -- 'OK' | 'EXC' | 'DEP' | 'INS'
    display_order   INTEGER NOT NULL
);


-- -----------------------------------------------------------------------------
-- capacity
-- Core entity. Structural identity + metadata only. No text content.
-- capacity_id is computed: level_code || axis_number || pole_code (e.g. 'I1a')
--
-- Vertical relations between capacities (enables / supports / emerges_from)
-- are defined in axioms.yml but are NOT stored here: they are fully derivable
-- from the structural triple (level_code, axis_number, pole_code) shared across
-- adjacent levels. The isomorphism bar in detailpanel.py computes them at runtime.
-- -----------------------------------------------------------------------------

CREATE TABLE capacity (
    capacity_id    TEXT    PRIMARY KEY,

    -- Structural identity (never editable after creation)
    level_code      TEXT    NOT NULL REFERENCES level(level_code),
    axis_number     INTEGER NOT NULL REFERENCES axis(axis_number),
    pole_code       TEXT    NOT NULL REFERENCES poles(pole_code),

    -- Metadata
    is_canonical    INTEGER NOT NULL DEFAULT 1
                        CHECK (is_canonical IN (0, 1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),

    UNIQUE (level_code, axis_number, pole_code)
);


-- -----------------------------------------------------------------------------
-- capacity_translation
-- Text content for a capacity in one language.
-- PK: (capacity_id, lang)
-- -----------------------------------------------------------------------------

CREATE TABLE capacity_translation (
    capacity_id            TEXT NOT NULL REFERENCES capacity(capacity_id) ON DELETE CASCADE,
    lang                    TEXT NOT NULL,   -- 'fr' | 'en'

    label                   TEXT NOT NULL DEFAULT '',
    definition              TEXT,
    central_function        TEXT,
    observable              TEXT,
    risk_insufficient       TEXT,
    risk_excessive          TEXT,

    PRIMARY KEY (capacity_id, lang)
);


-- -----------------------------------------------------------------------------
-- question
-- Ordered list of interview / diagnostic question per capacity.
-- No text columns — text lives in question_translation.
-- -----------------------------------------------------------------------------

CREATE TABLE question (
    question_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    capacity_id    TEXT    NOT NULL REFERENCES capacity(capacity_id)
                                ON DELETE CASCADE,
    display_order   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_question_capacity ON question(capacity_id);


-- -----------------------------------------------------------------------------
-- question_translation
-- PK: (question_id, lang)
-- -----------------------------------------------------------------------------

CREATE TABLE question_translation (
    question_id     INTEGER NOT NULL REFERENCES question(question_id) ON DELETE CASCADE,
    lang            TEXT    NOT NULL,   -- 'fr' | 'en'
    text            TEXT    NOT NULL DEFAULT '',

    PRIMARY KEY (question_id, lang)
);


-- -----------------------------------------------------------------------------
-- observable_item
-- Categorized observable behaviors / manifestations per capacity.
-- No text columns — text lives in observable_item_translation.
-- -----------------------------------------------------------------------------

CREATE TABLE observable_item (
    item_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    capacity_id    TEXT    NOT NULL REFERENCES capacity(capacity_id)
                                ON DELETE CASCADE,
    category_code   TEXT    NOT NULL REFERENCES observable_category(category_code),
    display_order   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_observable_item_capacity  ON observable_item(capacity_id);
CREATE INDEX idx_observable_item_category   ON observable_item(capacity_id, category_code);


-- -----------------------------------------------------------------------------
-- observable_item_translation
-- PK: (item_id, lang)
-- -----------------------------------------------------------------------------

CREATE TABLE observable_item_translation (
    item_id         INTEGER NOT NULL REFERENCES observable_item(item_id) ON DELETE CASCADE,
    lang            TEXT    NOT NULL,   -- 'fr' | 'en'
    text            TEXT    NOT NULL DEFAULT '',

    PRIMARY KEY (item_id, lang)
);


-- -----------------------------------------------------------------------------
-- coaching
-- Coaching header row: 1-to-1 with capacity.
-- Created automatically when a capacity is created.
-- Text content lives in coaching_translation.
-- -----------------------------------------------------------------------------

CREATE TABLE coaching (
    capacity_id    TEXT PRIMARY KEY
                        REFERENCES capacity(capacity_id)
                        ON DELETE CASCADE,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);


-- -----------------------------------------------------------------------------
-- coaching_translation
-- PK: (capacity_id, lang)
-- -----------------------------------------------------------------------------

CREATE TABLE coaching_translation (
    capacity_id            TEXT NOT NULL REFERENCES coaching(capacity_id) ON DELETE CASCADE,
    lang                    TEXT NOT NULL,   -- 'fr' | 'en'

    reflection_themes       TEXT,
    intervention_levers     TEXT,
    recommended_missions    TEXT,

    PRIMARY KEY (capacity_id, lang)
);


-- -----------------------------------------------------------------------------
-- app_setting
-- Persisted application state (key-value).
-- -----------------------------------------------------------------------------

CREATE TABLE app_setting (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
