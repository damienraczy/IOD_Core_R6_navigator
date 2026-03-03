# R6 Navigator — UI Specification

## Layout overview

```
┌─────────────────────────────────────────────────────────────────┐
│  R6 Navigator                              [fr ▾]               │
├──────────────────────┬──────────────────────────────────────────┤
│                      │  Siblings: [I1a] ←→ [O1a] ←→ [S1a]       │
│  NAVIGATION          ├──────────────────────────────────────────┤
│  (Treeview)          │  [ Fiche ] [ Questions ] [ Coaching ]    │
│                      │                                          │
│  Filters:            │  (tab content)                           │
│  [Level ▾][Axis ▾]   │                                          │
│  [Pole  ▾]           │                                          │
│                      │                                          │
├──────────────────────┴──────────────────────────────────────────┤
│  [Nouveau] [Modifier] [Supprimer]    [Sauvegarder] [Restaurer] [Créer DOCX] │
└─────────────────────────────────────────────────────────────────┘
```

---

## Navigation panel (left)

**Widget**: `Treeview`, fixed width ~280px, always visible.

**Tree hierarchy**:
```
▶ S — Stratégique            (level node, not selectable as capacity)
    ▶ Axe 1 — Direction      (axis node, not selectable as capacity)
        S1a  Se positionner...  [a]
        S1b  Se positionner...  [b]
    ▶ Axe 2 ...
▶ O — Organisationnel
    ...
▶ I — Individuel
    ...
```

Each capacity leaf shows: `{capacity_id}  {label (truncated)}  [{pole_code}]`

Pole badge color: agentive `a` → blue tag, instrumental `b` → orange tag.

**Filters** (above the tree, always visible):
- Level combobox: `Tous | S | O | I`
- Axis combobox: `Tous | 1 | 2 | 3`
- Pole combobox: `Tous | a | b`

Filters hide non-matching nodes. Changing a filter collapses and re-renders the tree.

**Selection**: single-click on a capacity leaf loads it in the detail panel.
Clicking a level or axis node toggles expand/collapse only.

---

## Isomorphism bar

Positioned between the tree and the tab bar, always visible when a capacity is loaded.

Format: `  [I1a]   ←isomorphe→   [O1a]   ←isomorphe→   [S1a]  `

Each code is a `Button` (or styled `Label` with click binding).
Clicking loads the corresponding capacity without changing the tree selection highlight.

---

## Tab: Fiche (default)

All fields read-only by default. Edit mode activated by `[Modifier]` button.

**Read-only header** (non-editable, always displayed):

| Label           | Value example          |
|-----------------|------------------------|
| Niveau          | Individuel (I)         |
| Axe             | Axe 1 — Direction      |
| Pôle            | Agentif (a)            |
| Code            | I1a                    |

**Editable fields** (bilingual, one column per language in the form):

| Field label      | Widget          | DB field (`CapacityTranslation`) |
|------------------|-----------------|----------------------------------|
| Intitulé         | `QLineEdit`     | `label`                          |
| Définition       | `QPlainTextEdit`| `definition`                     |
| Fonction centrale| `QPlainTextEdit`| `central_function`               |
| Risque si insuffisant | `QPlainTextEdit` | `risk_insufficient`        |
| Risque si excessif    | `QPlainTextEdit` | `risk_excessive`           |

**AI generation buttons** (always visible, independent of edit mode):

| Button (`btn_*`) | Positioned near | Calls | Populates |
|------------------|-----------------|-------|-----------|
| `btn_generer` | Section header (top) | `generate_fiche()` | Intitulé, Définition, Fonction centrale |
| `btn_generer_risque` | Risk fields header | `generate_fiche_risque()` | Risque si insuffisant, Risque si excessif |

---

## Tab: Questions

Two sections stacked vertically.

### Section 1 — Questions

```
┌────────────────────────────────────────────────────────────────┐
│ Questions              [Générer]          [+ Nouvelle question] │
├────┬──────────────────────────────────────────────┬────────────┤
│ #  │ Question                                     │ Actions    │
├────┼──────────────────────────────────────────────┼────────────┤
│ 1  │ [question text — editable in place]          │ [↑][↓][✕] │
│ 2  │ ...                                          │ [↑][↓][✕] │
└────┴──────────────────────────────────────────────┴────────────┘
```

