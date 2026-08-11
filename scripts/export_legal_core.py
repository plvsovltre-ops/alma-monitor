#!/usr/bin/env python3
"""Export an owner-reviewed ALMA Legal Core sheet CSV without an API."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


RELEASE_ID = "kz-0.1.0-rc1"
REVIEW_DATE = "2026-08-11"
REVIEW_VIEW_VERSION = "1.2"
SOURCE_SPREADSHEET_ID = "1OfPXFwk3RnrJP6H6FVsv_KIRpX-9Gy-ULkWom1ZThaQ"
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


def truthy(value: str) -> bool:
    return value.strip().upper() in {"TRUE", "ИСТИНА", "1", "YES"}


def canonical_url(value: str) -> str:
    parts = urlsplit(value.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in {"adilet.zan.kz", "www.adilet.zan.kz"}:
        raise ValueError(f"Official source is not an Adilet HTTPS URL: {value}")
    return urlunsplit(("https", "adilet.zan.kz", parts.path, parts.query, ""))


def validated_official_url(value: str) -> str:
    original = value.strip()
    canonical_url(original)
    return original


def load_cards(csv_path: Path) -> list[dict]:
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
            rule_id = row["rule_id"].strip()
            if not rule_id:
                continue
            if not RULE_ID.fullmatch(rule_id):
                raise ValueError(f"Row {sheet_row}: invalid rule_id {rule_id!r}")
            if rule_id in seen:
                raise ValueError(f"Row {sheet_row}: duplicate rule_id {rule_id}")
            seen.add(rule_id)

            if not truthy(row["Согласен"]) or truthy(row["Не согласен"]):
                raise ValueError(f"Row {sheet_row}: owner acceptance is incomplete")
            if row["backend_action"].strip() != "ACCEPT_CARD":
                raise ValueError(f"Row {sheet_row}: backend action is not ACCEPT_CARD")
            if row["Статус"].strip() != "СОГЛАСОВАНО ВЛАДЕЛЬЦЕМ":
                raise ValueError(f"Row {sheet_row}: owner status is not accepted")
            if row["review_view_version"].strip() != REVIEW_VIEW_VERSION:
                raise ValueError(f"Row {sheet_row}: unexpected review view version")
            if "LEGAL_RELEASE_BLOCKED" not in row["legal_release_gate"]:
                raise ValueError(f"Row {sheet_row}: public legal release must stay blocked")

            card_hash = row["card_hash"].strip()
            if not CARD_HASH.fullmatch(card_hash):
                raise ValueError(f"Row {sheet_row}: invalid card hash")
            provision = row["Норма"].strip()
            safe_summary = row["Что говорит карточка"].strip()
            source_id = row["source_id"].strip()
            if not provision or not safe_summary or not source_id:
                raise ValueError(f"Row {sheet_row}: required card text is empty")

            cards.append(
                {
                    "rule_id": rule_id,
                    "jurisdiction": "KZ",
                    "provision": provision,
                    "safe_summary": safe_summary,
                    "source_id": source_id,
                    "official_url": validated_official_url(row["official_url"]),
                    "card_hash": card_hash,
                    "review": {
                        "owner_status": "OWNER_ACCEPTED",
                        "pilot_status": "PILOT_ELIGIBLE",
                        "lawyer_status": "LAWYER_REVIEW_PENDING",
                        "public_release_status": "PUBLIC_LEGAL_RELEASE_BLOCKED",
                        "sheet_status": "СОГЛАСОВАНО ВЛАДЕЛЬЦЕМ",
                        "review_view_version": REVIEW_VIEW_VERSION,
                        "source_checked_at": REVIEW_DATE,
                        "source_change_status": "MANUAL_BASELINE_ONLY",
                    },
                    "editorial_comment": row.get("Комментарий (необязательно)", "").strip() or None,
                    "source_sheet_row": sheet_row,
                }
            )
    if not cards:
        raise ValueError("CSV does not contain Legal Core cards")
    return cards


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_release(cards: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    card_document = {
        "schema_version": "1.0",
        "release": {
            "id": RELEASE_ID,
            "jurisdiction": "KZ",
            "status": "PILOT_RELEASE_CANDIDATE",
            "generated_on": REVIEW_DATE,
            "source_spreadsheet_id": SOURCE_SPREADSHEET_ID,
            "source_review_view": "ALMA Legal Review — Kazakhstan v1.2",
            "authorship": "ALMA was initiated and originally designed by Yernar Sailybayev in Almaty, Kazakhstan.",
        },
        "cards": cards,
    }

    grouped: dict[str, dict] = defaultdict(lambda: {"rule_count": 0, "urls": set()})
    for card in cards:
        grouped[card["source_id"]]["rule_count"] += 1
        grouped[card["source_id"]]["urls"].add(canonical_url(card["official_url"]))
    sources = {
        "release_id": RELEASE_ID,
        "sources": [
            {
                "source_id": source_id,
                "official_url": sorted(data["urls"])[0],
                "rule_count": data["rule_count"],
                "monitoring_status": "MANUAL_BASELINE_ONLY",
                "last_manual_check": REVIEW_DATE,
            }
            for source_id, data in sorted(grouped.items())
        ],
    }

    artifacts = {
        "cards.json": json_bytes(card_document),
        "sources.json": json_bytes(sources),
    }
    for name, content in artifacts.items():
        (output_dir / name).write_bytes(content)

    checksums = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in artifacts.items()
    }
    manifest = {
        "release_id": RELEASE_ID,
        "status": "PILOT_RELEASE_CANDIDATE",
        "card_count": len(cards),
        "source_count": len(sources["sources"]),
        "owner_review_status": "OWNER_ACCEPTED",
        "lawyer_review_status": "LAWYER_REVIEW_PENDING",
        "public_legal_release_status": "PUBLIC_LEGAL_RELEASE_BLOCKED",
        "artifacts": checksums,
    }
    manifest_bytes = json_bytes(manifest)
    (output_dir / "manifest.json").write_bytes(manifest_bytes)
    checksums["manifest.json"] = hashlib.sha256(manifest_bytes).hexdigest()
    checksum_text = "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items()))
    (output_dir / "SHA256SUMS").write_text(checksum_text, encoding="ascii")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: export_legal_core.py REVIEW.csv OUTPUT_DIR", file=sys.stderr)
        return 2
    try:
        write_release(load_cards(Path(argv[1])), Path(argv[2]))
    except (OSError, ValueError) as exc:
        print(f"Legal Core export failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
