"""Analyse itérative de verbatims d'entretien — pipeline v2 (DOSSIER-impl-v3).

Pipeline en 3 phases :
    1. Segmentation hybride — détection tours de parole + LLM (marqueurs ||BREAK||)
    2. Identification capacité + validation Halliday — LLM (JSON)
    3. Évaluation maturité + interprétation — LLM (JSON)

Architecture plate : tout le pipeline est dans ce seul module.
Fonction publique : ``analyze_verbatim_v2()``

Logging :
    INFO    — début/fin des phases principales et comptages.
    WARNING — fallbacks activés (JSON invalide, segmentation LLM échouée, halliday manquant).
    ERROR   — non utilisé ici (propagé en RuntimeError depuis _call_ollama).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from r6_navigator.services.llm_json import strip_markdown_json
from r6_navigator.services.prompt import load_prompt

log = logging.getLogger("r6_navigator.ai_analyze_v2")

_HALLIDAY_RULES_PATH = Path(__file__).parent / "prompt" / "halliday_rules.json"

_LEVEL_NAMES = {"S": "Strategic", "O": "Organizational", "I": "Individual"}
_CAPACITY_LIST = (
    "S1a, S1b, S2a, S2b, S3a, S3b (Stratégique)\n"
    "O1a, O1b, O2a, O2b, O3a, O3b (Organisationnel)\n"
    "I1a, I1b, I2a, I2b, I3a, I3b (Individuel)"
)
_BATCH_SIZE = 8  # Nombre max de blocs par appel LLM (évite les truncations)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class _SpeechTurn:
    """Prise de parole continue d'un locuteur."""

    speaker: str  # "consultant", "interviewe", "unknown"
    text: str
    start_pos: int
    end_pos: int


@dataclass
class SemanticBlock:
    """Bloc sémantique identifié par la Phase 1."""

    block_id: str  # Format : "r{replique_id}_{index}" ou "meta_{replique_id}"
    text: str  # Citation littérale du verbatim
    context: str  # Résumé 10 mots (peuplé par Phase 2)
    sentences: list[str]  # Phrases constituant le bloc
    start_position: int
    end_position: int
    word_count: int
    type_contenu: (
        str  # "observable", "organisationnel", "strategique", "meta", "unknown"
    )
    irrelevant: bool  # True si méta-discours consultant
    replique_id: int


@dataclass
class CapacityIdentification:
    """Résultat de la Phase 2 : identification capacité + validation Halliday."""

    block_id: str
    capacity_id: str | None  # Ex : "I3a", None si ambigu
    level_code: str | None  # "S", "O" ou "I" — déterminé par le LLM
    halliday_consistent: bool
    halliday_justification: str
    alternative_capacity: str | None = None


@dataclass
class MaturityEvaluation:
    """Résultat de la Phase 3 : évaluation maturité + interprétation."""

    block_id: str
    maturity_level: str
    confidence: float
    interpretation: str


@dataclass
class AnalyzedBlock:
    """Résultat complet de l'analyse itérative (3 phases fusionnées)."""

    block: SemanticBlock
    capacity: CapacityIdentification
    validation: MaturityEvaluation
    aggregate_confidence: float  # cap_conf × validation.confidence


# ---------------------------------------------------------------------------
# Phase 1 — Segmentation hybride
# ---------------------------------------------------------------------------

