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
| Observable       | `QPlainTextEdit`| `observable`                     |
| Risque si insuffisant | `QPlainTextEdit` | `risk_insufficient`        |
| Risque si excessif    | `QPlainTextEdit` | `risk_excessive`           |

The "Observable" label (i18n key `fiche.observable`) is identical across all levels.
This free-text field is separate from the structured `ObservableItem` list in the Questions tab.

---

## Tab: Questions

Two sections stacked vertically.

### Section 1 — Questions

```
┌──────────────────────────────────────────────────────┐
│ Questions                          [+ Nouvelle]      │
│ ────────────────────────────────────────────────────  │
│  1. [question text — active language]  [↑] [↓] [✕]  │
│  2. [question text — active language]  [↑] [↓] [✕]  │
└──────────────────────────────────────────────────────┘
```

- Each question shows the active language text
- Inline edit: click on a question row to edit in place (or open a small edit dialog)
- `[↑]` `[↓]`: reorder (updates `display_order`)
- `[✕]`: delete with confirmation
- `[+ Nouvelle]`: appends a new empty question

### Section 2 — Manifestations observables

```
┌──────────────────────────────────────────────────────┐
│ Manifestations observables         [+ Nouvel item]   │
│ ────────────────────────────────────────────────────  │
│  Catégorie ▾  │  Texte                │  [↑][↓][✕]  │
│  ✅ OK        │  ...                  │              │
│  ⚠️ Excessif  │  ...                  │              │
│  🔼 Dépasse   │  ...                  │              │
│  ❌ Insuffisant│  ...                 │              │
└──────────────────────────────────────────────────────┘
```

- Items grouped and sorted by `category_code` then `display_order`
- Category selector on `[+ Nouvel item]`: combobox with the 4 categories
- `category_code` values: `OK` | `EXC` | `DEP` | `INS`
- Category display labels come from `i18n` (not hardcoded)

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