Widget: `QTableWidget` with 3 columns: `#` (number), `Question` (stretch), `Actions`.

- Text column uses `ResizeMode.Stretch` — resizes proportionally with the window
- Inline edit: double-click a cell to edit text in place
- `[↑]` `[↓]`: reorder (updates `display_order`)
- `[✕]`: delete with confirmation
- `[+ Nouvelle question]`: appends a new empty row
- `[Générer]`: calls `generate_questions()` via `_GenerateWorker` (QThread) — replaces all rows

### Section 2 — Manifestations observables

```
┌────────────────────────────────────────────────────────────────┐
│ Manifestations observables  [Générer items]   [+ Nouvel item]  │
├──────────────────┬───────────────────────────────┬────────────┤
│ Catégorie        │ Texte                         │ Actions    │
├──────────────────┼───────────────────────────────┼────────────┤
│ ✅ Manifeste     │ ...                           │ [↑][↓][✕] │
│ ⚠️ Excessif      │ ...                           │ [↑][↓][✕] │
│ 🔼 Dépasse       │ ...                           │ [↑][↓][✕] │
│ ❌ Insuffisant   │ ...                           │ [↑][↓][✕] │
└──────────────────┴───────────────────────────────┴────────────┘
```

Widget: `QTableWidget` with 3 columns: `Catégorie`, `Texte` (stretch), `Actions`.

- Items sorted by `category_code` display_order then item `display_order`
- Category selector on `[+ Nouvel item]`: combobox with the 4 categories
- `category_code` values: `OK` | `EXC` | `DEP` | `INS`
- Category display labels come from `i18n` (not hardcoded)
- `[Générer items]`: calls `generate_questions_items()` via `_GenerateItemsWorker` (QThread)

---

## Tab: Coaching

Three free-text zones, each with its own label.

| Zone label (fr)          | Zone label (en)           | `coaching_translations` field |
|--------------------------|---------------------------|-------------------------------|
| Thèmes de réflexion      | Reflection themes         | `reflection_themes`           |
| Leviers d'intervention   | Intervention levers       | `intervention_levers`         |
| Missions à envisager     | Recommended missions      | `recommended_missions`        |

Widget: `Text` for each zone, ~6 lines height, vertical scrollbar.
Content is always editable (no separate edit mode for coaching tab).
Auto-save on tab switch or capacity change (with unsaved-change guard).
Content is read/written for the active language (`current_lang()`) via
`crud.get_coaching_translation()` / `crud.upsert_coaching_translation()`.

---

## Toolbar (bottom)

All buttons always visible. Disabled state when no capacity is selected:

| Button        | Always enabled | Enabled when capacity selected |
|---------------|----------------|---------------------------------|
| Nouveau       | ✓              |                                 |
| Modifier      |                | ✓                               |
| Supprimer     |                | ✓                               |
| Sauvegarder   | ✓              |                                 |
| Restaurer     | ✓              |                                 |
| Créer DOCX    |                | ✓                               |
| Juger         |                | ✓                               |
| Missions      | ✓              |                                 |

### [Nouveau] flow
1. Open a small creation dialog: select Level, Axis, Pole (3 comboboxes) + enter label (FR, optionally EN)
2. Validate: check uniqueness → create capacity + capacityTranslation + empty Coaching → select in tree → open in edit mode

### [Supprimer] flow
1. If `is_canonical`: show reinforced warning dialog (two-step confirm)
2. Otherwise: standard confirm dialog
3. On confirm: delete → select previous/next capacity in tree

### [Créer DOCX] flow
1. Open config dialog (see `dialogs.py`):
   - Scope: current capacity only vs. selection (multi-select in tree) vs. all
   - Tabs to include: checkboxes for Fiche / Questions / Coaching
   - Language: fr / en / both
2. Generate → file save dialog → open file on success

