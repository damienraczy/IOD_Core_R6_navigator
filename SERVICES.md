# R6 Navigator — Services Specification

## General rules

- Navigator CRUD goes through `services/crud.py`; mission CRUD goes through `services/crud_mission.py`
- Services receive and return **SQLAlchemy model instances** or Python primitives
- Services never import anything from `ui/`
- Services never construct UI strings (use i18n keys, not translated labels)
- All write operations are wrapped in a session `commit` / `rollback`

---

## services/crud.py

### Translations — Capacity

```python
def get_capacity_translation(session, capacity_id: str, lang: str) -> CapacityTranslation | None

def upsert_capacity_translation(session, capacity_id: str, lang: str,
                                  **fields) -> CapacityTranslation
    # fields: label, definition, central_function,
    #         risk_insufficient, risk_excessive
    # Creates if (capacity_id, lang) does not exist; updates if it does.
```

### Translations — Question

```python
def get_question_translation(session, question_id: int, lang: str) -> QuestionTranslation | None

def upsert_question_translation(session, question_id: int, lang: str,
                                 **fields) -> QuestionTranslation
    # fields: text
```

### Translations — ObservableItem

```python
def get_observable_item_translation(session, item_id: int, lang: str) -> ObservableItemTranslation | None

def upsert_observable_item_translation(session, item_id: int, lang: str,
                                        **fields) -> ObservableItemTranslation
    # fields: text
```

### Translations — Coaching

```python
def get_coaching_translation(session, capacity_id: str, lang: str) -> CoachingTranslation | None

def upsert_coaching_translation(session, capacity_id: str, lang: str,
                                 **fields) -> CoachingTranslation
    # fields: reflection_themes, intervention_levers, recommended_missions
    # Also ensures the parent Coaching row exists (creates it if missing).
```

---

### Capacities

```python
def get_all_capacities(session) -> list[Capacity]
    # Returns all capacities ordered by level display_order, axis_number, pole_code

def get_capacity(session, capacity_id: str) -> Capacity | None

def create_capacity(session, level_code: str, axis_number: int, pole_code: str,
                     label: str, lang: str = 'fr',
                     is_canonical: bool = True,
                     **translation_fields) -> Capacity
    # Computes capacity_id, creates Capacity + CapacityTranslation + empty Coaching.
    # translation_fields are written to CapacityTranslation (e.g. definition=...).
    # Raises ValueError if capacity_id already exists or label is empty.

def update_capacity(session, capacity_id: str, **fields) -> Capacity
    # Updates only structural metadata (e.g. is_canonical).
    # Raises ValueError if attempting to change level_code, axis_number, pole_code.
    # Text content must be updated via upsert_capacity_translation().

def delete_capacity(session, capacity_id: str) -> None
    # Cascades to questions, observable_items, coaching and all translation rows.
```

### Questions

```python
def get_questions(session, capacity_id: str) -> list[Question]
    # Ordered by display_order

def create_question(session, capacity_id: str, text: str, lang: str = 'fr') -> Question
    # Creates Question + QuestionTranslation for the given language.

def update_question(session, question_id: int, **fields) -> Question
    # Updates metadata (display_order). Text must go through upsert_question_translation().

def delete_question(session, question_id: int) -> None

def reorder_questions(session, capacity_id: str, ordered_ids: list[int]) -> None
    # Reassigns display_order values based on the provided id sequence
```

### ObservableItems

```python
def get_observable_items(session, capacity_id: str) -> list[ObservableItem]
    # Ordered by category display_order then item display_order

def get_observable_items_by_category(session, capacity_id: str,
                                     category_code: str) -> list[ObservableItem]

def create_observable_item(session, capacity_id: str, category_code: str,
                            text: str, lang: str = 'fr') -> ObservableItem
    # Creates ObservableItem + ObservableItemTranslation for the given language.

def update_observable_item(session, item_id: int, **fields) -> ObservableItem
    # Updates metadata. Text must go through upsert_observable_item_translation().

def delete_observable_item(session, item_id: int) -> None

def reorder_observable_items(session, category_code: str,
                              ordered_ids: list[int]) -> None
```

### Coaching

```python
def get_coaching(session, capacity_id: str) -> Coaching | None
    # Returns the Coaching header row (no text fields).

def upsert_coaching(session, capacity_id: str, **fields) -> Coaching
    # Creates or updates the Coaching header row (metadata only).
    # For text content use upsert_coaching_translation().
```

### Settings

```python
def get_setting(session, key: str) -> str | None

def set_setting(session, key: str, value: str) -> None
```

### Reference data

