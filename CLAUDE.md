# R6 Navigator — CLAUDE.md

## Purpose

Desktop application for IOD consultants to manage the R6 competency framework
and run diagnostic missions (verbatim analysis → interpretation → R6 report).
R6 is a three-level organizational model (Strategic / Organizational / Individual)
with 18 capacities (3 levels × 3 axes × 2 poles). Full CRUD referential, bilingual (fr/en),
DOCX export, Ollama AI generation + 3-judge LLM evaluation + mission diagnostic module.

**This project covers application code only. All data entry is done through the UI.**

---

## Stack

| Layer    | Technology                                    |
|----------|-----------------------------------------------|
| Language | Python 3.11+                                  |
| UI       | PySide6                                       |
| ORM      | SQLAlchemy 2.x (declarative, mapped classes)  |
| DB       | SQLite 3 (single file `r6_navigator.db`)      |
| Export   | python-docx                                   |
| AI gen.  | Ollama (local) via `urllib` — no SDK dep.     |
| Config   | PyYAML (`params.yml` at project root)         |
| Tests    | pytest (63 tests)                             |

---

## Project structure

```
IOD_R6_base_v2/                  # project root
├── params.yml                   # AI config: Ollama model + timeout
├── requirements.txt
├── schema.sql                   # Reference schema (documentation; ORM is authoritative)
├── DOMAIN.md                    # Domain model specification (read before coding)
├── SERVICES.md                  # Services layer API contracts
├── UI.md                        # UI layout and interaction specification
├── TESTS.md                     # Test coverage specification
│
├── cli/
│   ├── populate_db.py           # AI population of the DB (fiche, questions, coaching)
│   ├── translate_db.py          # AI translation of DB content (fr ↔ en)
│   └── compile_ui.py            # Compile .ui files → ui_*.py via pyside6-uic
│
└── r6_navigator/
    ├── axioms.yml               # Foundation of R6 model
    ├── capacities_en.yml        # Canonical English capacity names (application-facing)
    ├── capacities_fr.yml        # Canonical French capacity names (application-facing)
    ├── main.py                  # Entry point: init DB, launch UI
    │
    ├── db/
    │   ├── database.py          # Engine, session factory, init_db() + 3 migrations
    │   └── models.py            # All SQLAlchemy mapped classes (20 tables)
    │
    ├── services/
    │   ├── crud.py              # Navigator CRUD (capacities, questions, items, coaching)
    │   ├── crud_mission.py      # Mission CRUD (mission, interview, verbatim, extract,
    │   │                        #   interpretation, report)
    │   ├── export_docx.py       # DOCX generation (capacities + mission reports)
    │   ├── backup.py            # Save/restore DB (file copy + integrity check)
    │   ├── ai_generate.py       # Ollama generation + translation (5 sections, retry logic)
    │   ├── ai_judge.py          # 3-judge LLM evaluation (parallel threads)
    │   ├── ai_analyze.py        # Mission verbatim analysis + report generation
    │   └── prompt/              # Prompt files (.txt/.json) — use load_prompt(), not str.format()
    │       ├── __init__.py      # load_prompt(name, **kwargs) — safe brace-aware substitution
    │       ├── system_01.txt    # System prompt (English) — R6/Halliday expert role
    │       ├── halliday_rules.json  # Halliday transitivity rules (injected into judge prompts)
    │       ├── generate_fiche.txt
    │       ├── generate_fiche_risque.txt
    │       ├── generate_questions.txt
    │       ├── generate_questions_items.txt
    │       ├── generate_coaching.txt
    │       ├── translate_fiche.txt
    │       ├── translate_questions.txt
    │       ├── translate_observable_items.txt
    │       ├── translate_coaching.txt
    │       ├── analyze_verbatim.txt         # Mission verbatim analysis prompt
    │       ├── generate_mission_report.txt  # Mission report generation prompt
    │       ├── judge_*.txt                  # 9 judge prompts (3 criteria × 3 sections)
    │       └── versions/                   # Archived previous versions of prompts
    │
    ├── maturity_scales/         # Reference Markdown scales for mission verbatim analysis
    │   ├── I6_EQF_Proficiency_Levels_short.md
    │   ├── O6_Maturity_Levels_short.md
    │   └── S6_Maturity_Levels_short.md
    │
    ├── ui/
    │   └── qt/
    │       ├── app.py                  # Main window: composition, signals, language selector
    │       ├── navpanel.py             # Left QTreeWidget: Level → Axis → capacity
    │       ├── detailpanel.py          # Right QTabWidget: isomorphism bar + tab orchestration
    │       ├── tabfiche.py             # Fiche tab: fields + AI workers (fiche, risque)
    │       ├── tabquestions.py         # Questions tab: 2 QTableWidgets + AI workers
    │       ├── tabcoaching.py          # Coaching tab: free-text fields (always editable)
    │       ├── dialogs.py              # Confirm dialogs, DOCX export config dialog
    │       ├── verification_window.py  # 3-judge evaluation results dialog
    │       ├── mission_app.py          # Mission main window (QMainWindow, lazily created)
    │       ├── mission_nav.py          # Mission tree: Mission → Interview
    │       ├── mission_detail.py       # Mission 4-tab orchestrator
    │       ├── mission_tab_info.py     # Mission/interview metadata (edit mode)
    │       ├── mission_tab_verbatim.py # Verbatim editor + import/export + AI analysis
    │       ├── mission_tab_interpretations.py  # Validate/reject/correct interpretations
    │       ├── mission_tab_rapport.py  # Report generation + DOCX export
    │       └── forms/                  # Qt Designer source files — edit in pyside6-designer
    │           ├── tabfiche.ui         # Contains btn_generer + btn_generer_risque
    │           ├── tabquestions.ui     # Contains btn_generer + btn_generer_items + 2 QTableWidgets
    │           ├── tabcoaching.ui
    │           └── ui_*.py             # Generated by pyside6-uic — DO NOT edit manually
    │
    ├── i18n/
    │   ├── __init__.py          # Lang singleton, t("key") helper, current_lang()
    │   ├── fr.json              # French UI strings (incl. mission.* keys)
    │   └── en.json              # English UI strings (incl. mission.* keys)
    │
    └── tests/
        ├── conftest.py          # In-memory DB fixtures (session, session_with_capacities)
        ├── test_crud.py         # 23 tests: capacities, questions, items, coaching, settings
        ├── test_export.py       # 12 tests: DOCX single/bulk/bilingual/flags
        └── test_mission_crud.py # 28 tests: mission CRUD, cascade, status transitions
```

