import pytest

from r6_navigator.db.models import Capacity, CapacityTranslation, Coaching, Question
from r6_navigator.services import crud


# ---------------------------------------------------------------------------
# Capacity tests
# ---------------------------------------------------------------------------

def test_create_capacity_success(session):
    cap = crud.create_capacity(session, "I", 1, "a", label="Test label", lang="fr")

    assert cap.capacity_id == "I1a"
    assert cap.level_code == "I"
    assert cap.axis_number == 1
    assert cap.pole_code == "a"
    assert cap.is_canonical is True

    trans = session.get(CapacityTranslation, ("I1a", "fr"))
    assert trans is not None
    assert trans.label == "Test label"

    coaching = session.get(Coaching, "I1a")
    assert coaching is not None


def test_create_capacity_duplicate_raises(session):
    crud.create_capacity(session, "I", 1, "a", label="First", lang="fr")
    with pytest.raises(ValueError):
        crud.create_capacity(session, "I", 1, "a", label="Second", lang="fr")


def test_create_capacity_missing_label_raises(session):
    with pytest.raises(ValueError, match="label is required"):
        crud.create_capacity(session, "I", 1, "a", label="", lang="fr")


def test_get_capacity_exists(session):
    crud.create_capacity(session, "I", 2, "b", label="Test", lang="fr")
    cap = crud.get_capacity(session, "I2b")
    assert cap is not None
    assert cap.capacity_id == "I2b"


def test_get_capacity_not_found(session):
    cap = crud.get_capacity(session, "Z9z")
    assert cap is None


def test_upsert_capacity_translation(session):
    crud.create_capacity(session, "I", 1, "a", label="Label FR", lang="fr")

    # Add EN translation with extra fields
    trans_en = crud.upsert_capacity_translation(
        session, "I1a", "en", label="Label EN", definition="Def EN"
    )
    assert trans_en.lang == "en"
    assert trans_en.label == "Label EN"
    assert trans_en.definition == "Def EN"

    # Upsert again: update definition only — label must not change
    trans_en2 = crud.upsert_capacity_translation(
        session, "I1a", "en", definition="Updated def"
    )
    assert trans_en2.definition == "Updated def"
    assert trans_en2.label == "Label EN"


