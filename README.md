# R6 Navigator

Desktop application for IOD consultants to manage and consult the R6 organizational competency framework.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
cd r6_navigator
python main.py
```

The database (`r6_navigator.db`) is created automatically on first launch.
All data (capacities, questions, items, coaching) is entered through the UI.

## Quick Start

1. **Launch**: `cd r6_navigator && python main.py`
2. **Navigate**: Use the treeview on the left to select a capacity
3. **Edit**: Click [Modifier] to edit fields in the detail panel
4. **Save**: Click [Enregistrer] to persist changes
5. **Language**: Switch between fr/en using the combobox (top-right)

## AI Generation

The **[Générer]** button in the Fiche tab calls [Ollama](https://ollama.com) (local) to auto-fill:
- Définition
- Fonction centrale
- 5 Observables (bullet list)
- 5 Risques si insuffisant (bullet list)

**Prerequisites:**
- Ollama Desktop running locally
- Model configured in `params.yml` (project root) — default `mistral-large-3:675b-cloud`

The generated content is written to the form fields — review it, then save manually.

## Features

- **CRUD referential** for 18 R6 capacities (S/O/I levels × 3 axes × 2 poles)
- **Bilingual** (fr/en) UI and data storage
- **TabControl** navigation with Fiche, Questions, and Coaching tabs
- **DOCX export** of capacities with configurable scope and content
- **AI generation** of fiche content via Ollama (local LLM, non-blocking)

## Project Structure

```
IOD_R6_base_v2/
├── cli/
│   ├── populate_db.py   # AI-populate DB (fiche, questions, coaching)
│   ├── translate_db.py  # AI-translate DB content (fr ↔ en)
│   └── compile_ui.py    # Compile .ui → ui_*.py
└── r6_navigator/
    ├── db/              # Database layer (models, engine, migrations)
    ├── shared/          # Shared utilities (backup, Ollama HTTP client)
    ├── navigator/       # R6 referential sub-app (CRUD, export, AI generation)
    │   ├── services/    # Business logic + prompts
    │   └── ui/          # PySide6 UI (main window, tabs, forms)
    ├── missions/        # Mission interpretation sub-app (verbatim analysis)
    │   ├── services/    # Business logic + prompts
    │   └── ui/          # PySide6 UI (mission window, tabs)
    ├── i18n/            # Internationalization (fr/en)
    ├── tests/           # pytest tests (navigator/ + missions/)
    └── main.py          # Entry point
```

## CLI Tools

All standalone scripts live in `cli/`. Run them from the **project root**:

```bash
# Populate the DB via Ollama AI (completes missing data only)
python cli/populate_db.py
python cli/populate_db.py --lang fr en       # both languages
python cli/populate_db.py --full             # regenerate everything
python cli/populate_db.py --capacity I1a S2b # specific capacities

# Translate existing DB content (fr → en by default)
python cli/translate_db.py
python cli/translate_db.py --from en --to fr
python cli/translate_db.py --full            # force retranslate all

# Recompile Qt Designer .ui files after editing in Qt Designer
python cli/compile_ui.py
```

## Documentation

| File | Content |
|------|---------|
| `CLAUDE.md` | Claude Code instructions — read first |
| `DOMAIN.md` | Domain model, entities, business rules |
| `UI.md` | UI layout, widgets, interaction flows |
| `SERVICES.md` | Services layer API contracts |
| `TESTS.md` | Test coverage specification |
| `schema.sql` | Reference SQL schema (documentation only) |

## Stack

- Python 3.11+ / PySide6 / SQLAlchemy 2.x / SQLite / python-docx / PyYAML / Ollama

## Tests

```bash
cd r6_navigator
pytest tests/
```
