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
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml

from r6_navigator.services.prompt import load_prompt

_PACKAGE_DIR = Path(__file__).parent.parent  # r6_navigator/
_PROJECT_ROOT = _PACKAGE_DIR.parent  # project root (params.yml lives here)


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


@dataclass
class GeneratedFiche:
    """Résultat de ``generate_fiche()`` — trois champs de la fiche descriptive.

    Attributes:
        name: Intitulé canonique de la capacité dans la langue cible.
        definition: Bloc de 5 items « - phrase.\n » décrivant la capacité.
        central_function: Prose de 3 phrases exposant la fonction centrale.
    """

    name: str
    definition: str
    central_function: str


@dataclass
class GeneratedRisque:
    """Résultat de ``generate_fiche_risque()`` — deux blocs de risques.

    Attributes:
        risk_insufficient: Bloc « - phrase.\n » (max 5) décrivant les
            conséquences d'un niveau insuffisant de la capacité.
        risk_excessive: Bloc « - phrase.\n » (max 5) décrivant les
            conséquences d'un niveau excessif de la capacité.
    """

    risk_insufficient: str
    risk_excessive: str


@dataclass
class GeneratedContent:
    """Résultat de ``translate_fiche()`` — traduction complète de la fiche.

    Attributes:
        name: Intitulé traduit dans la langue cible.
        definition: Bloc de définition traduit (max 5 items « - phrase.\n »).
        central_function: Fonction centrale traduite (prose 3 phrases).
        risk_insufficient: Risques si insuffisant traduits (max 5 items).
        risk_excessive: Risques si excessif traduits (max 5 items).
    """

    name: str
    definition: str
    central_function: str
    risk_insufficient: str
    risk_excessive: str


@dataclass
class GeneratedCoaching:
    """Résultat de ``generate_coaching()`` — trois sections de coaching.

    Attributes:
        reflection_themes: Thèmes de réflexion en liste à puces
            (format « - phrase.\n »).
        intervention_levers: Leviers d'intervention en liste à puces.
        recommended_missions: Missions recommandées en liste à puces.
    """

    reflection_themes: str
    intervention_levers: str
    recommended_missions: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_fiche(capacity_id: str, lang: str) -> GeneratedFiche:
    """Calls Ollama to generate name, definition and central_function for one capacity.

    Args:
        capacity_id: e.g. "I1a"
        lang: active UI language ("fr" or "en"); model responds in this language.

    Returns:
        GeneratedFiche populated from the JSON response.

    Raises:
        RuntimeError: if Ollama is unreachable or the response is not valid JSON.
    """
    params = _load_params()
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


def generate_fiche_risque(capacity_id: str, lang: str) -> GeneratedRisque:
    """Calls Ollama to generate risk_insufficient and risk_excessive for one capacity.

    Args:
        capacity_id: e.g. "I1a"
        lang: active UI language ("fr" or "en"); model responds in this language.

    Returns:
        GeneratedRisque populated from the JSON response.

    Raises:
        RuntimeError: if Ollama is unreachable or the response is not valid JSON.
    """
    params = _load_params()
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
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    return _parse_risque_response(raw)


