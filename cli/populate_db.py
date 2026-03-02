#!/usr/bin/env python3
"""CLI de peuplement de la base de données R6 Navigator via génération IA.

Parcourt toutes les capacités et génère — pour chaque langue demandée — les
contenus Fiche, Risques, Questions, Items observables et Coaching.

Usage:
    python cli/populate_db.py                        # complète les données manquantes (fr)
    python cli/populate_db.py --lang fr en           # complète en fr et en
    python cli/populate_db.py --full                 # regénère tout (fr)
    python cli/populate_db.py --full --lang fr en    # regénère tout en fr et en
    python cli/populate_db.py --capacity I1a S2b     # capacités spécifiques seulement
    python cli/populate_db.py --skip fiche coaching  # saute certaines sections
"""

from __future__ import annotations

import argparse
import sys
import textwrap
import time
from pathlib import Path

# ── Résolution du chemin vers le package r6_navigator ─────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from r6_navigator.db.database import get_engine, get_session_factory, init_db
from r6_navigator.navigator.services import crud
from r6_navigator.navigator.services.ai_generate import (
    generate_coaching,
    generate_fiche,
    generate_fiche_risque,
    generate_questions,
    generate_questions_items,
)

_DB_PATH = _ROOT / "r6_navigator.db"

# ── Sections disponibles ───────────────────────────────────────────────────────
_ALL_SECTIONS = ("fiche", "risque", "questions", "items", "coaching")


# ─────────────────────────────────────────────────────────────────────────────
# Détection des données manquantes
# ─────────────────────────────────────────────────────────────────────────────

def _fiche_is_missing(session_factory, capacity_id: str, lang: str) -> bool:
    """Retourne True si la fiche est absente ou incomplète (définition vide)."""
    with session_factory() as session:
        trans = crud.get_capacity_translation(session, capacity_id, lang)
    return trans is None or not (trans.definition or "").strip()


def _risque_is_missing(session_factory, capacity_id: str, lang: str) -> bool:
    """Retourne True si les risques sont absents ou incomplets (risk_insufficient vide)."""
    with session_factory() as session:
        trans = crud.get_capacity_translation(session, capacity_id, lang)
    return trans is None or not (trans.risk_insufficient or "").strip()


def _questions_are_missing(session_factory, capacity_id: str) -> bool:
    """Retourne True si aucune question n'existe pour cette capacité."""
    with session_factory() as session:
        return len(crud.get_questions(session, capacity_id)) == 0


def _items_are_missing(session_factory, capacity_id: str) -> bool:
    """Retourne True si aucun item observable n'existe pour cette capacité."""
    with session_factory() as session:
        return len(crud.get_observable_items(session, capacity_id)) == 0