---

## Domain model

See `DOMAIN.md` for the full domain specification. Read it before writing any code.

Key facts:
- A **capacity** is identified by `level_code + str(axis_number) + pole_code` (e.g. `"I1a"`)
- There are exactly **18 canonical capacities** in the standard R6 model
- `is_canonical` flag protects standard capacities from accidental deletion
- All user-visible text is stored in **dedicated translation tables** (i18n pattern):
  one row per `(entity_id, lang)` in `*_translation` tables
- The active language is exposed by `i18n.current_lang()` → `'fr'` or `'en'`
- `coaching` is a 1-to-1 extension of `capacity` (separate table, same PK)
- **Mission entities**: Mission → Interview → Verbatim → Extract → Interpretation (cascade);
  Mission → MissionReport (cascade). `Interpretation.status`: pending/validated/rejected/corrected

---

## Coding conventions

- Type hints on all function signatures
- SQLAlchemy mapped classes as data carriers — no plain dicts crossing layer boundaries
- No raw SQL strings anywhere — use SQLAlchemy ORM exclusively
- No DB access in UI files — persistence through `services/crud.py` or `services/crud_mission.py`
- No business logic in UI files — UI calls services only
- `pathlib.Path` for all file paths
- All user-visible strings through `i18n.t("key")` — no hardcoded labels in UI code
- **Prompt substitution**: always use `load_prompt(name, **kwargs)` from `services/prompt/__init__.py`,
  never `str.format()` on prompt file content — prompt files contain JSON examples with literal `{}`
  that `str.format()` would misinterpret as placeholders
