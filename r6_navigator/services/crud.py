from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from r6_navigator.db.models import (
    AppSetting,
    Axis,
    Capacity,
    CapacityTranslation,
    Coaching,
    CoachingTranslation,
    Level,
    ObservableCategory,
    ObservableItem,
    ObservableItemTranslation,
    Question,
    QuestionTranslation,
)


# ---------------------------------------------------------------------------
# Capacities
# ---------------------------------------------------------------------------

def get_all_capacities(session: Session) -> list[Capacity]:
    stmt = (
        select(Capacity)
        .join(Level, Capacity.level_code == Level.level_code)
        .order_by(Level.display_order, Capacity.axis_number, Capacity.pole_code)
    )
    return list(session.scalars(stmt).all())


def get_capacity(session: Session, capacity_id: str) -> Capacity | None:
    return session.get(Capacity, capacity_id)


def create_capacity(
    session: Session,
    level_code: str,
    axis_number: int,
    pole_code: str,
    label: str,
    lang: str = "fr",
    is_canonical: bool = True,
    **translation_fields,
) -> Capacity:
    if not label or not label.strip():
        raise ValueError("label is required")

    capacity_id = f"{level_code}{axis_number}{pole_code}"

    if session.get(Capacity, capacity_id) is not None:
        raise ValueError(f"Capacity '{capacity_id}' already exists")

    capacity = Capacity(
        capacity_id=capacity_id,
        level_code=level_code,
        axis_number=axis_number,
        pole_code=pole_code,
        is_canonical=is_canonical,
    )
    session.add(capacity)
    session.add(CapacityTranslation(
        capacity_id=capacity_id,
        lang=lang,
        label=label,
        **translation_fields,
    ))
    session.add(Coaching(capacity_id=capacity_id))
    session.commit()
    session.refresh(capacity)
    return capacity


def update_capacity(session: Session, capacity_id: str, **fields) -> Capacity:
    structural = {"level_code", "axis_number", "pole_code"}
    forbidden = structural & fields.keys()
    if forbidden:
        raise ValueError(f"Cannot change structural fields: {forbidden}")

    capacity = session.get(Capacity, capacity_id)
    if capacity is None:
        raise ValueError(f"Capacity '{capacity_id}' not found")

    for key, value in fields.items():
        setattr(capacity, key, value)

    session.commit()
    session.refresh(capacity)
    return capacity


def delete_capacity(session: Session, capacity_id: str) -> None:
    capacity = session.get(Capacity, capacity_id)
    if capacity is not None:
        session.delete(capacity)
        session.commit()


# ---------------------------------------------------------------------------
# Translations — Capacity
# ---------------------------------------------------------------------------

def get_capacity_translation(
    session: Session, capacity_id: str, lang: str
) -> CapacityTranslation | None:
    return session.get(CapacityTranslation, (capacity_id, lang))


def upsert_capacity_translation(
    session: Session, capacity_id: str, lang: str, **fields
) -> CapacityTranslation:
    trans = session.get(CapacityTranslation, (capacity_id, lang))
    if trans is None:
        trans = CapacityTranslation(capacity_id=capacity_id, lang=lang)
        session.add(trans)

    for key, value in fields.items():
        setattr(trans, key, value)

    session.commit()
    session.refresh(trans)
    return trans


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

def get_questions(session: Session, capacity_id: str) -> list[Question]:
    stmt = (
        select(Question)
        .where(Question.capacity_id == capacity_id)
        .order_by(Question.display_order)
    )
    return list(session.scalars(stmt).all())


def create_question(
    session: Session, capacity_id: str, text: str, lang: str = "fr"
) -> Question:
    question = Question(capacity_id=capacity_id)
    session.add(question)
    session.flush()  # Obtain question_id before creating translation
    session.add(QuestionTranslation(question_id=question.question_id, lang=lang, text=text))
    session.commit()
    session.refresh(question)
    return question


def update_question(session: Session, question_id: int, **fields) -> Question:
    question = session.get(Question, question_id)
    if question is None:
        raise ValueError(f"Question '{question_id}' not found")

    for key, value in fields.items():
        setattr(question, key, value)

    session.commit()
    session.refresh(question)
    return question


def delete_question(session: Session, question_id: int) -> None:
    question = session.get(Question, question_id)
    if question is not None:
        session.delete(question)
        session.commit()


def reorder_questions(
    session: Session, capacity_id: str, ordered_ids: list[int]
) -> None:
    for position, question_id in enumerate(ordered_ids):
        question = session.get(Question, question_id)
        if question is not None:
            question.display_order = position
    session.commit()


# ---------------------------------------------------------------------------
# Translations — Question
# ---------------------------------------------------------------------------

def get_question_translation(
    session: Session, question_id: int, lang: str
) -> QuestionTranslation | None:
    return session.get(QuestionTranslation, (question_id, lang))


def upsert_question_translation(
    session: Session, question_id: int, lang: str, **fields
) -> QuestionTranslation:
    trans = session.get(QuestionTranslation, (question_id, lang))
    if trans is None:
        trans = QuestionTranslation(question_id=question_id, lang=lang)
        session.add(trans)

    for key, value in fields.items():
        setattr(trans, key, value)

    session.commit()
    session.refresh(trans)
    return trans


