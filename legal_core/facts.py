"""Small fact-state primitives used by deterministic legal rules."""

from __future__ import annotations

from enum import Enum


class FactState(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


def normalize_fact_state(value: object) -> FactState:
    """Normalize a fact without converting an unknown value into an assumption."""
    if value is None or value == "":
        return FactState.UNKNOWN
    if isinstance(value, FactState):
        return value
    if value is True:
        return FactState.PRESENT
    if value is False:
        return FactState.ABSENT
    if isinstance(value, str):
        normalized = value.strip().upper()
        aliases = {
            "PRESENT": FactState.PRESENT,
            "ABSENT": FactState.ABSENT,
            "UNKNOWN": FactState.UNKNOWN,
        }
        if normalized in aliases:
            return aliases[normalized]
    raise ValueError("Fact state must be PRESENT, ABSENT, UNKNOWN, true, false, or null")
