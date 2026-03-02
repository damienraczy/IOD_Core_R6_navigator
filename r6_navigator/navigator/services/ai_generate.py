"""Génération de contenus R6 via Ollama (LLM local).

Ce module expose les fonctions publiques de génération et de traduction
pour chacune des cinq sections d'une capacité :

* ``generate_fiche``           — intitulé, définition, fonction centrale
* ``generate_fiche_risque``    — risques si insuffisant / si excessif
* ``generate_questions``       — 10 questions d'entretien STAR
* ``generate_questions_items`` — 4×5 manifestations observables (OK/DEP/EXC/INS)
* ``generate_coaching``        — thèmes, leviers, missions de coaching
* ``translate_fiche``          — traduction complète de la fiche
* ``translate_questions``      — traduction des questions
* ``translate_observable_items`` — traduction des items observables
* ``translate_coaching``       — traduction du coaching

Tous les appels Ollama passent par ``_call_ollama``, qui réessaie jusqu'à
``_OLLAMA_MAX_RETRIES`` fois en cas d'erreur réseau ou de réponse malformée.
Le prompt système est chargé depuis ``services/prompt/system_01.txt``.
La configuration Ollama (URL, modèle, timeout) provient de ``params.yml``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from r6_navigator.shared.ollama_client import (
    _call_ollama,
    _cap_bullets,
    _fix_json_strings,
    _strip_markdown_json,
    _to_str,
    load_params,
)
from r6_navigator.navigator.services.prompt import load_prompt

_PACKAGE_DIR = Path(__file__).parent.parent.parent  # r6_navigator/
_PROJECT_ROOT = _PACKAGE_DIR.parent  # project root (params.yml lives here)


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


@dataclass
class GeneratedFiche:
    """Résultat de ``generate_fiche()`` — trois champs de la fiche descriptive."""

    name: str
    definition: str
    central_function: str


@dataclass
class GeneratedRisque:
    """Résultat de ``generate_fiche_risque()`` — deux blocs de risques."""

    risk_insufficient: str
    risk_excessive: str


@dataclass
class GeneratedContent:
    """Résultat de ``translate_fiche()`` — traduction complète de la fiche."""

    name: str
    definition: str
    central_function: str
    risk_insufficient: str
    risk_excessive: str


@dataclass
class GeneratedCoaching:
    """Résultat de ``generate_coaching()`` — trois sections de coaching."""

    reflection_themes: str
    intervention_levers: str
    recommended_missions: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_fiche(capacity_id: str, lang: str) -> GeneratedFiche:
    """Calls Ollama to generate name, definition and central_function for one capacity."""
    params = load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 10))
    system_prompt = _load_system_prompt()

    axioms = _load_axioms()
    canonical_name = _load_canonical_name(capacity_id, lang)

    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]

    ontology = axioms["r6_ontology"]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]

    halliday_context = _load_halliday_context(level_code)

    lang_name = "French" if lang == "fr" else "US English"
    user_prompt = load_prompt(
        "generate_fiche",
        lang_name=lang_name,
        capacity_id=capacity_id,
        level_name=level_info["name"],
        level_code=level_code,
        axis_name=axis_info["name"],
        axis_number=axis_number,
        pole_name=pole_info["name"],
        pole_code=pole_code,
        canonical_name=canonical_name,
        halliday_context=halliday_context,
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    return _parse_fiche_response(raw, capacity_id)


def generate_fiche_risque(
    capacity_id: str,
    lang: str,
    definition: str = "",
    central_function: str = "",
) -> GeneratedRisque:
    """Calls Ollama to generate risk_insufficient and risk_excessive for one capacity."""
    params = load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 10))
    system_prompt = _load_system_prompt()

    axioms = _load_axioms()
    canonical_name = _load_canonical_name(capacity_id, lang)

    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]

    ontology = axioms["r6_ontology"]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]

    halliday_context = _load_halliday_context(level_code)

    capacities_map = ontology["capacities"]
    cap_data = capacities_map[capacity_id]
    twin_pole = "b" if pole_code == "a" else "a"
    twin_id = f"{level_code}{axis_number}{twin_pole}"
    twin_name = _load_canonical_name(twin_id, lang)
    relational_lines = [
        f"Twin pole (same axis {axis_number}, opposite pole): {twin_id} — {twin_name}",
    ]
    enables_id = cap_data.get("enables")
    if enables_id:
        enables_name = _load_canonical_name(enables_id, lang)
        relational_lines.append(f"Enables (level above): {enables_id} — {enables_name}")
    emerges_from_id = cap_data.get("emerges_from")
    if emerges_from_id:
        emerges_from_name = _load_canonical_name(emerges_from_id, lang)
        relational_lines.append(
            f"Emerges from (level below): {emerges_from_id} — {emerges_from_name}"
        )
    relational_context = "\n".join(relational_lines)

    capacity_content_lines: list[str] = []
    if definition.strip() or central_function.strip():
        capacity_content_lines.append(
            "\n=== CAPACITY CONTENT (already generated — use to ground risk bullets) ==="
        )
        if definition.strip():
            capacity_content_lines.append(f"Definition:\n{definition.strip()}")
        if central_function.strip():
            capacity_content_lines.append(
                f"Central function:\n{central_function.strip()}"
            )
    capacity_content = "\n\n".join(capacity_content_lines)

    lang_name = "French" if lang == "fr" else "US English"
    user_prompt = load_prompt(
        "generate_fiche_risque",
        lang_name=lang_name,
        capacity_id=capacity_id,
        level_name=level_info["name"],
        level_code=level_code,
        axis_name=axis_info["name"],
        axis_number=axis_number,
        pole_name=pole_info["name"],
        pole_code=pole_code,
        canonical_name=canonical_name,
        halliday_context=halliday_context,
        relational_context=relational_context,
        capacity_content=capacity_content,
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    return _parse_risque_response(raw)


def generate_questions(capacity_id: str, lang: str) -> list[str]:
    """Génère les 10 questions d'entretien pour une capacité."""
    params = load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 10))
    system_prompt = _load_system_prompt()

    axioms = _load_axioms()
    canonical_name = _load_canonical_name(capacity_id, lang)

    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]

    ontology = axioms["r6_ontology"]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]

    interview_rules = _load_halliday_rules(level_code)

    lang_name = "French" if lang == "fr" else "US English"
    user_prompt = load_prompt(
        "generate_questions",
        lang_name=lang_name,
        capacity_id=capacity_id,
        level_name=level_info["name"],
        level_code=level_code,
        axis_name=axis_info["name"],
        axis_number=axis_number,
        pole_name=pole_info["name"],
        pole_code=pole_code,
        canonical_name=canonical_name,
        interview_target=interview_rules["interview_target"],
        participant_1=interview_rules["participant_1"],
        process_type=interview_rules["process_type"],
        participant_2=interview_rules["participant_2"],
        circumstance=interview_rules["circumstance"],
        proscription=interview_rules["proscription"],
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    return _parse_questions_response(raw)


def generate_questions_items(capacity_id: str, lang: str) -> dict[str, list[str]]:
    """Génère les 4×5 items observables (OK/DEP/EXC/INS) pour une capacité."""
    params = load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 10))
    system_prompt = _load_system_prompt()

    axioms = _load_axioms()
    canonical_name = _load_canonical_name(capacity_id, lang)

    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]

    ontology = axioms["r6_ontology"]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]

    halliday_context = _load_halliday_context(level_code)

    lang_name = "French" if lang == "fr" else "US English"
    user_prompt = load_prompt(
        "generate_questions_items",
        lang_name=lang_name,
        capacity_id=capacity_id,
        level_name=level_info["name"],
        level_code=level_code,
        axis_name=axis_info["name"],
        axis_number=axis_number,
        pole_name=pole_info["name"],
        pole_code=pole_code,
        canonical_name=canonical_name,
        halliday_context=halliday_context,
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    return _parse_items_response(raw)


def generate_coaching(capacity_id: str, lang: str) -> GeneratedCoaching:
    """Génère les contenus de coaching d'une capacité (thèmes, leviers, missions)."""
    params = load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 10))
    system_prompt = _load_system_prompt()

    axioms = _load_axioms()
    canonical_name = _load_canonical_name(capacity_id, lang)

    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]

    ontology = axioms["r6_ontology"]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]

    halliday_context = _load_halliday_context(level_code)

    lang_name = "French" if lang == "fr" else "US English"
    user_prompt = load_prompt(
        "generate_coaching",
        lang_name=lang_name,
        capacity_id=capacity_id,
        level_name=level_info["name"],
        level_code=level_code,
        level_description=level_info["description"],
        axis_name=axis_info["name"],
        axis_number=axis_number,
        pole_a_tension=axis_info["tension"]["pole_a"],
        pole_b_tension=axis_info["tension"]["pole_b"],
        pole_name=pole_info["name"],
        pole_code=pole_code,
        pole_characteristics=pole_info["characteristics"],
        canonical_name=canonical_name,
        halliday_context=halliday_context,
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    return _parse_coaching_response(raw)


def translate_fiche(
    capacity_id: str,
    source_fields: dict[str, str],
    source_lang: str,
    target_lang: str,
) -> GeneratedContent:
    """Traduit le contenu Fiche d'une capacité d'une langue vers une autre via Ollama."""
    params = load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 10))
    system_prompt = _load_system_prompt()

    axioms = _load_axioms()
    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]
    ontology = axioms["r6_ontology"]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]

    source_lang_name = "French" if source_lang == "fr" else "US English"
    target_lang_name = "French" if target_lang == "fr" else "US English"

    user_prompt = load_prompt(
        "translate_fiche",
        source_lang_name=source_lang_name,
        target_lang_name=target_lang_name,
        capacity_id=capacity_id,
        level_name=level_info["name"],
        level_code=level_code,
        axis_name=axis_info["name"],
        axis_number=axis_number,
        pole_name=pole_info["name"],
        pole_code=pole_code,
        source_content=json.dumps(source_fields, ensure_ascii=False, indent=2),
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    return _parse_content_response(raw, capacity_id)


def translate_questions(
    capacity_id: str,
    questions: list[str],
    source_lang: str,
    target_lang: str,
) -> list[str]:
    """Traduit une liste de questions d'entretien d'une langue vers une autre via Ollama."""
    params = load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 10))
    system_prompt = _load_system_prompt()

    axioms = _load_axioms()
    level_code = capacity_id[0]
    level_info = axioms["r6_ontology"]["levels"][level_code]

    source_lang_name = "French" if source_lang == "fr" else "US English"
    target_lang_name = "French" if target_lang == "fr" else "US English"

    user_prompt = load_prompt(
        "translate_questions",
        source_lang_name=source_lang_name,
        target_lang_name=target_lang_name,
        capacity_id=capacity_id,
        level_name=level_info["name"],
        level_code=level_code,
        source_questions=json.dumps(questions, ensure_ascii=False, indent=2),
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    return _parse_questions_list(raw)


def translate_observable_items(
    capacity_id: str,
    items_by_cat: dict[str, list[str]],
    source_lang: str,
    target_lang: str,
) -> dict[str, list[str]]:
    """Traduit les manifestations observables par catégorie via Ollama."""
    params = load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 10))
    system_prompt = _load_system_prompt()

    axioms = _load_axioms()
    level_code = capacity_id[0]
    level_info = axioms["r6_ontology"]["levels"][level_code]

    source_lang_name = "French" if source_lang == "fr" else "US English"
    target_lang_name = "French" if target_lang == "fr" else "US English"

    user_prompt = load_prompt(
        "translate_observable_items",
        source_lang_name=source_lang_name,
        target_lang_name=target_lang_name,
        capacity_id=capacity_id,
        level_name=level_info["name"],
        level_code=level_code,
        source_items=json.dumps(items_by_cat, ensure_ascii=False, indent=2),
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    return _parse_items_dict(raw, items_by_cat)


def translate_coaching(
    capacity_id: str,
    source_fields: dict[str, str],
    source_lang: str,
    target_lang: str,
) -> GeneratedCoaching:
    """Traduit le contenu Coaching d'une capacité d'une langue vers une autre via Ollama."""
    params = load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 10))
    system_prompt = _load_system_prompt()

    axioms = _load_axioms()
    level_code = capacity_id[0]
    ontology = axioms["r6_ontology"]
    level_info = ontology["levels"][level_code]

    source_lang_name = "French" if source_lang == "fr" else "US English"
    target_lang_name = "French" if target_lang == "fr" else "US English"

    user_prompt = load_prompt(
        "translate_coaching",
        source_lang_name=source_lang_name,
        target_lang_name=target_lang_name,
        capacity_id=capacity_id,
        level_name=level_info["name"],
        level_code=level_code,
        source_content=json.dumps(source_fields, ensure_ascii=False, indent=2),
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    return _parse_coaching_response(raw)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_system_prompt() -> str:
    """Charge le prompt système depuis ``services/prompt/system_01.txt``."""
    path = Path(__file__).parent / "prompt" / "system_01.txt"
    with open(path, encoding="utf-8") as f:
        return f.read()


def _load_axioms() -> dict:
    """Charge l'ontologie R6 depuis ``axioms.yml``."""
    axioms_path = _PACKAGE_DIR / "axioms.yml"
    with open(axioms_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_halliday_rules(level_code: str) -> dict:
    """Charge les règles Halliday spécifiques au niveau depuis ``halliday_rules.json``."""
    rules_path = Path(__file__).parent / "prompt" / "halliday_rules.json"
    with open(rules_path, encoding="utf-8") as f:
        data = json.load(f)
    return data[level_code]


def _load_halliday_context(level_code: str) -> str:
    """Retourne le contexte Halliday formaté pour injection dans les prompts."""
    rules = _load_halliday_rules(level_code)
    lines = [
        f"Analysis Target: {rules['interview_target']}",
        f"Primary Participant (Role 1): {rules['participant_1']}",
        f"Process Type: {rules['process_type']}",
        f"Secondary Participant (Role 2): {rules['participant_2']}",
        f"Circumstantial Context: {rules['circumstance']}",
        f"Proscription/Constraints: {rules['proscription']}",
        f"Audit Rule: {rules['audit_rule_main_clause']}",
    ]
    if "audit_rule_inversion" in rules:
        lines.append(f"Audit Rule (inversion test): {rules['audit_rule_inversion']}")
    return "\n".join(lines)


def _load_canonical_name(capacity_id: str, lang: str) -> str:
    """Retourne le nom canonique d'une capacité dans la langue indiquée."""
    names_path = _PACKAGE_DIR / f"capacities_{lang}.yml"
    try:
        with open(names_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        names = data.get(f"capacities_{lang}", {})
        return names.get(capacity_id, capacity_id)
    except FileNotFoundError:
        return capacity_id


def _parse_fiche_response(raw: str, capacity_id: str) -> GeneratedFiche:
    clean = _strip_markdown_json(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Ollama response is not valid JSON: {e}\nRaw (first 300 chars): {raw[:300]}"
        ) from e

    return GeneratedFiche(
        name=_to_str(data.get("name"), fallback=capacity_id),
        definition=_cap_bullets(data.get("definition", "")),
        central_function=_to_str(data.get("central_function")),
    )


def _parse_risque_response(raw: str) -> GeneratedRisque:
    clean = _strip_markdown_json(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Ollama response is not valid JSON: {e}\nRaw (first 300 chars): {raw[:300]}"
        ) from e

    return GeneratedRisque(
        risk_insufficient=_cap_bullets(data.get("risk_insufficient", "")),
        risk_excessive=_cap_bullets(data.get("risk_excessive", "")),
    )


def _parse_content_response(raw: str, capacity_id: str) -> GeneratedContent:
    clean = _strip_markdown_json(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Ollama response is not valid JSON: {e}\nRaw (first 300 chars): {raw[:300]}"
        ) from e

    return GeneratedContent(
        name=_to_str(data.get("name"), fallback=capacity_id),
        definition=_cap_bullets(data.get("definition", "")),
        central_function=_to_str(data.get("central_function")),
        risk_insufficient=_cap_bullets(data.get("risk_insufficient", "")),
        risk_excessive=_cap_bullets(data.get("risk_excessive", "")),
    )


def _parse_questions_list(raw: str) -> list[str]:
    clean = _strip_markdown_json(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Ollama response is not valid JSON: {e}\nRaw (first 300 chars): {raw[:300]}"
        ) from e

    raw_questions = data.get("questions", [])
    if isinstance(raw_questions, list):
        return [str(q).strip() for q in raw_questions if str(q).strip()]
    return [
        line.strip(" -") for line in str(raw_questions).splitlines() if line.strip()
    ]


def _parse_items_dict(raw: str, source: dict[str, list[str]]) -> dict[str, list[str]]:
    clean = _strip_markdown_json(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Ollama response is not valid JSON: {e}\nRaw (first 300 chars): {raw[:300]}"
        ) from e

    result: dict[str, list[str]] = {}
    for code, src_items in source.items():
        raw_cat = data.get(code, [])
        if isinstance(raw_cat, list):
            items = [str(t).strip() for t in raw_cat if str(t).strip()]
        else:
            items = [
                line.strip(" -") for line in str(raw_cat).splitlines() if line.strip()
            ]
        result[code] = items[: len(src_items)]
    return result


def _parse_questions_response(raw: str) -> list[str]:
    clean = _strip_markdown_json(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Ollama response is not valid JSON: {e}\nRaw (first 300 chars): {raw[:300]}"
        ) from e

    raw_questions = data.get("questions", [])
    if isinstance(raw_questions, list):
        return [str(q).strip() for q in raw_questions if str(q).strip()]
    return [
        line.strip(" -") for line in str(raw_questions).splitlines() if line.strip()
    ]


def _parse_items_response(raw: str) -> dict[str, list[str]]:
    clean = _strip_markdown_json(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Ollama response is not valid JSON: {e}\nRaw (first 300 chars): {raw[:300]}"
        ) from e

    raw_items = data.get("observable_items", {})
    if not isinstance(raw_items, dict):
        raw_items = {}
    result: dict[str, list[str]] = {}
    for code in ("OK", "DEP", "EXC", "INS"):
        raw_cat = raw_items.get(code, [])
        if isinstance(raw_cat, list):
            items = [str(t).strip() for t in raw_cat if str(t).strip()]
        else:
            items = [
                line.strip(" -") for line in str(raw_cat).splitlines() if line.strip()
            ]
        result[code] = items[:5]
    return result


def _parse_coaching_response(raw: str) -> GeneratedCoaching:
    clean = _strip_markdown_json(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Ollama response is not valid JSON: {e}\nRaw (first 300 chars): {raw[:300]}"
        ) from e

    return GeneratedCoaching(
        reflection_themes=_cap_bullets(data.get("reflection_themes", "")),
        intervention_levers=_cap_bullets(data.get("intervention_levers", "")),
        recommended_missions=_cap_bullets(data.get("recommended_missions", "")),
    )
