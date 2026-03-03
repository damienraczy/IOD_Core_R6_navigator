# R6 Navigator

Desktop application for IOD consultants to manage and consult the R6 organizational
competency framework, and to run diagnostic missions (verbatim analysis, interpretation,
report generation).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
python -m r6_navigator.main
```

The database (`r6_navigator.db`) is created automatically on first launch.
All data is entered through the UI or CLI tools.

## Quick Start

1. **Launch**: `python -m r6_navigator.main` (from project root)
2. **Navigate**: Use the treeview on the left to select a capacity
3. **Edit**: Click [Modifier] to edit fields, [Enregistrer] to save
4. **Language**: Switch between fr/en with the combobox (top-right)
5. **Missions**: Click [Missions] in the toolbar to open the diagnostic missions window

## Features

- **CRUD referential** for 18 R6 capacities (S/O/I levels × 3 axes × 2 poles)
- **Bilingual** (fr/en) UI and data storage
- **3 tabs** per capacity: Fiche, Questions (QTableWidget), Coaching
- **DOCX export** with configurable scope (current / all) and content flags
- **AI generation** via Ollama (local LLM, non-blocking QThread workers):
  - Fiche: label, définition, fonction centrale
  - Risques: risque si insuffisant, risque si excessif
  - Questions: 10 questions d'entretien
  - Items: 4×5 manifestations observables (OK / EXC / DEP / INS)
- **AI evaluation (Judge)**: 3-LLM panel scores each capacity on axioms R6,
  Halliday transitivity, and level/pole coherence (`verification_window.py`)
- **Missions module**: full diagnostic workflow
  - Create missions and interviews
  - Edit verbatim (import from file, export to file)
  - Analyze verbatim with AI → extract R6 interpretations
  - Validate / reject / correct AI-proposed interpretations
  - Generate structured R6 diagnostic report
  - Export report to DOCX

## Project Structure

```
IOD_R6_base_v2/
├── params.yml               # Ollama config (model, url, timeout)
├── cli/
│   ├── populate_db.py       # AI-populate DB (fiche, questions, coaching)
│   ├── translate_db.py      # AI-translate DB content (fr ↔ en)
│   └── compile_ui.py        # Compile .ui → ui_*.py
└── r6_navigator/
    ├── db/                  # SQLAlchemy models + engine + migrations
    ├── services/            # CRUD, export, backup, AI generation, AI analysis
    ├── maturity_scales/     # Reference Markdown scales injected into analysis prompts
    ├── ui/qt/               # PySide6 UI (navigator + missions)
    ├── i18n/                # Internationalization (fr/en JSON)
    ├── tests/               # pytest tests (63 tests)
    └── main.py              # Entry point
```

## AI Generation

**Prerequisites**: Ollama running locally; model configured in `params.yml`.

| Button | Tab | What it generates |
|--------|-----|-------------------|
| [Générer] | Fiche | Label, définition, fonction centrale |
| [Générer risques] | Fiche | Risque si insuffisant/excessif |
| [Générer] | Questions | 10 interview questions |
| [Générer items] | Questions | 4×5 observable manifestations |
| [Analyser] | Verbatim (Missions) | Extract + interpret verbatim passages |
| [Générer le rapport] | Rapport (Missions) | R6 diagnostic report (Markdown) |

Generated content is written to the form fields — review it, then save manually.

## CLI Tools

All scripts live in `cli/`. Run from the **project root**:

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
| `DOMAIN.md` | Domain model, entities, business rules (incl. Mission entities) |
| `UI.md` | UI layout, widgets, interaction flows (incl. Missions UI) |
| `SERVICES.md` | Services layer API contracts |
| `TESTS.md` | Test coverage specification |
| `schema.sql` | Reference SQL schema (documentation only) |

## Stack

- Python 3.11+ / PySide6 / SQLAlchemy 2.x / SQLite / python-docx / PyYAML / Ollama

## Tests

```bash
python -m pytest r6_navigator/tests/ -v    # 63 tests
```