def generate_questions(capacity_id: str, lang: str) -> list[str]:
    """Génère les 10 questions d'entretien pour une capacité.

    Args:
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        lang: Langue active (``"fr"`` ou ``"en"``).

    Returns:
        Liste de 10 textes de questions d'entretien.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la réponse n'est pas un JSON valide.
    """
    params = _load_params()
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
    """Génère les 4×5 items observables (OK/DEP/EXC/INS) pour une capacité.

    Args:
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        lang: Langue active (``"fr"`` ou ``"en"``).

    Returns:
        Dictionnaire ``{code_catégorie: [texte, ...]}`` avec les clés OK, DEP, EXC, INS.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la réponse n'est pas un JSON valide.
    """
    params = _load_params()
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
    """Génère les contenus de coaching d'une capacité (thèmes, leviers, missions).

    Args:
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        lang: Langue active (``"fr"`` ou ``"en"``).

    Returns:
        GeneratedCoaching avec les trois champs texte en listes à puces.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la réponse n'est pas un JSON valide.
    """
    params = _load_params()
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
    """Traduit le contenu Fiche d'une capacité d'une langue vers une autre via Ollama.

    Args:
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        source_fields: Dictionnaire des champs sources avec les clés
            ``name``, ``definition``, ``central_function``,
            ``risk_insufficient``, ``risk_excessive``.
        source_lang: Code de la langue source (``"fr"`` ou ``"en"``).
        target_lang: Code de la langue cible (``"fr"`` ou ``"en"``).

    Returns:
        GeneratedContent peuplé avec les champs traduits.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la réponse n'est pas un JSON valide.
    """
    params = _load_params()
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
    """Traduit une liste de questions d'entretien d'une langue vers une autre via Ollama.

    Args:
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        questions: Liste des textes de questions dans la langue source.
        source_lang: Code de la langue source (``"fr"`` ou ``"en"``).
        target_lang: Code de la langue cible (``"fr"`` ou ``"en"``).

    Returns:
        Liste de textes traduits dans le même ordre que la liste source.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la réponse n'est pas un JSON valide.
    """
    params = _load_params()
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
    """Traduit les manifestations observables par catégorie via Ollama.

    Args:
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        items_by_cat: Dictionnaire ``{code_catégorie: [texte, ...]}`` en langue source.
            Les codes valides sont ``OK``, ``EXC``, ``DEP``, ``INS``.
        source_lang: Code de la langue source (``"fr"`` ou ``"en"``).
        target_lang: Code de la langue cible (``"fr"`` ou ``"en"``).

    Returns:
        Dictionnaire ``{code_catégorie: [texte_traduit, ...]}`` dans le même ordre
        que la source, avec les mêmes clés.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la réponse n'est pas un JSON valide.
    """
    params = _load_params()
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
    """Traduit le contenu Coaching d'une capacité d'une langue vers une autre via Ollama.

    Args:
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        source_fields: Dictionnaire des champs sources avec les clés
            ``reflection_themes``, ``intervention_levers``, ``recommended_missions``.
        source_lang: Code de la langue source (``"fr"`` ou ``"en"``).
        target_lang: Code de la langue cible (``"fr"`` ou ``"en"``).

    Returns:
        GeneratedCoaching peuplé avec les trois champs traduits.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la réponse n'est pas un JSON valide.
    """
    params = _load_params()
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


