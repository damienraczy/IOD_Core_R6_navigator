"""Analyse de verbatims d'entretien et génération de rapports de mission via Ollama.

Ce module expose deux fonctions publiques :

* ``analyze_verbatim``        — extrait et interprète les passages significatifs
                                d'un verbatim d'entretien en les rattachant aux
                                capacités R6 et à un niveau de maturité.
* ``generate_mission_report`` — synthétise l'ensemble des interprétations validées
                                d'une mission en un rapport de diagnostic R6 structuré.

Pipeline commun :
    1. Chargement de la configuration Ollama depuis ``params.yml``.
    2. Construction du prompt via ``load_prompt()`` (substitution sécurisée —
       jamais ``str.format()`` sur des fichiers contenant des accolades JSON).
    3. Appel HTTP à l'API Ollama non-streamée (``/api/generate``) avec retry.
    4. Parsing de la réponse JSON + normalisation vers les types de retour publics.

Les détails du pattern de retry et de l'appel Ollama sont identiques à
``ai_generate.py`` pour garantir la cohérence.

Logging :
    Le module utilise le logger ``r6_navigator.ai_analyze``.
    CRITICAL  — fichier de configuration ou prompt système manquant (bloquant).
    ERROR     — toutes les tentatives Ollama ont échoué.
    WARNING   — dégradation non bloquante (échelle de maturité absente,
                fallback de parsing JSON activé, clé de rapport manquante).
    INFO      — démarrage et succès des opérations principales.
    DEBUG     — détails de retry et de parsing interne.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml

from r6_navigator.services.llm_json import strip_markdown_json
from r6_navigator.services.prompt import load_prompt

# ────────────────────────────────────────────────
# Logger du module
# ────────────────────────────────────────────────

log = logging.getLogger("r6_navigator.ai_analyze")

# ────────────────────────────────────────────────
# Chemins résolus une seule fois au chargement du module
# ────────────────────────────────────────────────

_PACKAGE_DIR = Path(__file__).parent.parent  # r6_navigator/
_PROJECT_ROOT = _PACKAGE_DIR.parent          # racine du projet (contient params.yml)

# ────────────────────────────────────────────────
# Constantes de retry Ollama
# ────────────────────────────────────────────────

_OLLAMA_MAX_RETRIES = 3   # Nombre maximum de tentatives avant d'abandonner.
_OLLAMA_RETRY_DELAY = 2   # Délai en secondes entre deux tentatives successives.

# Correspondance code court → nom complet du niveau R6 (injecté dans les prompts).
_LEVEL_NAMES = {
    "S": "Strategic",
    "O": "Organizational",
    "I": "Individual",
}


# ────────────────────────────────────────────────
# Modèle de données public
# ────────────────────────────────────────────────

@dataclass
class AnalyzedExtract:
    """Un extrait de verbatim annoté avec son interprétation R6.

    Chaque instance correspond à un passage identifié par le LLM comme
    significatif vis-à-vis du modèle R6 : il est rattaché à une capacité,
    évalué sur l'échelle de maturité du niveau concerné, et accompagné
    d'une interprétation analytique en langage naturel.

    Attributes:
        text: Citation directe ou condensé du passage issu du verbatim.
        tag: Code court de la capacité R6 identifiée (ex. ``"I3a"``), ou
            ``None`` si aucune capacité n'a pu être associée.
        capacity_id: Identifiant de la capacité — généralement identique à
            ``tag`` ; les deux champs coexistent car le LLM peut les retourner
            sous l'un ou l'autre nom de clé JSON.
        maturity_level: Évaluation qualitative du niveau de maturité observable
            dans l'extrait (ex. ``"insuffisant"``, ``"confirmé"``, ``"expert"``).
        confidence: Score de confiance de l'interprétation, entre 0.0 et 1.0.
            Fourni par le LLM ; indicatif, non calibré statistiquement.
        interpretation: Analyse textuelle de l'extrait (2-4 phrases) expliquant
            le lien avec la capacité et justifiant le niveau de maturité attribué.
    """

    text: str
    tag: str | None
    capacity_id: str | None
    maturity_level: str
    confidence: float
    interpretation: str


# ────────────────────────────────────────────────
# API publique
# ────────────────────────────────────────────────

def analyze_verbatim(
    verbatim_text: str,
    interview_info: dict,
    lang: str = "fr",
) -> list[AnalyzedExtract]:
    """Analyse un verbatim d'entretien et retourne les extraits significatifs.

    Construit un prompt contextualisé (sujet, rôle, niveau R6, date, échelle
    de maturité correspondante) puis interroge Ollama pour identifier et
    interpréter les passages du verbatim pertinents vis-à-vis du modèle R6.

    Le niveau ``level_code`` détermine l'échelle de maturité injectée :
        - ``"I"`` → EQF Proficiency Levels (individuel)
        - ``"O"`` → O6 Maturity Levels (organisationnel)
        - ``"S"`` → S6 Maturity Levels (stratégique)

    Args:
        verbatim_text: Texte brut du verbatim d'entretien à analyser.
        interview_info: Dictionnaire de métadonnées de l'entretien. Clés
            reconnues : ``subject_name``, ``subject_role``, ``level_code``,
            ``interview_date``. Toutes sont optionnelles ; ``level_code``
            vaut ``"I"`` par défaut si absent.
        lang: Langue de l'analyse (``"fr"`` ou ``"en"``). Transmis au prompt
            mais le modèle peut répondre dans sa propre langue par défaut.

    Returns:
        Liste d'``AnalyzedExtract`` dans l'ordre retourné par le LLM
        (généralement trié par pertinence décroissante).

    Raises:
        RuntimeError: Si la configuration est invalide, si Ollama est
            inaccessible après ``_OLLAMA_MAX_RETRIES`` tentatives, ou si la
            réponse ne contient pas de JSON parseable.
    """
    log.info("Début d'analyse du verbatim (level_code=%s, lang=%s)",
             interview_info.get("level_code", "I"), lang)

    params = _load_params()
    ollama_cfg = _extract_ollama_cfg(params)
    system_prompt = _load_system_prompt()

    # Résolution du niveau : on récupère le code court et on dérive le nom
    # complet pour l'injection dans le prompt (ex. "I" → "Individual").
    level_code = interview_info.get("level_code", "I")
    maturity_scale = _load_maturity_scale(level_code)
    level_name = _LEVEL_NAMES.get(level_code, level_code)

    # Construction sécurisée du prompt : load_prompt() fait une substitution
    # littérale clé par clé, sans risque de collision avec les accolades JSON
    # présentes dans le fichier de prompt.
    user_prompt = load_prompt(
        "analyze_verbatim",
        subject_name=interview_info.get("subject_name", "N/A"),
        subject_role=interview_info.get("subject_role", "N/A"),
        level_code=level_code,
        level_name=level_name,
        interview_date=interview_info.get("interview_date", "N/A"),
        maturity_scale=maturity_scale,
        verbatim_text=verbatim_text,
    )

    raw = _call_ollama(
        ollama_cfg["url"], ollama_cfg["model"],
        system_prompt, user_prompt, ollama_cfg["timeout"],
    )
    extracts = _parse_extracts_response(raw)
    log.info("Analyse terminée : %d extrait(s) identifié(s)", len(extracts))
    return extracts


def generate_mission_report(
    mission_id: int,
    session_factory,
    lang: str = "fr",
) -> str:
    """Génère un rapport de diagnostic R6 pour une mission complète.

    Récupère en base toutes les interprétations de statut ``validated`` ou
    ``corrected`` pour la mission, les regroupe par niveau (S / O / I), puis
    appelle Ollama pour produire un rapport structuré en Markdown.

    Seules les interprétations validées ou corrigées sont incluses : les
    entrées ``pending`` et ``rejected`` sont ignorées, ce qui garantit que
    le rapport reflète uniquement les analyses validées par le consultant.

    Args:
        mission_id: Identifiant entier de la mission en base de données.
        session_factory: Factory de session SQLAlchemy (sessionmaker) —
            injectée depuis ``MissionApp`` pour éviter toute dépendance
            circulaire entre modules de services et UI.
        lang: Langue du rapport généré (``"fr"`` ou ``"en"``).

    Returns:
        Texte du rapport au format Markdown, prêt à l'affichage ou à
        l'export DOCX via ``export_docx.export_mission_report()``.

    Raises:
        ValueError: Si ``mission_id`` ne correspond à aucune mission en base.
        RuntimeError: Si la configuration est invalide, si Ollama est
            inaccessible ou retourne une réponse non exploitable après
            ``_OLLAMA_MAX_RETRIES`` tentatives.
    """
    # Import local pour éviter les imports circulaires au niveau module.
    from r6_navigator.services.crud_mission import (
        get_all_mission_interpretations,
        get_mission,
    )

    log.info("Début de génération du rapport (mission_id=%d, lang=%s)", mission_id, lang)

    # Phase 1 : lecture en base — session fermée dès que les données sont
    # extraites pour ne pas maintenir une connexion ouverte pendant l'appel LLM.
    with session_factory() as session:
        mission = get_mission(session, mission_id)
        if mission is None:
            log.error("Mission introuvable en base (mission_id=%d)", mission_id)
            raise ValueError(f"Mission {mission_id} not found")

        mission_name = mission.name
        client = mission.client or "N/A"
        consultant = mission.consultant or "N/A"
        interview_count = len(mission.interviews)

        # Toutes les interprétations de la mission, tous statuts confondus.
        interpretations = get_all_mission_interpretations(session, mission_id)

        # On ne retient que les interprétations actées par le consultant.
        validated = [i for i in interpretations if i.status in ("validated", "corrected")]

    total = len(interpretations)
    kept = len(validated)
    log.info(
        "Mission '%s' : %d interprétation(s) dont %d retenue(s) (validated/corrected)",
        mission_name, total, kept,
    )
    if kept == 0:
        log.warning(
            "Aucune interprétation validée pour la mission '%s' (id=%d) — "
            "le rapport sera généré sur données vides.",
            mission_name, mission_id,
        )

    # Phase 2 : regroupement des interprétations par niveau R6 (S / O / I).
    # Le premier caractère du capacity_id encode le niveau (ex. "S2b" → "S").
    # Les capacity_id absents ou inconnus sont rattachés au niveau "I" par défaut.
    by_level: dict[str, list[str]] = {"S": [], "O": [], "I": []}
    for interp in validated:
        cap_id = interp.capacity_id or ""
        if cap_id and cap_id[0] in ("S", "O", "I"):
            level = cap_id[0]
        else:
            log.warning(
                "Interprétation id=%s : capacity_id=%r non reconnu, rattaché au niveau 'I'.",
                getattr(interp, "id", "?"), cap_id or None,
            )
            level = "I"

        # Format "[CapacityID — maturité] Texte" pour permettre au LLM de
        # croiser facilement capacité et maturité dans le prompt.
        entry = f"[{cap_id}] {interp.text}"
        if interp.maturity_level:
            entry = f"[{cap_id} — {interp.maturity_level}] {interp.text}"
        by_level[level].append(entry)

    def _fmt(items: list[str]) -> str:
        """Formate une liste d'interprétations en liste Markdown à puces.

        Retourne un message de substitution bilingue si la liste est vide,
        afin d'éviter une section vierge dans le prompt (ce qui pourrait
        induire le LLM en erreur sur la complétude des données).

        Args:
            items: Textes d'interprétations pour un niveau R6 donné.

        Returns:
            Chaîne Markdown formatée, ou message d'absence.
        """
        if not items:
            return "(aucune interprétation validée)" if lang == "fr" else "(no validated interpretation)"
        return "\n".join(f"- {item}" for item in items)

    # Phase 3 : appel Ollama — même pattern que analyze_verbatim.
    params = _load_params()
    ollama_cfg = _extract_ollama_cfg(params)
    system_prompt = _load_system_prompt()

    # Nom complet de la langue injecté dans le prompt pour guider le LLM
    # vers la bonne langue de rédaction du rapport.
    lang_name = "French" if lang == "fr" else "US English"
    user_prompt = load_prompt(
        "generate_mission_report",
        mission_name=mission_name,
        client=client,
        consultant=consultant,
        interview_count=str(interview_count),
        lang_name=lang_name,
        interpretations_S=_fmt(by_level["S"]),
        interpretations_O=_fmt(by_level["O"]),
        interpretations_I=_fmt(by_level["I"]),
    )

    raw = _call_ollama(
        ollama_cfg["url"], ollama_cfg["model"],
        system_prompt, user_prompt, ollama_cfg["timeout"],
    )
    report = _parse_report_response(raw)
    log.info("Rapport généré avec succès pour la mission '%s' (id=%d)", mission_name, mission_id)
    return report


# ────────────────────────────────────────────────
# Helpers internes
# ────────────────────────────────────────────────

def _load_maturity_scale(level_code: str) -> str:
    """Charge l'échelle de maturité Markdown pour un niveau R6 donné.

    Les fichiers d'échelle (format court) sont stockés dans
    ``r6_navigator/maturity_scales/`` et injectés verbatim dans le prompt
    d'analyse pour ancrer l'évaluation du LLM sur des critères explicites.

    En cas de fichier absent ou de code inconnu, une chaîne vide est retournée
    (dégradation acceptée) et un WARNING est émis dans les logs pour alerter
    l'opérateur : l'analyse peut continuer, mais l'évaluation de maturité
    sera moins précise.

    Args:
        level_code: Code court du niveau R6 — ``"I"`` (Individuel),
            ``"O"`` (Organisationnel) ou ``"S"`` (Stratégique).

    Returns:
        Contenu brut du fichier Markdown de l'échelle correspondante,
        ou chaîne vide si le code est inconnu ou si le fichier est absent.
    """
    scales_dir = _PACKAGE_DIR / "maturity_scales"

    candidates = {
        "I": "I6_EQF_Proficiency_Levels_short.md",
        "O": "O6_Maturity_Levels_short.md",
        "S": "S6_Maturity_Levels_short.md",
    }
    filename = candidates.get(level_code)
    if filename is None:
        log.warning(
            "Code de niveau R6 inconnu : %r — aucune échelle de maturité injectée. "
            "Codes valides : %s.",
            level_code, ", ".join(candidates),
        )
        return ""

    path = scales_dir / filename
    try:
        content = path.read_text(encoding="utf-8")
        log.debug("Échelle de maturité chargée : %s", path)
        return content
    except FileNotFoundError:
        log.warning(
            "Fichier d'échelle de maturité introuvable : %s — "
            "l'analyse continuera sans référentiel de maturité explicite. "
            "Vérifiez que le répertoire 'maturity_scales/' est complet.",
            path,
        )
        return ""


def _load_params() -> dict:
    """Charge la configuration Ollama depuis ``params.yml`` à la racine du projet.

    Le fichier est relu à chaque appel pour refléter d'éventuelles modifications
    à chaud (changement de modèle, de timeout, etc.) sans redémarrer l'application.

    Returns:
        Dictionnaire Python issu du YAML, avec au minimum la clé ``"ollama"``
        contenant ``url``, ``model`` et ``timeout``.

    Raises:
        RuntimeError: Si ``params.yml`` est absent, illisible ou malformé.
            L'exception d'origine est enchaînée pour faciliter le diagnostic.
    """
    params_path = _PROJECT_ROOT / "params.yml"
    try:
        with open(params_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        log.debug("Configuration chargée depuis %s", params_path)
        return data
    except FileNotFoundError:
        log.critical(
            "Fichier de configuration introuvable : %s — "
            "impossible de démarrer l'analyse. "
            "Créez ou restaurez params.yml à la racine du projet.",
            params_path,
        )
        raise RuntimeError(f"params.yml introuvable : {params_path}") from None
    except yaml.YAMLError as exc:
        log.critical(
            "Impossible de parser %s : %s — "
            "vérifiez la syntaxe YAML du fichier de configuration.",
            params_path, exc,
        )
        raise RuntimeError(f"params.yml malformé : {exc}") from exc


def _extract_ollama_cfg(params: dict) -> dict:
    """Valide et extrait le sous-dictionnaire de configuration Ollama.

    Centralise la vérification des clés obligatoires afin de produire un
    message d'erreur explicite plutôt qu'un ``KeyError`` non contextualisé.

    Args:
        params: Dictionnaire complet issu de ``_load_params()``.

    Returns:
        Dictionnaire avec les clés ``url``, ``model`` et ``timeout`` (int).

    Raises:
        RuntimeError: Si la section ``ollama`` est absente ou si l'une des
            clés ``url`` ou ``model`` manque.
    """
    if "ollama" not in params:
        log.critical(
            "La section 'ollama' est absente de params.yml — "
            "impossible de configurer l'accès au LLM."
        )
        raise RuntimeError("Section 'ollama' manquante dans params.yml")

    cfg = params["ollama"]
    missing = [k for k in ("url", "model") if not cfg.get(k)]
    if missing:
        log.critical(
            "Clé(s) obligatoire(s) manquante(s) dans params.yml[ollama] : %s",
            ", ".join(missing),
        )
        raise RuntimeError(
            f"params.yml[ollama] : clé(s) manquante(s) : {', '.join(missing)}"
        )

    return {
        "url": cfg["url"],
        "model": cfg["model"],
        "timeout": int(cfg.get("timeout", 120)),
    }


def _load_system_prompt() -> str:
    """Charge le prompt système R6/Halliday depuis ``services/prompt/system_01.txt``.

    Le prompt système est commun à toutes les fonctions d'analyse et de
    génération : il définit le rôle d'expert R6/Halliday du LLM. Il est lu
    depuis le disque à chaque appel pour permettre des modifications à chaud.

    Returns:
        Contenu textuel brut du fichier ``system_01.txt``.

    Raises:
        RuntimeError: Si le fichier est absent — erreur critique car le LLM
            ne peut pas fonctionner sans prompt système.
    """
    path = Path(__file__).parent / "prompt" / "system_01.txt"
    try:
        content = path.read_text(encoding="utf-8")
        log.debug("Prompt système chargé depuis %s", path)
        return content
    except FileNotFoundError:
        log.critical(
            "Prompt système introuvable : %s — "
            "toute génération ou analyse LLM est impossible. "
            "Vérifiez l'intégrité de l'installation (répertoire prompt/).",
            path,
        )
        raise RuntimeError(f"Prompt système introuvable : {path}") from None


def _call_ollama(url: str, model: str, system: str, prompt: str, timeout: int) -> str:
    """Appelle l'API Ollama (non streamée, format JSON) avec mécanisme de retry.

    L'API ``/api/generate`` d'Ollama est invoquée en mode non streamé
    (``stream: false``) avec ``format: "json"`` pour contraindre le modèle
    à retourner du JSON valide. La réponse complète est lue en une seule fois.

    En cas d'erreur réseau (``URLError``) ou de réponse mal formée
    (``KeyError``, ``JSONDecodeError``), l'appel est réessayé jusqu'à
    ``_OLLAMA_MAX_RETRIES`` fois avec un délai de ``_OLLAMA_RETRY_DELAY``
    secondes entre chaque tentative. Chaque échec intermédiaire est loggué
    en WARNING ; l'échec définitif est loggué en ERROR avant propagation.

    Args:
        url: URL de base du serveur Ollama (ex. ``"http://localhost:11434"``).
            Le trailing slash est normalisé avant concaténation.
        model: Identifiant du modèle Ollama à utiliser (ex. ``"mistral:7b"``).
        system: Texte du prompt système injecté dans le champ ``"system"``
            du payload Ollama.
        prompt: Texte du prompt utilisateur injecté dans le champ ``"prompt"``.
        timeout: Délai maximum en secondes pour la requête HTTP (``urlopen``).

    Returns:
        Valeur du champ ``"response"`` de la réponse JSON d'Ollama — chaîne
        brute contenant le JSON généré par le modèle.

    Raises:
        RuntimeError: Si toutes les tentatives ont échoué, encapsulant la
            dernière erreur (réseau ou format de réponse inattendu).
    """
    # Sérialisation unique du payload : évite de re-encoder à chaque tentative.
    payload = json.dumps(
        {
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,    # Réponse complète en une seule fois.
            "format": "json",   # Force le modèle à produire du JSON valide.
        }
    ).encode("utf-8")

    # Normalisation de l'URL : supprime le trailing slash éventuel avant
    # d'ajouter le chemin de l'endpoint.
    endpoint = f"{url.rstrip('/')}/api/generate"

    last_exc: Exception | None = None
    for attempt in range(1, _OLLAMA_MAX_RETRIES + 1):
        log.debug("Appel Ollama (tentative %d/%d) → %s [model=%s]",
                  attempt, _OLLAMA_MAX_RETRIES, endpoint, model)
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
            log.warning(
                "Tentative %d/%d : Ollama inaccessible (%s). %s",
                attempt, _OLLAMA_MAX_RETRIES, url,
                f"Nouvelle tentative dans {_OLLAMA_RETRY_DELAY}s."
                if attempt < _OLLAMA_MAX_RETRIES else "Abandon.",
            )
        except KeyError:
            last_exc = RuntimeError(
                f"Champ 'response' absent de la réponse Ollama (model={model})"
            )
            log.warning(
                "Tentative %d/%d : réponse Ollama sans champ 'response'. %s",
                attempt, _OLLAMA_MAX_RETRIES,
                f"Nouvelle tentative dans {_OLLAMA_RETRY_DELAY}s."
                if attempt < _OLLAMA_MAX_RETRIES else "Abandon.",
            )
        except json.JSONDecodeError as e:
            last_exc = RuntimeError(f"Réponse Ollama non JSON : {e}")
            log.warning(
                "Tentative %d/%d : réponse Ollama non parseable en JSON (%s). %s",
                attempt, _OLLAMA_MAX_RETRIES, e,
                f"Nouvelle tentative dans {_OLLAMA_RETRY_DELAY}s."
                if attempt < _OLLAMA_MAX_RETRIES else "Abandon.",
            )

        if attempt < _OLLAMA_MAX_RETRIES:
            time.sleep(_OLLAMA_RETRY_DELAY)

    log.error(
        "Toutes les tentatives Ollama ont échoué (%d/%d) sur %s — %s",
        _OLLAMA_MAX_RETRIES, _OLLAMA_MAX_RETRIES, endpoint, last_exc,
    )
    raise last_exc  # type: ignore[misc]


def _parse_extracts_response(raw: str) -> list[AnalyzedExtract]:
    """Parse la réponse JSON d'Ollama en liste d'``AnalyzedExtract``.

    Le parsing est volontairement tolérant pour absorber les variations de
    format entre modèles. Chaque fallback activé est loggué en WARNING afin
    que les réponses anormales soient visibles sans être bloquantes :

    1. Tentative de parse direct de ``raw`` comme tableau JSON.
    2. Si échec, recherche par regex d'un sous-tableau JSON dans la chaîne
       (utile quand le modèle ajoute du texte avant ou après le JSON).
    3. Si ``raw`` est un objet JSON (dict), on cherche un tableau imbriqué
       sous les clés ``"extracts"``, ``"results"`` ou ``"items"``.

    Pour chaque élément du tableau, ``tag`` et ``capacity_id`` sont
    réconciliés : certains modèles utilisent l'un ou l'autre nom de clé,
    on accepte les deux et on se rabat sur l'autre si l'un est absent.

    Args:
        raw: Chaîne brute retournée par le champ ``"response"`` d'Ollama.

    Returns:
        Liste d'``AnalyzedExtract`` construite depuis les éléments JSON.
        Retourne une liste vide si le tableau JSON est vide.

    Raises:
        RuntimeError: Si ni le parse direct ni la recherche regex ne
            permettent d'extraire un tableau JSON valide, ou si le résultat
            n'est pas une liste après tentatives de dépliage.
    """
    clean = strip_markdown_json(raw)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        # Fallback regex : certains modèles entourent le JSON de texte explicatif.
        # On tente de localiser le premier tableau JSON dans la réponse nettoyée.
        log.warning(
            "Réponse Ollama non JSON à la racine — tentative d'extraction par regex. "
            "Début de la réponse : %.120s…",
            clean,
        )
        match = re.search(r"\[.*\]", clean, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                log.warning("Tableau JSON extrait par regex — vérifiez la qualité du modèle.")
            except json.JSONDecodeError as e:
                log.error(
                    "Impossible de parser le tableau JSON trouvé par regex : %s. "
                    "Réponse (120 premiers caractères) : %.120s",
                    e, clean,
                )
                raise RuntimeError(
                    f"Cannot parse extracts response as JSON: {clean[:200]}"
                ) from e
        else:
            log.error(
                "Aucun tableau JSON trouvé dans la réponse Ollama. "
                "Réponse (120 premiers caractères) : %.120s",
                clean,
            )
            raise RuntimeError(f"Cannot parse extracts response as JSON: {clean[:200]}")

    if isinstance(data, dict):
        # Certains modèles encapsulent le tableau sous une clé racine.
        # On sonde les noms les plus courants et on "déplie" si trouvé.
        for key in ("extracts", "results", "items"):
            if key in data:
                log.warning(
                    "Réponse enveloppée dans un dict sous la clé '%s' — "
                    "le modèle ne respecte pas le format attendu (tableau direct).",
                    key,
                )
                data = data[key]
                break

    if not isinstance(data, list):
        log.error(
            "Structure JSON inattendue : attendu list, obtenu %s. "
            "Réponse (120 premiers caractères) : %.120s",
            type(data).__name__, raw,
        )
        raise RuntimeError(f"Expected JSON array, got: {type(data)}")

    results = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            log.warning("Élément %d ignoré : type inattendu %s (attendu dict).", idx, type(item).__name__)
            continue
        # Réconciliation tag / capacity_id : si le modèle n'en fournit qu'un,
        # on utilise l'autre comme valeur de repli pour garantir la cohérence
        # des deux champs dans AnalyzedExtract.
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
    """Parse la réponse JSON d'Ollama pour extraire le texte du rapport.

    Le LLM est invité à retourner un objet JSON avec une clé ``"report"``
    contenant le Markdown. Chaque dégradation est loggée en WARNING afin
    que les réponses anormales soient traçables sans bloquer l'utilisateur :

    * JSON invalide → ``raw`` retourné tel quel.
    * JSON valide mais clé ``"report"`` absente → ``raw`` retourné tel quel.

    Args:
        raw: Chaîne brute retournée par le champ ``"response"`` d'Ollama.

    Returns:
        Texte Markdown du rapport. Si le JSON est valide et contient la clé
        ``"report"``, sa valeur est retournée. Sinon, ``raw`` est retourné
        tel quel (dégradation gracieuse).
    """
    clean = strip_markdown_json(raw)
    try:
        data = json.loads(clean)
        if isinstance(data, dict):
            if "report" not in data:
                log.warning(
                    "Réponse JSON valide mais clé 'report' absente — "
                    "clés disponibles : %s. La réponse brute est utilisée.",
                    list(data.keys()),
                )
                return raw
            return str(data["report"])
        log.warning(
            "Réponse JSON parseable mais pas un objet dict (type=%s) — "
            "la réponse brute est utilisée.",
            type(data).__name__,
        )
        return str(data)
    except json.JSONDecodeError as e:
        log.warning(
            "Réponse Ollama non parseable en JSON pour le rapport (%s) — "
            "la réponse brute est utilisée. Début : %.120s…",
            e, clean,
        )
        return raw