### [Juger] flow
1. Opens `VerificationWindow` for the currently selected capacity.
2. Runs 3 parallel LLM evaluations (axioms R6, Halliday, level/pole coherence) via `ai_judge.py`.
3. Shows per-criterion verdict + aggregate score; user can compare with original content.

### [Missions] flow
Opens the `MissionApp` window (lazy creation — only one instance at a time).

---

## VerificationWindow (`verification_window.py`)

A `QDialog` that displays the 3-judge LLM evaluation for the selected capacity.

```
┌─────────────────────────────────────────────────────────┐
│  Vérification — I1a                             [✕]     │
├──────────────────────────────────────────────────────────┤
│  Version  [Original ▾]   / 1                             │
├─────────────────────┬────────────────────────────────────┤
│  R6 Axioms          │  verdict + commentary              │
│  Halliday           │  verdict + commentary              │
│  Level/pole coher.  │  verdict + commentary              │
├─────────────────────┴────────────────────────────────────┤
│  Aggregate verdict:  Satisfaisant                        │
└──────────────────────────────────────────────────────────┘
```

- Verdicts: `"pas_bon"` | `"satisfaisant"` | `"tres_bon"`
- Aggregate is the lowest of the three individual verdicts
- Uses `ollama.model_judge` from params.yml (separate from the generation model)

---

## Edit mode

Edit mode applies to **Fiche** and **Questions** tabs.
**Coaching** tab is always directly editable.

### State machine

```
READ_ONLY ──[Modifier]──> EDIT
EDIT ──[Enregistrer]──> READ_ONLY  (after successful DB write)
EDIT ──[Annuler]──────> READ_ONLY  (discard, reload from DB)
```

### EditGuard

`EditGuard` is a class in `app.py` that:
- Tracks `is_dirty: bool` (any unsaved change in Fiche or Questions)
- Is checked before: tree node selection, language change, window close
- If dirty: shows a confirm dialog ("Unsaved changes — save, discard, or cancel?")

---

## Language switching

- Language combobox at top-right: `fr` | `en`
- On change:
  1. `EditGuard` check (prompt if dirty)
  2. Update `Lang` singleton
  3. Redraw all UI labels, tree node labels, tab headings
  4. Reload active capacity content in the new language
  5. Persist selection to `app_settings`

---

## Window behavior

- Minimum size: 900 × 600 px
- Remember last window size and position (`app_settings`)
- On close: `EditGuard` check
- Title bar: `R6 Navigator — {capacity_id} {label}` when a capacity is loaded

---

## Missions window (`mission_app.py`, `mission_nav.py`, `mission_detail.py`)

Opened from the main window's [Missions] toolbar button. Lazily created, singleton:
one `MissionApp` instance is shared across the session.

```
┌──────────────────────────────────────────────────────────────┐
│  R6 Navigator — Missions                                      │
├──────────────────────────────────────────────────────────────┤
│  [Nouvelle mission] [Nouvel entretien] [Supprimer]            │
├───────────────────────┬──────────────────────────────────────┤
│                       │  [ Infos ] [ Verbatim ]              │
│  ▶ Mission A          │  [ Interprétations ] [ Rapport ]     │
│      Interviewé 1     │                                      │
│      Interviewé 2     │  (tab content)                       │
│  ▶ Mission B          │                                      │
│      ...              │                                      │
└───────────────────────┴──────────────────────────────────────┘
```

`MissionApp(QMainWindow)` receives the `session_factory` from the main app and injects it
into all child components via `set_session_factory()`.

### MissionNav (`mission_nav.py`)

`QTreeWidget`, fixed left column (~250 px):
- Two levels: Mission → Interview
- Click on Mission → `mission_selected = Signal(int)` (mission_id)
- Click on Interview → `interview_selected = Signal(int)` (interview_id)
- `refresh()` method reloads tree from DB

### MissionDetailPanel (`mission_detail.py`)

`QTabWidget` with 4 tabs:

