# DOSSIER-impl-v2.md — Plan d'Implémentation

**Version** : 1.0.0
**Date** : 2026-03-05
**Statut** : Plan d'implémentation détaillé pour DOSSIER-v2.md

---

## 1. Vue d'ensemble de l'implémentation

### 1.1. Architecture cible

L'implémentation poursuit deux objectifs contradictoires :

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

| Composant DOSSIER-v2 | Fichier cible | Notes |
|---------------------|---------------|-------|
| `SemanticBlock` | Nouveau dataclass | `r6_navigator/services/analyze_v2/models.py` |
| `IterativeAnalyzer` | Modifier `ai_analyze.py` | Nouvelle fonction `analyze_verbatim_v2()` |
| `QualityDashboard` | Nouveau module | `r6_navigator/services/quality_dashboard.py` |
| Prompts segmentation | Nouveau fichier | `prompt/segmenter_hybrid.txt` |
| Prompts analyse itérative | Modifier existant | `prompt/identify_capacity.txt`, `valider_niveau.txt` |

---

## 2. Modèles de données

### 2.1. Nouveaux modèles Pydantic (à créer dans `services/analyze_v2/models.py`)

```python
# services/analyze_v2/models.py

from pydantic import BaseModel
from typing import List, Optional
from dataclasses import dataclass

# --- Modèles pour la segmentation ---

@dataclass
class SemanticBlock:
    """Bloc sémantique identifié par la Phase 1."""
    block_id: str              # Format: "{replique_id}_{index}"
    text: str                  # Citation littérale (extrait du verbatim)
    context: str               # Résumé 10 mots du thème
    sentences: List[str]       # Phrases constituant le bloc
    start_position: int        # Position dans le verbatim brut
    end_position: int          # Position de fin
    word_count: int            # Nombre de mots
    type_contenu: str          # "observable", "organisationnel", "strategique", "meta"
    irrelevant: bool           # true si meta-discours consultant
    replique_id: str           # ID de la prise de parole d'origine


# --- Modèles pour l'analyse itérative ---

@dataclass
class CapacityIdentification:
    """Résultat de l'étape 2 : identification capacité + validation Halliday."""
    capacity_id: Optional[str]      # Ex: "I3a", None si ambigu
    level_code: str                 # "S", "O", "I" (confirmé par Halliday)
    halliday_consistent: bool       # Le registre correspond-il au niveau ?
    halliday_justification: str     # 1-2 phrases justifiant le choix
    alternative_capacity: Optional[str]  # Proposition si halliday_consistent=False


@dataclass
class MaturityEvaluation:
    """Résultat de l'étape 3 : évaluation maturité + interprétation."""
    maturity_level: str        # "insuffisant", "émergent", "satisfaisant", "avancé", "expert"
    confidence: float          # 0.0 à 1.0 (calibré sur l'évaluation seule)
    interpretation: str        # 2-4 phrases d'analyse


@dataclass
class AnalyzedBlock:
    """Résultat complet de l'analyse itérative."""
    block: SemanticBlock
    capacity: CapacityIdentification
    validation: MaturityEvaluation
    aggregate_confidence: float  # capacity.conf × validation.conf × interpretation.conf
```

### 2.2. Modifications du schéma de base de données

**Option retenue : Option B** (voir DOSSIER.md §4)

Ajouter deux colonnes à la table `extract` :

```sql
ALTER TABLE "extract" ADD COLUMN halliday_note TEXT;
ALTER TABLE "extract" ADD COLUMN halliday_ok BOOLEAN;
```

**Migration à ajouter dans `database.py` :**

