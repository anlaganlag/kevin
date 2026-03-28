"""Map GitHub Issue labels to a Blueprint ID.

The intent classifier looks at issue labels and returns the best-matching
blueprint. Priority order: specific task labels > type labels > default.
"""

from __future__ import annotations

from dataclasses import dataclass

from kevin.config import DEFAULT_INTENT_MAP, DEFAULT_LABEL_ALIASES, KEVIN_TRIGGER_LABEL


@dataclass(frozen=True)
class Intent:
    """Resolved intent from issue labels."""

    blueprint_id: str
    matched_label: str
    confidence: str  # "exact" | "alias"


def classify(
    labels: list[str],
    intent_map: dict[str, str] | None = None,
    label_aliases: dict[str, str] | None = None,
) -> Intent | None:
    """Return the Intent for a set of issue labels, or None if not a Kevin issue.

    Rules:
    1. Issue must have the KEVIN_TRIGGER_LABEL ("kevin").
    2. First matching label (by intent_map key order) wins → confidence="exact".
    3. If no exact match, check label_aliases → confidence="alias".
    4. If nothing matches, returns None.
    """
    if KEVIN_TRIGGER_LABEL not in labels:
        return None

    mapping = intent_map or DEFAULT_INTENT_MAP
    aliases = label_aliases or DEFAULT_LABEL_ALIASES
    label_set = set(labels)

    # Pass 1: exact match against intent_map keys
    for label, blueprint_id in mapping.items():
        if label in label_set:
            return Intent(
                blueprint_id=blueprint_id,
                matched_label=label,
                confidence="exact",
            )

    # Pass 2: alias match — resolve alias to intent_map key, then look up blueprint
    for label in labels:
        canonical = aliases.get(label)
        if canonical and canonical in mapping:
            return Intent(
                blueprint_id=mapping[canonical],
                matched_label=label,
                confidence="alias",
            )

    return None