def _coaching_is_missing(session_factory, capacity_id: str, lang: str) -> bool:
    """Retourne True si le coaching est absent ou incomplet (thèmes vides)."""
    with session_factory() as session:
        trans = crud.get_coaching_translation(session, capacity_id, lang)
    return trans is None or not (trans.reflection_themes or "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Peuplement par section
# ─────────────────────────────────────────────────────────────────────────────

def populate_fiche(
    session_factory, capacity_id: str, lang: str, full: bool
) -> bool:
    """Génère et persiste l'information générale (label, définition, fonction centrale).

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        lang: Langue cible (``"fr"`` ou ``"en"``).
        full: Si True, regénère même si des données existent déjà.

    Returns:
        True si une génération a été effectuée, False si ignorée.
    """
    if not full and not _fiche_is_missing(session_factory, capacity_id, lang):
        return False

    content = generate_fiche(capacity_id, lang)

    with session_factory() as session:
        crud.upsert_capacity_translation(
            session,
            capacity_id,
            lang,
            label=content.name,
            definition=content.definition,
            central_function=content.central_function,
        )
    return True


def populate_risque(
    session_factory, capacity_id: str, lang: str, full: bool
) -> bool:
    """Génère et persiste les risques (insuffisant et excessif).

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité (ex. ``"I1a"``).
        lang: Langue cible (``"fr"`` ou ``"en"``).
        full: Si True, regénère même si des données existent déjà.

    Returns:
        True si une génération a été effectuée, False si ignorée.
    """
    if not full and not _risque_is_missing(session_factory, capacity_id, lang):
        return False

    with session_factory() as session:
        trans = crud.get_capacity_translation(session, capacity_id, lang)
    definition = (trans.definition or "") if trans else ""
    central_function = (trans.central_function or "") if trans else ""

    content = generate_fiche_risque(
        capacity_id, lang,
        definition=definition,
        central_function=central_function,
    )

    with session_factory() as session:
        crud.upsert_capacity_translation(
            session,
            capacity_id,
            lang,
            risk_insufficient=content.risk_insufficient,
            risk_excessive=content.risk_excessive,
        )
    return True


def populate_questions(
    session_factory, capacity_id: str, lang: str, full: bool
) -> bool:
    """Génère et persiste les 10 questions d'entretien.

    En mode full, supprime d'abord les questions existantes avant de créer
    les nouvelles entrées.

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité.
        lang: Langue cible.
        full: Si True, regénère même si des données existent déjà.

    Returns:
        True si une génération a été effectuée, False si ignorée.
    """
    if not full and not _questions_are_missing(session_factory, capacity_id):
        return False

    questions = generate_questions(capacity_id, lang)

    with session_factory() as session:
        # Suppression des questions existantes en mode full rebuild.
        if full:
            for q in crud.get_questions(session, capacity_id):
                crud.delete_question(session, q.question_id)

        # Création des questions.
        q_ids: list[int] = []
        for text in questions:
            if text.strip():
                q = crud.create_question(session, capacity_id, text.strip(), lang)
                q_ids.append(q.question_id)
        if q_ids:
            crud.reorder_questions(session, capacity_id, q_ids)

    return True


def populate_items(
    session_factory, capacity_id: str, lang: str, full: bool
) -> bool:
    """Génère et persiste les 4×5 items observables (OK/DEP/EXC/INS).

    En mode full, supprime d'abord les items existants avant de créer
    les nouvelles entrées.

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité.
        lang: Langue cible.
        full: Si True, regénère même si des données existent déjà.

    Returns:
        True si une génération a été effectuée, False si ignorée.
    """
    if not full and not _items_are_missing(session_factory, capacity_id):
        return False

    items = generate_questions_items(capacity_id, lang)

    with session_factory() as session:
        # Suppression des items existants en mode full rebuild.
        if full:
            for item in crud.get_observable_items(session, capacity_id):
                crud.delete_observable_item(session, item.item_id)

        # Création des items observables par catégorie.
        for code in ("OK", "EXC", "DEP", "INS"):
            item_ids: list[int] = []
            for text in items.get(code, []):
                if text.strip():
                    item = crud.create_observable_item(
                        session, capacity_id, code, text.strip(), lang
                    )
                    item_ids.append(item.item_id)
            if item_ids:
                crud.reorder_observable_items(session, code, item_ids)

    return True


def populate_coaching(
    session_factory, capacity_id: str, lang: str, full: bool
) -> bool:
    """Génère et persiste le contenu Coaching pour une capacité et une langue.

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité.
        lang: Langue cible.
        full: Si True, regénère même si des données existent déjà.

    Returns:
        True si une génération a été effectuée, False si ignorée.
    """
    if not full and not _coaching_is_missing(session_factory, capacity_id, lang):
        return False

    content = generate_coaching(capacity_id, lang)

    with session_factory() as session:
        crud.upsert_coaching_translation(
            session,
            capacity_id,
            lang,
            reflection_themes=content.reflection_themes,
            intervention_levers=content.intervention_levers,
            recommended_missions=content.recommended_missions,
        )
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Boucle principale
# ─────────────────────────────────────────────────────────────────────────────

_SECTION_FN = {
    "fiche": populate_fiche,
    "risque": populate_risque,
    "questions": populate_questions,
    "items": populate_items,
    "coaching": populate_coaching,
}


def run(
    full: bool,
    langs: list[str],
    capacity_ids: list[str] | None,
    skip: list[str],
) -> None:
    """Exécute le peuplement de la base de données.

    Args:
        full: Si True, regénère toutes les données même si elles existent.
        langs: Liste des langues à générer (ex. ``["fr", "en"]``).
        capacity_ids: Liste de capacités à traiter, ou None pour toutes.
        skip: Sections à sauter (sous-ensemble de ``_ALL_SECTIONS``).
    """
    if not _DB_PATH.exists():
        print(f"[ERREUR] Base de données introuvable : {_DB_PATH}", file=sys.stderr)
        sys.exit(1)

    engine = get_engine(_DB_PATH)
    init_db(engine, seed_capacities=True)
    session_factory = get_session_factory(engine)

    sections = [s for s in _ALL_SECTIONS if s not in skip]

    with session_factory() as session:
        all_caps = crud.get_all_capacities(session)

    targets = (
        [c for c in all_caps if c.capacity_id in capacity_ids]
        if capacity_ids
        else all_caps
    )

    if not targets:
        print("[AVERTISSEMENT] Aucune capacité à traiter.")
        return

    mode = "full rebuild" if full else "complétion"
    print(f"\nR6 Navigator — Peuplement IA ({mode})")
    print(f"  Capacités : {len(targets)}")
    print(f"  Langues   : {', '.join(langs)}")
    print(f"  Sections  : {', '.join(sections)}")
    print()

    total_ok = total_skip = total_err = 0

    for cap in targets:
        cid = cap.capacity_id
        for lang in langs:
            print(f"  [{cid}] [{lang}]", end="", flush=True)
            cap_ok = cap_skip = cap_err = 0

            for section in sections:
                fn = _SECTION_FN[section]
                label = f" {section}"
                try:
                    t0 = time.monotonic()
                    done = fn(session_factory, cid, lang, full)
                    elapsed = time.monotonic() - t0
                    if done:
                        print(f"{label}✓({elapsed:.1f}s)", end="", flush=True)
                        cap_ok += 1
                    else:
                        print(f"{label}—", end="", flush=True)
                        cap_skip += 1
                except Exception as exc:
                    short = str(exc)[:60]
                    print(f"{label}✗", end="", flush=True)
                    print(f"\n      ! {short}", end="", flush=True)
                    cap_err += 1

            print()
            total_ok += cap_ok
            total_skip += cap_skip
            total_err += cap_err

    print()
    print("─" * 50)
    print(f"  Généré  : {total_ok}")
    print(f"  Ignoré  : {total_skip}  (données déjà présentes)")
    print(f"  Erreurs : {total_err}")
    if total_err:
        print("\n  Vérifiez qu'Ollama est démarré et que l'URL/modèle dans params.yml sont corrects.")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Interface CLI
# ─────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="populate_db",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""\
            Peuple la base de données R6 Navigator via génération IA (Ollama).

            Par défaut, complète uniquement les données manquantes.
            Avec --full, regénère tout (questions/items existants supprimés et recréés).
        """),
    )
    parser.add_argument(
        "-f", "--full",
        action="store_true",
        help="regénère toutes les données, même celles déjà présentes",
    )
    parser.add_argument(
        "-l", "--lang",
        nargs="+",
        metavar="LANG",
        default=["fr"],
        choices=["fr", "en"],
        help="langue(s) de génération (défaut : fr)",
    )
    parser.add_argument(
        "-c", "--capacity",
        nargs="+",
        metavar="ID",
        default=None,
        help="traite uniquement ces capacités (ex. I1a S2b) ; défaut : toutes",
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        metavar="SECTION",
        default=[],
        choices=list(_ALL_SECTIONS),
        help="sections à sauter : fiche, risque, questions, items, coaching",
    )
    return parser


def main() -> None:
    """Point d'entrée principal du CLI."""
    parser = _build_parser()
    args = parser.parse_args()
    run(
        full=args.full,
        langs=args.lang,
        capacity_ids=args.capacity,
        skip=args.skip,
    )


if __name__ == "__main__":
    main()