```python
def _migrate_add_halliday_columns(engine: Engine) -> None:
    """Adds halliday_note and halliday_ok columns to extract table if absent."""
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(extract)")).fetchall()
        cols = {r[1] for r in rows}
        if "halliday_note" in cols and "halliday_ok" in cols:
            return  # Already migrated

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("PRAGMA foreign_keys = OFF")

        # SQLite requires full table rebuild
        cur.execute("""
            CREATE TABLE extract_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verbatim_id INTEGER NOT NULL REFERENCES verbatim(id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                tag TEXT,
                display_order INTEGER NOT NULL DEFAULT 0,
                halliday_note TEXT,
                halliday_ok BOOLEAN
            )
        """)
        cur.execute("""
            INSERT INTO extract_v2
                (id, verbatim_id, text, tag, display_order)
            SELECT id, verbatim_id, text, tag, display_order FROM extract
        """)
        cur.execute("DROP TABLE extract")
        cur.execute("ALTER TABLE extract_v2 RENAME TO extract")
        cur.execute("PRAGMA foreign_keys = ON")
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
```

**Intégration dans `init_db()` :**

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

### 3.1. Prompt de segmentation hybride (`prompt/segmenter_hybrid.txt`)

```
Tu es un expert en analyse de discours. Segmentes les réponses de l'interviewé en blocs sémantiques COHÉRENTS.

## Contexte de l'entretien
- Sujet : {subject_name}
- Rôle : {subject_role}
- Niveau R6 cible : {level_code}

## Tâche
1. Identifier les CHANGEMENTS DE REGISTRE (fait → jugement → projection)
2. Insérer le marqueur exact `||BREAK||` à chaque rupture
3. Produire un résumé de 10 mots pour chaque bloc
4. Classer chaque bloc selon son type : observable, organisationnel, strategique, meta

## Règles
- UN BLOC = UN thème, UN registre
- Ne pas couper au milieu d'une phrase
- Ignorer les "euh", "ben", les fausses reprises
- Conserver la formulation exacte
- Marquer `irrelevant: true` pour les questions du consultant et le méta-discours

## Type de contenu
- **observable** : Action/comportement observable, verbe d'action au passé composé, sujet individuel
- **organisationnel** : Processus, règles, structures, verbe d'état, sujet collectif (nous, équipe)
- **stratégique** : Jugement, projection, vision, verbes modaux (devrait, pourrait), futur
- **meta** : Commentaire sur l'entretien, question rhétorique → irrelevant: true

## Exemple de sortie JSON
```json
{
  "blocs": [
    {
      "block_id": "r1_0",
      "context": "Hésitation entre fournisseurs",
      "text": "J'hésitais entre les fournisseurs.",
      "type_contenu": "observable",
      "irrelevant": false
    },
    {
      "block_id": "r2_0",
      "context": "Processus de décision rationnel",
      "text": "J'ai fait un tableau comparatif.",
      "type_contenu": "observable",
      "irrelevant": false
    },
    {
      "block_id": "r2_1",
      "context": "Choix qualité sur coût",
      "text": "J'ai choisi le plus cher mais fiable.",
      "type_contenu": "strategique",
      "irrelevant": false
    },
    {
      "block_id": "meta_1",
      "context": "Question du consultant",
      "text": "Avez-vous testé la solution ?",
      "type_contenu": "meta",
      "irrelevant": true
    }
  ]
}
```

## Texte à segmenter
{verbatim_text}
```

### 3.2. Prompt d'identification capacité (`prompt/identify_capacity.txt`)

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

### 3.3. Prompt d'évaluation maturité (`prompt/evaluate_maturity.txt`)

```
Tu es un expert R6 framework. Évalue le niveau de maturité observable pour chaque bloc analysé.

## Échelle de maturité

{maturity_scale}

## Données disponibles
- Bloc analysé : {block_text}
- Capacité identifiée : {capacity_id}
- Niveau validé : {level_code}

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
      "interpretation": "L'individu agit de manière autonome mais vérifie les résultats, indiquant un équilibre entre action et réflexion."
    }
  ]
}
```

## Blocs à évaluer
{blocks_with_capacity}
```

---

## 4. Implémentation duanalyze_v2.py

### 4.1. Structure du module

```
r6_navigator/services/
├── ai_analyze.py          # Ancien module (conservé pour compat)
├── analyze_v2/            # NOUVEAU module
│   ├── __init__.py
│   ├── models.py          # SemanticBlock, AnalyzedBlock, etc.
│   ├── segmenter.py       # Phase 1 : segmentation
│   ├── identifier.py      # Phase 2 : identification capacité
│   ├── evaluator.py       # Phase 3 : évaluation maturité
│   └── analyzer.py        # Orchestrateur global
```

### 4.2. Code de segmentation (`analyze_v2/segmenter.py`)

```python
# r6_navigator/services/analyze_v2/segmenter.py

