"""Utilitaires de nettoyage JSON pour les sorties LLM.

Les LLM encapsulent souvent leur sortie JSON dans des blocs Markdown
(````json…````) et émettent parfois des caractères de contrôle nus à
l'intérieur des valeurs de chaînes, ce qui rend le JSON invalide.

``strip_markdown_json`` est l'unique point d'entrée : elle retire l'enveloppe
Markdown si présente, puis délègue à ``_fix_json_strings`` pour normaliser
les newlines et tabulations littéraux à l'intérieur des chaînes JSON.

Usage typique ::

    from r6_navigator.services.llm_json import strip_markdown_json

    clean = strip_markdown_json(raw)
    data = json.loads(clean)
"""

from __future__ import annotations

import re


def _fix_json_strings(text: str) -> str:
    """Échappe les sauts de ligne et tabulations littéraux dans les valeurs JSON.

    Les LLM émettent parfois des retours à la ligne bruts à l'intérieur de
    chaînes JSON, ce qui rend le JSON invalide. Cette fonction parcourt le texte
    caractère par caractère et remplace les ``\\n`` / ``\\r`` / ``\\t`` nus
    trouvés à l'intérieur d'une chaîne (entre guillemets non échappés) par
    leurs équivalents échappés. Les ``\\r`` nus sont silencieusement supprimés.

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
            pass  # supprime les carriage-returns nus dans les chaînes
        elif in_string and ch == "\t":
            result.append("\\t")
        else:
            result.append(ch)
    return "".join(result)


def strip_markdown_json(text: str) -> str:
    """Supprime l'enveloppe Markdown ``` optionnelle et corrige les newlines nus.

    Certains modèles encapsulent leur réponse JSON dans un bloc
    ````json…```` ou ````…````. Cette fonction extrait le contenu brut si
    ce bloc est présent, puis délègue à ``_fix_json_strings`` pour
    normaliser les caractères de contrôle à l'intérieur des chaînes.

    Args:
        text: Réponse brute du LLM, avec ou sans bloc Markdown.

    Returns:
        Texte JSON nettoyé prêt pour ``json.loads()``.
    """
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    return _fix_json_strings(text)
