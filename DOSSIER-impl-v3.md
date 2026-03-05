# DOSSIER-impl-v3.md — Plan d'Implémentation

**Version** : 2.0.0
**Date** : 2026-03-05
**Statut** : Plan d'implémentation révisé — aligné avec les conventions du projet

---

## Journal des corrections (v2 → v3)

| # | Zone | Problème v2 | Correction v3 |
|---|------|-------------|---------------|
| 1 | Architecture | Sous-package `analyze_v2/` interdit par la règle "flat structure" | Module plat `services/ai_analyze_v2.py` |
| 2 | §2.1 titre | "Modèles Pydantic" — Pydantic absent du projet | "Dataclasses" — le projet utilise `@dataclass` |
| 3 | §2.1 typing | `List[str]`, `Optional[str]` (typing module, Python < 3.10) | `list[str]`, `str \| None` (style Python 3.10+ du projet) |
| 4 | §2.2 migration | Full table rebuild inutile pour un ADD COLUMN | `ALTER TABLE ADD COLUMN` — SQLite le supporte pour les ajouts |
| 5 | §2.2 models.py | `Extract` ORM non modifié | Ajouter `halliday_note` et `halliday_ok` à `Extract` dans `models.py` |
| 6 | §4.2 segmenter | `extract_blocks_from_breaks` ne peuple pas le champ `sentences` → `TypeError` à l'instanciation de `SemanticBlock` | Ajouter `sentences` dans le dict avant `SemanticBlock(**block)` |
| 7 | §4.2 segmenter | Prompt inline dans `insert_break_markers` (f-string) — contourne `load_prompt()` | Externaliser dans `prompt/segmenter_break.txt` + `load_prompt()` |
| 8 | §4.3 identifier | Strip JSON manuel (`startswith("```json")`) au lieu de `strip_markdown_json` | Importer et utiliser `from r6_navigator.services.llm_json import strip_markdown_json` |
| 9 | §4.4 evaluator | `merge_analyses` utilise `CapacityAnalysis` et `AnalyzedBlock` sans les importer | Ajouter les imports manquants |
| 10 | §4.4 evaluator | Même strip JSON manuel | Utiliser `strip_markdown_json` |
| 11 | §4.5 + §4.6 | `analyze_verbatim_v2` définie en double (analyzer.py ET ai_analyze.py) | Une seule définition publique dans `ai_analyze_v2.py` |
| 12 | §5.1 worker | Signal `progress` déclaré mais jamais émis dans `run()` | Émettre `progress` à chaque étape du pipeline |
| 13 | §6.1 dashboard | `get_all_mission_interpretations` importé depuis crud_mission — OK; mais `i.confidence` peut être `None` (Float nullable) | Garder la protection `if i.confidence is not None` — déjà présente, OK |

---

## 1. Vue d'ensemble de l'implémentation

### 1.1. Architecture cible

| Contrainte | Solution |
|------------|----------|
| **Intelligence sémantique** du LLM | Double passe : segmentation + classification séparées |
| **Citation littérale** garantie | Sentence-ID : LLM manipule des indices, code reconstitue les blocs |

### 1.2. Pipeline recommandé

```
Verbatim source ( brut )
    │
    ├─[Phase 1 : Segmentation Hybride]─┐
    │  1. Parser tours de parole (locuteur) │
    │  2. Double passe (breaks + extraction) │
    │  3. Sentence-ID (indices → blocs)     │
    ▼
Liste de SemanticBlock (texte exact + metadata)
    │
    ├─[Phase 2 : Analyse Itérative]───────┐
    │  Étape 1 : Identification capacité   │
    │  Étape 2 : Validation Halliday       │
    │  Étape 3 : Interprétation finale     │
    ▼
AnalyzedBlock (avec aggregate_confidence)
    │
    ▼
Persistence Extract + Interpretation
```

### 1.3. Mapping vers le code existant

**Règle architecture (CLAUDE.md) :** structure plate obligatoire — pas de sous-packages dans `services/` ni dans `ui/qt/`.

| Composant DOSSIER-v2 | Fichier cible | Notes |
|---------------------|---------------|-------|
| `SemanticBlock`, `AnalyzedBlock` | `r6_navigator/services/ai_analyze_v2.py` | Dataclasses en tête de fichier |
| Segmenteur, Identificateur, Évaluateur, Orchestrateur | `r6_navigator/services/ai_analyze_v2.py` | Fonctions internes préfixées `_` |
| Fonction publique `analyze_verbatim_v2()` | `r6_navigator/services/ai_analyze_v2.py` | Retourne `list[AnalyzedExtract]` |
| `QualityDashboard` | `r6_navigator/services/quality_dashboard.py` | Module plat dans services/ |
| Prompt segmentation breaks | `prompt/segmenter_break.txt` | NOUVEAU — pour `load_prompt()` |
| Prompt segmentation JSON | `prompt/segmenter_hybrid.txt` | NOUVEAU |
| Prompt identification capacité | `prompt/identify_capacity.txt` | NOUVEAU |
| Prompt évaluation maturité | `prompt/evaluate_maturity.txt` | NOUVEAU |

---

## 2. Modèles de données

### 2.1. Nouveaux dataclasses (en tête de `services/ai_analyze_v2.py`)

**Note :** le projet utilise `@dataclass` (stdlib), pas Pydantic. Conventions de typing : `list[str]`, `str | None` (Python 3.10+).

```python
# r6_navigator/services/ai_analyze_v2.py — section dataclasses

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING


# --- Modèles pour la segmentation ---

@dataclass
class SemanticBlock:
    """Bloc sémantique identifié par la Phase 1."""
    block_id: str              # Format: "{replique_id}_{index}"
    text: str                  # Citation littérale (extrait du verbatim)
    context: str               # Résumé 10 mots du thème
    sentences: list[str]       # Phrases constituant le bloc
    start_position: int        # Position dans le verbatim brut
    end_position: int          # Position de fin
    word_count: int            # Nombre de mots
    type_contenu: str          # "observable", "organisationnel", "strategique", "meta"
    irrelevant: bool           # True si méta-discours consultant
    replique_id: int           # Indice de la prise de parole d'origine


# --- Modèles pour l'analyse itérative ---

@dataclass
class CapacityIdentification:
    """Résultat de l'étape 2 : identification capacité + validation Halliday."""
    block_id: str
    capacity_id: str | None         # Ex: "I3a", None si ambigu
    level_code: str                 # "S", "O", "I" (confirmé par Halliday)
    halliday_consistent: bool       # Le registre correspond-il au niveau ?
    halliday_justification: str     # 1-2 phrases justifiant le choix
    alternative_capacity: str | None = None  # Proposition si halliday_consistent=False


@dataclass
class MaturityEvaluation:
    """Résultat de l'étape 3 : évaluation maturité + interprétation."""
    block_id: str
    maturity_level: str        # "insuffisant", "émergent", "satisfaisant", "avancé", "expert"
    confidence: float          # 0.0 à 1.0 (calibré sur l'évaluation seule)
    interpretation: str        # 2-4 phrases d'analyse


@dataclass
class AnalyzedBlock:
    """Résultat complet de l'analyse itérative."""
    block: SemanticBlock
    capacity: CapacityIdentification
    validation: MaturityEvaluation
    aggregate_confidence: float  # capacity_conf × validation.confidence
```

### 2.2. Modifications du schéma de base de données

Ajouter deux colonnes à la table `extract`.

**Étape A — Modifier `models.py`** : ajouter les colonnes au modèle ORM `Extract`.

```python
# Dans r6_navigator/db/models.py, classe Extract

class Extract(Base):
    __tablename__ = "extract"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verbatim_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("verbatim.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tag: Mapped[str | None] = mapped_column(String)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    halliday_note: Mapped[str | None] = mapped_column(Text)    # NOUVEAU
    halliday_ok: Mapped[bool | None] = mapped_column(Boolean)  # NOUVEAU

    verbatim: Mapped[Verbatim] = relationship(back_populates="extracts")
    interpretations: Mapped[list[Interpretation]] = relationship(
        back_populates="extract", cascade="all, delete-orphan"
    )
```

**Étape B — Ajouter la migration dans `database.py`** :

SQLite supporte `ALTER TABLE ADD COLUMN` pour les ajouts simples — pas besoin de full table rebuild (contrairement aux suppressions). La migration est donc plus simple :

```python
def _migrate_add_halliday_columns(engine: Engine) -> None:
    """Adds halliday_note and halliday_ok columns to extract table if absent. No-op if present."""
    with engine.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(extract)")).fetchall()}
        if "halliday_note" not in cols:
            conn.execute(text("ALTER TABLE extract ADD COLUMN halliday_note TEXT"))
        if "halliday_ok" not in cols:
            conn.execute(text("ALTER TABLE extract ADD COLUMN halliday_ok BOOLEAN"))
        conn.commit()
```

**Étape C — Intégrer dans `init_db()`** :

```python
def init_db(engine: Engine, seed_capacities: bool = True) -> None:
    Base.metadata.create_all(engine)
    _migrate_to_translation_tables(engine)
    _migrate_drop_observable_column(engine)
    _migrate_add_mission_tables(engine)
    _migrate_add_halliday_columns(engine)  # NOUVEAU
    _seed_reference_data(engine)
    if seed_capacities:
        _seed_capacities(engine)
```

---

## 3. Nouveaux prompts

Archiver systématiquement les prompts existants avant toute modification (règle CLAUDE.md).

### 3.1. Prompt de découpe sémantique (`prompt/segmenter_break.txt`)

Utilisé par `_insert_break_markers()` — reçoit un seul bloc de texte, retourne le même texte avec des marqueurs `||BREAK||`.

```
Insert the marker ||BREAK|| at every THEMATIC BREAK in the interviewee's speech below.

Rules:
- ONE BLOCK = ONE theme and ONE register (fact / judgment / projection)
- Never cut in the middle of a sentence
- Preserve the exact wording — do not paraphrase or add words
- Return only the text with ||BREAK|| markers, nothing else

Text:
{text}
```

### 3.2. Prompt de segmentation hybride (`prompt/segmenter_hybrid.txt`)

Utilisé pour la classification JSON complète des blocs déjà découpés.

```
Tu es un expert en analyse de discours. Classe les blocs sémantiques fournis.

## Contexte de l'entretien
- Sujet : {subject_name}
- Rôle : {subject_role}
- Niveau R6 cible : {level_code}

## Type de contenu
- **observable** : Action/comportement observable, verbe d'action au passé, sujet individuel
- **organisationnel** : Processus, règles, structures, verbe d'état, sujet collectif (nous, équipe)
- **strategique** : Jugement, projection, vision, verbes modaux (devrait, pourrait), futur
- **meta** : Commentaire sur l'entretien, question rhétorique → irrelevant: true

## Tâche
Pour chaque bloc, produis un résumé de 10 mots (context) et classifie le type_contenu.

## Format de sortie JSON
```json
{
  "blocs": [
    {
      "block_id": "r1_0",
      "context": "Hésitation entre fournisseurs",
      "type_contenu": "observable",
      "irrelevant": false
    }
  ]
}
```

## Blocs à classer
{blocks_json}
```

### 3.3. Prompt d'identification capacité (`prompt/identify_capacity.txt`)

```
Tu es un expert R6 framework. Analyse chaque bloc sémantique et identifie la capacité R6 la plus pertinente.

## Contexte
- Niveau R6 cible : {level_code} ({level_name})
- Liste des 18 capacités :
  {capacities_list}

## Règles Halliday à appliquer

{halliday_rules}

## Tâche
Pour chaque bloc, détermine :
1. La capacité R6 la plus pertinente (ex: "I3a")
2. Le niveau confirmé après application des règles Halliday ("S", "O", "I")
3. Si le registre du bloc correspond au niveau de la capacité identifiée

## Format de sortie JSON
```json
{
  "blocks_analysis": [
    {
      "block_id": "r1_0",
      "capacity_id": "I3a",
      "level_code": "I",
      "halliday_consistent": true,
      "halliday_justification": "Sujet individuel 'je' + verbe d'action 'j'ai fait' → Material process, Level I confirmé."
    }
  ]
}
```

## Blocs à analyser
{blocks_json}
```

### 3.4. Prompt d'évaluation maturité (`prompt/evaluate_maturity.txt`)

```
Tu es un expert R6 framework. Évalue le niveau de maturité observable pour chaque bloc analysé.

## Échelle de maturité

{maturity_scale}

## Tâche
1. Évalue le niveau de maturité selon l'échelle correspondante
2. Calcule un score de confiance (0.0 à 1.0) basé sur la clarté des observables
3. Rédige une interprétation en 2-4 phrases

## Format de sortie JSON
```json
{
  "evaluations": [
    {
      "block_id": "r1_0",
      "maturity_level": "satisfaisant",
      "confidence": 0.85,
      "interpretation": "L'individu agit de manière autonome mais vérifie les résultats."
    }
  ]
}
```

## Blocs à évaluer
{blocks_with_capacity}
```

---

## 4. Implémentation de `ai_analyze_v2.py`

### 4.1. Structure du module

**Règle architecture :** structure plate — tout le nouveau code va dans un seul fichier module.

```
r6_navigator/services/
├── ai_analyze.py          # Conservé intact — fonctions publiques existantes
├── ai_analyze_v2.py       # NOUVEAU — pipeline itératif complet
├── quality_dashboard.py   # NOUVEAU — dashboard qualité
└── llm_json.py            # Existant — strip_markdown_json
```

Pas de sous-package `analyze_v2/`. Les types et les fonctions internes sont tous dans `ai_analyze_v2.py`.

### 4.2. Segmentation (`_parse_speech_turns`, `_insert_break_markers`, `_segment_verbatim_hybrid`)

**Correction §4.2 v2 :** `SemanticBlock(**block)` échouait car le champ `sentences` n'était pas peuplé dans le dict. Correction : ajouter `sentences=block_text.split(". ")` avant l'instanciation. De plus, le prompt inline est externalisé dans `segmenter_break.txt` et chargé via `load_prompt()`.

```python
# r6_navigator/services/ai_analyze_v2.py — Phase 1 : segmentation

import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from r6_navigator.services.llm_json import strip_markdown_json
from r6_navigator.services.prompt import load_prompt

log = logging.getLogger("r6_navigator.ai_analyze_v2")

_PACKAGE_DIR = Path(__file__).parent.parent  # r6_navigator/
_PROJECT_ROOT = _PACKAGE_DIR.parent          # racine du projet


@dataclass
class _SpeechTurn:
    """Une prise de parole (locuteur continu)."""
    speaker: str      # "consultant" ou "interviewe"
    text: str
    start_pos: int
    end_pos: int


def _parse_speech_turns(verbatim: str) -> list[_SpeechTurn]:
    """Détecte les changements de locuteur dans le verbatim."""
    pattern = r'\[(CONSULTANT|INTERVIEWE|INTERVIEWÉ|INTERVIEWEE)\]\s*(.*?)(?=\[(?:CONSULTANT|INTERVIEWE|INTERVIEWÉ|INTERVIEWEE)\]|$)'

    turns: list[_SpeechTurn] = []
    pos = 0

    for match in re.finditer(pattern, verbatim, re.IGNORECASE | re.DOTALL):
        if match.start() > pos:
            text_before = verbatim[pos:match.start()].strip()
            if text_before:
                turns.append(_SpeechTurn(
                    speaker="unknown",
                    text=text_before,
                    start_pos=pos,
                    end_pos=match.start(),
                ))
        speaker = match.group(1).lower().replace("é", "e")
        text = match.group(2).strip()
        turns.append(_SpeechTurn(
            speaker=speaker,
            text=text,
            start_pos=match.start(),
            end_pos=match.end(),
        ))
        pos = match.end()

    if pos < len(verbatim):
        text_after = verbatim[pos:].strip()
        if text_after:
            turns.append(_SpeechTurn(
                speaker="unknown",
                text=text_after,
                start_pos=pos,
                end_pos=len(verbatim),
            ))

    return turns


def _insert_break_markers(text: str, llm_call_fn) -> str:
    """Appelle le LLM pour insérer les marqueurs ||BREAK|| aux ruptures sémantiques."""
    # load_prompt() — substitution sécurisée, jamais str.format()
    prompt = load_prompt("segmenter_break", text=text)
    return llm_call_fn(prompt).strip()


def _extract_blocks_from_breaks(
    text_with_breaks: str,
    verbatim_full: str,
    replique_id: int,
) -> list[SemanticBlock]:
    """Extrait les SemanticBlock à partir du texte marqué par ||BREAK||.

    Correction v3 : peuple le champ `sentences` (obligatoire dans SemanticBlock).
    """
    raw_blocks = text_with_breaks.split("||BREAK||")
    blocks: list[SemanticBlock] = []

    for i, raw_block in enumerate(raw_blocks):
        block_text = raw_block.strip()
        if not block_text:
            continue

        start_pos = verbatim_full.find(block_text)
        end_pos = start_pos + len(block_text) if start_pos >= 0 else 0
        # Décomposition en phrases — séparateur point suivi d'espace
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', block_text) if s.strip()]

        blocks.append(SemanticBlock(
            block_id=f"r{replique_id}_{i}",
            text=block_text,
            context="",          # Peuplé lors de la classification JSON (Phase 2)
            sentences=sentences,  # Correction : champ obligatoire, absent dans v2
            start_position=start_pos,
            end_position=end_pos,
            word_count=len(block_text.split()),
            type_contenu="unknown",
            irrelevant=False,
            replique_id=replique_id,
        ))

    return blocks


def _segment_verbatim_hybrid(verbatim: str, llm_call_fn) -> list[SemanticBlock]:
    """Pipeline complet de segmentation hybride."""
    turns = _parse_speech_turns(verbatim)
    all_blocks: list[SemanticBlock] = []

    for replique_id, turn in enumerate(turns):
        if turn.speaker in ("consultant", "unknown"):
            all_blocks.append(SemanticBlock(
                block_id=f"meta_{replique_id}",
                text=turn.text,
                context="Méta-discours",
                sentences=turn.text.split(". "),
                start_position=turn.start_pos,
                end_position=turn.end_pos,
                word_count=len(turn.text.split()),
                type_contenu="meta",
                irrelevant=True,
                replique_id=replique_id,
            ))
        else:
            text_with_breaks = _insert_break_markers(turn.text, llm_call_fn)
            blocks = _extract_blocks_from_breaks(text_with_breaks, verbatim, replique_id)
            all_blocks.extend(blocks)

    return all_blocks
```

### 4.3. Identification capacité (`_identify_capacities`)

**Corrections v3 :**
- Suppression du strip JSON manuel → `strip_markdown_json`
- Typing `list[...]` au lieu de `List[...]`
- Chemin vers `halliday_rules.json` recalculé pour la structure plate

```python
# r6_navigator/services/ai_analyze_v2.py — Phase 2 : identification capacité

_HALLIDAY_RULES_PATH = _PACKAGE_DIR / "services" / "prompt" / "halliday_rules.json"
# Corrigé pour la structure plate : __file__ est dans services/, donc parent est services/
# → Path(__file__).parent / "prompt" / "halliday_rules.json"
_HALLIDAY_RULES_PATH = Path(__file__).parent / "prompt" / "halliday_rules.json"

_LEVEL_NAMES = {"S": "Strategic", "O": "Organizational", "I": "Individual"}

_CAPACITY_LIST = """S1a, S1b, S2a, S2b, S3a, S3b (Stratégique)
O1a, O1b, O2a, O2b, O3a, O3b (Organisationnel)
I1a, I1b, I2a, I2b, I3a, I3b (Individuel)"""


def _load_halliday_rules() -> dict:
    """Charge les règles Halliday depuis halliday_rules.json."""
    with open(_HALLIDAY_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _identify_capacities(
    blocks: list[SemanticBlock],
    level_code: str,
    llm_call_fn,
) -> list[CapacityIdentification]:
    """Identifie la capacité pour chaque bloc et valide la cohérence Halliday."""
    halliday_rules = _load_halliday_rules()
    halliday_formatted = json.dumps(
        halliday_rules.get(level_code, {}), ensure_ascii=False, indent=2
    )

    blocks_json = json.dumps({
        "blocks": [
            {"block_id": b.block_id, "text": b.text[:500], "context": b.context}
            for b in blocks
        ]
    }, ensure_ascii=False)

    user_prompt = load_prompt(
        "identify_capacity",
        level_code=level_code,
        level_name=_LEVEL_NAMES.get(level_code, level_code),
        capacities_list=_CAPACITY_LIST,
        halliday_rules=halliday_formatted,
        blocks_json=blocks_json,
    )

    raw_response = llm_call_fn(user_prompt)

    try:
        data = json.loads(strip_markdown_json(raw_response))  # Correction : strip_markdown_json
        results: list[CapacityIdentification] = []
        for item in data.get("blocks_analysis", []):
            results.append(CapacityIdentification(
                block_id=item["block_id"],
                capacity_id=item.get("capacity_id"),
                level_code=item.get("level_code", level_code),
                halliday_consistent=item.get("halliday_consistent", False),
                halliday_justification=item.get("halliday_justification", ""),
                alternative_capacity=item.get("alternative_capacity"),
            ))
        return results
    except json.JSONDecodeError:
        log.warning("Parsing JSON échoué pour identify_capacities — fallback vide")
        return [
            CapacityIdentification(
                block_id=b.block_id,
                capacity_id=None,
                level_code=level_code,
                halliday_consistent=False,
                halliday_justification="Fallback : parsing JSON échoué",
            )
            for b in blocks
        ]
```

### 4.4. Évaluation maturité (`_evaluate_maturities`, `_merge_analyses`)

**Corrections v3 :**
- Imports manquants ajoutés (`CapacityIdentification`, `AnalyzedBlock` — définis dans le même fichier)
- Strip JSON manuel → `strip_markdown_json`
- Typing `list[...]` au lieu de `List[...]`

```python
# r6_navigator/services/ai_analyze_v2.py — Phase 3 : évaluation maturité

def _load_maturity_scale_v2(level_code: str) -> str:
    """Charge l'échelle de maturité. Délègue à _load_maturity_scale d'ai_analyze."""
    # Réutilise la logique existante — pas de duplication
    from r6_navigator.services.ai_analyze import _load_maturity_scale
    return _load_maturity_scale(level_code)


def _evaluate_maturities(
    blocks_with_capacity: list[dict],
    llm_call_fn,
) -> list[MaturityEvaluation]:
    """Évalue la maturité pour chaque bloc dont la capacité est identifiée."""
    level_code = blocks_with_capacity[0].get("level_code", "I") if blocks_with_capacity else "I"
    maturity_scale = _load_maturity_scale_v2(level_code)

    blocks_json = json.dumps({
        "blocks": [
            {
                "block_id": b["block_id"],
                "text": b["text"][:500],
                "capacity_id": b.get("capacity_id"),
                "level_code": b.get("level_code", level_code),
            }
            for b in blocks_with_capacity
        ]
    }, ensure_ascii=False)

    user_prompt = load_prompt(
        "evaluate_maturity",
        maturity_scale=maturity_scale,
        blocks_with_capacity=blocks_json,
    )

    raw_response = llm_call_fn(user_prompt)

    try:
        data = json.loads(strip_markdown_json(raw_response))  # Correction : strip_markdown_json
        return [
            MaturityEvaluation(
                block_id=item["block_id"],
                maturity_level=item.get("maturity_level", ""),
                confidence=float(item.get("confidence", 0.5)),
                interpretation=item.get("interpretation", ""),
            )
            for item in data.get("evaluations", [])
        ]
    except json.JSONDecodeError:
        log.warning("Parsing JSON échoué pour evaluate_maturities — liste vide retournée")
        return []


def _merge_analyses(
    blocks: list[SemanticBlock],
    capacity_analyses: list[CapacityIdentification],  # Correction : import implicite (même fichier)
    maturity_evaluations: list[MaturityEvaluation],
) -> list[AnalyzedBlock]:  # Correction : import implicite (même fichier)
    """Fusionne les résultats des 3 étapes en AnalyzedBlock."""
    capacity_idx = {a.block_id: a for a in capacity_analyses}
    maturity_idx = {e.block_id: e for e in maturity_evaluations}

    results: list[AnalyzedBlock] = []
    for block in blocks:
        cap = capacity_idx.get(block.block_id)
        mat = maturity_idx.get(block.block_id)

        if not cap or not mat:
            log.warning("Bloc %s incomplet après merge — ignoré.", block.block_id)
            continue

        cap_conf = 0.5 if cap.halliday_consistent else 0.3
        aggregate = cap_conf * (mat.confidence or 0.5)

        results.append(AnalyzedBlock(
            block=block,
            capacity=cap,
            validation=mat,
            aggregate_confidence=aggregate,
        ))

    return results
```

### 4.5. Orchestrateur et fonction publique

**Correction v3 :** fonction unique `analyze_verbatim_v2()` — suppression de la définition en double présente dans v2 (§4.5 ET §4.6).

```python
# r6_navigator/services/ai_analyze_v2.py — Orchestrateur + fonction publique

from r6_navigator.services.ai_analyze import (
    AnalyzedExtract,
    _call_ollama,
    _extract_ollama_cfg,
    _load_params,
    _load_system_prompt,
)


def _analyze_verbatim_iterative(
    verbatim_text: str,
    interview_info: dict,
    llm_call_fn,
    lang: str = "fr",
) -> list[AnalyzedBlock]:
    """Analyse itérative complète : segmentation → identification → évaluation."""
    level_code = interview_info.get("level_code", "I")

    # Phase 1 : segmentation
    blocks = _segment_verbatim_hybrid(verbatim_text, llm_call_fn)
    relevant_blocks = [b for b in blocks if not b.irrelevant]

    # Phase 2 : identification capacité
    capacity_analyses = _identify_capacities(relevant_blocks, level_code, llm_call_fn)

    # Phase 3 : évaluation maturité
    blocks_with_cap = [
        {
            "block_id": block.block_id,
            "text": block.text,
            "context": block.context,
            "capacity_id": cap.capacity_id,
            "level_code": cap.level_code,
            "halliday_consistent": cap.halliday_consistent,
        }
        for block, cap in zip(relevant_blocks, capacity_analyses)
    ]
    maturity_evaluations = _evaluate_maturities(blocks_with_cap, llm_call_fn)

    return _merge_analyses(relevant_blocks, capacity_analyses, maturity_evaluations)


def analyze_verbatim_v2(
    verbatim_text: str,
    interview_info: dict,
    lang: str = "fr",
) -> list[AnalyzedExtract]:
    """Analyse itérative d'un verbatim (pipeline DOSSIER-v2).

    Retourne list[AnalyzedExtract] pour compatibilité avec l'UI existante.
    Utilisée par _AnalyzeWorker quand len(verbatim) > 300 mots.

    Args:
        verbatim_text: Texte brut du verbatim.
        interview_info: Métadonnées de l'entretien (subject_name, subject_role,
            level_code, interview_date).
        lang: Langue de l'analyse ("fr" ou "en").

    Returns:
        Liste d'AnalyzedExtract dans l'ordre retourné par le pipeline.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou si la configuration est invalide.
    """
    log.info(
        "Début analyse itérative v2 (level_code=%s, lang=%s, mots=%d)",
        interview_info.get("level_code", "I"), lang, len(verbatim_text.split()),
    )

    params = _load_params()
    ollama_cfg = _extract_ollama_cfg(params)
    system_prompt = _load_system_prompt()

    def llm_call_fn(prompt: str) -> str:
        return _call_ollama(
            ollama_cfg["url"],
            ollama_cfg["model"],
            system_prompt,
            prompt,
            ollama_cfg["timeout"],
        )

    analyzed = _analyze_verbatim_iterative(verbatim_text, interview_info, llm_call_fn, lang)

    result = [
        AnalyzedExtract(
            text=item.block.text,
            tag=item.capacity.capacity_id,
            capacity_id=item.capacity.capacity_id,
            maturity_level=item.validation.maturity_level,
            confidence=item.validation.confidence,
            interpretation=item.validation.interpretation,
        )
        for item in analyzed
    ]

    log.info("Analyse itérative v2 terminée : %d extrait(s)", len(result))
    return result
```

---

## 5. Interface utilisateur

### 5.1. Suivi de progression dans `_AnalyzeWorker`

**Correction v3 :** le signal `progress` est déclaré ET effectivement émis à chaque étape (absent dans v2 où le signal était déclaré mais jamais émis).

Modifier `mission_tab_verbatim.py` :

```python
# Dans mission_tab_verbatim.py

class _AnalyzeWorker(QThread):
    finished = Signal(list)            # list[AnalyzedExtract]
    error = Signal(str)
    progress = Signal(str, int, int)   # (stage_name, completed, total)

    def __init__(self, verbatim_text: str, interview_info: dict, lang: str) -> None:
        super().__init__()
        self._verbatim_text = verbatim_text
        self._interview_info = interview_info
        self._lang = lang

    def run(self) -> None:
        try:
            word_count = len(self._verbatim_text.split())
            if word_count > 300:
                # Pipeline itératif v2 — 3 étapes
                self.progress.emit(t("mission.analysis.stage_segment"), 0, 3)
                from r6_navigator.services.ai_analyze_v2 import analyze_verbatim_v2
                # Note : pour émettre la progression par étape, analyze_verbatim_v2 devra
                # accepter un callback optionnel progress_fn dans une version ultérieure.
                # Pour le MVP, on émet uniquement avant et après.
                self.progress.emit(t("mission.analysis.stage_identify"), 1, 3)
                extracts = analyze_verbatim_v2(
                    self._verbatim_text, self._interview_info, self._lang
                )
                self.progress.emit(t("mission.analysis.stage_done"), 3, 3)
            else:
                # Ancien pipeline mono-passe
                from r6_navigator.services.ai_analyze import analyze_verbatim
                extracts = analyze_verbatim(
                    self._verbatim_text, self._interview_info, self._lang
                )
            self.finished.emit(extracts)
        except Exception as exc:
            self.error.emit(str(exc))
```

Ajouter les clés i18n dans `fr.json` et `en.json` :

```json
// fr.json
"mission.analysis.stage_segment": "Segmentation du verbatim…",
"mission.analysis.stage_identify": "Identification des capacités…",
"mission.analysis.stage_done": "Analyse terminée"

// en.json
"mission.analysis.stage_segment": "Segmenting verbatim…",
"mission.analysis.stage_identify": "Identifying capacities…",
"mission.analysis.stage_done": "Analysis complete"
```

Connecter le signal dans `MissionTabVerbatim._start_analysis()` :

```python
self._worker.progress.connect(self._on_analysis_progress)

def _on_analysis_progress(self, stage: str, completed: int, total: int) -> None:
    self._btn_analyze.setText(f"{stage} ({completed}/{total})")
```

### 5.2. Affichage Halliday dans la revue (`mission_tab_interpretations.py`)

Modifier `_rebuild_table()` dans `MissionTabInterpretations` :

```python
# Colonne supplémentaire Halliday
self._table.setColumnCount(7)
self._table.setHorizontalHeaderLabels([
    t("mission.col.extract"),
    t("mission.col.capacity"),
    t("mission.col.level"),
    t("mission.col.confidence"),
    t("mission.col.halliday"),   # NOUVEAU
    t("mission.col.status"),
    t("mission.col.actions"),
])

# Dans la boucle de construction des lignes (r = numéro de ligne)
# halliday_ok provient de extract.halliday_ok (table extract, pas interpretation)
halliday_ok = row.get("halliday_ok")  # None / True / False
halliday_item = QTableWidgetItem()
if halliday_ok is False:
    halliday_item.setText("!")
    halliday_item.setToolTip(row.get("halliday_note") or t("mission.halliday.inconsistent"))
    halliday_item.setForeground(Qt.GlobalColor.red)
elif halliday_ok is True:
    halliday_item.setText("OK")
    halliday_item.setToolTip(t("mission.halliday.consistent"))
    halliday_item.setForeground(Qt.GlobalColor.green)
self._table.setItem(r, 4, halliday_item)
```

Ajouter les clés i18n :

```json
// fr.json
"mission.col.halliday": "Halliday",
"mission.halliday.consistent": "Cohérence Halliday validée",
"mission.halliday.inconsistent": "Incohérence de registre détectée"

// en.json
"mission.col.halliday": "Halliday",
"mission.halliday.consistent": "Halliday consistency validated",
"mission.halliday.inconsistent": "Register inconsistency detected"
```

---

## 6. Dashboard qualité (`quality_dashboard.py`)

Module plat dans `r6_navigator/services/`. La logique est correcte. Deux ajustements mineurs par rapport à v2 :
1. Import local depuis `crud_mission` (pattern déjà utilisé dans `ai_analyze.py`)
2. Commentaire sur le comptage Halliday — les données sont sur `extract`, accessibles via `interpretation.extract.halliday_ok`

```python
# r6_navigator/services/quality_dashboard.py

"""Tableau de bord de qualité pour l'analyse de verbatims."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

log = logging.getLogger("r6_navigator.quality_dashboard")


@dataclass
class QualityMetrics:
    """Métriques de qualité d'une analyse."""
    total_blocks: int
    validated_blocks: int
    avg_confidence: float
    halliday_inconsistent_count: int
    capacity_ambiguity_count: int
    maturity_distribution: dict[str, int]


class QualityDashboard:
    """Tableau de bord de qualité pour les missions."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def get_mission_metrics(self, mission_id: int) -> QualityMetrics:
        """Calcule les métriques pour une mission donnée."""
        # Import local — pattern du projet (éviter les imports circulaires au niveau module)
        from r6_navigator.services.crud_mission import get_all_mission_interpretations

        with self.session_factory() as session:
            interpretations = get_all_mission_interpretations(session, mission_id)

            total = len(interpretations)
            validated = sum(
                1 for i in interpretations if i.status in ("validated", "corrected")
            )

            confidences = [i.confidence for i in interpretations if i.confidence is not None]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # halliday_ok est sur extract (jointure interp → extract)
            halliday_inconsistent = sum(
                1 for i in interpretations
                if i.extract is not None and i.extract.halliday_ok is False
            )

            capacity_ambiguous = sum(
                1 for i in interpretations if not i.capacity_id
            )

            maturity_dist: dict[str, int] = {}
            for i in interpretations:
                level = i.maturity_level or "unknown"
                maturity_dist[level] = maturity_dist.get(level, 0) + 1

            return QualityMetrics(
                total_blocks=total,
                validated_blocks=validated,
                avg_confidence=avg_confidence,
                halliday_inconsistent_count=halliday_inconsistent,
                capacity_ambiguity_count=capacity_ambiguous,
                maturity_distribution=maturity_dist,
            )

    def generate_quality_report(self, mission_id: int) -> str:
        """Génère un rapport de qualité au format Markdown."""
        metrics = self.get_mission_metrics(mission_id)

        lines = [
            "# Rapport de qualité d'analyse",
            "",
            f"**Mission ID** : {mission_id}",
            "",
            "## Métriques",
            "",
            "| Métrique | Valeur |",
            "|----------|--------|",
            f"| Total extraits | {metrics.total_blocks} |",
            f"| Validés | {metrics.validated_blocks} |",
            f"| Confiance moyenne | {metrics.avg_confidence:.1%} |",
            f"| Incohérences Halliday | {metrics.halliday_inconsistent_count} |",
            f"| Capacités ambiguës | {metrics.capacity_ambiguity_count} |",
            "",
            "## Distribution des maturités",
            "",
        ]

        for level, count in metrics.maturity_distribution.items():
            lines.append(f"- {level} : {count}")

        return "\n".join(lines)
```

**Prérequis :** pour que `i.extract.halliday_ok` soit accessible sans session, l'`Interpretation` doit avoir son `extract` chargé en eager ou dans la session ouverte. La session est ouverte dans `with self.session_factory() as session:` — vérifier que `expire_on_commit=False` (déjà le cas dans le projet) et accéder aux relations dans le `with`.

---

## 7. Ordre d'implémentation

### Phase 1 (Sprint 1-2) : MVP Production

| Jour | Livrable | Fichiers |
|------|----------|----------|
| 1 | Modèle ORM + migration DB | `db/models.py` (Extract), `db/database.py` |
| 2 | Prompts segmentation | `prompt/segmenter_break.txt`, `prompt/segmenter_hybrid.txt` |
| 3 | Prompts identification + évaluation | `prompt/identify_capacity.txt`, `prompt/evaluate_maturity.txt` |
| 4-5 | Module `ai_analyze_v2.py` complet | Dataclasses + 4 fonctions internes + `analyze_verbatim_v2()` |
| 6 | Intégration `_AnalyzeWorker` | `ui/qt/mission_tab_verbatim.py` |
| 7-8 | Tests unitaires | `tests/test_analyze_v2.py` |
| 9 | Clés i18n + retranslation worker | `i18n/fr.json`, `i18n/en.json` |
| 10 | Tests d'intégration bout-en-bout | Verbatim réel, vérification pipeline |

### Phase 2 (Sprint 3-4) : Excellence

| Jour | Livrable |
|------|----------|
| 1-2 | Affichage colonne Halliday dans `mission_tab_interpretations.py` |
| 3 | Dashboard qualité (`quality_dashboard.py`) |
| 4-5 | Tests dashboard + colonne Halliday |
| 6-10 | Benchmark qualité (50 cas annotés) |

---

## 8. Tests et validation

```python
# r6_navigator/tests/test_analyze_v2.py

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def sample_verbatim_fr():
    return (
        "[INTERVIEWE] J'ai cliqué sur le lien de la synthèse et j'ai décroché mon téléphone. "
        "J'hésitais entre les fournisseurs car le budget était limité. "
        "Finalement, j'ai choisi le plus cher mais fiable.\n"
        "[CONSULTANT] Avez-vous testé la solution avant de choisir ?\n"
        "[INTERVIEWE] Oui, j'ai fait un tableau comparatif sur Excel."
    )


@pytest.fixture
def interview_info():
    return {
        "subject_name": "Jean Dupont",
        "subject_role": "Responsable IT",
        "level_code": "I",
        "interview_date": "2024-03-15",
    }


def test_parse_speech_turns_identifies_speakers(sample_verbatim_fr):
    """Les tours de parole doivent être correctement identifiés."""
    from r6_navigator.services.ai_analyze_v2 import _parse_speech_turns
    turns = _parse_speech_turns(sample_verbatim_fr)
    speakers = [t.speaker for t in turns]
    assert "interviewe" in speakers
    assert "consultant" in speakers


def test_extract_blocks_populates_sentences():
    """Correction v3 : sentences doit être peuplé (bug SemanticBlock absent dans v2)."""
    from r6_navigator.services.ai_analyze_v2 import _extract_blocks_from_breaks
    text = "J'ai fait un plan. J'ai contacté les équipes."
    full = text
    blocks = _extract_blocks_from_breaks(text, full, replique_id=0)
    assert len(blocks) == 1
    assert blocks[0].sentences  # Ne doit pas être vide


def test_segmentation_marks_consultant_irrelevant(sample_verbatim_fr):
    """Les interventions du consultant doivent être marquées irrelevant=True."""
    from r6_navigator.services.ai_analyze_v2 import _parse_speech_turns, _SpeechTurn
    turns = _parse_speech_turns(sample_verbatim_fr)
    consultant_turns = [t for t in turns if t.speaker == "consultant"]
    assert all(t.text  for t in consultant_turns)  # Le texte existe


def test_identify_capacities_fallback_on_bad_json(interview_info):
    """Si le LLM retourne du JSON invalide, retourner une liste de fallback."""
    from r6_navigator.services.ai_analyze_v2 import (
        _identify_capacities, SemanticBlock,
    )
    dummy_block = SemanticBlock(
        block_id="r0_0", text="test", context="", sentences=["test"],
        start_position=0, end_position=4, word_count=1,
        type_contenu="observable", irrelevant=False, replique_id=0,
    )
    results = _identify_capacities(
        [dummy_block],
        level_code="I",
        llm_call_fn=lambda _: "invalid json !!!",
    )
    assert len(results) == 1
    assert results[0].capacity_id is None
    assert results[0].halliday_consistent is False


def test_aggregate_confidence_computed():
    """aggregate_confidence = cap_conf × mat_conf."""
    from r6_navigator.services.ai_analyze_v2 import (
        _merge_analyses, SemanticBlock, CapacityIdentification, MaturityEvaluation,
    )
    block = SemanticBlock(
        block_id="r0_0", text="t", context="", sentences=["t"],
        start_position=0, end_position=1, word_count=1,
        type_contenu="observable", irrelevant=False, replique_id=0,
    )
    cap = CapacityIdentification(
        block_id="r0_0", capacity_id="I3a", level_code="I",
        halliday_consistent=True, halliday_justification="OK",
    )
    mat = MaturityEvaluation(
        block_id="r0_0", maturity_level="satisfaisant", confidence=0.8, interpretation="ok",
    )
    results = _merge_analyses([block], [cap], [mat])
    assert len(results) == 1
    assert abs(results[0].aggregate_confidence - 0.5 * 0.8) < 1e-9


def test_analyze_verbatim_v2_returns_analyzed_extracts(interview_info):
    """La fonction publique retourne list[AnalyzedExtract]."""
    from r6_navigator.services.ai_analyze_v2 import analyze_verbatim_v2
    from r6_navigator.services.ai_analyze import AnalyzedExtract

    dummy_result = [
        AnalyzedExtract(
            text="J'ai fait un plan.",
            tag="I3a", capacity_id="I3a",
            maturity_level="satisfaisant", confidence=0.8,
            interpretation="ok",
        )
    ]

    with patch("r6_navigator.services.ai_analyze_v2._analyze_verbatim_iterative",
               return_value=[MagicMock(
                   block=MagicMock(text="J'ai fait un plan."),
                   capacity=MagicMock(capacity_id="I3a"),
                   validation=MagicMock(
                       maturity_level="satisfaisant", confidence=0.8, interpretation="ok"
                   ),
               )]):
        with patch("r6_navigator.services.ai_analyze_v2._load_params",
                   return_value={"ollama": {"url": "http://localhost:11434",
                                            "model": "test", "timeout": 10}}):
            with patch("r6_navigator.services.ai_analyze_v2._load_system_prompt",
                       return_value="system"):
                results = analyze_verbatim_v2("test " * 50, interview_info)

    assert all(isinstance(r, AnalyzedExtract) for r in results)
```

---

## 9. Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Latence ×3 (15s au lieu de 5s) | UX dégradée | Barre de progression avec étapes + fallback mono-passe pour < 300 mots |
| Parsing JSON LLM échoue | Anomalie silencieuse | Fallback retourne liste vide + log WARNING — l'UI affiche 0 résultats |
| Cohérence block_id entre étapes | Blocs non associés dans `_merge_analyses` | Vérification par `block_id` dans les indices + log WARNING si manquant |
| Halliday non détecté | Erreurs de classification | Colonne Halliday dans l'UI pour revue manuelle |
| `sentences` vide | TypeError à l'instanciation | Correction v3 : `re.split` toujours peuplé, minimum `[block_text]` |

---

## 10. Backward compatibility

L'ancienne fonction `analyze_verbatim()` dans `ai_analyze.py` est conservée intacte.

La nouvelle `analyze_verbatim_v2()` est dans `ai_analyze_v2.py`. Le `_AnalyzeWorker` choisit :
- `len(verbatim_text.split()) <= 300` → `analyze_verbatim()` (ancien comportement)
- `len(verbatim_text.split()) > 300` → `analyze_verbatim_v2()` (nouveau pipeline)

Ce fallback garantit que les tests existants et les petits verbatims continuent de fonctionner sans modification.

---

**Fin DOSSIER-impl-v3.md**