"""Phase 1 : Segmentation hybride du verbatim."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class SpeechTurn:
    """Une prise de parole (locuteur continu)."""
    speaker: str      # "consultant" ou "interviewe"
    text: str
    start_pos: int
    end_pos: int


def parse_speech_turns(verbatim: str) -> List[SpeechTurn]:
    """Détecte les changements de locuteur dans le verbatim."""
    # Pattern pour détecter les marqueurs de locuteur
    # Ex: "[CONSULTANT]", "[INTERVIEWE]", ou simple détecteur basé sur le contexte
    pattern = r'\[(CONSULTANT|INTERVIEWE|INTERVIEWÉ|INTERVIEWEE)\]\s*(.*)'

    turns = []
    pos = 0

    for match in re.finditer(pattern, verbatim, re.IGNORECASE):
        if match.start() > pos:
            # Texte non marqué entre les marques
            text_before = verbatim[pos:match.start()]
            if text_before.strip():
                turns.append(SpeechTurn(
                    speaker="unknown",
                    text=text_before.strip(),
                    start_pos=pos,
                    end_pos=match.start()
                ))

        speaker = match.group(1).lower().replace("é", "e")
        text = match.group(2).strip()
        turns.append(SpeechTurn(
            speaker=speaker,
            text=text,
            start_pos=match.start(),
            end_pos=match.end()
        ))
        pos = match.end()

    # Texte restant
    if pos < len(verbatim):
        text_after = verbatim[pos:].strip()
        if text_after:
            turns.append(SpeechTurn(
                speaker="unknown",
                text=text_after,
                start_pos=pos,
                end_pos=len(verbatim)
            ))

    return turns


def insert_break_markers(text: str, llm_call_fn) -> str:
    """Appelle LLM pour insérer les marqueurs ||BREAK|| aux ruptures sémantiques."""
    # Prompt simplifié pour cette étape
    prompt = f"""Segmentes ce texte en insérant ||BREAK|| aux ruptures thématiques.
Règles : ne pas couper au milieu d'une phrase. Un bloc = un thème.

Texte :
{text}

Réponse (texte avec ||BREAK||) :"""

    result = llm_call_fn(prompt)
    return result.strip()


def extract_blocks_from_breaks(text_with_breaks: str, verbatim_full: str) -> List[dict]:
    """Extrait les blocs à partir du texte marqué par ||BREAK||."""
    raw_blocks = text_with_breaks.split("||BREAK||")

    blocks = []
    for i, raw_block in enumerate(raw_blocks):
        block_text = raw_block.strip()
        if not block_text:
            continue

        # Chercher la position dans le verbatim original
        start_pos = verbatim_full.find(block_text)
        end_pos = start_pos + len(block_text) if start_pos >= 0 else 0

        blocks.append({
            "block_id": f"block_{i:03d}",
            "text": block_text,
            "start_position": start_pos,
            "end_position": end_pos,
            "word_count": len(block_text.split()),
            "type_contenu": "unknown",  # À déterminer en phase 2
            "irrelevant": False,
            "context": ""  # À générer
        })

    return blocks


def segment_verbatim_hybrid(verbatim: str, llm_call_fn) -> List[SemanticBlock]:
    """Pipeline complet de segmentation hybride (Approche 6 + 1)."""
    # Étape 1 : Parser les tours de parole
    turns = parse_speech_turns(verbatim)

    all_blocks = []
    replique_id = 0

    for turn in turns:
        if turn.speaker == "consultant":
            # Meta-discours consultant
            all_blocks.append(SemanticBlock(
                block_id=f"meta_{replique_id}",
                text=turn.text,
                context="Méta-discours consultant",
                sentences=turn.text.split(". "),
                start_position=turn.start_pos,
                end_position=turn.end_pos,
                word_count=len(turn.text.split()),
                type_contenu="meta",
                irrelevant=True,
                replique_id=replique_id
            ))
        else:
            # Étape 2 : Double passe pour l'interviewé
            text_with_breaks = insert_break_markers(turn.text, llm_call_fn)
            blocks_raw = extract_blocks_from_breaks(text_with_breaks, verbatim)

            for block in blocks_raw:
                block["replique_id"] = replique_id
                all_blocks.append(SemanticBlock(**block))

        replique_id += 1

    return all_blocks
```

### 4.3. Code d'identification capacité (`analyze_v2/identifier.py`)

```python
# r6_navigator/services/analyze_v2/identifier.py

"""Phase 2 : Identification capacité + validation Halliday."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from r6_navigator.services.prompt import load_prompt


