"""Fail-closed access layer for a versioned ALMA Legal Core release."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_RELEASE = (
    Path(__file__).resolve().parent
    / "releases"
    / "kz"
    / "0.1.0-rc1"
    / "cards.json"
)


class LegalCoreError(RuntimeError):
    """Base error for deterministic Legal Core failures."""


class UnknownRuleError(LegalCoreError):
    """Raised when a caller requests a rule that is not in the release."""


class CardBlockedError(LegalCoreError):
    """Raised when a known card is not approved for the requested use."""


class SourceChangedError(CardBlockedError):
    """Raised when an official source changed after the last review."""


class LegalCoreCatalog:
    """Load cards and expose citations only by an existing ``rule_id``.

    The catalog deliberately has no free-text article selection method. A caller
    must supply an identifier already selected by deterministic application
    rules. This prevents an LLM from inventing a citation.
    """

    def __init__(self, release_path: str | Path = DEFAULT_RELEASE):
        self.release_path = Path(release_path)
        with self.release_path.open(encoding="utf-8") as handle:
            self.release = json.load(handle)

        cards = self.release.get("cards")
        if not isinstance(cards, list):
            raise LegalCoreError("Legal Core release does not contain a card list")

        self._cards: dict[str, dict[str, Any]] = {}
        for card in cards:
            rule_id = card.get("rule_id")
            if not rule_id:
                raise LegalCoreError("Legal Core card is missing rule_id")
            if rule_id in self._cards:
                raise LegalCoreError(f"Duplicate Legal Core rule_id: {rule_id}")
            self._cards[rule_id] = card

    def rule_ids(self) -> tuple[str, ...]:
        return tuple(self._cards)

    def require_card(self, rule_id: str, *, use_case: str = "pilot") -> dict[str, Any]:
        """Return an approved card or fail without attempting a substitute."""
        try:
            card = self._cards[rule_id]
        except KeyError as exc:
            raise UnknownRuleError(f"Unknown Legal Core rule_id: {rule_id}") from exc

        review = card.get("review", {})
        if review.get("source_change_status") == "SOURCE_CHANGED_UNREVIEWED":
            raise SourceChangedError(
                f"Official source changed; editor review required: {rule_id}"
            )
        if review.get("owner_status") != "OWNER_ACCEPTED":
            raise CardBlockedError(f"Owner review is incomplete: {rule_id}")

        if use_case == "pilot":
            if review.get("pilot_status") != "PILOT_ELIGIBLE":
                raise CardBlockedError(f"Card is blocked for pilot use: {rule_id}")
        elif use_case == "public_legal_release":
            if review.get("public_release_status") != "PUBLIC_LEGAL_RELEASE_APPROVED":
                raise CardBlockedError(
                    f"Card is blocked for public legal release: {rule_id}"
                )
        else:
            raise ValueError(f"Unsupported Legal Core use case: {use_case}")

        return copy.deepcopy(card)

    def citations(
        self,
        rule_ids: Iterable[str],
        *,
        use_case: str = "pilot",
    ) -> list[dict[str, str]]:
        """Resolve citations exclusively from approved cards."""
        resolved = []
        for rule_id in rule_ids:
            card = self.require_card(rule_id, use_case=use_case)
            resolved.append(
                {
                    "rule_id": card["rule_id"],
                    "provision": card["provision"],
                    "official_url": card["official_url"],
                    "safe_summary": card["safe_summary"],
                }
            )
        return resolved
