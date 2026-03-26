"""Map GitHub Issue labels to a Blueprint ID.

The intent classifier looks at issue labels and returns the best-matching
blueprint. Priority order: specific task labels > type labels > default.
"""

from __future__ import annotations

from dataclasses import dataclass

from kevin.config import DEFAULT_INTENT_MAP, KEVIN_TRIGGER_LABEL


@dataclass(frozen=True)
class Intent:
    """Resolved intent from issue labels."""

    blueprint_id: str
    matched_label: str
    confidence: str  # "exact" | "default"


def classify(
    labels: list[str],
    intent_map: dict[str, str] | None = None,
) -> Intent | None:
    """Return the Intent for a set of issue labels, or None if not a Kevin issue.

    Rules:
    1. Issue must have the KEVIN_TRIGGER_LABEL ("kevin").
    2. First matching label (by intent_map key order) wins.
    3. If no specific match, returns None (unknown task type).
    """
    if KEVIN_TRIGGER_LABEL not in labels:
        return None

    mapping = intent_map or DEFAULT_INTENT_MAP
    label_set = set(labels)

    for label, blueprint_id in mapping.items():
        if label in label_set:
            return Intent(
                blueprint_id=blueprint_id,
                matched_label=label,
                confidence="exact",
            )

    return None
