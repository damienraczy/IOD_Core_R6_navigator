# R6 Navigator — Tests Specification

## Framework

- `pytest`
- All tests use an **in-memory SQLite DB** (`":memory:"`) via SQLAlchemy
- No UI tests
- No file system tests for backup (mock `shutil.copy2`)
- Total: **63 tests** (23 CRUD + 12 export + 28 mission CRUD)

---

## tests/conftest.py

Provides a `session` fixture:

```python
@pytest.fixture
def session():
    engine = get_engine(Path(":memory:"))
    init_db(engine, seed_capacities=False)
    factory = get_session_factory(engine)
    with factory() as s:
        yield s
```

Provides a `session_with_capacities` fixture:
- Same as `session` but creates **3 synthetic capacities** (one per level, all on axis 1 pole a):
  `S1a`, `O1a`, `I1a` — with a `CapacityTranslation(lang='fr', label='capacity {id}')` for each.
- Does **not** use real R6 content — tests must not depend on specific labels.

Note: mission CRUD tests use the plain `session` fixture (no capacities needed since
`Interpretation.capacity_id` is nullable).

---

## tests/test_crud.py

### capacity tests

| Test | Description |
|------|-------------|
| `test_create_capacity_success` | Creates a capacity with `label`/`lang`, verifies `capacity_id`, translation, and auto-created coaching |
| `test_create_capacity_duplicate_raises` | Same level/axis/pole raises `ValueError` |
| `test_create_capacity_missing_label_raises` | Empty `label` raises `ValueError("label is required")` |
| `test_get_capacity_exists` | Returns correct capacity |
| `test_get_capacity_not_found` | Returns `None` |
| `test_upsert_capacity_translation` | Creates FR translation at `create_capacity`, then upserts to add EN and update fields |
| `test_update_capacity_structural_fields_raises` | Attempting to change `level_code` raises `ValueError` |
| `test_delete_capacity` | capacity removed, cascade to questions/items/coaching/translations verified |
| `test_get_all_capacities_ordering` | Returned in level_order → axis_number → pole_code order |

### Question tests

| Test | Description |
|------|-------------|
| `test_create_question` | Creates with `text`/`lang`, verifies `QuestionTranslation` |
| `test_reorder_questions` | `reorder_questions` correctly reassigns `display_order` |
| `test_delete_question` | Removed without affecting sibling questions |
| `test_upsert_question_translation` | Creates EN translation, then updates FR translation |

### ObservableItem tests

| Test | Description |
|------|-------------|
| `test_create_observable_item` | Creates with `text`/`lang`, verifies `ObservableItemTranslation` |
| `test_create_observable_item_invalid_category` | Invalid `category_code` raises `ValueError` |
| `test_get_items_by_category` | Returns only items matching category, in order |
| `test_reorder_observable_items` | Reassigns `display_order` within a category |

### Coaching tests

| Test | Description |
|------|-------------|
| `test_coaching_auto_created` | Coaching row exists after `create_capacity` |
| `test_upsert_coaching_translation_creates` | Creates `CoachingTranslation` on missing record |
| `test_upsert_coaching_translation_updates` | Updates fields on existing `CoachingTranslation` |
| `test_coaching_translations_independent_by_lang` | FR and EN translations coexist independently |

### Settings tests

| Test | Description |
|------|-------------|
| `test_get_setting_default` | `active_language` returns `'fr'` after `init_db` |
| `test_set_and_get_setting` | Set then get returns correct value |

---

## tests/test_export.py

Uses the `session` fixture. Capacities are created inline in each test.

| Test | Description |
|------|-------------|
| `test_export_single_capacity_fr` | Generates DOCX from FR translation — file exists, non-empty |
| `test_export_single_capacity_en` | Generates DOCX from EN translation (added via `upsert_capacity_translation`) |
| `test_export_includes_fiche_content` | Document body contains the `definition` translation text |
| `test_export_bullet_rendering` | `risk_insufficient` bullet text appears correctly in the DOCX output |
| `test_export_includes_questions` | Document contains question text from `QuestionTranslation` |
| `test_export_observable_items_under_questions` | Observable items appear under the Questions section, grouped by category |
| `test_export_includes_coaching` | Document contains coaching text from `CoachingTranslation` |
| `test_export_excludes_fiche_when_flagged` | `include_fiche=False` → definition text absent from output |
| `test_export_bulk` | Multiple capacities → one file, ≥2 Heading 1 entries |
| `test_export_both_languages` | `language='both'` → one file containing FR and EN sections for each capacity |
| `test_export_empty_fields_no_crash` | No EN translation exists → all fields empty → no exception |
| `test_make_filename` | `_make_filename()` returns a slug-safe string derived from capacity_id and label |

---

## tests/test_mission_crud.py

Uses the `session` fixture (no capacities seeded).
`Interpretation.capacity_id` is set to `None` in fixtures since no capacity is available.

### Mission tests

| Test | Description |
|------|-------------|
| `test_create_mission` | Creates a mission, verifies all fields stored correctly |
| `test_get_all_missions` | Returns multiple missions; order is deterministic |
| `test_get_mission` | Returns correct mission by id |
| `test_update_mission` | Updates name/client/consultant fields |
| `test_delete_mission_cascades` | Deleting mission removes linked interview, verbatim, extract, interpretation |

### Interview tests

| Test | Description |
|------|-------------|
| `test_create_interview` | Creates interview linked to mission |
| `test_get_interviews` | Returns all interviews for a mission |
| `test_update_interview` | Updates subject_name, level_code |
| `test_delete_interview_cascades` | Deleting interview removes verbatim, extract, interpretation |

### Verbatim tests

| Test | Description |
|------|-------------|
| `test_create_verbatim` | Creates verbatim with initial text |
| `test_update_verbatim` | Updates text field |
| `test_delete_verbatim_cascades` | Deleting verbatim removes extract, interpretation |

### Extract tests

| Test | Description |
|------|-------------|
| `test_create_extract` | Creates extract with tag and display_order |
| `test_get_extracts_ordered` | Returns extracts sorted by display_order |
| `test_delete_extract_cascades` | Deleting extract removes interpretation |

### Interpretation tests

| Test | Description |
|------|-------------|
| `test_create_interpretation_pending` | Default status is `"pending"` |
| `test_update_interpretation_validated` | Status transitions to `"validated"` |
| `test_update_interpretation_rejected` | Status transitions to `"rejected"` |
| `test_update_interpretation_corrected` | Status → `"corrected"`, text replaced with corrected text |
| `test_get_all_mission_interpretations` | Traverses full Mission→…→Interpretation chain |

### MissionReport tests

| Test | Description |
|------|-------------|
| `test_upsert_mission_report_creates` | First upsert creates a new report row |
| `test_upsert_mission_report_updates` | Second upsert replaces text, updates generated_at |
| `test_get_mission_report_by_lang` | Returns correct report for the specified language |
| `test_get_mission_report_missing` | Returns `None` when no report exists for that lang |
