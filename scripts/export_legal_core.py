#!/usr/bin/env python3
"""Export an owner-reviewed ALMA Legal Core sheet CSV without an API."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from legal_core.integrity import (
    IntegrityError,
    canonical_card_hash,
    canonical_official_url,
)


REQUIRED_COLUMNS = {
    "Норма",
    "Что говорит карточка",
    "Согласен",
    "Не согласен",
    "Статус",
    "rule_id",
    "card_hash",
    "source_id",
    "backend_action",
    "legal_release_gate",
    "review_view_version",
    "official_url",
}
CARD_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
RULE_ID = re.compile(r"^kz-[a-z0-9-]+$")
RELEASE_ID = re.compile(r"^kz-[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.]+)?$")
CHECKBOX_VALUES = {"TRUE": True, "ИСТИНА": True, "FALSE": False, "ЛОЖЬ": False}


@dataclass(frozen=True)
class ReleaseMetadata:
    release_id: str
    review_date: str
    review_view_version: str
    source_spreadsheet_id: str
    source_review_view: str
    expected_card_count: int
    legal_reviewer_name: str
    legal_review_date: str

    def validate(self) -> None:
        if not RELEASE_ID.fullmatch(self.release_id):
            raise ValueError(f"Invalid release ID: {self.release_id}")
        try:
            owner_review_date = date.fromisoformat(self.review_date)
        except (TypeError, ValueError) as exc:
            raise ValueError("Review date must use YYYY-MM-DD") from exc
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.review_date):
            raise ValueError("Review date must use YYYY-MM-DD")
        if self.expected_card_count < 1:
            raise ValueError("Expected card count must be positive")
        try:
            legal_review_date = date.fromisoformat(self.legal_review_date)
        except (TypeError, ValueError) as exc:
            raise ValueError("Legal review date must use YYYY-MM-DD") from exc
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.legal_review_date):
            raise ValueError("Legal review date must use YYYY-MM-DD")
        if legal_review_date < owner_review_date:
            raise ValueError("Legal review date cannot precede owner review date")
        for field_name in (
            "review_view_version",
            "source_spreadsheet_id",
            "source_review_view",
            "legal_reviewer_name",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"Release metadata is empty: {field_name}")


def checkbox(value: str | None, *, row: int, column: str) -> bool:
    normalized = (value or "").strip().upper()
    try:
        return CHECKBOX_VALUES[normalized]
    except KeyError as exc:
        raise ValueError(f"Row {row}: invalid checkbox value in {column}: {value!r}") from exc


def validated_official_url(value: str | None) -> str:
    original = (value or "").strip()
    try:
        canonical_official_url(original)
    except IntegrityError as exc:
        raise ValueError(str(exc)) from exc
    return original


def load_cards(csv_path: Path, metadata: ReleaseMetadata) -> list[dict]:
    metadata.validate()
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        raw_reader = csv.reader(handle)
        header = None
        header_row = 0
        for header_row, values in enumerate(raw_reader, start=1):
            if REQUIRED_COLUMNS.issubset(set(values)):
                header = values
                break
        if header is None:
            raise ValueError(
                "CSV does not contain the Legal Core review header: "
                + ", ".join(sorted(REQUIRED_COLUMNS))
            )
        reader = csv.DictReader(handle, fieldnames=header)

        cards = []
        seen = set()
        for sheet_row, row in enumerate(reader, start=header_row + 1):
            rule_id = (row.get("rule_id") or "").strip()
            if not rule_id:
                continue
            if not RULE_ID.fullmatch(rule_id):
                raise ValueError(f"Row {sheet_row}: invalid rule_id {rule_id!r}")
            if rule_id in seen:
                raise ValueError(f"Row {sheet_row}: duplicate rule_id {rule_id}")
            seen.add(rule_id)

            agree = checkbox(row.get("Согласен"), row=sheet_row, column="Согласен")
            disagree = checkbox(
                row.get("Не согласен"),
                row=sheet_row,
                column="Не согласен",
            )
            if not agree or disagree:
                raise ValueError(f"Row {sheet_row}: owner acceptance is incomplete")
            if (row.get("backend_action") or "").strip() != "ACCEPT_CARD":
                raise ValueError(f"Row {sheet_row}: backend action is not ACCEPT_CARD")
            if (row.get("Статус") or "").strip() != "СОГЛАСОВАНО ВЛАДЕЛЬЦЕМ":
                raise ValueError(f"Row {sheet_row}: owner status is not accepted")
            if (row.get("review_view_version") or "").strip() != metadata.review_view_version:
                raise ValueError(f"Row {sheet_row}: unexpected review view version")
            release_gates = {
                token.strip()
                for token in (row.get("legal_release_gate") or "").split(";")
                if token.strip()
            }
            if "LEGAL_RELEASE_BLOCKED" not in release_gates:
                raise ValueError(f"Row {sheet_row}: public legal release must stay blocked")

            provision = (row.get("Норма") or "").strip()
            safe_summary = (row.get("Что говорит карточка") or "").strip()
            source_id = (row.get("source_id") or "").strip()
            official_url = validated_official_url(row.get("official_url"))
            if not provision or not safe_summary or not source_id:
                raise ValueError(f"Row {sheet_row}: required card text is empty")
            if not RULE_ID.fullmatch(source_id):
                raise ValueError(f"Row {sheet_row}: invalid source_id {source_id!r}")

            card = {
                "rule_id": rule_id,
                "jurisdiction": "KZ",
                "provision": provision,
                "safe_summary": safe_summary,
                "source_id": source_id,
                "official_url": official_url,
                "card_hash": (row.get("card_hash") or "").strip(),
                "review": {
                    "owner_status": "OWNER_ACCEPTED",
                    "pilot_status": "PILOT_ELIGIBLE",
                    "legal_editor_status": "AUTHOR_LEGAL_REVIEW_APPROVED",
                    "independent_lawyer_status": (
                        "INDEPENDENT_LAWYER_REVIEW_PENDING"
                    ),
                    "public_release_status": "PUBLIC_LEGAL_RELEASE_BLOCKED",
                    "sheet_status": "СОГЛАСОВАНО ВЛАДЕЛЬЦЕМ",
                    "review_view_version": metadata.review_view_version,
                    "source_checked_at": metadata.review_date,
                    "source_change_status": "MANUAL_BASELINE_ONLY",
                },
                "editorial_comment": (
                    row.get("Комментарий (необязательно)") or ""
                ).strip()
                or None,
                "source_sheet_row": sheet_row,
            }
            card_hash = card["card_hash"]
            if not CARD_HASH.fullmatch(card_hash):
                raise ValueError(f"Row {sheet_row}: invalid card hash")
            expected_hash = canonical_card_hash(card)
            if card_hash != expected_hash:
                raise ValueError(
                    f"Row {sheet_row}: card hash does not match reviewed content"
                )
            cards.append(card)
    if not cards:
        raise ValueError("CSV does not contain Legal Core cards")
    if len(cards) != metadata.expected_card_count:
        raise ValueError(
            f"Expected {metadata.expected_card_count} cards, found {len(cards)}"
        )
    return cards


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_release(
    cards: list[dict],
    output_dir: Path,
    metadata: ReleaseMetadata,
) -> None:
    metadata.validate()
    if len(cards) != metadata.expected_card_count:
        raise ValueError(
            f"Expected {metadata.expected_card_count} cards, found {len(cards)}"
        )
    if output_dir.exists():
        if not output_dir.is_dir() or any(output_dir.iterdir()):
            raise FileExistsError(f"Release output is not empty: {output_dir}")
    else:
        output_dir.mkdir(parents=True)

    grouped: dict[str, dict] = defaultdict(lambda: {"rule_count": 0, "urls": set()})
    for card in cards:
        if card.get("card_hash") != canonical_card_hash(card):
            raise ValueError(f"Card hash mismatch: {card.get('rule_id')}")
        grouped[card["source_id"]]["rule_count"] += 1
        grouped[card["source_id"]]["urls"].add(
            canonical_official_url(card["official_url"])
        )
    for source_id, data in grouped.items():
        if len(data["urls"]) != 1:
            raise ValueError(f"One source_id maps to multiple documents: {source_id}")

    card_document = {
        "schema_version": "1.0",
        "release": {
            "id": metadata.release_id,
            "jurisdiction": "KZ",
            "status": "CONTROLLED_PILOT_APPROVED",
            "generated_on": metadata.review_date,
            "source_spreadsheet_id": metadata.source_spreadsheet_id,
            "source_review_view": metadata.source_review_view,
            "authorship": "ALMA was initiated and originally designed by Yernar Sailybayev in Almaty, Kazakhstan.",
        },
        "cards": cards,
    }
    sources = {
        "release_id": metadata.release_id,
        "sources": [
            {
                "source_id": source_id,
                "official_url": next(iter(data["urls"])),
                "rule_count": data["rule_count"],
                "monitoring_status": "MANUAL_BASELINE_ONLY",
                "last_manual_check": metadata.review_date,
            }
            for source_id, data in sorted(grouped.items())
        ],
    }

    artifacts = {
        "cards.json": json_bytes(card_document),
        "sources.json": json_bytes(sources),
    }
    reviewed_hashes = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in artifacts.items()
    }
    review_record = {
        "release_id": metadata.release_id,
        "card_count": len(cards),
        "decision": "CONTROLLED_PILOT_APPROVED",
        "scope": "CONTROLLED_PILOT_ONLY",
        "reviewed_on": metadata.legal_review_date,
        "reviewer": {
            "name": metadata.legal_reviewer_name,
            "capacity": "AUTHOR_AND_LEGAL_EDITOR",
        },
        "reviewed_artifacts": reviewed_hashes,
        "independent_lawyer_review_status": (
            "INDEPENDENT_LAWYER_REVIEW_PENDING"
        ),
        "public_release_status": "PUBLIC_LEGAL_RELEASE_BLOCKED",
        "statement": (
            "The reviewer approved the reviewed cards for controlled use by "
            "ALMA during a private pilot. This is not an independent legal "
            "review or approval for a public legal release."
        ),
    }
    artifacts["review.json"] = json_bytes(review_record)
    for name, content in artifacts.items():
        (output_dir / name).write_bytes(content)

    checksums = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in artifacts.items()
    }
    manifest = {
        "release_id": metadata.release_id,
        "status": "CONTROLLED_PILOT_APPROVED",
        "card_count": len(cards),
        "source_count": len(sources["sources"]),
        "owner_review_status": "OWNER_ACCEPTED",
        "legal_editor_review_status": "AUTHOR_LEGAL_REVIEW_APPROVED",
        "legal_reviewer_name": metadata.legal_reviewer_name,
        "independent_lawyer_review_status": (
            "INDEPENDENT_LAWYER_REVIEW_PENDING"
        ),
        "public_legal_release_status": "PUBLIC_LEGAL_RELEASE_BLOCKED",
        "artifacts": checksums,
    }
    manifest_bytes = json_bytes(manifest)
    (output_dir / "manifest.json").write_bytes(manifest_bytes)
    checksums["manifest.json"] = hashlib.sha256(manifest_bytes).hexdigest()
    checksum_text = "".join(
        f"{digest}  {name}\n" for name, digest in sorted(checksums.items())
    )
    (output_dir / "SHA256SUMS").write_text(checksum_text, encoding="ascii")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review_csv", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--review-date", required=True)
    parser.add_argument("--review-view-version", required=True)
    parser.add_argument("--source-spreadsheet-id", required=True)
    parser.add_argument("--source-review-view", required=True)
    parser.add_argument("--expected-card-count", required=True, type=int)
    parser.add_argument("--legal-reviewer-name", required=True)
    parser.add_argument("--legal-review-date", required=True)
    return parser.parse_args(argv[1:])


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    metadata = ReleaseMetadata(
        release_id=args.release_id,
        review_date=args.review_date,
        review_view_version=args.review_view_version,
        source_spreadsheet_id=args.source_spreadsheet_id,
        source_review_view=args.source_review_view,
        expected_card_count=args.expected_card_count,
        legal_reviewer_name=args.legal_reviewer_name,
        legal_review_date=args.legal_review_date,
    )
    try:
        cards = load_cards(args.review_csv, metadata)
        write_release(cards, args.output_dir, metadata)
    except (OSError, ValueError, IntegrityError) as exc:
        print(f"Legal Core export failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