- Commit messages: imperative, English, lowercase (`add docx export config dialog`)

---

## UI conventions

- All detail fields are **read-only by default**
- `[Modifier]` button switches to edit mode (fields become active)
- In edit mode: show `[Enregistrer]` + `[Annuler]`, hide `[Modifier]`
- `[Enregistrer]`: validate → write to DB → refresh tree if label changed → back to read-only
- `[Annuler]`: discard, reload from DB, back to read-only
- Language selector (top-right `QComboBox`, values `["fr", "en"]`): triggers full UI redraw
- `EditGuard` in `ui/qt/app.py` prevents navigating away from unsaved changes (confirm dialog)

### AI generation buttons (navigator)

Each button runs in a background `QThread` — UI stays responsive:

| Button | Tab | Worker class | Function called | Fields populated |
|--------|-----|--------------|-----------------|-----------------|
| `btn_generer` | Fiche | `_GenerateWorker` | `generate_fiche()` | Intitulé, Définition, Fonction centrale |
| `btn_generer_risque` | Fiche | `_GenerateRisqueWorker` | `generate_fiche_risque()` | Risque si insuffisant, Risque si excessif |
| `btn_generer` | Questions | `_GenerateWorker` | `generate_questions()` | 10 interview questions |
| `btn_generer_items` | Questions | `_GenerateItemsWorker` | `generate_questions_items()` | 4×5 observable items (OK/EXC/DEP/INS) |

- Generation language matches the active UI language (`current_lang()`)
- User reviews generated content, then saves manually via `[Modifier]` → `[Enregistrer]`
- Canonical name resolution: `capacities_fr.yml[capacity_id]` (or `capacities_en.yml` for EN)
- On network/LLM error: retried up to 3 times, 2-second delay (`_OLLAMA_MAX_RETRIES`)

### AI buttons (missions)

| Button | Tab | Worker class | Function called |
|--------|-----|--------------|-----------------|
| `_btn_analyze` | Verbatim | `_AnalyzeWorker` | `analyze_verbatim()` |
| `_btn_generate_report` | Rapport | `_ReportWorker` | `generate_mission_report()` |

### Judge ([Juger] toolbar button)

Opens `VerificationWindow` for the current capacity. Runs 3 parallel LLM threads
(axioms R6, Halliday, level/pole coherence) via `ai_judge.py`. Uses `ollama.model_judge`.

### CLI generation (`cli/populate_db.py`)

Five independent sections:

| Section | Function | Fields populated |
|---------|----------|-----------------|
| `fiche` | `generate_fiche()` | `label`, `definition`, `central_function` |
| `risque` | `generate_fiche_risque()` | `risk_insufficient`, `risk_excessive` |
| `questions` | `generate_questions()` | Interview questions (10 per capacity) |
| `items` | `generate_questions_items()` | Observable items 4×5 (OK/EXC/DEP/INS) |
| `coaching` | `generate_coaching()` | Coaching fields |

Use `--skip SECTION` to omit sections, `--capacity ID…` to target specific capacities.

---

## params.yml

Located at the **project root**. Contains:

| Key | Description |
|-----|-------------|
| `ollama.url` | Ollama API base URL (default `http://localhost:11434`) |
| `ollama.model` | Model for generation (e.g. `mistral-large-3:675b-cloud`) |
| `ollama.model_judge` | Model for evaluation / judge (e.g. `kimi-k2-thinking:cloud`) |
| `ollama.timeout` | HTTP timeout in seconds |

The system prompt is read from `r6_navigator/services/prompt/system_01.txt`
via `_load_system_prompt()` — it is **not** in `params.yml`.

`ai_generate.py` reads `params.yml` via `Path(__file__).parent.parent.parent / "params.yml"`.