```python
def get_levels(session) -> list[Level]
    # Ordered by display_order

def get_axes(session) -> list[Axis]
    # Ordered by axis_number

def get_observable_categories(session) -> list[ObservableCategory]
    # Ordered by display_order
```

---

## services/crud_mission.py

All functions receive a live SQLAlchemy session as first argument.
All writes call `session.commit()` before returning.

### Mission

```python
def get_all_missions(session) -> list[Mission]
    # Ordered by created_at DESC

def get_mission(session, mission_id: int) -> Mission | None

def create_mission(session, name: str, client: str = "", consultant: str = "",
                   start_date: str = "", objective: str = "") -> Mission

def update_mission(session, mission_id: int, **kwargs) -> Mission
    # kwargs: name, client, consultant, start_date, objective

def delete_mission(session, mission_id: int) -> None
    # Cascades to all interviews, verbatims, extracts, interpretations, reports
```

### Interview

```python
def get_interviews(session, mission_id: int) -> list[Interview]
    # Ordered by interview_date, then id

def create_interview(session, mission_id: int, subject_name: str = "",
                     subject_role: str = "", interview_date: str = "",
                     level_code: str = "I", notes: str = "") -> Interview

def update_interview(session, interview_id: int, **kwargs) -> Interview
    # kwargs: subject_name, subject_role, interview_date, level_code, notes

def delete_interview(session, interview_id: int) -> None
    # Cascades to verbatim, extracts, interpretations
```

### Verbatim

```python
def get_verbatims(session, interview_id: int) -> list[Verbatim]

def create_verbatim(session, interview_id: int, text: str = "") -> Verbatim

def update_verbatim(session, verbatim_id: int, text: str) -> Verbatim

def delete_verbatim(session, verbatim_id: int) -> None
```

### Extract

```python
def get_extracts(session, verbatim_id: int) -> list[Extract]
    # Ordered by display_order

def create_extract(session, verbatim_id: int, text: str, tag: str = "",
                   display_order: int = 0) -> Extract

def delete_extract(session, extract_id: int) -> None
    # Cascades to interpretations
```

### Interpretation

```python
def get_interpretations(session, extract_id: int) -> list[Interpretation]

def get_all_mission_interpretations(session, mission_id: int) -> list[Interpretation]
    # Traverses Mission → Interview → Verbatim → Extract → Interpretation

def create_interpretation(session, extract_id: int, capacity_id: str | None,
                           maturity_level: str = "", confidence: float = 0.5,
                           text: str = "") -> Interpretation
    # Created with status="pending"

def update_interpretation_status(session, interp_id: int, status: str,
                                  corrected_text: str | None = None) -> Interpretation
    # status: "validated" | "rejected" | "corrected"
    # If corrected_text is provided, also replaces interp.text

def delete_interpretation(session, interp_id: int) -> None
```

### MissionReport

```python
def get_mission_report(session, mission_id: int, lang: str) -> MissionReport | None

def upsert_mission_report(session, mission_id: int, lang: str,
                           text: str) -> MissionReport
    # Inserts or replaces; updates generated_at to now()
```

---

## services/backup.py

```python
def save_backup(db_path: Path, backup_dir: Path) -> Path
    # Copies db_path to backup_dir/r6_navigator_YYYYMMDD_HHMMSS.db
    # Returns the backup file path
    # Raises IOError on failure

def restore_backup(backup_path: Path, db_path: Path) -> None
    # Validates backup_path is a valid SQLite file (sqlite3.connect + integrity_check)
    # Copies backup_path over db_path
    # Caller is responsible for reinitializing the session and reloading the UI
```

---

## services/export_docx.py

```python
def export_capacity(capacity_id: str, session, config: ExportConfig) -> Path
    # Generates a DOCX for one capacity.
    # Reads text content from *_translation tables using config.language.
    # Returns the output file path.

def export_bulk(capacity_ids: list[str], session, config: ExportConfig) -> Path
    # Generates one combined DOCX for multiple capacities (page break between each).
    # Returns the output file path.

def export_mission_report(mission_id: int, session_factory, output_path: Path,
                           lang: str = "fr") -> None
    # Generates a DOCX from the stored MissionReport text (Markdown → Word styles).
    # Markdown mapping: "## " → Heading 2, "### " → Heading 3, "# " → Heading 1,
    #                   "- " lines → List Bullet, plain text → Normal.
    # Raises ValueError if no report exists for (mission_id, lang).
```

### ExportConfig dataclass

```python
@dataclass
class ExportConfig:
    language: str           # 'fr' | 'en'
    include_fiche: bool     # True
    include_questions: bool # True
    include_coaching: bool  # True
    output_path: Path
```

### DOCX document structure (per capacity)

