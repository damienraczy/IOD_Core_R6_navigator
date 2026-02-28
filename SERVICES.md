# R6 Navigator — Services Specification

## General rules

- All DB access goes through `services/crud.py`
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
    # fields: label, definition, central_function, observable,
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
   - Observable (Heading 2 + paragraph — free-text field from `CapacityTranslation.observable`)
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

```python
@dataclass
class GeneratedContent:
    name: str               # Intitulé (canonical name or capacity_id fallback)
    definition: str
    central_function: str
    observable: str         # Bullet string: "- phrase.\n- phrase.\n" (max 5 items)
    risk_insufficient: str  # Bullet string: "- phrase.\n- phrase.\n" (max 5 items)
    risk_excessive: str     # Bullet string: "- phrase.\n- phrase.\n" (max 5 items)

def generate_fiche(capacity_id: str, lang: str) -> GeneratedContent
    # lang = current_lang() — generates content in the active UI language
    # Reads params.yml: ollama.url, ollama.model, ollama.timeout, system_prompt
    # Reads axioms.yml: level/axis/pole structure for the capacity
    # Reads capacities_en.yml or capacities_fr.yml (based on lang) for canonical name
    # Name resolution: capacities_*.yml[capacity_id] or capacity_id (fallback)
    # Prompt: sent in English regardless of lang; model responds in lang
    # Prompt includes: capacity_id, level, axis, pole, canonical name, R6 context
    # Calls Ollama API via urllib (no SDK dependency)
    # Expects JSON response — strips markdown delimiters (```json ... ```) before parsing
    # Caps observable + risk lists to 5 items each
    # Raises RuntimeError if Ollama unreachable or response unparseable
```

### params.yml structure (project root)

```yaml
ollama:
  url: "http://localhost:11434"
  model: "mistral-large-3:675b-cloud"
  timeout: 10               # HTTP timeout in seconds

system_prompt: |
  [System instruction for the model — to be defined]
```

### Canonical name files (r6_navigator/)

- `capacities_en.yml` — canonical English names, keyed by capacity_id
- `capacities_fr.yml` — canonical French names, keyed by capacity_id
- `axioms.yml` is the structural authority; `capacities_*.yml` are the application-facing labels

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
    #    the four affected tables to drop legacy columns.
    # 3. Inserts reference data (level, axis, pole, observable_category,
    #    app_setting) using session.merge() — idempotent.
    # 4. If seed_capacities=True: seeds 18 canonical Capacity rows and their
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
