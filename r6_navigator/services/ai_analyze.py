"""Analyse de verbatims d'entretien et génération de rapports de mission via Ollama.

Ce module expose deux fonctions publiques :

* ``analyze_verbatim``       — extrait et interprète les passages significatifs d'un verbatim
* ``generate_mission_report`` — génère un rapport de diagnostic R6 à partir des interprétations
                                validées d'une mission

Les appels Ollama réutilisent le même pattern que ``ai_generate.py`` :
``_call_ollama`` avec retry, chargement de la config depuis ``params.yml``,
prompt système depuis ``services/prompt/system_01.txt``.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml

_PACKAGE_DIR = Path(__file__).parent.parent  # r6_navigator/
_PROJECT_ROOT = _PACKAGE_DIR.parent          # project root

_OLLAMA_MAX_RETRIES = 3
_OLLAMA_RETRY_DELAY = 2  # seconds between attempts

_LEVEL_NAMES = {
    "S": "Strategic",
    "O": "Organizational",
    "I": "Individual",
}


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------

@dataclass
class AnalyzedExtract:
    """Un extrait du verbatim avec son interprétation R6.

    Attributes:
        text: Extrait cité ou condensé du verbatim.
        tag: Code de la capacité R6 identifiée (ex. ``"I3a"``), ou None.
        capacity_id: Identifiant de la capacité (identique à tag).
        maturity_level: Évaluation du niveau de maturité (ex. ``"insuffisant"``).
        confidence: Score de confiance de l'interprétation (0.0 – 1.0).
        interpretation: Texte analytique expliquant l'extrait (2-4 phrases).
    """

    text: str
    tag: str | None
    capacity_id: str | None
    maturity_level: str
    confidence: float
    interpretation: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_verbatim(
    verbatim_text: str,
    interview_info: dict,
    lang: str = "fr",
) -> list[AnalyzedExtract]:
    """Analyse un verbatim d'entretien et retourne les extraits significatifs.

    Args:
        verbatim_text: Texte brut du verbatim d'entretien.
        interview_info: Dictionnaire avec les clés ``subject_name``, ``subject_role``,
            ``level_code``, ``interview_date`` (toutes optionnelles sauf ``level_code``).
        lang: Langue de l'analyse (``"fr"`` ou ``"en"``).

    Returns:
        Liste d'``AnalyzedExtract`` triés par pertinence décroissante.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la réponse n'est pas un JSON valide.
    """
    params = _load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 120))
    system_prompt = _load_system_prompt()

    level_code = interview_info.get("level_code", "I")
    maturity_scale = _load_maturity_scale(level_code)
    level_name = _LEVEL_NAMES.get(level_code, level_code)

    prompt_template = _load_prompt_file("analyze_verbatim")
    user_prompt = prompt_template.format(
        subject_name=interview_info.get("subject_name", "N/A"),
        subject_role=interview_info.get("subject_role", "N/A"),
        level_code=level_code,
        level_name=level_name,
        interview_date=interview_info.get("interview_date", "N/A"),
        maturity_scale=maturity_scale,
        verbatim_text=verbatim_text,
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    return _parse_extracts_response(raw)


def generate_mission_report(
    mission_id: int,
    session_factory,
    lang: str = "fr",
) -> str:
    """Génère un rapport de diagnostic R6 pour une mission.

    Charge toutes les interprétations validées de la mission, les organise
    par niveau S/O/I, et appelle Ollama pour générer le rapport structuré.

    Args:
        mission_id: Identifiant de la mission en base.
        session_factory: Factory de session SQLAlchemy (sessionmaker).
        lang: Langue du rapport (``"fr"`` ou ``"en"``).

    Returns:
        Texte du rapport en Markdown.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la réponse n'est pas un JSON valide.
        ValueError: Si la mission n'existe pas.
    """
    from r6_navigator.services.crud_mission import (
        get_all_mission_interpretations,
        get_mission,
    )

    with session_factory() as session:
        mission = get_mission(session, mission_id)
        if mission is None:
            raise ValueError(f"Mission {mission_id} not found")

        mission_name = mission.name
        client = mission.client or "N/A"
        consultant = mission.consultant or "N/A"
        interview_count = len(mission.interviews)

        interpretations = get_all_mission_interpretations(session, mission_id)
        validated = [i for i in interpretations if i.status in ("validated", "corrected")]

    # Group by level
    by_level: dict[str, list[str]] = {"S": [], "O": [], "I": []}
    for interp in validated:
        cap_id = interp.capacity_id or ""
        level = cap_id[0] if cap_id and cap_id[0] in ("S", "O", "I") else "I"
        entry = f"[{cap_id}] {interp.text}"
        if interp.maturity_level:
            entry = f"[{cap_id} — {interp.maturity_level}] {interp.text}"
        by_level[level].append(entry)

    def _fmt(items: list[str]) -> str:
        if not items:
            return "(aucune interprétation validée)" if lang == "fr" else "(no validated interpretation)"
        return "\n".join(f"- {item}" for item in items)

    params = _load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model"]
    timeout = int(ollama_cfg.get("timeout", 120))
    system_prompt = _load_system_prompt()

    lang_name = "French" if lang == "fr" else "US English"
    prompt_template = _load_prompt_file("generate_mission_report")
    user_prompt = prompt_template.format(
        mission_name=mission_name,
        client=client,
        consultant=consultant,
        interview_count=interview_count,
        lang_name=lang_name,
        interpretations_S=_fmt(by_level["S"]),
        interpretations_O=_fmt(by_level["O"]),
        interpretations_I=_fmt(by_level["I"]),
    )

    raw = _call_ollama(url, model, system_prompt, user_prompt, timeout)
    return _parse_report_response(raw)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_maturity_scale(level_code: str) -> str:
    """Charge l'échelle de maturité Markdown pour un niveau R6 donné.

    Args:
        level_code: Code du niveau (``"I"``, ``"O"`` ou ``"S"``).

    Returns:
        Contenu brut du fichier Markdown de l'échelle, ou chaîne vide si absent.
    """
    scales_dir = _PACKAGE_DIR / "maturity_scales"
    candidates = {
        "I": "I6_EQF_Proficiency_Levels_short.md",
        "O": "O6_Maturity_Levels_short.md",
        "S": "S6_Maturity_Levels_short.md",
    }
    filename = candidates.get(level_code)
    if filename is None:
        return ""
    path = scales_dir / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _load_prompt_file(name: str) -> str:
    """Charge un fichier de prompt depuis ``services/prompt/``.

    Args:
        name: Nom du prompt sans extension (ex. ``"analyze_verbatim"``).

    Returns:
        Contenu brut du fichier .txt.

    Raises:
        FileNotFoundError: Si le fichier est absent.
    """
    path = Path(__file__).parent / "prompt" / f"{name}.txt"
    return path.read_text(encoding="utf-8")


def _load_params() -> dict:
    params_path = _PROJECT_ROOT / "params.yml"
    with open(params_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_system_prompt() -> str:
    path = Path(__file__).parent / "prompt" / "system_01.txt"
    return path.read_text(encoding="utf-8")


def _call_ollama(url: str, model: str, system: str, prompt: str, timeout: int) -> str:
    """Appelle l'API Ollama (non streamée) avec retry.

    Args:
        url: URL de base du serveur Ollama.
        model: Nom du modèle.
        system: Prompt système.
        prompt: Prompt utilisateur.
        timeout: Délai HTTP maximum en secondes.

    Returns:
        Réponse brute du champ ``response`` d'Ollama.

    Raises:
        RuntimeError: Si toutes les tentatives échouent.
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

    raise last_exc  # type: ignore[misc]


