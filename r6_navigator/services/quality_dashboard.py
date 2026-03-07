"""Tableau de bord de qualité pour l'analyse de verbatims de mission."""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger("r6_navigator.quality_dashboard")


@dataclass
class QualityMetrics:
    """Métriques de qualité d'une analyse de mission."""
    total_blocks: int
    validated_blocks: int
    avg_confidence: float
    halliday_inconsistent_count: int
    capacity_ambiguity_count: int
    maturity_distribution: dict[str, int]


class QualityDashboard:
    """Tableau de bord de qualité pour les missions."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def get_mission_metrics(self, mission_id: int) -> QualityMetrics:
        """Calcule les métriques de qualité pour une mission."""
        # Import local — pattern du projet pour éviter les imports circulaires
        from r6_navigator.services.crud_mission import get_all_mission_interpretations

        with self.session_factory() as session:
            interpretations = get_all_mission_interpretations(session, mission_id)

            total = len(interpretations)
            validated = sum(
                1 for i in interpretations if i.status in ("validated", "corrected")
            )

            confidences = [i.confidence for i in interpretations if i.confidence is not None]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # halliday_ok est sur extract (relation lazy chargée dans la session ouverte)
            halliday_inconsistent = sum(
                1 for i in interpretations
                if i.extract is not None and i.extract.halliday_ok is False
            )

            capacity_ambiguous = sum(1 for i in interpretations if not i.capacity_id)

            maturity_dist: dict[str, int] = {}
            for i in interpretations:
                level = i.maturity_level or "unknown"
                maturity_dist[level] = maturity_dist.get(level, 0) + 1

            return QualityMetrics(
                total_blocks=total,
                validated_blocks=validated,
                avg_confidence=avg_confidence,
                halliday_inconsistent_count=halliday_inconsistent,
                capacity_ambiguity_count=capacity_ambiguous,
                maturity_distribution=maturity_dist,
            )

    def generate_quality_report(self, mission_id: int) -> str:
        """Génère un rapport de qualité au format Markdown."""
        metrics = self.get_mission_metrics(mission_id)

        lines = [
            "# Rapport de qualité d'analyse",
            "",
            f"**Mission ID** : {mission_id}",
            "",
            "## Métriques",
            "",
            "| Métrique | Valeur |",
            "|----------|--------|",
            f"| Total extraits | {metrics.total_blocks} |",
            f"| Validés | {metrics.validated_blocks} |",
            f"| Confiance moyenne | {metrics.avg_confidence:.1%} |",
            f"| Incohérences Halliday | {metrics.halliday_inconsistent_count} |",
            f"| Capacités ambiguës | {metrics.capacity_ambiguity_count} |",
            "",
            "## Distribution des maturités",
            "",
        ]
        for level, count in sorted(metrics.maturity_distribution.items()):
            lines.append(f"- {level} : {count}")

        return "\n".join(lines)