Canonical capacity names: `r6_navigator/capacities_fr.yml` and `r6_navigator/capacities_en.yml`.

---

## UI architecture — how `.ui` files, generated code, and logic classes fit together

### Layer stack

```
forms/*.ui          Qt Designer XML — edit with pyside6-designer, never by hand
    │
    ▼ pyside6-uic (compile step, run manually or via cli/compile_ui.py)
forms/ui_*.py       Generated Python — widget declarations + setupUi() — do not edit
    │
    ▼ multiple inheritance mixin
ui/qt/*.py          Logic classes — business behaviour, signal wiring, DB calls
```

The **mission UI files** (`mission_*.py`) do **not** use `.ui` source files — widgets are
constructed programmatically in `_build_ui()` methods.

### Mixin pattern (navigator tabs only)

```python
class TabFiche(QWidget, Ui_TabFiche):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)   # instantiates all widgets defined in tabfiche.ui
        ...
```

`setupUi(self)` makes every widget declared in the `.ui` file accessible as
`self.<objectName>` (e.g. `self.btn_generer`, `self.text_definition`).

### Recompiling `.ui` files

```bash
pyside6-uic r6_navigator/ui/qt/forms/tabfiche.ui \
    -o r6_navigator/ui/qt/forms/ui_tabfiche.py
# Or: python cli/compile_ui.py
```

### Session factory injection

`R6NavigatorApp` (in `app.py`) creates a single `session_factory` and injects it:

```python
self.tab_fiche.set_session_factory(self.session_factory)
```

Each component stores it and opens short-lived sessions on demand:
```python
with self.session_factory() as session:
    ...
```

`MissionApp` receives the same `session_factory` from `R6NavigatorApp._on_open_missions()`.

### Population flow (capacity selection → screen)

```
NavPanel.tree (click)
    → NavPanel._on_item_clicked()
        → emit capacity_selected(capacity_id)       # Signal(str)

R6NavigatorApp._on_capacity_selected(capacity_id)
    → detail_panel.load_capacity(capacity_id)       # updates isomorphism bar
    → tab_fiche.load_capacity(dim)
    → tab_questions.load_capacity(dim)
    → tab_coaching.load_capacity(dim)
```

### Language switching / redraw

```
app.redraw_ui()
    → nav_panel.redraw()        # _retranslate() + _populate_tree()
    → detail_panel.redraw()     # _retranslate() + re-labels tab headers
    → tab_fiche.redraw()        # _retranslate() + _load_capacity() with current dim
    → tab_questions.redraw()
    → tab_coaching.redraw()
```

---

## DB migration

`init_db()` in `database.py` runs three idempotent migrations after `create_all()`:

1. **`_migrate_to_translation_tables()`** — detects old bilingual columns (`label_fr`, etc.) via
   `PRAGMA table_info`, copies data into `*_translation` tables, rebuilds affected tables to drop
   legacy columns. No-op on fresh DB or already-migrated DB.

2. **`_migrate_drop_observable_column()`** — drops the `observable` column from
   `capacity_translation` if it exists (SQLite full table rebuild). No-op if absent.

3. **`_migrate_add_mission_tables()`** — detects a legacy mission schema where the PK was
   a string `mission_id` (old refactoring). Checks for an integer `id` column via
   `PRAGMA table_info(mission)`; if absent, drops all 6 mission tables and recreates them
   with the current schema via `Base.metadata.create_all(engine, tables=[...])`. No-op if
   current schema already present or mission tables don't exist yet.

All three migrations run transparently on application startup and are safe to run repeatedly.

---

## Prompt versioning rule

**ALWAYS archive the current prompt before modifying it.**
Archive location: `r6_navigator/services/prompt/versions/`
Naming: `<prompt_name>_vX.Y.txt` (increment last version found in `versions/`)
Do this BEFORE editing the `.txt` file, never after.

---

## Not implemented

- Structural relationship visualization (radar, matrix, graph)
- Multi-user or network sync
- Change history / versioning
