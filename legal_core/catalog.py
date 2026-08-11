"""Fail-closed access layer for a versioned ALMA Legal Core release."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable

from .integrity import (
    IntegrityError,
    canonical_card_hash,
    canonical_official_url,
    verify_release_bundle,
)


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
        manifest = verify_release_bundle(self.release_path)
        try:
            with self.release_path.open(encoding="utf-8") as handle:
                self.release = json.load(handle)
            sources_document = json.loads(
                (self.release_path.parent / "sources.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise IntegrityError("Legal Core release JSON is invalid") from exc

        cards = self.release.get("cards")
        if not isinstance(cards, list):
            raise IntegrityError("Legal Core release does not contain a card list")

        self._cards: dict[str, dict[str, Any]] = {}
        source_counts: dict[str, int] = {}
        source_urls: dict[str, set[str]] = {}
        for card in cards:
            if not isinstance(card, dict):
                raise IntegrityError("Legal Core card must be an object")
            rule_id = card.get("rule_id")
            if not rule_id:
                raise IntegrityError("Legal Core card is missing rule_id")
            if rule_id in self._cards:
                raise IntegrityError(f"Duplicate Legal Core rule_id: {rule_id}")
            if card.get("card_hash") != canonical_card_hash(card):
                raise IntegrityError(f"Legal Core card hash mismatch: {rule_id}")
            self._cards[rule_id] = card
            source_id = card.get("source_id")
            source_counts[source_id] = source_counts.get(source_id, 0) + 1
            source_urls.setdefault(source_id, set()).add(
                canonical_official_url(card.get("official_url"))
            )

        sources = sources_document.get("sources")
        if not isinstance(sources, list):
            raise IntegrityError("Legal Core source registry is invalid")
        registered: dict[str, dict[str, Any]] = {}
        for source in sources:
            if not isinstance(source, dict) or not source.get("source_id"):
                raise IntegrityError("Legal Core source entry is invalid")
            source_id = source["source_id"]
            if source_id in registered:
                raise IntegrityError(f"Duplicate Legal Core source_id: {source_id}")
            registered[source_id] = source

        if set(registered) != set(source_counts):
            raise IntegrityError("Card sources and source registry do not match")
        for source_id, source in registered.items():
            if source.get("rule_count") != source_counts[source_id]:
                raise IntegrityError(f"Source rule count mismatch: {source_id}")
            urls = source_urls[source_id]
            if len(urls) != 1 or canonical_official_url(source.get("official_url")) not in urls:
                raise IntegrityError(f"Source URL mismatch: {source_id}")

        release_id = self.release.get("release", {}).get("id")
        if not release_id or manifest.get("release_id") != release_id:
            raise IntegrityError("Manifest and card release IDs do not match")
        if sources_document.get("release_id") != release_id:
            raise IntegrityError("Source registry and card release IDs do not match")
        if manifest.get("card_count") != len(cards):
            raise IntegrityError("Manifest card count is incorrect")
        if manifest.get("source_count") != len(sources):
            raise IntegrityError("Manifest source count is incorrect")

    def rule_ids(self) -> tuple[str, ...]:
        return tuple(self._cards)

    def require_card(self, rule_id: str, *, use_case: str = "pilot") -> dict[str, Any]:
        """Return an approved card or fail without attempting a substitute."""
        try:
            card = self._cards[rule_id]
        except KeyError as exc:
            raise UnknownRuleError(f"Unknown Legal Core rule_id: {rule_id}") from exc

        review = card.get("review", {})
        source_status = review.get("source_change_status")
        if source_status == "SOURCE_CHANGED_UNREVIEWED":
            raise SourceChangedError(
                f"Official source changed; editor review required: {rule_id}"
            )
        if source_status not in {"MANUAL_BASELINE_ONLY", "UNCHANGED"}:
            raise SourceChangedError(
                f"Official source status is not safe for use: {rule_id}"
            )
        if review.get("owner_status") != "OWNER_ACCEPTED":
            raise CardBlockedError(f"Owner review is incomplete: {rule_id}")

        if use_case == "pilot":
            if review.get("pilot_status") != "PILOT_ELIGIBLE":
                raise CardBlockedError(f"Card is blocked for pilot use: {rule_id}")
        elif use_case == "public_legal_release":
            if (
                review.get("lawyer_status") != "LAWYER_REVIEW_APPROVED"
                or review.get("public_release_status")
                != "PUBLIC_LEGAL_RELEASE_APPROVED"
            ):
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