1. **Header**: `{capacity_id} — {label}` (Heading 1)
2. **Metadata block**: Level / Axis / Pole (table, 2 columns)
3. **Fiche section** (if `include_fiche`):
   - Définition (Heading 2 + paragraph)
   - Fonction centrale (Heading 2 + paragraph)
   - Observable items table: columns Category | Text (grouped by category, from `ObservableItem`)
   - Risque si insuffisant (Heading 2 + paragraph)
   - Risque si excessif (Heading 2 + paragraph)
4. **Questions section** (if `include_questions`):
   - Numbered list of questions
5. **Coaching section** (if `include_coaching`):
   - Thèmes de réflexion / Reflection themes
   - Leviers d'intervention / Intervention levers
   - Missions à envisager / Recommended missions

For bulk export: each capacity starts on a new page.

---

## services/ai_generate.py

Generation is split into five independent steps, each using a dedicated prompt file.

```python
@dataclass
class GeneratedFiche:
    name: str               # Intitulé (canonical name or capacity_id fallback)
    definition: str
    central_function: str

@dataclass
class GeneratedRisque:
    risk_insufficient: str  # Bullet string: "- phrase.\n- phrase.\n" (max 5 items)
    risk_excessive: str     # Bullet string: "- phrase.\n- phrase.\n" (max 5 items)

@dataclass
class GeneratedCoaching:
    reflection_themes: str
    intervention_levers: str
    recommended_missions: str

@dataclass
class GeneratedContent:
    """Result of translate_fiche() — full translation without observable."""
    name: str
    definition: str
    central_function: str
    risk_insufficient: str
    risk_excessive: str

def generate_fiche(capacity_id: str, lang: str) -> GeneratedFiche
    # Generates label, definition, central_function only.
    # Prompt file: generate_fiche.txt
    # Used by: TabFiche [Générer] button (UI), cli/populate_db.py section "fiche"

def generate_fiche_risque(capacity_id: str, lang: str) -> GeneratedRisque
    # Generates risk_insufficient and risk_excessive only.
    # Prompt file: generate_fiche_risque.txt
    # Used by: TabFiche [Générer risques] button (UI), cli/populate_db.py section "risque"

def generate_questions(capacity_id: str, lang: str) -> list[str]
    # Generates 10 interview questions. Returns a plain list of strings.
    # Prompt file: generate_questions.txt
    # Used by: TabQuestions [Générer] button (UI), cli/populate_db.py section "questions"

def generate_questions_items(capacity_id: str, lang: str) -> dict[str, list[str]]
    # Generates 4×5 observable items (OK/EXC/DEP/INS).
    # Returns: {"OK": [...], "EXC": [...], "DEP": [...], "INS": [...]}
    # Prompt file: generate_questions_items.txt
    # Used by: TabQuestions [Générer items] button (UI), cli/populate_db.py section "items"

def generate_coaching(capacity_id: str, lang: str) -> GeneratedCoaching
    # Generates coaching fields.
    # Prompt file: generate_coaching.txt
    # Used by: cli/populate_db.py section "coaching"

def translate_fiche(capacity_id: str, source_lang: str, target_lang: str,
                    source_fields: dict) -> GeneratedContent
    # Translates fiche content (without observable) to target_lang.
    # Prompt file: translate_fiche.txt
    # Used by: cli/translate_db.py
```

Common behaviour for all generation functions:
- Reads `params.yml`: `ollama.url`, `ollama.model`, `ollama.timeout`
- Reads `services/prompt/system_01.txt` for the system prompt via `_load_system_prompt()`
- Reads `axioms.yml` for level/axis/pole structure of the capacity
- Reads `capacities_fr.yml` or `capacities_en.yml` (based on `lang`) for canonical name
- Name resolution: `capacities_*.yml[capacity_id]` → fallback to `capacity_id`
- Calls Ollama API via `urllib` (no SDK dependency)
- Retries up to 3 times on network/format error (`_OLLAMA_MAX_RETRIES=3`, 2s delay)
- Expects JSON response — strips markdown delimiters (` ```json … ``` `) before parsing
- Raises `RuntimeError` if all retry attempts fail or response unparseable

### params.yml structure (project root)

```yaml
ollama:
  url: "http://localhost:11434"
  model: "mistral-large-3:675b-cloud"    # Generation model
  model_judge: "kimi-k2-thinking:cloud"  # Evaluation model (ai_judge.py)
  timeout: 120              # HTTP timeout in seconds
```

The system prompt is stored separately in `services/prompt/system_01.txt`
(English, R6/Halliday expert role). It is read at call time by `_load_system_prompt()`.

### Canonical name files (r6_navigator/)

