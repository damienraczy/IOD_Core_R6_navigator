"""Chargement des fichiers de prompts LLM.

Les prompts sont stockés dans ce dossier sous forme de fichiers .txt.
Les variables sont marquées {variable_name} et remplacées par substitution
littérale, ce qui évite tout conflit avec les accolades présentes dans les
valeurs dynamiques (JSON, Markdown, etc.).
"""

from __future__ import annotations

from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


def load_prompt(name: str, **kwargs: object) -> str:
    """Charge un fichier de prompt et substitue les variables.

    Args:
        name: Nom du fichier sans extension (ex. ``"generate_fiche"``).
        **kwargs: Variables à substituer dans le template (``{variable_name}``).

    Returns:
        Prompt prêt à être envoyé au LLM.

    Raises:
        FileNotFoundError: Si le fichier ``name.txt`` n'existe pas.
    """
    path = _PROMPT_DIR / f"{name}.txt"
    template = path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))
    return template