@dataclass
class CapacityAnalysis:
    block_id: str
    capacity_id: Optional[str]
    level_code: str
    halliday_consistent: bool
    halliday_justification: str
    alternative_capacity: Optional[str] = None


def load_halliday_rules() -> dict:
    """Charge les règles Halliday depuis halliday_rules.json."""
    path = Path(__file__).parent.parent / "prompt" / "halliday_rules.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_capacity_definitions() -> dict:
    """Charge les définitions courtes des 18 capacités."""
    # À implémenter : charger depuis capacities_fr.yml / capacities_en.yml
    # Pour MVP, on retourne une structure vide (le LLM connaît les 18 capacités)
    return {}


def identify_capacities(
    blocks: List[dict],
    level_code: str,
    llm_call_fn,
    lang: str = "fr"
) -> List[CapacityAnalysis]:
    """Identifie la capacité pour chaque bloc et valide la cohérence Halliday."""

    halliday_rules = load_halliday_rules()
    capacities = load_capacity_definitions()

    # Formatage des blocs pour le prompt
    blocks_json = json.dumps({
        "blocks": [
            {
                "block_id": b["block_id"],
                "text": b["text"][:500],  # Limite taille
                "context": b.get("context", "")
            }
            for b in blocks
        ]
    }, ensure_ascii=False)

    # Formatage des règles Halliday
    halliday_formatted = json.dumps(halliday_rules.get(level_code, {}), ensure_ascii=False, indent=2)

    # Formatage des capacités (18 capacités)
    capacity_list = """
S1a, S1b, S2a, S2b, S3a, S3b (Stratégique)
O1a, O1b, O2a, O2b, O3a, O3b (Organisationnel)
I1a, I1b, I2a, I2b, I3a, I3b (Individuel)
"""

    # Charger le prompt
    user_prompt = load_prompt(
        "identify_capacity",
        level_code=level_code,
        level_name={"S": "Strategic", "O": "Organizational", "I": "Individual"}.get(level_code, level_code),
        capacities_list=capacity_list,
        halliday_rules=halliday_formatted,
        blocks_json=blocks_json,
    )

    # Appel LLM
    raw_response = llm_call_fn(user_prompt)

    # Parsing
    try:
        clean = raw_response.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        data = json.loads(clean)
        results = []

        for item in data.get("blocks_analysis", []):
            results.append(CapacityAnalysis(
                block_id=item["block_id"],
                capacity_id=item.get("capacity_id"),
                level_code=item.get("level_code", level_code),
                halliday_consistent=item.get("halliday_consistent", False),
                halliday_justification=item.get("halliday_justification", ""),
                alternative_capacity=item.get("alternative_capacity")
            ))

        return results
    except json.JSONDecodeError:
        # Fallback : retourner une analyse vide
        return [
            CapacityAnalysis(
                block_id=b["block_id"],
                capacity_id=None,
                level_code=level_code,
                halliday_consistent=False,
                halliday_justification="Fallback : parsing JSON échoué",
                alternative_capacity=None
            )
            for b in blocks
        ]
```

### 4.4. Code d'évaluation maturité (`analyze_v2/evaluator.py`)

```python
# r6_navigator/services/analyze_v2/evaluator.py

