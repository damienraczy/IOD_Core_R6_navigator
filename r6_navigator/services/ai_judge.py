"""Évaluation d'une fiche R6 par 3 juges LLM tournant en parallèle.

Chaque juge appelle Ollama avec un prompt spécialisé et retourne un verdict
structuré. Les trois appels sont lancés simultanément via threading.Thread.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import yaml

from r6_navigator.services.prompt import load_prompt

_PACKAGE_DIR = Path(__file__).parent.parent  # r6_navigator/
_PROJECT_ROOT = _PACKAGE_DIR.parent  # project root (params.yml)


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------

VERDICTS = ("pas_bon", "satisfaisant", "tres_bon")
SCORES = {
    "pas_bon": 1,
    "satisfaisant": 2,
    "tres_bon": 3,
}


@dataclass
class SingleJudgeResult:
    judge_name: str
    verdict: str  # "pas_bon" | "satisfaisant" | "tres_bon"
    score: int  # 1 | 2 | 3
    justification: str
    error: str | None = None


@dataclass
class JudgeResults:
    judge_axioms: SingleJudgeResult  # Juge 1 — axiomes R6
    judge_halliday: SingleJudgeResult  # Juge 2 — Halliday
    judge_coherence: SingleJudgeResult  # Juge 3 — cohérence niveau/pôle
    aggregate_verdict: str  # majorité ou pire des 3
    aggregate_score: float  # moyenne des 3 scores


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def judge_fiche(content: dict, capacity_id: str, lang: str) -> JudgeResults:
    """Évalue une fiche R6 via 3 juges LLM tournant en parallèle.

    Args:
        content: Dictionnaire des champs de la fiche avec les clés
            ``label``, ``definition``, ``central_function``, ``observable``,
            ``risk_insufficient``, ``risk_excessive``.
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        lang: Langue active (``"fr"`` ou ``"en"``).

    Returns:
        JudgeResults agrégés des 3 juges.
    """
    params = _load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model_judge"]
    timeout = int(ollama_cfg.get("timeout", 60))
    system_prompt = params.get("system_prompt", "")

    axioms = _load_axioms()
    ontology = axioms["r6_ontology"]
    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]
    principles = ontology["fundamental_principles"]

    content_str = json.dumps(content, ensure_ascii=False, indent=2)

    # ---- Variables communes aux 3 juges ------------------------------------

    lang_name = "French" if lang == "fr" else "US English"
    content_str = json.dumps(content, ensure_ascii=False, indent=2)

    # ---- Prompts des 3 juges ------------------------------------------------

    axioms_context = "\n".join(
        f"- {k}: {v}"
        for k, v in principles.items()
        if k != "linguistic_differentiation"
    )
    prompt_axioms = load_prompt(
        "judge_axioms",
        axioms_context=axioms_context,
        capacity_id=capacity_id,
        level_name=level_info["name"],
        level_code=level_code,
        axis_name=axis_info["name"],
        axis_number=axis_number,
        pole_name=pole_info["name"],
        pole_code=pole_code,
        content_str=content_str,
        lang_name=lang_name,
    )

    halliday_spec = _load_halliday_spec()
    halliday_context = _halliday_context_for_level(halliday_spec, level_code)
    prompt_halliday = load_prompt(
        "judge_halliday",
        level_code=level_code,
        level_name=level_info["name"],
        halliday_context=halliday_context,
        capacity_id=capacity_id,
        axis_name=axis_info["name"],
        axis_number=axis_number,
        pole_name=pole_info["name"],
        pole_code=pole_code,
        content_str=content_str,
        lang_name=lang_name,
    )

    prompt_coherence = load_prompt(
        "judge_coherence",
        capacity_id=capacity_id,
        level_name=level_info["name"],
        level_code=level_code,
        level_description=level_info["description"],
        axis_number=axis_number,
        axis_name=axis_info["name"],
        pole_a_tension=axis_info["tension"]["pole_a"],
        pole_b_tension=axis_info["tension"]["pole_b"],
        pole_code=pole_code,
        pole_name=pole_info["name"],
        pole_characteristics=pole_info["characteristics"],
        content_str=content_str,
        lang_name=lang_name,
    )

    # ---- Appels parallèles --------------------------------------------------

    results: dict[str, SingleJudgeResult] = {}
    lock = threading.Lock()

    def run_judge(judge_key: str, judge_name: str, prompt: str) -> None:
        try:
            raw = _call_ollama(url, model, system_prompt, prompt, timeout)
            result = _parse_judge_response(raw, judge_name)
        except Exception as exc:
            result = SingleJudgeResult(
                judge_name=judge_name,
                verdict="pas_bon",
                score=1,
                justification="",
                error=str(exc),
            )
        with lock:
            results[judge_key] = result

    threads = [
        threading.Thread(
            target=run_judge,
            args=("axioms", "axioms_r6", prompt_axioms),
            daemon=True,
        ),
        threading.Thread(
            target=run_judge,
            args=("halliday", "halliday", prompt_halliday),
            daemon=True,
        ),
        threading.Thread(
            target=run_judge,
            args=("coherence", "coherence", prompt_coherence),
            daemon=True,
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    judge_axioms = results["axioms"]
    judge_halliday = results["halliday"]
    judge_coherence = results["coherence"]

    aggregate_score = (
        judge_axioms.score + judge_halliday.score + judge_coherence.score
    ) / 3.0

    # Majorité : le verdict qui apparaît le plus souvent (ou le moins bon si égalité).
    verdicts_list = [
        judge_axioms.verdict,
        judge_halliday.verdict,
        judge_coherence.verdict,
    ]
    verdict_counts: dict[str, int] = {}
    for v in verdicts_list:
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
    # En cas d'égalité (tous différents), on prend le pire.
    max_count = max(verdict_counts.values())
    majority_candidates = [v for v, c in verdict_counts.items() if c == max_count]
    if len(majority_candidates) == 1:
        aggregate_verdict = majority_candidates[0]
    else:
        # Tous différents → on prend le pire (score le plus bas).
        aggregate_verdict = min(majority_candidates, key=lambda v: SCORES.get(v, 0))

    return JudgeResults(
        judge_axioms=judge_axioms,
        judge_halliday=judge_halliday,
        judge_coherence=judge_coherence,
        aggregate_verdict=aggregate_verdict,
        aggregate_score=aggregate_score,
    )


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


def _load_halliday_spec() -> str:
    spec_path = _PROJECT_ROOT / "R6" / "Halliday.md"
    try:
        with open(spec_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


# Marqueurs de section par niveau dans Halliday.md
_HALLIDAY_LEVEL_MARKER = {
    "I": "### 2.1.",
    "O": "### 2.2.",
    "S": "### 2.3.",
}


def _halliday_context_for_level(spec: str, level_code: str) -> str:
    """Extrait les règles Halliday pertinentes pour un niveau R6 donné.

    Retourne la section 2.x du niveau, la ligne de synthèse correspondante,
    et les règles d'audit (section 4).

    Args:
        spec: Contenu brut de Halliday.md.
        level_code: Code du niveau (``"I"``, ``"O"`` ou ``"S"``).

    Returns:
        Texte concaténé prêt à être injecté dans le prompt.
    """
    if not spec:
        return "(Halliday specification not available)"

    parts: list[str] = []

    # ---- Section 2.x : règles du niveau ------------------------------------
    marker = _HALLIDAY_LEVEL_MARKER.get(level_code, "")
    if marker:
        idx = spec.find(marker)
        if idx != -1:
            after = spec[idx:]
            # S'arrête au prochain heading ### ou à un séparateur ---
            boundary = re.search(r"\n(?:###|---)", after[1:])
            if boundary:
                section = after[: boundary.start() + 1].strip()
            else:
                section = after.strip()
            parts.append(section)

    # ---- Ligne de synthèse du tableau (section 3) --------------------------
    for line in spec.splitlines():
        if f"**{level_code} " in line or f"| **{level_code}" in line:
            parts.append(f"Synthèse pour le niveau {level_code} :\n{line.strip()}")
            break

    # ---- Section 4 : règles d'audit ----------------------------------------
    audit_idx = spec.find("## 4.")
    if audit_idx != -1:
        # S'arrête à la fin du fichier ou au prochain ## heading
        after_audit = spec[audit_idx:]
        next_section = re.search(r"\n## ", after_audit[1:])
        if next_section:
            audit_section = after_audit[: next_section.start() + 1].strip()
        else:
            audit_section = after_audit.strip()
        parts.append(audit_section)

    return "\n\n".join(parts)


def _call_ollama(url: str, model: str, system: str, prompt: str, timeout: int) -> str:
    import urllib.error
    import urllib.request

    payload = json.dumps(
        {
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["response"]
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama unreachable at {url}: {e}") from e
    except (KeyError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Unexpected Ollama response format: {e}") from e


def _strip_markdown_json(text: str) -> str:
    import re

    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


def _parse_judge_response(raw: str, judge_name: str) -> SingleJudgeResult:
    clean = _strip_markdown_json(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Judge {judge_name}: response not valid JSON: {e}\nRaw: {raw[:200]}"
        ) from e

    raw_verdict = str(data.get("verdict", "satisfaisant")).strip().lower()
    if raw_verdict not in VERDICTS:
        raw_verdict = "satisfaisant"

    raw_score = data.get("score", SCORES[raw_verdict])
    try:
        score = int(raw_score)
    except (TypeError, ValueError):
        score = SCORES[raw_verdict]
    score = max(1, min(3, score))

    justification = str(data.get("justification", "")).strip()

    return SingleJudgeResult(
        judge_name=judge_name,
        verdict=raw_verdict,
        score=score,
        justification=justification,
    )
