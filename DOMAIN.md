# R6 Navigator — Domain Model

## The R6 structure

The R6 framework organizes organizational competency across three orthogonal levels,
each structured by three axes and two poles per axis.

```
Level  (level_code TEXT):  'S' | 'O' | 'I'
  Axis (axis_number INT):   1 (Direction) | 2 (Coordination) | 3 (Realization)
    Pole (pole_code TEXT):  'a' (agentive) | 'b' (instrumental)
```

A **capacity** is the leaf node of this structure. Its natural key is:

```
capacity_id = level_code + str(axis_number) + pole_code
# Examples: "S1a", "O3b", "I2a"
```

The 18 canonical IDs:
```
S1a  S1b  S2a  S2b  S3a  S3b
O1a  O1b  O2a  O2b  O3a  O3b
I1a  I1b  I2a  I2b  I3a  I3b
```

**Isomorphism**: capacities sharing the same `axis_number + pole_code` across levels
are structurally homologous (e.g. I1a ↔ O1a ↔ S1a).

---

## Bilingual architecture

Textual content is stored in **dedicated translation tables** (one row per entity + language),
not as column pairs on the parent entity. This allows adding languages without schema changes.

The active language is provided at runtime by `i18n.current_lang()` (returns `'fr'` or `'en'`).
UI layers always read and write the translation for `current_lang()`.

---

## Entities

### Capacity

Core entity. Holds structural identity and metadata only — no text content.

| Field          | Type      | Notes                                                         |
|----------------|-----------|---------------------------------------------------------------|
| `capacity_id` | TEXT PK   | Computed from level+axis+pole. Never editable after creation. |
| `level_code`   | TEXT FK   | → level.level_code                                            |
| `axis_number`  | INT FK    | → axis.axis_number                                            |
| `pole_code`    | TEXT FK   | → pole.pole_code                                              |
| `is_canonical` | BOOL      | True for the 18 standard R6 capacities                        |
| `created_at`   | DATETIME  |                                                               |
| `updated_at`   | DATETIME  | Auto-updated on write                                         |

Unique constraint: `(level_code, axis_number, pole_code)`.

### CapacityTranslation

Text content for a capacity in one language. One row per `(capacity_id, lang)`.

| Field              | Type    | Notes                   |
|--------------------|---------|-------------------------|
| `capacity_id`     | TEXT FK | → capacity, CASCADE     |
| `lang`             | TEXT    | `'fr'` or `'en'`        |
| `label`            | TEXT    | Required (not nullable) |
| `definition`       | TEXT    |                         |
| `central_function` | TEXT    |                         |
| `risk_insufficient`| TEXT    |                         |
| `risk_excessive`   | TEXT    |                         |

Primary key: `(capacity_id, lang)`.

### Question

STAR interview question (level I) or diagnostic question (levels O, S).
A capacity has 0–N questions, ordered explicitly.

| Field          | Type    | Notes                   |
|----------------|---------|-------------------------|
| `question_id`  | INT PK  | Autoincrement           |
| `capacity_id` | TEXT FK | → capacity, CASCADE     |
| `display_order`| INT     | Default 0               |

### QuestionTranslation

| Field         | Type    | Notes                   |
|---------------|---------|-------------------------|
| `question_id` | INT FK  | → question, CASCADE     |
| `lang`        | TEXT    | `'fr'` or `'en'`        |
| `text`        | TEXT    | Required (not nullable) |

Primary key: `(question_id, lang)`.

### ObservableItem

A structured observable behavior or manifestation, categorized by adequacy level.
A capacity has 0–N items, ordered per category.

| Field           | Type    | Notes                                  |
|-----------------|---------|----------------------------------------|
| `item_id`       | INT PK  | Autoincrement                          |
| `capacity_id`  | TEXT FK | → capacity, CASCADE                    |
| `category_code` | TEXT FK | → observable_category.category_code   |
| `display_order` | INT     | Default 0, scoped per category         |

### ObservableItemTranslation