"""Phase 3 : Évaluation maturité + interprétation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from r6_navigator.services.prompt import load_prompt


@dataclass
class MaturityEvaluation:
    block_id: str
    maturity_level: str
    confidence: float
    interpretation: str


def load_maturity_scale(level_code: str) -> str:
    """Charge l'échelle de maturité pour un niveau donné."""
    scales_dir = Path(__file__).parent.parent.parent / "maturity_scales"

    filenames = {
        "I": "I6_EQF_Proficiency_Levels_short.md",
        "O": "O6_Maturity_Levels_short.md",
        "S": "S6_Maturity_Levels_short.md",
    }

    filename = filenames.get(level_code)
    if not filename:
        return ""

    path = scales_dir / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def evaluate_maturities(
    blocks_with_capacity: List[dict],
    llm_call_fn,
    lang: str = "fr"
) -> List[MaturityEvaluation]:
    """Évalue la maturité pour chaque bloc dont la capacité est identifiée."""

    level_code = blocks_with_capacity[0].get("level_code", "I") if blocks_with_capacity else "I"
    maturity_scale = load_maturity_scale(level_code)

    # Formatage des données
    blocks_json = json.dumps({
        "blocks": [
            {
                "block_id": b["block_id"],
                "text": b["text"][:500],
                "capacity_id": b.get("capacity_id"),
                "level_code": b.get("level_code", level_code)
            }
            for b in blocks_with_capacity
        ]
    }, ensure_ascii=False)

    # Charger le prompt
    user_prompt = load_prompt(
        "evaluate_maturity",
        maturity_scale=maturity_scale,
        blocks_with_capacity=blocks_json,
    )

    # Appel LLM
    raw_response = llm_call_fn(user_prompt)

    # Parsing
    try:
        clean = raw_response.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        data = json.loads(clean)
        results = []

        for item in data.get("evaluations", []):
            results.append(MaturityEvaluation(
                block_id=item["block_id"],
                maturity_level=item.get("maturity_level", ""),
                confidence=float(item.get("confidence", 0.5)),
                interpretation=item.get("interpretation", "")
            ))

        return results
    except json.JSONDecodeError:
        return []


def merge_analyses(
    blocks: List[dict],
    capacity_analyses: List[CapacityAnalysis],
    maturity_evaluations: List[MaturityEvaluation]
) -> List[AnalyzedBlock]:
    """Fusionne les résultats des 3 étapes en AnalyzedBlock."""

    # Index by block_id
    capacity_idx = {a.block_id: a for a in capacity_analyses}
    maturity_idx = {e.block_id: e for e in maturity_evaluations}

    results = []
    for block in blocks:
        cap = capacity_idx.get(block["block_id"])
        mat = maturity_idx.get(block["block_id"])

        if not cap or not mat:
            continue  # Bloc incomplet

        # Calcul de la confiance agrégée
        # Note : confidence de base 0.5 si non fourni
        cap_conf = 0.5 if cap.halliday_consistent else 0.3
        mat_conf = mat.confidence if mat.confidence else 0.5

        aggregate = cap_conf * mat_conf

        results.append(AnalyzedBlock(
            block=block,  # Note: block is dict, should be SemanticBlock
            capacity=cap,
            validation=mat,
            aggregate_confidence=aggregate
        ))

    return results
```

### 4.5. Orchestrateur principal (`analyze_v2/analyzer.py`)

```python
# r6_navigator/services/analyze_v2/analyzer.py

"""Orchestrateur de l'analyse itérative complète."""

from __future__ import annotations

from typing import List
from dataclasses import dataclass

from r6_navigator.services.analyze_v2.segmenter import segment_verbatim_hybrid, SemanticBlock
from r6_navigator.services.analyze_v2.identifier import identify_capacities, CapacityAnalysis
from r6_navigator.services.analyze_v2.evaluator import evaluate_maturities, MaturityEvaluation, load_maturity_scale
from r6_navigator.services.analyze_v2.models import AnalyzedBlock