def test_update_capacity_structural_fields_raises(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    with pytest.raises(ValueError):
        crud.update_capacity(session, "I1a", level_code="S")


def test_delete_capacity(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    q = crud.create_question(session, "I1a", text="Q1", lang="fr")
    q_id = q.question_id

    crud.delete_capacity(session, "I1a")

    assert crud.get_capacity(session, "I1a") is None
    assert session.get(CapacityTranslation, ("I1a", "fr")) is None
    assert session.get(Coaching, "I1a") is None
    assert session.get(Question, q_id) is None


def test_get_all_capacities_ordering(session):
    # Create capacities in non-natural order
    crud.create_capacity(session, "I", 3, "b", label="I3b", lang="fr")
    crud.create_capacity(session, "S", 1, "a", label="S1a", lang="fr")
    crud.create_capacity(session, "O", 2, "a", label="O2a", lang="fr")
    crud.create_capacity(session, "I", 1, "a", label="I1a", lang="fr")

    caps = crud.get_all_capacities(session)
    ids = [c.capacity_id for c in caps]

    # Level order: S (display_order=1) < O (display_order=2) < I (display_order=3)
    assert ids.index("S1a") < ids.index("O2a")
    assert ids.index("O2a") < ids.index("I1a")
    # Within same level, axis ordering
    assert ids.index("I1a") < ids.index("I3b")


# ---------------------------------------------------------------------------
# Question tests
# ---------------------------------------------------------------------------

def test_create_question(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    q = crud.create_question(session, "I1a", text="Ma question", lang="fr")

    assert q.question_id is not None
    assert q.capacity_id == "I1a"

    trans = crud.get_question_translation(session, q.question_id, "fr")
    assert trans is not None
    assert trans.text == "Ma question"


def test_reorder_questions(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    q1 = crud.create_question(session, "I1a", text="Q1", lang="fr")
    q2 = crud.create_question(session, "I1a", text="Q2", lang="fr")
    q3 = crud.create_question(session, "I1a", text="Q3", lang="fr")

    crud.reorder_questions(session, "I1a", [q3.question_id, q1.question_id, q2.question_id])

    questions = crud.get_questions(session, "I1a")
    assert questions[0].question_id == q3.question_id
    assert questions[1].question_id == q1.question_id
    assert questions[2].question_id == q2.question_id


def test_delete_question(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    q1 = crud.create_question(session, "I1a", text="Q1", lang="fr")
    q2 = crud.create_question(session, "I1a", text="Q2", lang="fr")

    crud.delete_question(session, q1.question_id)

    questions = crud.get_questions(session, "I1a")
    assert len(questions) == 1
    assert questions[0].question_id == q2.question_id


def test_upsert_question_translation(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    q = crud.create_question(session, "I1a", text="Question FR", lang="fr")

    trans_en = crud.upsert_question_translation(session, q.question_id, "en", text="Question EN")
    assert trans_en.text == "Question EN"

    trans_fr = crud.upsert_question_translation(session, q.question_id, "fr", text="Question FR updated")
    assert trans_fr.text == "Question FR updated"


# ---------------------------------------------------------------------------
# ObservableItem tests
# ---------------------------------------------------------------------------

def test_create_observable_item(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    item = crud.create_observable_item(session, "I1a", "OK", text="Item text", lang="fr")

    assert item.item_id is not None
    assert item.capacity_id == "I1a"
    assert item.category_code == "OK"

    trans = crud.get_observable_item_translation(session, item.item_id, "fr")
    assert trans is not None
    assert trans.text == "Item text"


def test_create_observable_item_invalid_category(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    with pytest.raises(ValueError):
        crud.create_observable_item(session, "I1a", "INVALID", text="Item", lang="fr")


def test_get_items_by_category(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    crud.create_observable_item(session, "I1a", "OK", text="OK item 1", lang="fr")
    crud.create_observable_item(session, "I1a", "OK", text="OK item 2", lang="fr")
    crud.create_observable_item(session, "I1a", "EXC", text="EXC item", lang="fr")

    ok_items = crud.get_observable_items_by_category(session, "I1a", "OK")
    assert len(ok_items) == 2
    assert all(i.category_code == "OK" for i in ok_items)


def test_reorder_observable_items(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    item1 = crud.create_observable_item(session, "I1a", "OK", text="Item 1", lang="fr")
    item2 = crud.create_observable_item(session, "I1a", "OK", text="Item 2", lang="fr")
    item3 = crud.create_observable_item(session, "I1a", "OK", text="Item 3", lang="fr")

    crud.reorder_observable_items(
        session, "OK", [item3.item_id, item1.item_id, item2.item_id]
    )

    items = crud.get_observable_items_by_category(session, "I1a", "OK")
    assert items[0].item_id == item3.item_id
    assert items[1].item_id == item1.item_id
    assert items[2].item_id == item2.item_id


# ---------------------------------------------------------------------------
# Coaching tests
# ---------------------------------------------------------------------------

def test_coaching_auto_created(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    coaching = crud.get_coaching(session, "I1a")
    assert coaching is not None


def test_upsert_coaching_translation_creates(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    trans = crud.upsert_coaching_translation(session, "I1a", "fr", reflection_themes="Thèmes")

    assert trans.capacity_id == "I1a"
    assert trans.lang == "fr"
    assert trans.reflection_themes == "Thèmes"


def test_upsert_coaching_translation_updates(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    crud.upsert_coaching_translation(session, "I1a", "fr", reflection_themes="Initial")

    trans = crud.upsert_coaching_translation(
        session, "I1a", "fr",
        reflection_themes="Updated",
        intervention_levers="Levers",
    )
    assert trans.reflection_themes == "Updated"
    assert trans.intervention_levers == "Levers"


def test_coaching_translations_independent_by_lang(session):
    crud.create_capacity(session, "I", 1, "a", label="Test", lang="fr")
    crud.upsert_coaching_translation(session, "I1a", "fr", reflection_themes="Thèmes FR")
    crud.upsert_coaching_translation(session, "I1a", "en", reflection_themes="Themes EN")

    fr_trans = crud.get_coaching_translation(session, "I1a", "fr")
    en_trans = crud.get_coaching_translation(session, "I1a", "en")

    assert fr_trans.reflection_themes == "Thèmes FR"
    assert en_trans.reflection_themes == "Themes EN"


# ---------------------------------------------------------------------------
# Settings tests
# ---------------------------------------------------------------------------

def test_get_setting_default(session):
    value = crud.get_setting(session, "active_language")
    assert value == "fr"


def test_set_and_get_setting(session):
    crud.set_setting(session, "active_language", "en")
    value = crud.get_setting(session, "active_language")
    assert value == "en"
