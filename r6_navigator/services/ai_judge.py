"""Évaluation des contenus R6 par trois juges LLM indépendants en parallèle.

Trois critères sont évalués simultanément pour chaque section (fiche, questions,
coaching) :

* **Axiomes R6** — respect de l'ontologie (niveaux, axes, pôles, isomorphisme).
* **Halliday** — transitivité grammaticale et registre linguistique appropriés au
  niveau (I / O / S).
* **Cohérence niveau/pôle** — alignement sémantique avec le niveau et le pôle
  de la capacité évaluée.

Chaque juge appelle Ollama (modèle ``model_judge`` de ``params.yml``) avec un
prompt spécialisé et retourne un verdict parmi ``pas_bon``, ``satisfaisant``,
``tres_bon``. Les trois appels sont lancés simultanément via ``threading.Thread``
pour minimiser la latence totale.

Le verdict agrégé est déterminé par majorité simple ; en cas d'égalité parfaite
(trois verdicts différents), le pire des trois est retenu par conservatisme.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

import yaml

from r6_navigator.services.ai_generate import _load_halliday_context, _load_system_prompt
from r6_navigator.services.prompt import load_prompt

_PACKAGE_DIR = Path(__file__).parent.parent  # r6_navigator/
_PROJECT_ROOT = _PACKAGE_DIR.parent  # project root (params.yml)


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------

# Verdicts ordonnés du moins bon au meilleur (utilisés pour la comparaison).
VERDICTS = ("pas_bon", "satisfaisant", "tres_bon")

# Correspondance verdict → score numérique pour le calcul de la moyenne agrégée.
SCORES = {
    "pas_bon": 1,
    "satisfaisant": 2,
    "tres_bon": 3,
}


@dataclass
class SingleJudgeResult:
    """Résultat d'un juge LLM individuel.

    Attributes:
        judge_name: Identifiant du juge (``"axioms_r6"``, ``"halliday"``
            ou ``"coherence"``).
        verdict: Verdict parmi ``"pas_bon"``, ``"satisfaisant"``,
            ``"tres_bon"``.
        score: Valeur numérique correspondant au verdict (1, 2 ou 3).
        justification: Explication textuelle fournie par le LLM.
        error: Message d'erreur si l'appel Ollama a échoué, sinon ``None``.
    """

    judge_name: str
    verdict: str
    score: int
    justification: str
    error: str | None = None


@dataclass
class JudgeResults:
    """Résultats agrégés des trois juges LLM pour une évaluation complète.

    Attributes:
        judge_axioms: Résultat du juge vérifiant les axiomes R6.
        judge_halliday: Résultat du juge vérifiant la transitivité Halliday.
        judge_coherence: Résultat du juge vérifiant la cohérence niveau/pôle.
        aggregate_verdict: Verdict de majorité (pire des trois si égalité
            parfaite).
        aggregate_score: Moyenne arithmétique des trois scores (entre 1.0
            et 3.0).
    """

    judge_axioms: SingleJudgeResult
    judge_halliday: SingleJudgeResult
    judge_coherence: SingleJudgeResult
    aggregate_verdict: str
    aggregate_score: float


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def judge_questions(content: dict, capacity_id: str, lang: str) -> JudgeResults:
    """Évalue les questions STAR et items observables via 3 juges LLM en parallèle.

    Args:
        content: Dictionnaire avec les clés ``questions`` (liste de textes) et
            ``observable_items`` (dict catégorie → liste de textes).
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        lang: Langue active (``"fr"`` ou ``"en"``).

    Returns:
        JudgeResults agrégés des 3 juges.
    """
    return _run_judges(
        content=content,
        capacity_id=capacity_id,
        lang=lang,
        prompt_names=("judge_questions_axioms", "judge_questions_halliday", "judge_questions_coherence"),
    )


def judge_coaching(content: dict, capacity_id: str, lang: str) -> JudgeResults:
    """Évalue le contenu coaching via 3 juges LLM en parallèle.

    Args:
        content: Dictionnaire avec les clés ``reflection_themes``,
            ``intervention_levers``, ``recommended_missions``.
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        lang: Langue active (``"fr"`` ou ``"en"``).

    Returns:
        JudgeResults agrégés des 3 juges.
    """
    return _run_judges(
        content=content,
        capacity_id=capacity_id,
        lang=lang,
        prompt_names=("judge_coaching_axioms", "judge_coaching_halliday", "judge_coaching_coherence"),
    )


def judge_fiche(content: dict, capacity_id: str, lang: str) -> JudgeResults:
    """Évalue une fiche R6 via 3 juges LLM tournant en parallèle.

    Args:
        content: Dictionnaire des champs de la fiche avec les clés
            ``label``, ``definition``, ``central_function``,
            ``risk_insufficient``, ``risk_excessive``.
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        lang: Langue active (``"fr"`` ou ``"en"``).

    Returns:
        JudgeResults agrégés des 3 juges.
    """
    return _run_judges(
        content=content,
        capacity_id=capacity_id,
        lang=lang,
        prompt_names=("judge_fiche_axioms", "judge_fiche_halliday", "judge_fiche_coherence"),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_judges(
    content: dict,
    capacity_id: str,
    lang: str,
    prompt_names: tuple[str, str, str],
) -> JudgeResults:
    """Logique commune aux trois fonctions publiques de jugement.

    Charge la configuration, construit les 3 prompts à partir des fichiers
    indiqués dans ``prompt_names``, lance les appels Ollama en parallèle et
    agrège les résultats.

    Args:
        content: Dictionnaire du contenu à évaluer (sérialisé en JSON pour le LLM).
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        lang: Langue active (``"fr"`` ou ``"en"``).
        prompt_names: Triplet (axioms_prompt, halliday_prompt, coherence_prompt)
            correspondant aux noms des fichiers .txt dans services/prompt/.

    Returns:
        JudgeResults agrégés des 3 juges.
    """
    params = _load_params()
    ollama_cfg = params["ollama"]
    url = ollama_cfg["url"]
    model = ollama_cfg["model_judge"]
    timeout = int(ollama_cfg.get("timeout", 60))
    system_prompt = _load_system_prompt()

    axioms = _load_axioms()
    ontology = axioms["r6_ontology"]
    level_code = capacity_id[0]
    axis_number = capacity_id[1]
    pole_code = capacity_id[2]
    level_info = ontology["levels"][level_code]
    axis_info = ontology["axes"][int(axis_number)]
    pole_info = ontology["poles"][pole_code]
    principles = ontology["fundamental_principles"]

    lang_name = "French" if lang == "fr" else "US English"
    content_str = json.dumps(content, ensure_ascii=False, indent=2)

    # ---- Variables communes injectées dans les 3 prompts -------------------

    axioms_context = "\n".join(
        f"- {k}: {v}"
        for k, v in principles.items()
        if k != "linguistic_differentiation"
    )
    halliday_context = _load_halliday_context(level_code)

    common_vars = dict(
        axioms_context=axioms_context,
        halliday_context=halliday_context,
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
        content_str=content_str,
        lang_name=lang_name,
    )

    name_axioms, name_halliday, name_coherence = prompt_names
    prompt_axioms = load_prompt(name_axioms, **common_vars)
    prompt_halliday = load_prompt(name_halliday, **common_vars)
    prompt_coherence = load_prompt(name_coherence, **common_vars)

    # ---- Appels parallèles --------------------------------------------------

    judge_results: dict[str, SingleJudgeResult] = {}
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
            judge_results[judge_key] = result

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

    judge_axioms = judge_results["axioms"]
    judge_halliday = judge_results["halliday"]
    judge_coherence = judge_results["coherence"]

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


def _load_params() -> dict:
    """Charge et retourne la configuration Ollama depuis ``params.yml``.

    Returns:
        Dictionnaire YAML avec les clés ``ollama`` (url, model, model_judge,
        timeout) et ``reserve`` (notes sur les modèles alternatifs).

    Raises:
        FileNotFoundError: Si ``params.yml`` est absent de la racine projet.
    """
    params_path = _PROJECT_ROOT / "params.yml"
    with open(params_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_axioms() -> dict:
    """Charge l'ontologie R6 depuis ``axioms.yml``.

    Returns:
        Dictionnaire YAML avec la clé ``r6_ontology`` contenant niveaux,
        axes, pôles et principes fondamentaux du modèle R6.

    Raises:
        FileNotFoundError: Si ``axioms.yml`` est absent du package.
    """
    axioms_path = _PACKAGE_DIR / "axioms.yml"
    with open(axioms_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _call_ollama(url: str, model: str, system: str, prompt: str, timeout: int) -> str:
    """Appelle l'API Ollama en mode génération non streamée et retourne la réponse brute.

    Contrairement à la version dans ``ai_generate``, cette implémentation n'effectue
    pas de nouvelle tentative : les trois juges tournant en parallèle, une défaillance
    est capturée localement par ``run_judge`` et propagée dans ``SingleJudgeResult.error``.

    Args:
        url: URL de base du serveur Ollama (ex. ``"http://localhost:11434"``).
        model: Nom du modèle juge à utiliser (ex. ``"kimi-k2-thinking:cloud"``).
        system: Prompt système décrivant le rôle et les règles du LLM.
        prompt: Prompt utilisateur contenant le contenu à évaluer.
        timeout: Délai maximum en secondes avant abandon de la requête HTTP.

    Returns:
        Chaîne brute retournée par Ollama dans le champ ``response``.

    Raises:
        RuntimeError: Si Ollama est inaccessible ou la réponse est malformée.
    """
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


def _fix_json_strings(text: str) -> str:
    """Échappe les sauts de ligne et tabulations littéraux dans les valeurs JSON.

    Même logique que dans ``ai_generate._fix_json_strings`` : parcours
    caractère par caractère pour repérer les séquences nues à l'intérieur
    des chaînes JSON et les remplacer par leurs équivalents échappés.

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
            pass
        elif in_string and ch == "\t":
            result.append("\\t")
        else:
            result.append(ch)
    return "".join(result)


def _strip_markdown_json(text: str) -> str:
    """Supprime l'enveloppe Markdown ``` optionnelle et corrige les newlines nus.

    Args:
        text: Réponse brute du LLM, avec ou sans bloc ```json…```.

    Returns:
        Texte JSON nettoyé prêt pour ``json.loads()``.
    """
    import re

    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    return _fix_json_strings(text)


def _parse_judge_response(raw: str, judge_name: str) -> SingleJudgeResult:
    """Parse la réponse JSON d'un juge LLM en ``SingleJudgeResult``.

    Applique des règles de tolérance : verdict inconnu → ``"satisfaisant"``,
    score non numérique → score correspondant au verdict, score hors [1, 3] →
    borné. Cela évite qu'un modèle mal cadré ne fasse planter l'agrégation.

    Args:
        raw: Chaîne JSON brute retournée par Ollama pour ce juge.
        judge_name: Identifiant du juge (utilisé pour le message d'erreur).

    Returns:
        ``SingleJudgeResult`` avec verdict, score et justification extraits.

    Raises:
        RuntimeError: Si la réponse n'est pas du JSON valide.
    """
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