# ---------------------------------------------------------------------------
# ObservableItems
# ---------------------------------------------------------------------------

def get_observable_items(session: Session, capacity_id: str) -> list[ObservableItem]:
    stmt = (
        select(ObservableItem)
        .join(
            ObservableCategory,
            ObservableItem.category_code == ObservableCategory.category_code,
        )
        .where(ObservableItem.capacity_id == capacity_id)
        .order_by(ObservableCategory.display_order, ObservableItem.display_order)
    )
    return list(session.scalars(stmt).all())


def get_observable_items_by_category(
    session: Session, capacity_id: str, category_code: str
) -> list[ObservableItem]:
    stmt = (
        select(ObservableItem)
        .where(
            ObservableItem.capacity_id == capacity_id,
            ObservableItem.category_code == category_code,
        )
        .order_by(ObservableItem.display_order)
    )
    return list(session.scalars(stmt).all())


def create_observable_item(
    session: Session,
    capacity_id: str,
    category_code: str,
    text: str,
    lang: str = "fr",
) -> ObservableItem:
    if session.get(ObservableCategory, category_code) is None:
        raise ValueError(f"Invalid category_code '{category_code}'")

    item = ObservableItem(capacity_id=capacity_id, category_code=category_code)
    session.add(item)
    session.flush()  # Obtain item_id before creating translation
    session.add(ObservableItemTranslation(item_id=item.item_id, lang=lang, text=text))
    session.commit()
    session.refresh(item)
    return item


def update_observable_item(session: Session, item_id: int, **fields) -> ObservableItem:
    item = session.get(ObservableItem, item_id)
    if item is None:
        raise ValueError(f"ObservableItem '{item_id}' not found")

    for key, value in fields.items():
        setattr(item, key, value)

    session.commit()
    session.refresh(item)
    return item


def delete_observable_item(session: Session, item_id: int) -> None:
    item = session.get(ObservableItem, item_id)
    if item is not None:
        session.delete(item)
        session.commit()


def reorder_observable_items(
    session: Session, category_code: str, ordered_ids: list[int]
) -> None:
    for position, item_id in enumerate(ordered_ids):
        item = session.get(ObservableItem, item_id)
        if item is not None:
            item.display_order = position
    session.commit()


# ---------------------------------------------------------------------------
# Translations — ObservableItem
# ---------------------------------------------------------------------------

def get_observable_item_translation(
    session: Session, item_id: int, lang: str
) -> ObservableItemTranslation | None:
    return session.get(ObservableItemTranslation, (item_id, lang))


def upsert_observable_item_translation(
    session: Session, item_id: int, lang: str, **fields
) -> ObservableItemTranslation:
    trans = session.get(ObservableItemTranslation, (item_id, lang))
    if trans is None:
        trans = ObservableItemTranslation(item_id=item_id, lang=lang)
        session.add(trans)

    for key, value in fields.items():
        setattr(trans, key, value)

    session.commit()
    session.refresh(trans)
    return trans


# ---------------------------------------------------------------------------
# Coaching
# ---------------------------------------------------------------------------

def get_coaching(session: Session, capacity_id: str) -> Coaching | None:
    return session.get(Coaching, capacity_id)


def upsert_coaching(session: Session, capacity_id: str, **fields) -> Coaching:
    coaching = session.get(Coaching, capacity_id)
    if coaching is None:
        coaching = Coaching(capacity_id=capacity_id)
        session.add(coaching)

    for key, value in fields.items():
        setattr(coaching, key, value)

    session.commit()
    session.refresh(coaching)
    return coaching


# ---------------------------------------------------------------------------
# Translations — Coaching
# ---------------------------------------------------------------------------

def get_coaching_translation(
    session: Session, capacity_id: str, lang: str
) -> CoachingTranslation | None:
    return session.get(CoachingTranslation, (capacity_id, lang))


def upsert_coaching_translation(
    session: Session, capacity_id: str, lang: str, **fields
) -> CoachingTranslation:
    # Ensure parent Coaching row exists
    if session.get(Coaching, capacity_id) is None:
        session.add(Coaching(capacity_id=capacity_id))
        session.flush()

    trans = session.get(CoachingTranslation, (capacity_id, lang))
    if trans is None:
        trans = CoachingTranslation(capacity_id=capacity_id, lang=lang)
        session.add(trans)

    for key, value in fields.items():
        setattr(trans, key, value)

    session.commit()
    session.refresh(trans)
    return trans


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_setting(session: Session, key: str) -> str | None:
    setting = session.get(AppSetting, key)
    return setting.value if setting is not None else None


def set_setting(session: Session, key: str, value: str) -> None:
    setting = session.get(AppSetting, key)
    if setting is None:
        session.add(AppSetting(key=key, value=value))
    else:
        setting.value = value
    session.commit()


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

def get_levels(session: Session) -> list[Level]:
    return list(session.scalars(select(Level).order_by(Level.display_order)).all())


def get_axes(session: Session) -> list[Axis]:
    return list(session.scalars(select(Axis).order_by(Axis.axis_number)).all())


def get_observable_categories(session: Session) -> list[ObservableCategory]:
    return list(
        session.scalars(
            select(ObservableCategory).order_by(ObservableCategory.display_order)
        ).all()
    )