_SPEAKER_PATTERN = re.compile(
    r"\[(CONSULTANT|INTERVIEWE|INTERVIEWÉ|INTERVIEWEE)\](.*?)(?=\[(?:CONSULTANT|INTERVIEWE|INTERVIEWÉ|INTERVIEWEE)\]|$)",
    re.IGNORECASE | re.DOTALL,
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _parse_speech_turns(verbatim: str) -> list[_SpeechTurn]:
    """Détecte les changements de locuteur via les marqueurs [CONSULTANT] / [INTERVIEWE].

    Sans marqueurs, le verbatim entier est traité comme un seul tour interviewé.
    """
    matches = list(_SPEAKER_PATTERN.finditer(verbatim))

    # Aucun marqueur → verbatim entier = un seul tour interviewé
    if not matches:
        if verbatim.strip():
            return [_SpeechTurn("interviewe", verbatim.strip(), 0, len(verbatim))]
        return []

    turns: list[_SpeechTurn] = []
    pos = 0

    for match in matches:
        if match.start() > pos:
            text_before = verbatim[pos : match.start()].strip()
            if text_before:
                turns.append(_SpeechTurn("unknown", text_before, pos, match.start()))
        speaker = match.group(1).lower().replace("é", "e")
        text = match.group(2).strip()
        if text:
            turns.append(_SpeechTurn(speaker, text, match.start(), match.end()))
        pos = match.end()

    if pos < len(verbatim):
        text_after = verbatim[pos:].strip()
        if text_after:
            turns.append(_SpeechTurn("unknown", text_after, pos, len(verbatim)))

    return turns


def _insert_break_markers(text: str, llm_call_fn) -> str:
    """Appelle le LLM pour insérer des marqueurs ||BREAK|| aux ruptures sémantiques."""
    prompt = load_prompt("segmenter_break", text=text)
    return llm_call_fn(prompt).strip()


def _extract_blocks_from_breaks(
    text_with_breaks: str,
    verbatim_full: str,
    replique_id: int,
) -> list[SemanticBlock]:
    """Découpe le texte marqué par ||BREAK|| en SemanticBlock."""
    blocks: list[SemanticBlock] = []
    for i, raw in enumerate(text_with_breaks.split("||BREAK||")):
        block_text = raw.strip()
        if not block_text:
            continue
        start = verbatim_full.find(block_text)
        end = start + len(block_text) if start >= 0 else 0
        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(block_text) if s.strip()]
        if not sentences:
            sentences = [block_text]
        blocks.append(
            SemanticBlock(
                block_id=f"r{replique_id}_{i}",
                text=block_text,
                context="",
                sentences=sentences,
                start_position=start,
                end_position=end,
                word_count=len(block_text.split()),
                type_contenu="unknown",
                irrelevant=False,
                replique_id=replique_id,
            )
        )
    return blocks


def _segment_verbatim_hybrid(verbatim: str, llm_call_fn) -> list[SemanticBlock]:
    """Pipeline de segmentation hybride : tours de parole + découpe LLM."""
    turns = _parse_speech_turns(verbatim)
    all_blocks: list[SemanticBlock] = []

    for replique_id, turn in enumerate(turns):
        if turn.speaker == "consultant":
            all_blocks.append(
                SemanticBlock(
                    block_id=f"meta_{replique_id}",
                    text=turn.text,
                    context="Méta-discours consultant",
                    sentences=[turn.text] if turn.text else [],
                    start_position=turn.start_pos,
                    end_position=turn.end_pos,
                    word_count=len(turn.text.split()),
                    type_contenu="meta",
                    irrelevant=True,
                    replique_id=replique_id,
                )
            )
        else:
            try:
                text_with_breaks = _insert_break_markers(turn.text, llm_call_fn)
                blocks = _extract_blocks_from_breaks(
                    text_with_breaks, verbatim, replique_id
                )
            except Exception:
                log.warning(
                    "Segmentation LLM échouée pour replique_id=%d — bloc entier conservé.",
                    replique_id,
                )
                blocks = _extract_blocks_from_breaks(turn.text, verbatim, replique_id)
            all_blocks.extend(blocks)

    return all_blocks


# ---------------------------------------------------------------------------
# Phase 2 — Identification capacité + validation Halliday
# ---------------------------------------------------------------------------