@dataclass
class AnalysisProgress:
    """Progression de l'analyse."""
    stage: str  # "segmentation", "identification", "evaluation"
    completed: int
    total: int


def analyze_verbatim_iterative(
    verbatim_text: str,
    interview_info: dict,
    llm_call_fn,
    lang: str = "fr"
) -> List[AnalyzedBlock]:
    """
    Analyse itérative complète du verbatim.

    Pipeline :
        1. Segmentation (Segmenter)
        2. Identification capacité + Halliday (Identifier)
        3. Évaluation maturité (Evaluator)
    """
    level_code = interview_info.get("level_code", "I")

    # Étape 1 : Segmentation
    blocks = segment_verbatim_hybrid(verbatim_text, llm_call_fn)

    # Filtrer les blocs irrelevant (consultant, méta-discours)
    relevant_blocks = [b for b in blocks if not b.irrelevant]

    # Étape 2 : Identification capacité
    capacity_analyses = identify_capacities(
        relevant_blocks,
        level_code,
        llm_call_fn,
        lang
    )

    # Étape 3 : Évaluation maturité
    # Préparer les blocs avec capacité identifiée
    blocks_with_cap = []
    for block, cap in zip(relevant_blocks, capacity_analyses):
        block_dict = {
            "block_id": block.block_id,
            "text": block.text,
            "context": block.context,
            "capacity_id": cap.capacity_id,
            "level_code": cap.level_code,
            "halliday_consistent": cap.halliday_consistent
        }
        blocks_with_cap.append(block_dict)

    maturity_evaluations = evaluate_maturities(
        blocks_with_cap,
        llm_call_fn,
        lang
    )

    # Fusionner les résultats
    # Note: This needs proper conversion from dict to SemanticBlock
    # Simplified for now
    return merge_analyses(relevant_blocks, capacity_analyses, maturity_evaluations)


# Pour compatibilité avec l'ancien code
def analyze_verbatim_v2(
    verbatim_text: str,
    interview_info: dict,
    lang: str = "fr"
) -> List[AnalyzedBlock]:
    """Wrapper avec appel Ollama intégré."""
    from r6_navigator.services.ai_analyze import _call_ollama, _load_params, _extract_ollama_cfg

    params = _load_params()
    ollama_cfg = _extract_ollama_cfg(params)

    def llm_call(prompt: str) -> str:
        system = """Tu es un expert R6 framework. Réponds uniquement en JSON valide sans texte supplémentaire."""
        return _call_ollama(
            ollama_cfg["url"],
            ollama_cfg["model"],
            system,
            prompt,
            ollama_cfg["timeout"]
        )

    return analyze_verbatim_iterative(verbatim_text, interview_info, llm_call, lang)
```

### 4.6. Intégration avec `ai_analyze.py`

Ajouter une nouvelle fonction publique dans `ai_analyze.py` :

```python
# Dans ai_analyze.py

def analyze_verbatim_v2(
    verbatim_text: str,
    interview_info: dict,
    lang: str = "fr"
) -> list[AnalyzedExtract]:
    """Nouvelle fonction d'analyse itérative (DOSSIER-v2)."""
    from r6_navigator.services.analyze_v2.analyzer import analyze_verbatim_iterative

    # Wrapper LLM pour les appels itératifs
    def llm_call_fn(prompt: str) -> str:
        from r6_navigator.services.ai_analyze import _call_ollama, _load_params, _extract_ollama_cfg, _load_system_prompt
        params = _load_params()
        ollama_cfg = _extract_ollama_cfg(params)
        system = _load_system_prompt()
        return _call_ollama(
            ollama_cfg["url"],
            ollama_cfg["model"],
            system,
            prompt,
            ollama_cfg["timeout"]
        )

    analyzed = analyze_verbatim_iterative(verbatim_text, interview_info, llm_call_fn, lang)

    # Convertir en AnalyzedExtract pour compatibilité avec l'UI
    result = []
    for item in analyzed:
        result.append(AnalyzedExtract(
            text=item.block.text,
            tag=item.capacity.capacity_id,
            capacity_id=item.capacity.capacity_id,
            maturity_level=item.validation.maturity_level,
            confidence=item.validation.confidence,
            interpretation=item.validation.interpretation
        ))

    return result