| Tab | Class | Loaded when |
|-----|-------|-------------|
| Infos | `MissionTabInfo` | Mission or Interview selected |
| Verbatim | `MissionTabVerbatim` | Interview selected |
| Interprétations | `MissionTabInterpretations` | Mission or Interview selected |
| Rapport | `MissionTabRapport` | Mission selected |

- `load_mission(mission_id)` → loads Infos + Interprétations + Rapport; clears Verbatim
- `load_interview(interview_id)` → loads Infos + Verbatim; Interprétations shows interview-level

---

## Tab: Mission Infos (`mission_tab_info.py`)

Edit mode pattern (same as Fiche/Questions: read-only by default, [Modifier] to edit).
Two `QGroupBox` sections:

**Mission fields**: name, client, consultant, start_date, objective

**Interview fields** (only visible when an interview is selected):
subject_name, subject_role, interview_date, level_code (QComboBox: S/O/I), notes

---

## Tab: Verbatim (`mission_tab_verbatim.py`)

```
┌──────────────────────────────────────────────────────────┐
│  Verbatim                                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │ (verbatim text — read-only by default)             │  │
│  │                                                    │  │
│  └────────────────────────────────────────────────────┘  │
│  [Modifier] [Enregistrer] [Annuler]  [Ouvrir] [Télécharger] [Analyser] │
├──────────────────────────────────────────────────────────┤
│  Interprétations                                         │
│  • [I3b] (82%) Passage text…                            │
│  • [O2a] (65%) …                                        │
│  ┌──────────────────────────────────────────────────┐    │
│  │                             [Sauvegarder extraits]│    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

**Buttons**:

| Button | Action |
|--------|--------|
| [Modifier] / [Enregistrer] / [Annuler] | Toggle edit mode for the verbatim text |
| [Ouvrir un fichier] | Import verbatim from `.txt` / `.md` file (UTF-8); saves immediately |
| [Télécharger le verbatim] | Export verbatim to `.txt` file via save dialog |
| [Analyser] | Runs `_AnalyzeWorker(QThread)` → `analyze_verbatim()` → populates extract list |
| [Sauvegarder les extraits] | Creates `Extract` + `Interpretation(status=pending)` for each result |

The bottom list shows AI-proposed extracts as `[tag] (confidence%) text…`.
Tooltip on each item shows the full interpretation text.
[Sauvegarder les extraits] is only enabled after a successful analysis.

---

## Tab: Interprétations (`mission_tab_interpretations.py`)

```
┌────────────────────────────────────────────────────────────────────┐
│  Filtre: [Tous ▾]                                                  │
├──────┬───────────┬────────┬──────────┬──────────┬─────────────────┤
│ Extrait │ Capacité │ Niveau │ Confiance │ Statut  │ Actions         │
├──────┴───────────┴────────┴──────────┴──────────┴─────────────────┤
│ text…  │ I3b      │ insuff.│ 82%       │ pending │ [✓][✗][✏]      │
│ ...    │ O2a      │ satis. │ 65%       │ valid.  │ [✓][✗][✏]      │
└────────────────────────────────────────────────────────────────────┘
```

- Filter combobox: `Tous | En attente | Validés | Rejetés`
- Per-row action buttons: `[✓ Valider]` `[✗ Rejeter]` `[✏ Corriger]`
- [Corriger] opens `QInputDialog` for the consultant to enter corrected text;
  saves with `status="corrected"` and replaces `interp.text`
- `reload()` is called after each status change

---

## Tab: Rapport (`mission_tab_rapport.py`)

```
┌──────────────────────────────────────────────────────────────────┐
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ (report text — read-only, Markdown rendered as plain text) │  │
│  └────────────────────────────────────────────────────────────┘  │
│                        [Générer le rapport]  [Exporter le rapport] │
└──────────────────────────────────────────────────────────────────┘
```

- [Générer le rapport] → `_ReportWorker(QThread)` → `generate_mission_report()` →
  saves result to DB via `upsert_mission_report()` → displays in text area
- [Exporter le rapport] → `QFileDialog` (`.docx`) → `export_mission_report()`
- Pre-condition check: if no validated interpretations exist, shows warning and
  blocks generation (uses i18n key `mission.no_validated_interpretations`)
