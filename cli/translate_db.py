#!/usr/bin/env python3
"""CLI de traduction de la base de données R6 Navigator via IA.

Lit les données existantes dans la langue source et génère — pour chaque
section demandée — les traductions dans la langue cible via Ollama.

Les questions et manifestations observables étant structurellement partagées
entre les langues, la traduction n'ajoute que les lignes de traduction manquantes
(``question_translations``, ``observable_item_translations``) sans recréer
les entités parentes.

Usage:
    python cli/translate_db.py                          # fr → en, données manquantes seulement
    python cli/translate_db.py --from en --to fr        # en → fr
    python cli/translate_db.py --full                   # retraduit tout (fr → en)
    python cli/translate_db.py --full --from en --to fr
    python cli/translate_db.py --capacity I1a S2b       # capacités spécifiques seulement
    python cli/translate_db.py --skip fiche coaching    # saute certaines sections
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
from r6_navigator.services import crud
from r6_navigator.services.ai_generate import (
    translate_coaching,
    translate_fiche,
    translate_observable_items,
    translate_questions,
)

_DB_PATH = _ROOT / "r6_navigator.db"

# ── Sections disponibles ───────────────────────────────────────────────────────
_ALL_SECTIONS = ("fiche", "questions", "coaching")


# ─────────────────────────────────────────────────────────────────────────────
# Détection des données manquantes côté cible
# ─────────────────────────────────────────────────────────────────────────────

def _fiche_source_exists(session_factory, capacity_id: str, source_lang: str) -> bool:
    """Retourne True si une fiche source non vide existe pour cette capacité.

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité.
        source_lang: Code de la langue source.

    Returns:
        True si la fiche source contient une définition non vide.
    """
    with session_factory() as session:
        trans = crud.get_capacity_translation(session, capacity_id, source_lang)
    return trans is not None and bool((trans.definition or "").strip())


def _fiche_target_missing(
    session_factory, capacity_id: str, target_lang: str
) -> bool:
    """Retourne True si la fiche cible est absente ou incomplète.

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité.
        target_lang: Code de la langue cible.

    Returns:
        True si la traduction cible de la fiche est absente ou vide.
    """
    with session_factory() as session:
        trans = crud.get_capacity_translation(session, capacity_id, target_lang)
    return trans is None or not (trans.definition or "").strip()


def _questions_to_translate(
    session_factory,
    capacity_id: str,
    source_lang: str,
    target_lang: str,
    full: bool,
) -> list[tuple[int, str]]:
    """Retourne la liste des (question_id, texte_source) à traduire.

    En mode complétion, ne retourne que les questions sans traduction cible.
    En mode full, retourne toutes les questions ayant une traduction source.

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité.
        source_lang: Code de la langue source.
        target_lang: Code de la langue cible.
        full: Si True, retourne toutes les questions (retranslation forcée).

    Returns:
        Liste de tuples ``(question_id, texte_source)``.
    """
    with session_factory() as session:
        questions = crud.get_questions(session, capacity_id)
        result = []
        for q in questions:
            src = crud.get_question_translation(session, q.question_id, source_lang)
            if not src or not (src.text or "").strip():
                continue  # Pas de source : impossible de traduire.
            if not full:
                tgt = crud.get_question_translation(session, q.question_id, target_lang)
                if tgt and (tgt.text or "").strip():
                    continue  # Traduction cible déjà présente.
            result.append((q.question_id, src.text))
    return result


def _items_to_translate(
    session_factory,
    capacity_id: str,
    source_lang: str,
    target_lang: str,
    full: bool,
) -> tuple[dict[str, list[str]], dict[str, list[int]]]:
    """Retourne les items observables à traduire, groupés par catégorie.

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité.
        source_lang: Code de la langue source.
        target_lang: Code de la langue cible.
        full: Si True, retourne tous les items (retranslation forcée).

    Returns:
        Tuple ``(textes_par_cat, ids_par_cat)`` où chaque dict est indexé par
        code de catégorie (``OK``, ``EXC``, ``DEP``, ``INS``).
    """
    with session_factory() as session:
        items = crud.get_observable_items(session, capacity_id)
        texts_by_cat: dict[str, list[str]] = {}
        ids_by_cat: dict[str, list[int]] = {}
        for item in items:
            src = crud.get_observable_item_translation(
                session, item.item_id, source_lang
            )
            if not src or not (src.text or "").strip():
                continue  # Pas de source : impossible de traduire.
            if not full:
                tgt = crud.get_observable_item_translation(
                    session, item.item_id, target_lang
                )
                if tgt and (tgt.text or "").strip():
                    continue  # Traduction cible déjà présente.
            code = item.category_code
            texts_by_cat.setdefault(code, []).append(src.text)
            ids_by_cat.setdefault(code, []).append(item.item_id)
    return texts_by_cat, ids_by_cat


def _coaching_source_exists(
    session_factory, capacity_id: str, source_lang: str
) -> bool:
    """Retourne True si un coaching source non vide existe pour cette capacité.

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité.
        source_lang: Code de la langue source.

    Returns:
        True si le coaching source contient des thèmes de réflexion non vides.
    """
    with session_factory() as session:
        trans = crud.get_coaching_translation(session, capacity_id, source_lang)
    return trans is not None and bool((trans.reflection_themes or "").strip())


def _coaching_target_missing(
    session_factory, capacity_id: str, target_lang: str
) -> bool:
    """Retourne True si le coaching cible est absent ou incomplet.

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité.
        target_lang: Code de la langue cible.

    Returns:
        True si la traduction cible du coaching est absente ou vide.
    """
    with session_factory() as session:
        trans = crud.get_coaching_translation(session, capacity_id, target_lang)
    return trans is None or not (trans.reflection_themes or "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Traduction par section
# ─────────────────────────────────────────────────────────────────────────────

def translate_fiche_section(
    session_factory,
    capacity_id: str,
    source_lang: str,
    target_lang: str,
    full: bool,
) -> bool:
    """Traduit et persiste la Fiche pour une capacité depuis source_lang vers target_lang.

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité.
        source_lang: Code de la langue source.
        target_lang: Code de la langue cible.
        full: Si True, retraduit même si une traduction cible existe déjà.

    Returns:
        True si une traduction a été effectuée, False si ignorée.
    """
    if not _fiche_source_exists(session_factory, capacity_id, source_lang):
        return False
    if not full and not _fiche_target_missing(session_factory, capacity_id, target_lang):
        return False

    with session_factory() as session:
        src = crud.get_capacity_translation(session, capacity_id, source_lang)
        source_fields = {
            "name": src.label or "",
            "definition": src.definition or "",
            "central_function": src.central_function or "",
            "observable": src.observable or "",
            "risk_insufficient": src.risk_insufficient or "",
            "risk_excessive": src.risk_excessive or "",
        }

    content = translate_fiche(capacity_id, source_fields, source_lang, target_lang)

    with session_factory() as session:
        crud.upsert_capacity_translation(
            session,
            capacity_id,
            target_lang,
            label=content.name,
            definition=content.definition,
            central_function=content.central_function,
            observable=content.observable,
            risk_insufficient=content.risk_insufficient,
            risk_excessive=content.risk_excessive,
        )
    return True


def translate_questions_section(
    session_factory,
    capacity_id: str,
    source_lang: str,
    target_lang: str,
    full: bool,
) -> bool:
    """Traduit et persiste les questions STAR et les manifestations observables.

    Les entités Question et ObservableItem ne sont pas recréées — seules les
    lignes de traduction manquantes (ou toutes en mode full) sont upsertées.

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité.
        source_lang: Code de la langue source.
        target_lang: Code de la langue cible.
        full: Si True, retraduit toutes les entités existantes.

    Returns:
        True si au moins une traduction a été effectuée, False si tout était déjà présent.
    """
    q_pairs = _questions_to_translate(
        session_factory, capacity_id, source_lang, target_lang, full
    )
    items_texts, items_ids = _items_to_translate(
        session_factory, capacity_id, source_lang, target_lang, full
    )

    if not q_pairs and not items_texts:
        return False

    # ── Traduction des questions ───────────────────────────────────────────────
    if q_pairs:
        source_texts = [text for _, text in q_pairs]
        translated_questions = translate_questions(
            capacity_id, source_texts, source_lang, target_lang
        )
        with session_factory() as session:
            for (q_id, _), tgt_text in zip(q_pairs, translated_questions):
                if tgt_text.strip():
                    crud.upsert_question_translation(
                        session, q_id, target_lang, text=tgt_text
                    )

    # ── Traduction des items observables ──────────────────────────────────────
    if items_texts:
        translated_items = translate_observable_items(
            capacity_id, items_texts, source_lang, target_lang
        )
        with session_factory() as session:
            for code, tgt_texts in translated_items.items():
                ids = items_ids.get(code, [])
                for item_id, text in zip(ids, tgt_texts):
                    if text.strip():
                        crud.upsert_observable_item_translation(
                            session, item_id, target_lang, text=text
                        )

    return True


def translate_coaching_section(
    session_factory,
    capacity_id: str,
    source_lang: str,
    target_lang: str,
    full: bool,
) -> bool:
    """Traduit et persiste le Coaching pour une capacité depuis source_lang vers target_lang.

    Args:
        session_factory: Factory de sessions SQLAlchemy.
        capacity_id: Identifiant de la capacité.
        source_lang: Code de la langue source.
        target_lang: Code de la langue cible.
        full: Si True, retraduit même si une traduction cible existe déjà.

    Returns:
        True si une traduction a été effectuée, False si ignorée.
    """
    if not _coaching_source_exists(session_factory, capacity_id, source_lang):
        return False
    if not full and not _coaching_target_missing(
        session_factory, capacity_id, target_lang
    ):
        return False

    with session_factory() as session:
        src = crud.get_coaching_translation(session, capacity_id, source_lang)
        source_fields = {
            "reflection_themes": src.reflection_themes or "",
            "intervention_levers": src.intervention_levers or "",
            "recommended_missions": src.recommended_missions or "",
        }

    content = translate_coaching(capacity_id, source_fields, source_lang, target_lang)

    with session_factory() as session:
        crud.upsert_coaching_translation(
            session,
            capacity_id,
            target_lang,
            reflection_themes=content.reflection_themes,
            intervention_levers=content.intervention_levers,
            recommended_missions=content.recommended_missions,
        )
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Boucle principale
# ─────────────────────────────────────────────────────────────────────────────

_SECTION_FN = {
    "fiche": translate_fiche_section,
    "questions": translate_questions_section,
    "coaching": translate_coaching_section,
}


def run(
    full: bool,
    source_lang: str,
    target_lang: str,
    capacity_ids: list[str] | None,
    skip: list[str],
) -> None:
    """Exécute la traduction de la base de données.

    Args:
        full: Si True, retraduit toutes les données même si elles existent déjà.
        source_lang: Code de la langue source (``"fr"`` ou ``"en"``).
        target_lang: Code de la langue cible (``"fr"`` ou ``"en"``).
        capacity_ids: Liste de capacités à traiter, ou None pour toutes.
        skip: Sections à sauter (sous-ensemble de ``fiche``, ``questions``, ``coaching``).
    """
    if source_lang == target_lang:
        print(
            f"[ERREUR] La langue source et la langue cible sont identiques ({source_lang}).",
            file=sys.stderr,
        )
        sys.exit(1)

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
    print(f"\nR6 Navigator — Traduction IA ({mode})")
    print(f"  Capacités : {len(targets)}")
    print(f"  Direction : {source_lang} → {target_lang}")
    print(f"  Sections  : {', '.join(sections)}")
    print()

    total_ok = total_skip = total_err = 0

    for cap in targets:
        cid = cap.capacity_id
        print(f"  [{cid}]", end="", flush=True)
        cap_ok = cap_skip = cap_err = 0

        for section in sections:
            fn = _SECTION_FN[section]
            label = f" {section}"
            try:
                t0 = time.monotonic()
                done = fn(session_factory, cid, source_lang, target_lang, full)
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
    print(f"  Traduit : {total_ok}")
    print(f"  Ignoré  : {total_skip}  (données déjà présentes ou source manquante)")
    print(f"  Erreurs : {total_err}")
    if total_err:
        print(
            "\n  Vérifiez qu'Ollama est démarré et que l'URL/modèle dans params.yml sont corrects."
        )
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Interface CLI
# ─────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    """Construit et retourne le parseur d'arguments CLI.

    Returns:
        ArgumentParser configuré pour translate_db.
    """
    parser = argparse.ArgumentParser(
        prog="translate_db",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""\
            Traduit la base de données R6 Navigator via IA (Ollama).

            Lit les données existantes dans la langue source et génère les
            traductions manquantes dans la langue cible.
            Avec --full, retraduit tout même si des traductions existent déjà.
        """),
    )
    parser.add_argument(
        "-f", "--full",
        action="store_true",
        help="retraduit toutes les données, même celles déjà traduites",
    )
    parser.add_argument(
        "-s", "--from",
        dest="source_lang",
        metavar="LANG",
        default="fr",
        choices=["fr", "en"],
        help="langue source (défaut : fr)",
    )
    parser.add_argument(
        "-t", "--to",
        dest="target_lang",
        metavar="LANG",
        default="en",
        choices=["fr", "en"],
        help="langue cible (défaut : en)",
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
        help="sections à sauter : fiche, questions, coaching",
    )
    return parser


def main() -> None:
    """Point d'entrée principal du CLI."""
    parser = _build_parser()
    args = parser.parse_args()
    run(
        full=args.full,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        capacity_ids=args.capacity,
        skip=args.skip,
    )


if __name__ == "__main__":
    main()