```

---

## 5. Interface utilisateur

### 5.1. Suivi de progression

Modifier `_AnalyzeWorker` pour émettre des signaux de progression intermédiaires :

```python
# Dans mission_tab_verbatim.py

class _AnalyzeWorker(QThread):
    finished = Signal(list)
    error = Signal(str)
    progress = Signal(str, int, int)  # stage_name, completed, total

    def run(self) -> None:
        try:
            from r6_navigator.services.ai_analyze import analyze_verbatim_v2
            extracts = analyze_verbatim_v2(self._verbatim_text, self._interview_info, self._lang)
            self.finished.emit(extracts)
        except Exception as exc:
            self.error.emit(str(exc))
```

### 5.2. Affichage Halliday dans la revue

Modifier `mission_tab_interpretations.py` pour afficher l'indicateur Halliday :

```python
# Dans _rebuild_table() de MissionTabInterpretations

# Ajouter une colonne Halliday
self._table.setColumnCount(7)  # +1 pour Halliday
self._table.setHorizontalHeaderLabels([
    t("mission.col.extract"),
    t("mission.col.capacity"),
    t("mission.col.level"),
    t("mission.col.confidence"),
    t("mission.col.halliday"),  # NOUVEAU
    t("mission.col.status"),
    t("mission.col.actions"),
])

# Dans la boucle de construction des lignes
halliday_item = QTableWidgetItem()
if row.get("halliday_ok") is False:
    halliday_item.setText("⚠️")
    halliday_item.setToolTip(row.get("halliday_note", "Incohérence Halliday"))
    halliday_item.setForeground(Qt.GlobalColor.red)
elif row.get("halliday_ok") is True:
    halliday_item.setText("✓")
    halliday_item.setToolTip("Cohérence Halliday validée")
    halliday_item.setForeground(Qt.GlobalColor.green)
else:
    halliday_item.setText("")
self._table.setItem(r, 4, halliday_item)  # Colonne 4 (décalage de +1)
```

---

## 6. Dashboard qualité

### 6.1. Nouveau module `services/quality_dashboard.py`

```python
# r6_navigator/services/quality_dashboard.py

"""Tableau de bord de qualité pour l'analyse de verbatims."""

from __future__ import annotations

from typing import Dict, List
from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass
class QualityMetrics:
    """Métriques de qualité d'une analyse."""
    total_blocks: int
    validated_blocks: int
    avg_confidence: float
    halliday_inconsistent_count: int
    capacity_ambiguity_count: int
    maturity_distribution: Dict[str, int]


