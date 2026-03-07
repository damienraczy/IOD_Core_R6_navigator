"""Tests unitaires pour ai_analyze_v2 — pipeline itératif v2."""

from __future__ import annotations

import json

import pytest

from r6_navigator.services.ai_analyze_v2 import (
    AnalyzedBlock,
    CapacityIdentification,
    MaturityEvaluation,
    SemanticBlock,
    _extract_blocks_from_breaks,
    _identify_capacities,
    _merge_analyses,
    _parse_speech_turns,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_verbatim_fr():
    return (
        "[INTERVIEWE] J'ai cliqué sur le lien de la synthèse et j'ai décroché mon téléphone. "
        "J'hésitais entre les fournisseurs car le budget était limité. "
        "Finalement, j'ai choisi le plus cher mais fiable.\n"
        "[CONSULTANT] Avez-vous testé la solution avant de choisir ?\n"
        "[INTERVIEWE] Oui, j'ai fait un tableau comparatif sur Excel."
    )


@pytest.fixture
def sample_verbatim_no_markers():
    return "J'ai organisé une réunion avec mon équipe. Nous avons pris la décision ensemble."


@pytest.fixture
def minimal_block() -> SemanticBlock:
    return SemanticBlock(
        block_id="r0_0",
        text="J'ai fait un plan.",
        context="",
        sentences=["J'ai fait un plan."],
        start_position=0,
        end_position=18,
        word_count=5,
        type_contenu="observable",
        irrelevant=False,
        replique_id=0,
    )


# ---------------------------------------------------------------------------
# Phase 1 — _parse_speech_turns
# ---------------------------------------------------------------------------

def test_parse_speech_turns_identifies_speakers(sample_verbatim_fr):
    turns = _parse_speech_turns(sample_verbatim_fr)
    speakers = {t.speaker for t in turns}
    assert "interviewe" in speakers
    assert "consultant" in speakers


def test_parse_speech_turns_no_markers(sample_verbatim_no_markers):
    """Sans marqueurs, le texte entier est un tour interviewe."""
    turns = _parse_speech_turns(sample_verbatim_no_markers)
    assert len(turns) == 1
    assert turns[0].speaker == "interviewe"
    assert turns[0].text == sample_verbatim_no_markers.strip()


def test_parse_speech_turns_consultant_irrelevant(sample_verbatim_fr):
    """Les tours consultant doivent exister et contenir du texte."""
    turns = _parse_speech_turns(sample_verbatim_fr)
    consultant_turns = [t for t in turns if t.speaker == "consultant"]
    assert consultant_turns
    assert all(t.text for t in consultant_turns)


# ---------------------------------------------------------------------------
# Phase 1 — _extract_blocks_from_breaks
# ---------------------------------------------------------------------------

def test_extract_blocks_populates_sentences():
    """Correction v3 : sentences doit être peuplé (bug absent dans v2)."""
    verbatim = "J'ai fait un plan. J'ai contacté les équipes."
    blocks = _extract_blocks_from_breaks(verbatim, verbatim, replique_id=0)
    assert len(blocks) == 1
    assert blocks[0].sentences  # non vide
    assert blocks[0].block_id == "r0_0"


def test_extract_blocks_with_breaks():
    """||BREAK|| doit produire plusieurs blocs."""
    text = "J'ai pris la décision.||BREAK||L'équipe a suivi le plan."
    verbatim = "J'ai pris la décision. L'équipe a suivi le plan."
    blocks = _extract_blocks_from_breaks(text, verbatim, replique_id=1)
    assert len(blocks) == 2
    assert blocks[0].block_id == "r1_0"
    assert blocks[1].block_id == "r1_1"


def test_extract_blocks_skips_empty():
    """Les blocs vides après split doivent être ignorés."""
    text = "||BREAK||Seul bloc valide.||BREAK||"
    blocks = _extract_blocks_from_breaks(text, "Seul bloc valide.", replique_id=0)
    assert len(blocks) == 1
    assert blocks[0].text == "Seul bloc valide."


def test_extract_blocks_sentences_fallback():
    """Si aucune phrase détectée par regex, le texte entier devient la seule phrase."""
    text = "Bloc sans ponctuation finale"
    blocks = _extract_blocks_from_breaks(text, text, replique_id=0)
    assert blocks[0].sentences == ["Bloc sans ponctuation finale"]


# ---------------------------------------------------------------------------
# Phase 2 — _identify_capacities
# ---------------------------------------------------------------------------

def test_identify_capacities_returns_empty_for_no_blocks():
    results = _identify_capacities([], llm_call_fn=lambda _: "")
    assert results == []


def test_identify_capacities_drops_block_on_invalid_json(minimal_block):
    """JSON invalide → le bloc est ignoré (pas de fake), résultat vide."""
    results = _identify_capacities(
        [minimal_block],
        llm_call_fn=lambda _: "not json at all !!!",
    )
    assert results == []


def test_identify_capacities_parses_valid_response(minimal_block):
    """Réponse JSON valide → CapacityIdentification correctement peuplée."""
    response = json.dumps({
        "blocks_analysis": [{
            "block_id": "r0_0",
            "capacity_id": "I3a",
            "level_code": "I",
            "halliday_consistent": True,
            "halliday_justification": "Material process confirmé.",
        }]
    })
    results = _identify_capacities(
        [minimal_block],
        llm_call_fn=lambda _: response,
    )
    assert len(results) == 1
    assert results[0].capacity_id == "I3a"
    assert results[0].halliday_consistent is True


# ---------------------------------------------------------------------------
# Fusion — _merge_analyses
# ---------------------------------------------------------------------------

def test_merge_analyses_computes_aggregate_confidence(minimal_block):
    cap = CapacityIdentification(
        block_id="r0_0",
        capacity_id="I3a",
        level_code="I",
        halliday_consistent=True,
        halliday_justification="OK",
    )
    mat = MaturityEvaluation(
        block_id="r0_0",
        maturity_level="satisfaisant",
        confidence=0.8,
        interpretation="Analyse ok.",
    )
    results = _merge_analyses([minimal_block], [cap], [mat])
    assert len(results) == 1
    assert abs(results[0].aggregate_confidence - 0.5 * 0.8) < 1e-9


def test_merge_analyses_halliday_inconsistent_lowers_confidence(minimal_block):
    """halliday_consistent=False → cap_conf=0.3 au lieu de 0.5."""
    cap = CapacityIdentification(
        block_id="r0_0",
        capacity_id="I3a",
        level_code="I",
        halliday_consistent=False,
        halliday_justification="Registre incorrect.",
    )
    mat = MaturityEvaluation(
        block_id="r0_0",
        maturity_level="insuffisant",
        confidence=0.6,
        interpretation="Analyse.",
    )
    results = _merge_analyses([minimal_block], [cap], [mat])
    assert abs(results[0].aggregate_confidence - 0.3 * 0.6) < 1e-9


def test_merge_analyses_skips_incomplete_blocks(minimal_block):
    """Bloc sans correspondance dans les analyses doit être ignoré."""
    cap = CapacityIdentification(
        block_id="r99_0",  # block_id différent → pas de correspondance
        capacity_id="I1a",
        level_code="I",
        halliday_consistent=True,
        halliday_justification="",
    )
    mat = MaturityEvaluation(
        block_id="r99_0",
        maturity_level="satisfaisant",
        confidence=0.7,
        interpretation="",
    )
    results = _merge_analyses([minimal_block], [cap], [mat])
    assert results == []


# ---------------------------------------------------------------------------
# AnalyzedExtract — champs halliday
# ---------------------------------------------------------------------------

def test_analyzed_extract_has_halliday_fields():
    """AnalyzedExtract doit accepter les champs halliday_ok et halliday_note."""
    from r6_navigator.services.ai_analyze import AnalyzedExtract

    ex = AnalyzedExtract(
        text="test",
        tag="I3a",
        capacity_id="I3a",
        maturity_level="satisfaisant",
        confidence=0.8,
        interpretation="ok",
        halliday_ok=True,
        halliday_note=None,
    )
    assert ex.halliday_ok is True
    assert ex.halliday_note is None


def test_analyzed_extract_halliday_defaults_to_none():
    """Les anciens appels sans halliday_ok/halliday_note restent valides."""
    from r6_navigator.services.ai_analyze import AnalyzedExtract

    ex = AnalyzedExtract(
        text="test",
        tag=None,
        capacity_id=None,
        maturity_level="",
        confidence=0.5,
        interpretation="",
    )
    assert ex.halliday_ok is None
    assert ex.halliday_note is None