| Field     | Type    | Notes                       |
|-----------|---------|-----------------------------|
| `item_id` | INT FK  | → observable_item, CASCADE  |
| `lang`    | TEXT    | `'fr'` or `'en'`            |
| `text`    | TEXT    | Required (not nullable)     |

Primary key: `(item_id, lang)`.

### Coaching

Free-text coaching notes attached to a capacity. One record per capacity (1-to-1).
Created automatically (empty) when a capacity is created.

| Field          | Type     |
|----------------|----------|
| `capacity_id` | TEXT PK / FK → capacity, CASCADE |
| `updated_at`   | DATETIME |

### CoachingTranslation

| Field                 | Type    | Notes                       |
|-----------------------|---------|-----------------------------|
| `capacity_id`        | TEXT FK | → coaching, CASCADE         |
| `lang`                | TEXT    | `'fr'` or `'en'`            |
| `reflection_themes`   | TEXT    |                             |
| `intervention_levers` | TEXT    |                             |
| `recommended_missions`| TEXT    |                             |

Primary key: `(capacity_id, lang)`.

---

## Reference tables (read-only at runtime)

These tables are populated at DB initialization and never modified by the user.

### level

| level_code | display_order | unit                    | measurement_scale               |
|------------|---------------|-------------------------|---------------------------------|
| S          | 1             | Strategic Pivot Logics  | S6_Maturity_Levels_and_Learning_Loops_short.md |
| O          | 2             | Organizational Capabilities | O6_Maturity_Levels_short.md |
| I          | 3             | Individual Competencies | I6_EQF_Proficiency_Levels_short.md |

Display labels (`level.S`, `level.O`, `level.I`) are UI strings managed via i18n.

### axis

| axis_number | name         | tension_pole_a | tension_pole_b  |
|-------------|--------------|----------------|-----------------|
| 1           | Direction    | Stability      | Change          |
| 2           | Coordination | Autonomy       | Interdependence |
| 3           | Realization  | Direct         | Mediated        |

Display labels (`axis.1`, `axis.2`, `axis.3`) are UI strings managed via i18n.

### pole

| pole_code | name         | characteristics                          |
|-----------|--------------|------------------------------------------|
| a         | Agentive     | Stabilizing / Individualizing / Direct   |
| b         | Instrumental | Transforming / Collectivizing / Mediated |

Display labels (`pole.a`, `pole.b`) are UI strings managed via i18n.

### observable_category

| category_code | display_order |
|---------------|---------------|
| OK            | 1             |
| EXC           | 2             |
| DEP           | 3             |
| INS           | 4             |

Category labels are UI strings managed via i18n.

---

## Application settings

Persisted in the `app_setting` key-value table.

| key                  | default value |
|----------------------|---------------|
| `active_language`    | `fr`          |
| `last_capacity_id`  | (empty)       |

---

## Business rules

### Creation
- `capacity_id` is computed automatically from `level_code + axis_number + pole_code`.
- `capacity_id` must be unique. Reject if the combination already exists.
- A non-empty `label` in the given language is required.
- A `Coaching` record is created automatically (empty) alongside every new `Capacity`.

### Structural identity
- `capacity_id`, `level_code`, `axis_number`, `pole_code` are **not editable** after creation.
  They define structural identity.

### Deletion
- If `is_canonical = True`: show a reinforced warning before deletion.
- Always require explicit confirmation.
- Cascade deletes `question`, `observable_item`, `coaching` and all associated translation rows.

### Save / Restore base
- Save: copy the `.db` file to `backups/r6_navigator_YYYYMMDD_HHMMSS.db`.
- Restore: file picker → replace active DB after confirmation → reload full UI.

---

## Isomorphism navigation

Capacities sharing `axis_number + pole_code` across levels are isomorphic siblings.
Example: `I2b`, `O2b`, `S2b` are siblings on axis 2, pole b.

The UI displays a sibling bar above the detail panel:
```
[I2b]  ←isomorphe→  [O2b]  ←isomorphe→  [S2b]
```
Each code is clickable and loads the sibling capacity.
This is a computed UI feature — no stored relation in the DB.
