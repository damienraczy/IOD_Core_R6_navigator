# R6 Navigator — Tests Specification

## Framework

- `pytest` with `pytest-fixtures`
- All tests use an **in-memory SQLite DB** (`":memory:"`) via SQLAlchemy
- No UI tests in v1
- No file system tests for backup (mock `shutil.copy2`)

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

Uses the `session` fixture. capacities are created inline in each test.

| Test | Description |
|------|-------------|
| `test_export_single_capacity_fr` | Generates DOCX from FR translation — file exists, non-empty |
| `test_export_single_capacity_en` | Generates DOCX from EN translation (added via `upsert_capacity_translation`) |
| `test_export_includes_fiche_content` | Document body contains the `definition` translation text |
| `test_export_includes_questions` | Document contains question text from `QuestionTranslation` |
| `test_export_includes_coaching` | Document contains coaching text from `CoachingTranslation` |
| `test_export_excludes_fiche_when_flagged` | `include_fiche=False` → definition text absent from output |
| `test_export_bulk` | Multiple capacities → one file, ≥2 Heading 1 entries |
| `test_export_empty_fields_no_crash` | No EN translation exists → all fields empty → no exception |