def _load_params() -> dict:
    """Charge et retourne la configuration depuis ``params.yml``.

    Returns:
        Dictionnaire YAML avec les clés ``ollama`` (url, model, timeout)
        et ``reserve`` (notes sur les modèles alternatifs).

    Raises:
        FileNotFoundError: Si ``params.yml`` est absent de la racine projet.
    """
    params_path = _PROJECT_ROOT / "params.yml"
    with open(params_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_system_prompt() -> str:
    """Charge le prompt système depuis ``services/prompt/system_01.txt``.

    Le prompt système définit le rôle d'expert R6/Halliday du LLM et les
    règles de différenciation linguistique obligatoires. Il est envoyé en
    paramètre ``system`` à chaque appel Ollama.

    Returns:
        Contenu brut du fichier (chaîne UTF-8).

    Raises:
        FileNotFoundError: Si ``system_01.txt`` est absent du dossier prompt.
    """
    path = Path(__file__).parent / "prompt" / "system_01.txt"
    with open(path, encoding="utf-8") as f:
        return f.read()


def _load_axioms() -> dict:
    """Charge l'ontologie R6 depuis ``axioms.yml``.

    Returns:
        Dictionnaire YAML avec la clé ``r6_ontology`` contenant les niveaux,
        axes, pôles et principes fondamentaux du modèle R6.

    Raises:
        FileNotFoundError: Si ``axioms.yml`` est absent du package.
    """
    axioms_path = _PACKAGE_DIR / "axioms.yml"
    with open(axioms_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_halliday_rules(level_code: str) -> dict:
    """Charge les règles Halliday spécifiques au niveau depuis ``halliday_rules.json``.

    Chaque niveau (I, O, S) dispose de sept champs décrivant les contraintes
    de transitivité grammaticale : ``interview_target``, ``participant_1``,
    ``process_type``, ``participant_2``, ``circumstance``, ``proscription``,
    et ``audit_rule_main_clause`` (plus ``audit_rule_inversion`` pour O).

    Args:
        level_code: Code du niveau R6 (``"I"``, ``"O"`` ou ``"S"``).

    Returns:
        Dictionnaire des champs Halliday pour le niveau demandé.

    Raises:
        FileNotFoundError: Si ``halliday_rules.json`` est absent du dossier prompt.
        KeyError: Si ``level_code`` n'est pas présent dans le fichier.
    """
    rules_path = Path(__file__).parent / "prompt" / "halliday_rules.json"
    with open(rules_path, encoding="utf-8") as f:
        data = json.load(f)
    return data[level_code]


def _load_halliday_context(level_code: str) -> str:
    """Retourne le contexte Halliday formaté pour injection dans les prompts.

    Lit les règles de transitivité depuis ``halliday_rules.json`` et les
    assemble en un bloc texte structuré prêt à être injecté comme
    ``{halliday_context}`` dans n'importe quel prompt de génération ou
    d'évaluation. Inclut les règles d'audit syntaxique (``audit_rule_main_clause``
    et, pour O, ``audit_rule_inversion``) afin de guider également le juge LLM.

    Args:
        level_code: Code du niveau R6 (``"I"``, ``"O"`` ou ``"S"``).

    Returns:
        Bloc texte multi-lignes décrivant les contraintes Halliday du niveau.
    """
    rules = _load_halliday_rules(level_code)
    lines = [
        f"Interview target: {rules['interview_target']}",
        f"Subject / Participant 1: {rules['participant_1']}",
        f"Process type: {rules['process_type']}",
        f"Object / Participant 2: {rules['participant_2']}",
        f"Circumstance: {rules['circumstance']}",
        f"Proscription: {rules['proscription']}",
        f"Audit rule (main clause): {rules['audit_rule_main_clause']}",
    ]
    if "audit_rule_inversion" in rules:
        lines.append(f"Audit rule (inversion test): {rules['audit_rule_inversion']}")
    return "\n".join(lines)


def _load_canonical_name(capacity_id: str, lang: str) -> str:
    """Retourne le nom canonique d'une capacité dans la langue indiquée.

    Lit ``capacities_fr.yml`` ou ``capacities_en.yml`` selon ``lang``.
    Si le fichier ou la clé est absent, retourne ``capacity_id`` en fallback
    pour ne jamais bloquer la génération.

    Args:
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        lang: Langue cible (``"fr"`` ou ``"en"``).

    Returns:
        Nom canonique localisé, ou ``capacity_id`` si introuvable.
    """
    names_path = _PACKAGE_DIR / f"capacities_{lang}.yml"
    try:
        with open(names_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        names = data.get(f"capacities_{lang}", {})
        return names.get(capacity_id, capacity_id)
    except FileNotFoundError:
        return capacity_id


_OLLAMA_MAX_RETRIES = 3
_OLLAMA_RETRY_DELAY = 2  # seconds between attempts


def _call_ollama(url: str, model: str, system: str, prompt: str, timeout: int) -> str:
    """Appelle l'API Ollama en mode génération non streamée et retourne la réponse brute.

    Réessaie jusqu'à ``_OLLAMA_MAX_RETRIES`` fois en cas d'erreur réseau ou
    de réponse JSON malformée, avec une pause de ``_OLLAMA_RETRY_DELAY``
    secondes entre chaque tentative.

    Args:
        url: URL de base du serveur Ollama (ex. ``"http://localhost:11434"``).
        model: Nom du modèle Ollama à utiliser (ex. ``"mistral-large-3:675b-cloud"``).
        system: Prompt système décrivant le rôle et les règles du LLM.
        prompt: Prompt utilisateur contenant la tâche de génération.
        timeout: Délai maximum en secondes avant abandon de la requête HTTP.

    Returns:
        Chaîne brute retournée par Ollama dans le champ ``response``.

    Raises:
        RuntimeError: Si toutes les tentatives échouent (réseau inaccessible
            ou réponse non conforme).
    """
    payload = json.dumps(
        {
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
    ).encode("utf-8")
    endpoint = f"{url.rstrip('/')}/api/generate"

    last_exc: Exception | None = None
    for attempt in range(1, _OLLAMA_MAX_RETRIES + 1):
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["response"]
        except urllib.error.URLError as e:
            last_exc = RuntimeError(f"Ollama unreachable at {url}: {e}")
        except (KeyError, json.JSONDecodeError) as e:
            last_exc = RuntimeError(f"Unexpected Ollama response format: {e}")

        if attempt < _OLLAMA_MAX_RETRIES:
            time.sleep(_OLLAMA_RETRY_DELAY)

    raise last_exc


def _fix_json_strings(text: str) -> str:
    """Échappe les sauts de ligne et tabulations littéraux dans les valeurs JSON.

    Les LLM émettent parfois des retours à la ligne bruts à l'intérieur de
    chaînes JSON, ce qui rend le JSON invalide. Cette fonction parcourt le texte
    caractère par caractère et remplace les ``\\n`` / ``\\r`` / ``\\t`` nus
    trouvés à l'intérieur d'une chaîne (entre guillemets non échappés) par
    leurs équivalents échappés ``\\\\n`` / ``\\\\t``. Les ``\\r`` sont
    silencieusement supprimés.

    Args:
        text: Texte JSON brut potentiellement invalide.

    Returns:
        Texte JSON dont les valeurs chaînes contiennent des séquences
        d'échappement valides.
    """
    result: list[str] = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
        elif ch == "\\" and in_string:
            result.append(ch)
            escape_next = True
        elif ch == '"':
            in_string = not in_string
            result.append(ch)
        elif in_string and ch == "\n":
            result.append("\\n")
        elif in_string and ch == "\r":
            pass  # discard bare carriage-returns inside strings
        elif in_string and ch == "\t":
            result.append("\\t")
        else:
            result.append(ch)
    return "".join(result)


def _strip_markdown_json(text: str) -> str:
    """Supprime l'enveloppe Markdown ``` optionnelle et corrige les newlines nus.

    Certains modèles encapsulent leur réponse JSON dans un bloc ```json…```.
    Cette fonction extrait le contenu brut si ce bloc est présent, puis
    délègue à ``_fix_json_strings`` pour normaliser les caractères de contrôle.

    Args:
        text: Réponse brute du LLM, avec ou sans bloc ```json…```.

    Returns:
        Texte JSON nettoyé prêt pour ``json.loads()``.
    """
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    return _fix_json_strings(text)


def _cap_bullets(value, max_items: int = 5) -> str:
    """Normalise et tronque une valeur LLM en bloc de puces « - phrase.\n ».

    Accepte aussi bien une chaîne multiligne qu'une liste Python, car certains
    modèles retournent les items sous forme de tableau JSON plutôt que de texte.
    Seules les lignes commençant par « - » sont conservées (filtre de sécurité).

    Args:
        value: Valeur brute issue du JSON LLM — chaîne ou liste de chaînes.
        max_items: Nombre maximum d'items retenus (défaut : 5).

    Returns:
        Chaîne avec au plus ``max_items`` lignes « - phrase. », terminée par
        un saut de ligne, ou chaîne vide si ``value`` est falsy.
    """
    if not value:
        return ""
    if isinstance(value, list):
        # Each element may already be "- text" or just "text"
        lines = []
        for item in value:
            item = str(item).strip()
            if not item.startswith("-"):
                item = f"- {item}"
            lines.append(item)
    else:
        lines = [
            line for line in str(value).splitlines() if line.strip().startswith("-")
        ]
    capped = lines[:max_items]
    return "\n".join(capped) + ("\n" if capped else "")


def _to_str(value, fallback: str = "") -> str:
    """Convertit toute valeur LLM en chaîne de caractères simple.

    Certains modèles retournent des listes là où une prose est attendue.
    Cette fonction unifie les cas : None → fallback, list → lignes jointes,
    autre → str().

    Args:
        value: Valeur brute issue du JSON LLM (None, str, list, ou autre).
        fallback: Valeur retournée si ``value`` est None (défaut : ``""``).

    Returns:
        Représentation textuelle de ``value``.
    """
    if value is None:
        return fallback
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def _parse_fiche_response(raw: str, capacity_id: str) -> GeneratedFiche:
    """Parse la réponse Ollama pour generate_fiche().

    Args:
        raw: Chaîne JSON brute retournée par Ollama.
        capacity_id: Utilisé comme fallback pour le champ ``name``.

    Returns:
        GeneratedFiche avec name, definition et central_function.

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

    return GeneratedFiche(
        name=_to_str(data.get("name"), fallback=capacity_id),
        definition=_cap_bullets(data.get("definition", "")),
        central_function=_to_str(data.get("central_function")),
    )


def _parse_risque_response(raw: str) -> GeneratedRisque:
    """Parse la réponse Ollama pour generate_fiche_risque().

    Args:
        raw: Chaîne JSON brute retournée par Ollama.

    Returns:
        GeneratedRisque avec risk_insufficient et risk_excessive.

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

    return GeneratedRisque(
        risk_insufficient=_cap_bullets(data.get("risk_insufficient", "")),
        risk_excessive=_cap_bullets(data.get("risk_excessive", "")),
    )


def _parse_content_response(raw: str, capacity_id: str) -> GeneratedContent:
    """Parse la réponse Ollama pour translate_fiche().

    Args:
        raw: Chaîne JSON brute retournée par Ollama.
        capacity_id: Utilisé comme fallback pour le champ ``name``.

    Returns:
        GeneratedContent sans observable.

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

    return GeneratedContent(
        name=_to_str(data.get("name"), fallback=capacity_id),
        definition=_cap_bullets(data.get("definition", "")),
        central_function=_to_str(data.get("central_function")),
        risk_insufficient=_cap_bullets(data.get("risk_insufficient", "")),
        risk_excessive=_cap_bullets(data.get("risk_excessive", "")),
    )


def _parse_questions_list(raw: str) -> list[str]:
    """Parse la réponse Ollama pour translate_questions().

    Args:
        raw: Chaîne JSON brute retournée par Ollama ; doit contenir la clé ``questions``.

    Returns:
        Liste de textes traduits dans l'ordre de la source.

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

    raw_questions = data.get("questions", [])
    if isinstance(raw_questions, list):
        return [str(q).strip() for q in raw_questions if str(q).strip()]
    return [
        line.strip(" -") for line in str(raw_questions).splitlines() if line.strip()
    ]


def _parse_items_dict(raw: str, source: dict[str, list[str]]) -> dict[str, list[str]]:
    """Parse la réponse Ollama pour translate_observable_items().

    Assure que chaque catégorie traduite contient au plus autant d'items
    que la source correspondante.

    Args:
        raw: Chaîne JSON brute retournée par Ollama.
        source: Dictionnaire source ``{code: [texte, ...]}`` utilisé comme référence
            pour le nombre d'items attendus par catégorie.

    Returns:
        Dictionnaire ``{code: [texte_traduit, ...]}`` pour les catégories présentes
        dans la source.

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

    result: dict[str, list[str]] = {}
    for code, src_items in source.items():
        raw_cat = data.get(code, [])
        if isinstance(raw_cat, list):
            items = [str(t).strip() for t in raw_cat if str(t).strip()]
        else:
            items = [
                line.strip(" -") for line in str(raw_cat).splitlines() if line.strip()
            ]
        # Tronque si le modèle a retourné plus d'items que la source.
        result[code] = items[: len(src_items)]
    return result


def _parse_questions_response(raw: str) -> list[str]:
    """Parse la réponse Ollama pour generate_questions().

    Args:
        raw: Chaîne JSON brute retournée par Ollama.

    Returns:
        Liste de textes de questions d'entretien.

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

    raw_questions = data.get("questions", [])
    if isinstance(raw_questions, list):
        return [str(q).strip() for q in raw_questions if str(q).strip()]
    return [
        line.strip(" -") for line in str(raw_questions).splitlines() if line.strip()
    ]


def _parse_items_response(raw: str) -> dict[str, list[str]]:
    """Parse la réponse Ollama pour generate_questions_items().

    Args:
        raw: Chaîne JSON brute retournée par Ollama.

    Returns:
        Dictionnaire ``{code: [texte, ...]}`` pour les 4 catégories OK, DEP, EXC, INS.

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
    """Parse la réponse Ollama pour generate_coaching().

    Args:
        raw: Chaîne JSON brute retournée par Ollama.

    Returns:
        GeneratedCoaching avec les trois champs en listes à puces.

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

    return GeneratedCoaching(
        reflection_themes=_cap_bullets(data.get("reflection_themes", "")),
        intervention_levers=_cap_bullets(data.get("intervention_levers", "")),
        recommended_missions=_cap_bullets(data.get("recommended_missions", "")),
    )