- `capacities_en.yml` — canonical English names, keyed by capacity_id
- `capacities_fr.yml` — canonical French names, keyed by capacity_id
- `axioms.yml` is the structural authority; `capacities_*.yml` are the application-facing labels

---

## services/ai_analyze.py

Verbatim analysis and mission report generation. Uses the same Ollama/retry pattern as
`ai_generate.py`, but operates on mission data rather than the R6 referential.

**IMPORTANT**: prompts for this module contain JSON example blocks with literal `{` and `}`.
Always use `load_prompt(name, **kwargs)` from `services/prompt/__init__.py` — never
`str.format()` — to avoid `KeyError` on those braces.

```python
@dataclass
class AnalyzedExtract:
    text: str           # Extracted passage (quoted or condensed from verbatim)
    tag: str | None     # R6 capacity code proposed by the model (e.g. "I3b")
    capacity_id: str | None  # Same as tag (redundant field for compatibility)
    maturity_level: str # e.g. "insuffisant", "satisfaisant", "excellent"
    confidence: float   # 0.0 – 1.0
    interpretation: str # 2–4 sentence analytical commentary

def analyze_verbatim(
    verbatim_text: str,
    interview_info: dict,   # keys: subject_name, subject_role, level_code, interview_date
    lang: str = "fr",
) -> list[AnalyzedExtract]
    # Calls Ollama with analyze_verbatim.txt prompt.
    # Loads the appropriate maturity scale from maturity_scales/ based on level_code.
    # Returns extracts sorted by relevance (as ordered by the model).
    # Raises RuntimeError if Ollama unreachable or response not valid JSON.

def generate_mission_report(
    mission_id: int,
    session_factory,
    lang: str = "fr",
) -> str
    # Loads all validated/corrected interpretations for the mission.
    # Groups them by level (S/O/I) and calls Ollama with generate_mission_report.txt.
    # Returns Markdown-formatted report text.
    # Raises ValueError if mission not found; RuntimeError on Ollama failure.
```

Internal helpers:

```python
def _load_maturity_scale(level_code: str) -> str
    # Reads r6_navigator/maturity_scales/{level_code}6_*_short.md
    # Returns empty string if file absent (graceful degradation).
```

### Maturity scale files (`r6_navigator/maturity_scales/`)

Three Markdown reference files injected into the analyze_verbatim prompt:

| File | Level | Content |
|------|-------|---------|
| `I6_EQF_Proficiency_Levels_short.md` | I | 6 EQF individual proficiency levels |
| `O6_Maturity_Levels_short.md` | O | 5 organizational maturity levels |
| `S6_Maturity_Levels_short.md` | S | 4 strategic pivot maturity levels |

---

## db/database.py

```python
def get_engine(db_path: Path) -> Engine
    # Creates SQLAlchemy engine with:
    #   connect_args={"check_same_thread": False}
    #   pragma foreign_keys = ON  (event listener on connect)

def get_session_factory(engine: Engine) -> sessionmaker

def init_db(engine: Engine, seed_capacities: bool = True) -> None
    # 1. Creates all tables from models metadata (create_all).
    # 2. Runs _migrate_to_translation_tables(): detects old _fr/_en columns via
    #    PRAGMA table_info, copies data to *_translation tables, then rebuilds
    #    the four affected tables to drop legacy columns. No-op on fresh DB.
    # 3. Runs _migrate_drop_observable_column(): drops the `observable` column
    #    from capacity_translation if it still exists (SQLite table rebuild). No-op if absent.
    # 4. Runs _migrate_add_mission_tables(): detects legacy mission schema (old
    #    string PK `mission_id`) via PRAGMA table_info; if found, drops all 6
    #    mission tables and recreates them with the current integer-PK schema.
    #    No-op if current schema or no mission tables exist.
    # 5. Inserts reference data (level, axis, pole, observable_category,
    #    app_setting) using session.merge() — idempotent.
    # 6. If seed_capacities=True: seeds 18 canonical Capacity rows and their
    #    CapacityTranslation (lang='fr', label=capacity_id) and Coaching rows.
```

Reference data inserted by `init_db()` (structural constants, not user data):

| Table                  | Rows inserted                                                              |
|------------------------|----------------------------------------------------------------------------|
| `level`                | S (order 1, unit/scale from axioms), O (order 2), I (order 3)             |
| `axis`                 | 1 Direction (Stability/Change), 2 Coordination (Autonomy/Interdependence), 3 Realization (Direct/Mediated) |
| `pole`                 | a Agentive, b Instrumental                                                 |
| `observable_category`  | OK (1), EXC (2), DEP (3), INS (4)                                          |
| `app_setting`          | active_language=fr, last_capacity_id=""                                    |
