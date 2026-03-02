"""Analyse de verbatims R6 et génération de rapports de mission via Ollama.

Ce module expose les fonctions publiques d'analyse :

* ``analyze_verbatim``        — extraction + classification des passages R6 dans un verbatim
* ``generate_mission_report`` — rapport narratif S-O-I à partir des interprétations validées

Tous les appels Ollama passent par ``_call_ollama`` importé de ``shared.ollama_client``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from r6_navigator.shared.ollama_client import (
    _call_ollama,
    _fix_json_strings,
    load_params,
    _strip_markdown_json,
)
from r6_navigator.navigator.services.ai_generate import _load_system_prompt
from r6_navigator.missions.services.prompt import load_prompt

_PACKAGE_DIR = Path(__file__).parent.parent.parent  # r6_navigator/
_R6_DIR = _PACKAGE_DIR.parent / "R6"  # project_root/R6/

_MATURITY_FILES: dict[str, str] = {
    "I": "I6_EQF_Proficiency_Levels_short.md",
    "O": "O6_Maturity_Levels_short.md",
    "S": "S6_Maturity_Levels_and_Learning_Loops_short.md",
}


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------

@dataclass
class AnalyzedExtract:
    """Un extrait du verbatim avec son interprétation R6.

    Attributes:
        text: Passage extrait du verbatim (citation ou paraphrase).
        capacity_id: Identifiant de la capacité R6 (ex. ``"I1a"``), ou None.
        maturity_score: Score de maturité selon l'échelle du niveau.
        direction: Classification (``"INS"``, ``"OK"``, ``"EXC"``).
        justification: Justification textuelle de la classification.
    """

    text: str
    capacity_id: str | None
    maturity_score: int | None
    direction: str | None
    justification: str | None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_verbatim(
    verbatim_id: int,
    session_factory,
    lang: str,
) -> list[AnalyzedExtract]:
    """Analyse un verbatim et retourne les extraits classifiés.

    1. Charge le verbatim + métadonnées de l'entretien depuis la DB
    2. Charge les 18 capacités comme contexte R6
    3. Charge l'échelle de maturité appropriée
    4. Appelle Ollama → JSON d'extraits
    5. Persiste les Extract + Interpretation en DB (status=pending)
    6. Marque le verbatim comme 'analyzed'

    Args:
        verbatim_id: ID du verbatim à analyser.
        session_factory: Callable retournant une session SQLAlchemy.
        lang: Code langue (``"fr"`` ou ``"en"``).

    Returns:
        Liste d'AnalyzedExtract persistés en DB.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la réponse est invalide.
        ValueError: Si le verbatim n'existe pas.
    """
    from r6_navigator.navigator.services import crud
    from r6_navigator.missions.services import crud as mission_crud

    params = load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 10))
    system_prompt = _load_system_prompt()

    # Load verbatim + interview context
    with session_factory() as session:
        verbatim = mission_crud.get_verbatim(session, verbatim_id)
        if verbatim is None:
            raise ValueError(f"Verbatim '{verbatim_id}' not found")
        interview = verbatim.interview
        raw_text = verbatim.raw_text
        interviewee_name = interview.interviewee_name
        interviewee_role = interview.interviewee_role or ""
        interviewee_level = interview.interviewee_level or ""

    # Build R6 capacity context
    with session_factory() as session:
        capacities_context = _build_capacities_context(session, lang)

    # Determine level distribution from capacity context for maturity scale
    # We need scales for all 3 levels since the verbatim may reference any
    maturity_scale = _build_all_maturity_scales()

    lang_name = "French" if lang == "fr" else "US English"
    user_prompt = load_prompt(
        "analyze_verbatim",
        lang_name=lang_name,
        capacities_context=capacities_context,
        maturity_scale=maturity_scale,
        interviewee_name=interviewee_name,
        interviewee_role=interviewee_role,
        interviewee_level=interviewee_level,
        verbatim_text=raw_text,
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    analyzed = _parse_verbatim_analysis(raw)

    # Persist extracts and interpretations
    with session_factory() as session:
        for item in analyzed:
            extract = mission_crud.create_extract(
                session,
                verbatim_id=verbatim_id,
                raw_text=item.text,
                created_by="AI",
            )
            mission_crud.create_interpretation(
                session,
                extract_id=extract.extract_id,
                capacity_id=item.capacity_id,
                maturity_score=item.maturity_score,
                direction=item.direction,
                justification=item.justification,
            )
        mission_crud.update_verbatim_status(session, verbatim_id, "analyzed")

    return analyzed


def generate_mission_report(
    mission_id: str,
    session_factory,
    lang: str,
) -> str:
    """Génère un rapport narratif S-O-I pour une mission.

    1. Charge toutes les interprétations validées de la mission
    2. Construit le profil de maturité par capacité
    3. Appelle Ollama → narrative structurée
    4. Persiste le MissionReport (status=draft) en DB

    Args:
        mission_id: ID de la mission.
        session_factory: Callable retournant une session SQLAlchemy.
        lang: Code langue (``"fr"`` ou ``"en"``).

    Returns:
        Contenu textuel du rapport généré.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la réponse est invalide.
        ValueError: Si la mission n'existe pas.
    """
    from r6_navigator.missions.services import crud as mission_crud

    params = load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 10))
    system_prompt = _load_system_prompt()

    with session_factory() as session:
        mission = mission_crud.get_mission(session, mission_id)
        if mission is None:
            raise ValueError(f"Mission '{mission_id}' not found")
        client_name = mission.client_name
        mission_description = mission.description or ""
        interviews = mission_crud.list_interviews(session, mission_id)
        nb_interviews = len(interviews)
        interpretations = mission_crud.list_interpretations_for_mission(
            session, mission_id, status_filter=None
        )
        # Include validated and corrected
        valid_interps = [
            i for i in interpretations if i.status in ("validated", "corrected")
        ]
        nb_interpretations = len(valid_interps)
        maturity_profile = _build_maturity_profile(valid_interps)

    maturity_scales = _build_all_maturity_scales()
    lang_name = "French" if lang == "fr" else "US English"

    user_prompt = load_prompt(
        "generate_mission_report",
        lang_name=lang_name,
        client_name=client_name,
        mission_description=mission_description,
        nb_interviews=nb_interviews,
        nb_interpretations=nb_interpretations,
        maturity_profile=maturity_profile,
        maturity_scales=maturity_scales,
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    content = _parse_report(raw)

    with session_factory() as session:
        mission_crud.create_mission_report(session, mission_id=mission_id, content=content)

    return content


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_maturity_scale(level_code: str) -> str:
    """Charge l'échelle de maturité pour un niveau depuis R6/.

    Args:
        level_code: Code du niveau (``"I"``, ``"O"`` ou ``"S"``).

    Returns:
        Contenu markdown de l'échelle, ou message d'indisponibilité.
    """
    filename = _MATURITY_FILES.get(level_code)
    if not filename:
        return f"Maturity scale for level {level_code}: not available."
    path = _R6_DIR / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Maturity scale for level {level_code} ({filename}): file not found."


def _build_all_maturity_scales() -> str:
    """Construit le bloc combiné des 3 échelles de maturité."""
    parts = []
    for level_code in ("S", "O", "I"):
        parts.append(f"=== Level {level_code} ===\n{_load_maturity_scale(level_code)}")
    return "\n\n".join(parts)


def _build_capacities_context(session, lang: str) -> str:
    """Construit le contexte des 18 capacités pour le prompt."""
    from r6_navigator.navigator.services import crud
    capacities = crud.get_all_capacities(session)
    lines = []
    for cap in capacities:
        trans = crud.get_capacity_translation(session, cap.capacity_id, lang)
        label = trans.label if trans and trans.label else cap.capacity_id
        definition = (trans.definition or "")[:200] if trans else ""
        lines.append(f"- {cap.capacity_id}: {label}")
        if definition:
            lines.append(f"  {definition[:200]}")
    return "\n".join(lines)


def _build_maturity_profile(interpretations) -> str:
    """Construit le profil de maturité à partir des interprétations validées."""
    from collections import defaultdict
    profile: dict[str, list] = defaultdict(list)
    for interp in interpretations:
        cap_id = interp.corrected_capacity_id or interp.capacity_id or "unknown"
        score = interp.corrected_maturity_score if interp.status == "corrected" else interp.maturity_score
        direction = interp.corrected_direction if interp.status == "corrected" else interp.direction
        profile[cap_id].append({"score": score, "direction": direction})

    lines = []
    for cap_id, entries in sorted(profile.items()):
        avg_score = sum(e["score"] for e in entries if e["score"] is not None)
        count = len([e for e in entries if e["score"] is not None])
        avg = round(avg_score / count, 1) if count > 0 else "N/A"
        directions = ", ".join(e["direction"] for e in entries if e["direction"])
        lines.append(f"- {cap_id}: avg_score={avg}, n={len(entries)}, directions=[{directions}]")

    return "\n".join(lines) if lines else "No validated interpretations."


def _parse_verbatim_analysis(raw: str) -> list[AnalyzedExtract]:
    """Parse la réponse Ollama pour analyze_verbatim().

    Args:
        raw: Chaîne JSON brute retournée par Ollama.

    Returns:
        Liste d'AnalyzedExtract.

    Raises:
        RuntimeError: Si la réponse n'est pas un JSON valide.
    """
    clean = _strip_markdown_json(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Ollama response is not valid JSON: {e}\nRaw (first 300 chars): {raw[:300]}"
        ) from e

    extracts_data = data.get("extracts", [])
    if not isinstance(extracts_data, list):
        extracts_data = []

    result = []
    for item in extracts_data:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        cap_id = item.get("capacity_id")
        if cap_id is not None:
            cap_id = str(cap_id).strip() or None
        score = item.get("maturity_score")
        if score is not None:
            try:
                score = int(score)
            except (ValueError, TypeError):
                score = None
        direction = item.get("direction")
        if direction is not None:
            direction = str(direction).strip().upper()
            if direction not in ("INS", "OK", "EXC"):
                direction = None
        justification = str(item.get("justification", "")).strip() or None
        result.append(AnalyzedExtract(
            text=text,
            capacity_id=cap_id,
            maturity_score=score,
            direction=direction,
            justification=justification,
        ))
    return result


def _parse_report(raw: str) -> str:
    """Parse la réponse Ollama pour generate_mission_report().

    Args:
        raw: Chaîne JSON brute retournée par Ollama.

    Returns:
        Contenu textuel du rapport.

    Raises:
        RuntimeError: Si la réponse n'est pas un JSON valide.
    """
    clean = _strip_markdown_json(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Ollama response is not valid JSON: {e}\nRaw (first 300 chars): {raw[:300]}"
        ) from e

    report = data.get("report", "")
    if isinstance(report, list):
        report = "\n".join(str(item) for item in report)
    return str(report).strip()