class QualityDashboard:
    """Tableau de bord de qualité pour les missions."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def get_mission_metrics(self, mission_id: int) -> QualityMetrics:
        """Calcule les métriques pour une mission donnée."""
        with self.session_factory() as session:
            # Récupérer toutes les interprétations de la mission
            from r6_navigator.services.crud_mission import get_all_mission_interpretations
            interpretations = get_all_mission_interpretations(session, mission_id)

            total = len(interpretations)
            validated = len([i for i in interpretations if i.status in ("validated", "corrected")])

            # Calculer la moyenne de confiance
            confidences = [i.confidence for i in interpretations if i.confidence is not None]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Compter les incohérences Halliday (si colonnes ajoutées)
            halliday_inconsistent = 0  # À implémenter si halliday_note/halliday_ok existent

            # Compter les capacités ambiguës (capacity_id null)
            capacity_ambiguous = len([i for i in interpretations if not i.capacity_id])

            # Distribution des niveaux de maturité
            maturity_dist: Dict[str, int] = {}
            for i in interpretations:
                level = i.maturity_level or "unknown"
                maturity_dist[level] = maturity_dist.get(level, 0) + 1

            return QualityMetrics(
                total_blocks=total,
                validated_blocks=validated,
                avg_confidence=avg_confidence,
                halliday_inconsistent_count=halliday_inconsistent,
                capacity_ambiguity_count=capacity_ambiguous,
                maturity_distribution=maturity_dist
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
            f"| Métrique | Valeur |",
            f"|----------|--------|",
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

---

## 7. Ordre d'implémentation

### Phase 1 (Sprint 1-2) : MVP Production

| Jour | Livrable | Fichiers |
|------|----------|----------|
| 1 | Prompts de segmentation | `prompt/segmenter_hybrid.txt` |
| 2 | Prompts identification + évaluation | `prompt/identify_capacity.txt`, `prompt/evaluate_maturity.txt` |
| 3-4 | Modèles Pydantic + segmentation | `analyze_v2/models.py`, `analyze_v2/segmenter.py` |
| 5 | Identification capacité + évaluation | `analyze_v2/identifier.py`, `analyze_v2/evaluator.py` |
| 6 | Orchestrateur | `analyze_v2/analyzer.py` |
| 7 | Intégration dans `ai_analyze.py` | Fonction `analyze_verbatim_v2()` |
| 8-9 | Tests unitaires | `test_analyze_v2.py` |
| 10 | UI progression | `_AnalyzeWorker` avec signaux progress |

### Phase 2 (Sprint 3-4) : Excellence

| Jour | Livrable |
|------|----------|
| 1-2 | Migration schéma DB (colonnes halliday) |
| 3-4 | Affichage Halliday dans l'UI |
| 5 | Dashboard qualité |
| 6-7 | Tests d'intégration |
| 8-10 | Benchmark qualité (50 cas annotés) |

---

## 8. Tests et validation

### 8.1. Cas de test recommandés

```python
# r6_navigator/tests/test_analyze_v2.py

import pytest

@pytest.fixture
def sample_verbatim_fr():
    return """[INTERVIEWE] J'ai cliqué sur le lien de la synthèse et j'ai décroché mon téléphone.
J'hésitais entre les fournisseurs car le budget était limité.
Finalement, j'ai choisi le plus cher mais fiable.
[CONSULTANT] Avez-vous testé la solution avant de choisir ?
[INTERVIEWE] Oui, j'ai fait un tableau comparatif sur Excel."""

@pytest.fixture
def interview_info():
    return {
        "subject_name": "Jean Dupont",
        "subject_role": "Responsable IT",
        "level_code": "I",
        "interview_date": "2024-03-15"
    }

def test_segmentation_detects_consultant_interviewe(sample_verbatim_fr, interview_info):
    # Le consultant doit être marqué irrelevant
    # L'interviewé doit être segmenté en blocs
    pass

def test_segmentation_preserves_exact_text(sample_verbatim_fr):
    # Le texte des blocs doit être une citation littérale
    pass

def test_identification_capacity_matches_level():
    # Un bloc avec sujet individuel doit être identifié à un niveau I
    pass

def test_halliday_validation_detects_inconsistency():
    # Si un bloc O est identifié à I (ou vice-versa), halliday_consistent = false
    pass

def test_maturity_evaluation_uses_scale():
    # La maturité doit être lue dans l'échelle correspondante
    pass

def test_aggregate_confidence_computed_correctly():
    # confidence_aggregate = confidence_capacity × confidence_maturity
    pass
```

---

## 9. Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Latence ×3 (15s au lieu de 5s) | UX dégradée | Barre de progression + indication temps estimé |
| Parsing JSON échoue | Anomalie silencieuse | Fallback : conserver ancien comportement si erreur |
| Cohérence entre étapes | Blocs non associés | Vérifier block_id correspondance + logging |
| Halliday non détecté | Erreurs de classification | Affichage visuel dans l'UI pour revue |

---

## 10. Backward compatibility

L'ancienne fonction `analyze_verbatim()` est conservée. La nouvelle fonction `analyze_verbatim_v2()` est ajoutée en parallèle.

**Fallback automatique :**
- Si verbatim < 300 mots → utiliser `analyze_verbatim()` (ancien comportement)
- Sinon → utiliser `analyze_verbatim_v2()` (nouveau comportement)

---

**Fin DOSSIER-impl-v2.md**