def _load_halliday_rules() -> dict:
    """Charge les règles Halliday depuis prompt/halliday_rules.json."""
    with open(_HALLIDAY_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _identify_capacities_batch(
    blocks: list[SemanticBlock],
    halliday_formatted: str,
    llm_call_fn,
) -> list[CapacityIdentification]:
    """Identifie les capacités pour un batch de blocs (max _BATCH_SIZE).

    Le LLM détermine le niveau R6 (S/O/I) pour chaque bloc à partir du registre
    linguistique. Utilise le block_id comme clé de réconciliation, avec fallback
    positionnel si le LLM modifie ou omet certains block_id.
    """
    blocks_json = json.dumps(
        {
            "blocks": [
                {"block_id": b.block_id, "text": b.text[:500], "context": b.context}
                for b in blocks
            ]
        },
        ensure_ascii=False,
    )

    user_prompt = load_prompt(
        "identify_capacity",
        capacities_list=_CAPACITY_LIST,
        halliday_rules=halliday_formatted,
        blocks_json=blocks_json,
    )

    raw = llm_call_fn(user_prompt)

    try:
        data = json.loads(strip_markdown_json(raw))
        items = data.get("blocks_analysis", [])
    except (json.JSONDecodeError, KeyError):
        log.warning(
            "Parsing JSON échoué (batch identify) — %d blocs ignorés.", len(blocks)
        )
        return []

    by_id: dict[str, dict] = {item.get("block_id", ""): item for item in items}

    results: list[CapacityIdentification] = []
    for block in blocks:
        item = by_id.get(block.block_id)
        if item is None:
            log.warning(
                "Bloc '%s' absent de la réponse LLM (identification) — ignoré.",
                block.block_id,
            )
            continue
        cap_id = item.get("capacity_id")
        raw_level = item.get("level_code")
        # Dériver le niveau depuis capacity_id si le LLM ne l'a pas retourné
        if not raw_level and cap_id and cap_id[0] in ("S", "O", "I"):
            raw_level = cap_id[0]
        if raw_level not in ("S", "O", "I"):
            log.warning(
                "Bloc '%s' : level_code=%r non reconnu — ignoré.",
                block.block_id,
                raw_level,
            )
            continue
        results.append(
            CapacityIdentification(
                block_id=block.block_id,
                capacity_id=cap_id,
                level_code=raw_level,
                halliday_consistent=bool(item.get("halliday_consistent", False)),
                halliday_justification=item.get("halliday_justification", ""),
                alternative_capacity=item.get("alternative_capacity"),
            )
        )

    return results


def _identify_capacities(
    blocks: list[SemanticBlock],
    llm_call_fn,
) -> list[CapacityIdentification]:
    """Identifie la capacité R6 et valide la cohérence Halliday — traitement par batch.

    Le niveau R6 (S/O/I) est déterminé par le LLM pour chaque bloc individuellement
    à partir du registre linguistique. Les règles Halliday des 3 niveaux sont toutes
    injectées dans le prompt.
    """
    if not blocks:
        return []

    try:
        halliday_rules = _load_halliday_rules()
        halliday_formatted = json.dumps(halliday_rules, ensure_ascii=False, indent=2)
    except (FileNotFoundError, json.JSONDecodeError):
        log.warning("halliday_rules.json introuvable ou invalide — règles vides.")
        halliday_formatted = "{}"

    results: list[CapacityIdentification] = []
    for i in range(0, len(blocks), _BATCH_SIZE):
        batch = blocks[i : i + _BATCH_SIZE]
        log.info(
            "Identification capacité — batch %d/%d (%d blocs).",
            i // _BATCH_SIZE + 1,
            (len(blocks) - 1) // _BATCH_SIZE + 1,
            len(batch),
        )
        results.extend(
            _identify_capacities_batch(batch, halliday_formatted, llm_call_fn)
        )

    return results


# ---------------------------------------------------------------------------
# Phase 3 — Évaluation maturité
# ---------------------------------------------------------------------------


def _evaluate_maturities_batch(
    batch: list[dict],
    level_code: str,
    maturity_scale: str,
    llm_call_fn,
) -> list[MaturityEvaluation]:
    """Évalue la maturité pour un batch de blocs avec fallback positionnel."""
    blocks_json = json.dumps(
        {
            "blocks": [
                {
                    "block_id": b["block_id"],
                    "text": b["text"][:500],
                    "capacity_id": b.get("capacity_id"),
                    "level_code": b.get("level_code") or level_code,
                }
                for b in batch
            ]
        },
        ensure_ascii=False,
    )

    user_prompt = load_prompt(
        "evaluate_maturity",
        maturity_scale=maturity_scale,
        blocks_with_capacity=blocks_json,
    )

    raw = llm_call_fn(user_prompt)

    try:
        data = json.loads(strip_markdown_json(raw))
        items = data.get("evaluations", [])
    except (json.JSONDecodeError, KeyError, ValueError):
        log.warning(
            "Parsing JSON échoué (batch evaluate) — %d blocs ignorés.", len(batch)
        )
        return []

    by_id: dict[str, dict] = {item.get("block_id", ""): item for item in items}

    results: list[MaturityEvaluation] = []
    for block in batch:
        item = by_id.get(block["block_id"])
        if item is None:
            log.warning(
                "Bloc '%s' absent de la réponse LLM (évaluation) — ignoré.",
                block["block_id"],
            )
            continue
        results.append(
            MaturityEvaluation(
                block_id=block["block_id"],
                maturity_level=item.get("maturity_level", ""),
                confidence=float(item.get("confidence", 0.5)),
                interpretation=item.get("interpretation", ""),
            )
        )

    return results


def _evaluate_maturities(
    blocks_with_capacity: list[dict],
    llm_call_fn,
) -> list[MaturityEvaluation]:
    """Évalue la maturité pour chaque bloc — traitement par batch.

    Les blocs sont regroupés par niveau R6 (déterminé en Phase 2) afin d'injecter
    l'échelle de maturité appropriée dans chaque batch.
    """
    if not blocks_with_capacity:
        return []

    from r6_navigator.services.ai_analyze import _load_maturity_scale

    # Regrouper par level_code issu de la Phase 2.
    # Les blocs sans niveau reconnu (level_code absent ou invalide) sont ignorés :
    # on ne peut pas évaluer la maturité sans connaître le niveau.
    by_level: dict[str, list[dict]] = {}
    for block in blocks_with_capacity:
        lc = block.get("level_code")
        if lc not in ("S", "O", "I"):
            log.warning(
                "Bloc '%s' ignoré en Phase 3 : level_code=%r non reconnu.",
                block["block_id"],
                lc,
            )
            continue
        by_level.setdefault(lc, []).append(block)

    total_blocks = sum(len(v) for v in by_level.values())
    processed = 0

    results_by_id: dict[str, MaturityEvaluation] = {}
    for lc, blocks in by_level.items():
        maturity_scale = _load_maturity_scale(lc)
        for i in range(0, len(blocks), _BATCH_SIZE):
            batch = blocks[i : i + _BATCH_SIZE]
            processed += len(batch)
            log.info(
                "Évaluation maturité (level=%s) — batch %d/%d (%d blocs, %d/%d total).",
                lc,
                i // _BATCH_SIZE + 1,
                (len(blocks) - 1) // _BATCH_SIZE + 1,
                len(batch),
                processed,
                total_blocks,
            )
            for ev in _evaluate_maturities_batch(
                batch, lc, maturity_scale, llm_call_fn
            ):
                results_by_id[ev.block_id] = ev

    # Restituer dans l'ordre d'origine (les blocs ignorés sont absents du résultat)
    return [
        results_by_id[b["block_id"]]
        for b in blocks_with_capacity
        if b["block_id"] in results_by_id
    ]


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------


def _merge_analyses(
    blocks: list[SemanticBlock],
    capacity_analyses: list[CapacityIdentification],
    maturity_evaluations: list[MaturityEvaluation],
) -> list[AnalyzedBlock]:
    """Fusionne les 3 phases en AnalyzedBlock par block_id."""
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
        results.append(
            AnalyzedBlock(
                block=block,
                capacity=cap,
                validation=mat,
                aggregate_confidence=aggregate,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Orchestrateur interne
# ---------------------------------------------------------------------------


def _analyze_verbatim_iterative(
    verbatim_text: str,
    interview_info: dict,
    llm_call_fn,
) -> list[AnalyzedBlock]:
    """Pipeline complet : segmentation → identification → évaluation → fusion."""
    blocks = _segment_verbatim_hybrid(verbatim_text, llm_call_fn)
    relevant = [b for b in blocks if not b.irrelevant]
    log.info(
        "Segmentation : %d bloc(s) pertinent(s) / %d total.", len(relevant), len(blocks)
    )

    capacity_analyses = _identify_capacities(relevant, llm_call_fn)
    log.info(
        "Identification : %d résultat(s) pour %d blocs pertinents.",
        len(capacity_analyses),
        len(relevant),
    )

    cap_by_id = {cap.block_id: cap for cap in capacity_analyses}
    blocks_with_cap = []
    for block in relevant:
        cap = cap_by_id.get(block.block_id)
        if cap is None:
            # Bloc non identifié par le LLM — ignoré (pas de fake)
            continue
        blocks_with_cap.append(
            {
                "block_id": block.block_id,
                "text": block.text,
                "context": block.context,
                "capacity_id": cap.capacity_id,
                "level_code": cap.level_code,  # garanti valide par _identify_capacities_batch
                "halliday_consistent": cap.halliday_consistent,
            }
        )

    maturity_evaluations = _evaluate_maturities(blocks_with_cap, llm_call_fn)
    log.info("Évaluation maturité : %d résultat(s).", len(maturity_evaluations))

    return _merge_analyses(relevant, capacity_analyses, maturity_evaluations)


# ---------------------------------------------------------------------------
# Fonction publique
# ---------------------------------------------------------------------------


def analyze_verbatim_v2(
    verbatim_text: str,
    interview_info: dict,
    lang: str = "fr",
) -> list:
    """Analyse itérative d'un verbatim d'entretien (pipeline 3 phases).

    Retourne ``list[AnalyzedExtract]`` (même type que ``analyze_verbatim``) pour
    compatibilité avec l'UI existante. Les champs ``halliday_ok`` et
    ``halliday_note`` sont renseignés sur chaque extrait pour la colonne Halliday.

    Utilisé par ``_AnalyzeWorker`` quand le verbatim dépasse 300 mots.

    Args:
        verbatim_text: Texte brut du verbatim d'entretien.
        interview_info: Métadonnées de l'entretien (subject_name, subject_role,
            interview_date). Le niveau R6 est déterminé par le LLM pour chaque
            bloc, pas en amont.
        lang: Langue de l'analyse (``"fr"`` ou ``"en"``).

    Returns:
        Liste d'``AnalyzedExtract`` avec ``halliday_ok`` et ``halliday_note``
        renseignés.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la configuration invalide.
    """
    from r6_navigator.services.ai_analyze import (
        AnalyzedExtract,
        _call_ollama,
        _extract_ollama_cfg,
        _load_params,
        _load_system_prompt,
    )

    log.info(
        "Début analyse itérative v2 (lang=%s, mots=%d)",
        lang,
        len(verbatim_text.split()),
    )

    params = _load_params()
    ollama_cfg = _extract_ollama_cfg(params)
    if not ollama_cfg.get("model_analyze"):
        raise RuntimeError(
            "Clé 'model_analyze' absente de params.yml[ollama] — "
            "ajoutez 'model_analyze: <nom_du_modèle>' dans params.yml."
        )
    system_prompt = _load_system_prompt()

    def llm_call_fn(prompt: str) -> str:
        return _call_ollama(
            ollama_cfg["url"],
            ollama_cfg["model_analyze"],
            system_prompt,
            prompt,
            ollama_cfg["timeout"],
        )

    analyzed = _analyze_verbatim_iterative(verbatim_text, interview_info, llm_call_fn)

    result = [
        AnalyzedExtract(
            text=item.block.text,
            tag=item.capacity.capacity_id,
            capacity_id=item.capacity.capacity_id,
            maturity_level=item.validation.maturity_level,
            confidence=item.validation.confidence,
            interpretation=item.validation.interpretation,
            halliday_ok=item.capacity.halliday_consistent,
            halliday_note=(
                item.capacity.halliday_justification
                if not item.capacity.halliday_consistent
                else None
            ),
        )
        for item in analyzed
    ]

    log.info("Analyse itérative v2 terminée : %d extrait(s).", len(result))
    return result
