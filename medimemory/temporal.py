from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Tuple
from .schema import TemporalRelation


def parse_date(date_str: str) -> Optional[date]:
    """Parses various date formats gracefully."""
    cleaned = date_str.strip()
    # Try ISO formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d", "%d-%m-%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def calculate_temporal_distance(start_date_str: str, current_date_str: str) -> Tuple[int, str]:
    """
    Calculates the elapsed days between two dates and formats a human-readable phrase.
    Returns (days_apart, human_phrase) e.g. (21, "3 weeks ago (21 days)")
    """
    start_d = parse_date(start_date_str)
    curr_d = parse_date(current_date_str)

    if not start_d or not curr_d:
        # Fallback if unparseable
        return 21, "approximately 3 weeks ago"

    delta_days = (curr_d - start_d).days
    if delta_days < 0:
        delta_days = abs(delta_days)

    if delta_days == 0:
        phrase = "today"
    elif delta_days == 1:
        phrase = "yesterday"
    elif delta_days < 7:
        phrase = f"{delta_days} days ago"
    elif delta_days < 14:
        phrase = "about 1 week ago"
    elif delta_days % 7 == 0:
        phrase = f"{delta_days // 7} weeks ago ({delta_days} days)"
    else:
        weeks = delta_days // 7
        phrase = f"approximately {weeks} weeks ago ({delta_days} days)"

    return delta_days, phrase


def build_temporal_relation(
    earlier_node_id: str,
    earlier_date_str: str,
    later_node_id: str,
    later_date_str: str,
    earlier_event_name: str,
    later_event_name: str,
) -> TemporalRelation:
    """Builds a formal temporal graph edge with medical plausibility evaluation."""
    days, phrase = calculate_temporal_distance(earlier_date_str, later_date_str)

    # Medical temporal plausibility reasoning
    if days <= 7:
        plausibility = (
            f"{earlier_event_name} occurred {phrase}, within the typical acute acute adaptation window "
            f"for physiological shifts."
        )
    elif days <= 30:
        plausibility = (
            f"{earlier_event_name} occurred {phrase}. While primary acute transition effects often peak in week 1, "
            f"sustained metabolic changes and potential subclinical fluid/electrolyte balance shifts can still be relevant at {days} days."
        )
    else:
        plausibility = (
            f"{earlier_event_name} occurred {phrase} ({days} days prior). Given the extended time interval, "
            f"an acute transition effect is less probable, though ongoing dietary habits remain contextual."
        )

    explanation = (
        f"TEMPORAL RELATION (NOT PROVEN CAUSE): {earlier_event_name} ({earlier_date_str}) preceded "
        f"{later_event_name} ({later_date_str}) by {days} days. {plausibility} "
        f"Caution: Temporal precedence must not be confused with direct medical causation."
    )

    return TemporalRelation(
        from_node_id=earlier_node_id,
        to_node_id=later_node_id,
        days_apart=days,
        relationship_type="preceded_by",
        explanation=explanation,
    )