def _parse_extracts_response(raw: str) -> list[AnalyzedExtract]:
    """Parse la réponse JSON Ollama en liste d'AnalyzedExtract.

    Args:
        raw: Chaîne brute retournée par Ollama.

    Returns:
        Liste d'``AnalyzedExtract``.

    Raises:
        RuntimeError: Si le JSON est invalide ou la structure inattendue.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to find a JSON array in the raw string
        import re
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
        else:
            raise RuntimeError(f"Cannot parse extracts response as JSON: {raw[:200]}")

    if isinstance(data, dict):
        # Some models wrap in {"extracts": [...]}
        for key in ("extracts", "results", "items"):
            if key in data:
                data = data[key]
                break

    if not isinstance(data, list):
        raise RuntimeError(f"Expected JSON array, got: {type(data)}")

    results = []
    for item in data:
        results.append(AnalyzedExtract(
            text=str(item.get("text", "")),
            tag=item.get("tag") or item.get("capacity_id"),
            capacity_id=item.get("capacity_id") or item.get("tag"),
            maturity_level=str(item.get("maturity_level", "")),
            confidence=float(item.get("confidence", 0.5)),
            interpretation=str(item.get("interpretation", "")),
        ))
    return results


def _parse_report_response(raw: str) -> str:
    """Parse la réponse JSON Ollama pour en extraire le texte du rapport.

    Args:
        raw: Chaîne brute retournée par Ollama.

    Returns:
        Texte du rapport en Markdown.
    """
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return str(data.get("report", raw))
        return str(data)
    except json.JSONDecodeError:
        return raw
