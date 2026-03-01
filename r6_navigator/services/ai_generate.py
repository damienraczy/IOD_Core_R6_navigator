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
    name: str
    definition: str  # Bullet string: "- phrase.\n" × 5
    central_function: str  # 3 prose sentences


@dataclass
class GeneratedRisque:
    risk_insufficient: str  # Bullet string (max 5 items)
    risk_excessive: str  # Bullet string (max 5 items)


@dataclass
class GeneratedContent:
    """Résultat de translate_fiche() — traduction complète sans observable."""

    name: str
    definition: str
    central_function: str
    risk_insufficient: str  # Bullet string (max 5 items)
    risk_excessive: str  # Bullet string (max 5 items)


@dataclass
class GeneratedCoaching:
    reflection_themes: str  # liste à puces "- phrase.\n"
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
    system_prompt = params.get("system_prompt", "")

    axioms = _load_axioms()
    canonical_name = _load_canonical_name(capacity_id, lang)

    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]

    ontology = axioms["r6_ontology"]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]

    halliday_context = _halliday_context_for_level(_load_halliday_spec(), level_code)

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
    system_prompt = params.get("system_prompt", "")

    axioms = _load_axioms()
    canonical_name = _load_canonical_name(capacity_id, lang)

    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]

    ontology = axioms["r6_ontology"]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]

    halliday_context = _halliday_context_for_level(_load_halliday_spec(), level_code)

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
    system_prompt = params.get("system_prompt", "")

    axioms = _load_axioms()
    canonical_name = _load_canonical_name(capacity_id, lang)

    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]

    ontology = axioms["r6_ontology"]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]

    interview_rules = _load_interview_rules(level_code)

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
    system_prompt = params.get("system_prompt", "")

    axioms = _load_axioms()
    canonical_name = _load_canonical_name(capacity_id, lang)

    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]

    ontology = axioms["r6_ontology"]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]

    halliday_context = _halliday_context_for_level(_load_halliday_spec(), level_code)

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
    system_prompt = params.get("system_prompt", "")

    axioms = _load_axioms()
    canonical_name = _load_canonical_name(capacity_id, lang)

    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]

    ontology = axioms["r6_ontology"]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]

    halliday_context = _halliday_context_for_level(_load_halliday_spec(), level_code)

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
    system_prompt = params.get("system_prompt", "")

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
    system_prompt = params.get("system_prompt", "")

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
    system_prompt = params.get("system_prompt", "")

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
    system_prompt = params.get("system_prompt", "")

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
    params_path = _PROJECT_ROOT / "params.yml"
    with open(params_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_axioms() -> dict:
    axioms_path = _PACKAGE_DIR / "axioms.yml"
    with open(axioms_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_interview_rules(level_code: str) -> dict:
    """Charge les paramètres d'entretien spécifiques au niveau depuis interview_rules.json."""
    rules_path = Path(__file__).parent / "prompt" / "interview_rules.json"
    with open(rules_path, encoding="utf-8") as f:
        data = json.load(f)
    return data[level_code]


def _load_halliday_spec() -> str:
    spec_path = _PROJECT_ROOT / "R6" / "Halliday.md"
    try:
        with open(spec_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


_HALLIDAY_LEVEL_MARKER = {
    "I": "### 2.1.",
    "O": "### 2.2.",
    "S": "### 2.3.",
}


def _halliday_context_for_level(spec: str, level_code: str) -> str:
    """Extrait les règles Halliday pertinentes pour un niveau R6 donné."""
    if not spec:
        return "(Halliday specification not available)"

    import re as _re

    parts: list[str] = []

    marker = _HALLIDAY_LEVEL_MARKER.get(level_code, "")
    if marker:
        idx = spec.find(marker)
        if idx != -1:
            after = spec[idx:]
            boundary = _re.search(r"\n(?:###|---)", after[1:])
            if boundary:
                section = after[: boundary.start() + 1].strip()
            else:
                section = after.strip()
            parts.append(section)

    for line in spec.splitlines():
        if f"**{level_code} " in line or f"| **{level_code}" in line:
            parts.append(f"Summary for level {level_code}:\n{line.strip()}")
            break

    audit_idx = spec.find("## 4.")
    if audit_idx != -1:
        after_audit = spec[audit_idx:]
        next_section = _re.search(r"\n## ", after_audit[1:])
        if next_section:
            audit_section = after_audit[: next_section.start() + 1].strip()
        else:
            audit_section = after_audit.strip()
        parts.append(audit_section)

    return "\n\n".join(parts)


def _load_canonical_name(capacity_id: str, lang: str) -> str:
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
    """Calls the Ollama API and returns the raw response string.

    Retries up to _OLLAMA_MAX_RETRIES times on any error, waiting
    _OLLAMA_RETRY_DELAY seconds between attempts. Raises RuntimeError
    if all attempts fail.
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
    """Escapes literal newlines and tabs inside JSON string values.

    LLMs sometimes emit raw line-breaks inside string literals, which is
    invalid JSON. This function walks the text character by character and
    replaces bare ``\\n`` / ``\\r`` / ``\\t`` characters found inside a JSON
    string (between unescaped double-quotes) with their escaped equivalents.
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
    """Removes optional ```json ... ``` wrapper and fixes bare newlines in strings."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    return _fix_json_strings(text)


def _cap_bullets(value, max_items: int = 5) -> str:
    """Keeps at most max_items bullet lines.

    Accepts either a plain string or a list (some models return arrays).
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
    """Coerce any model-returned value to a plain string."""
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
