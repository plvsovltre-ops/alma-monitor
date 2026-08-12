"""Fail-closed access layer for a versioned ALMA Legal Core release."""

from __future__ import annotations

import copy
import json
from datetime import date
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
CONTROLLED_PILOT_REVIEWER = "Yernar Sailybayev"


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
            review_record = json.loads(
                (self.release_path.parent / "review.json").read_text(encoding="utf-8")
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
        if self.release.get("release", {}).get("status") != manifest.get("status"):
            raise IntegrityError("Manifest and card release statuses do not match")
        if sources_document.get("release_id") != release_id:
            raise IntegrityError("Source registry and card release IDs do not match")
        if manifest.get("card_count") != len(cards):
            raise IntegrityError("Manifest card count is incorrect")
        if manifest.get("source_count") != len(sources):
            raise IntegrityError("Manifest source count is incorrect")

        self._validate_review_record(review_record, manifest, release_id, len(cards))
        self.review_record = review_record

    @staticmethod
    def _validate_review_record(
        review_record: Any,
        manifest: dict[str, Any],
        release_id: str,
        card_count: int,
    ) -> None:
        if not isinstance(review_record, dict):
            raise IntegrityError("Legal Core review record must be an object")
        if review_record.get("release_id") != release_id:
            raise IntegrityError("Review record and card release IDs do not match")
        if review_record.get("card_count") != card_count:
            raise IntegrityError("Review record card count is incorrect")

        reviewer = review_record.get("reviewer")
        if not isinstance(reviewer, dict):
            raise IntegrityError("Legal Core reviewer record is invalid")
        if not isinstance(reviewer.get("name"), str) or not reviewer["name"].strip():
            raise IntegrityError("Legal Core reviewer name is missing")
        if reviewer["name"].strip() != CONTROLLED_PILOT_REVIEWER:
            raise IntegrityError("Controlled pilot reviewer is not authorized")
        if reviewer.get("capacity") != "AUTHOR_AND_LEGAL_EDITOR":
            raise IntegrityError("Legal Core reviewer capacity is unsupported")

        try:
            date.fromisoformat(review_record.get("reviewed_on"))
        except (TypeError, ValueError) as exc:
            raise IntegrityError("Legal Core review date is invalid") from exc

        reviewed_artifacts = review_record.get("reviewed_artifacts")
        expected_artifacts = {
            name: manifest["artifacts"][name]
            for name in ("cards.json", "sources.json")
        }
        if reviewed_artifacts != expected_artifacts:
            raise IntegrityError("Review record does not bind the reviewed artifacts")

        if review_record.get("decision") != "CONTROLLED_PILOT_APPROVED":
            raise IntegrityError("Controlled pilot legal review is not approved")
        if review_record.get("scope") != "CONTROLLED_PILOT_ONLY":
            raise IntegrityError("Legal review scope is not controlled-pilot-only")
        if (
            review_record.get("independent_lawyer_review_status")
            != "INDEPENDENT_LAWYER_REVIEW_PENDING"
        ):
            raise IntegrityError(
                "Independent lawyer approval cannot be asserted by this release"
            )
        if (
            review_record.get("public_release_status")
            != "PUBLIC_LEGAL_RELEASE_BLOCKED"
        ):
            raise IntegrityError("Public legal release must remain blocked")

        expected_manifest_review = {
            "status": "CONTROLLED_PILOT_APPROVED",
            "owner_review_status": "OWNER_ACCEPTED",
            "legal_editor_review_status": "AUTHOR_LEGAL_REVIEW_APPROVED",
            "legal_reviewer_name": reviewer["name"],
            "independent_lawyer_review_status": review_record[
                "independent_lawyer_review_status"
            ],
            "public_legal_release_status": review_record["public_release_status"],
        }
        for field, expected in expected_manifest_review.items():
            if manifest.get(field) != expected:
                raise IntegrityError(
                    f"Manifest legal review metadata is inconsistent: {field}"
                )

    def rule_ids(self) -> tuple[str, ...]:
        return tuple(self._cards)

    def require_card(
        self,
        rule_id: str,
        *,
        use_case: str = "controlled_pilot",
    ) -> dict[str, Any]:
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

        if use_case == "controlled_pilot":
            if (
                review.get("pilot_status") != "PILOT_ELIGIBLE"
                or review.get("legal_editor_status")
                != "AUTHOR_LEGAL_REVIEW_APPROVED"
                or self.review_record.get("decision")
                != "CONTROLLED_PILOT_APPROVED"
            ):
                raise CardBlockedError(
                    f"Card is blocked for controlled pilot use: {rule_id}"
                )
        elif use_case == "public_legal_release":
            if (
                review.get("independent_lawyer_status")
                != "INDEPENDENT_LAWYER_REVIEW_APPROVED"
                or review.get("public_release_status")
                != "PUBLIC_LEGAL_RELEASE_APPROVED"
                or self.review_record.get("independent_lawyer_review_status")
                != "INDEPENDENT_LAWYER_REVIEW_APPROVED"
                or self.review_record.get("public_release_status")
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
        use_case: str = "controlled_pilot",
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
