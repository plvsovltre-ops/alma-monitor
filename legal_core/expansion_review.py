"""Hash-bound review package for a proposed ALMA Legal Core expansion.

The proposal is intentionally separate from the active runtime catalogs.  A
completed spreadsheet review therefore cannot activate legal rules or GIS
sources by itself.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROPOSAL = (
    PROJECT_ROOT
    / "legal_core"
    / "proposals"
    / "kz"
    / "0.2.0-rc1"
    / "proposal.json"
)

SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
INCIDENT_TYPES = {
    "waste",
    "logging",
    "construction",
    "soil_damage",
    "water_pollution",
}
OBJECT_TYPES = {
    "LEGAL_CARD",
    "LEGAL_CARD_STATUS",
    "CONTEXT_PROFILE",
    "POLICY_MAPPING",
    "AUTHORITY_ROUTE",
    "REQUEST_TEMPLATE_FAMILY",
    "SPATIAL_SOURCE",
}
OBJECT_TYPE_LABELS = {
    "LEGAL_CARD": "Карточка нормы",
    "LEGAL_CARD_STATUS": "Статус карточки",
    "CONTEXT_PROFILE": "Контекст территории",
    "POLICY_MAPPING": "Сопоставление сигнала",
    "AUTHORITY_ROUTE": "Маршрут органа",
    "REQUEST_TEMPLATE_FAMILY": "Основа просьбы",
    "SPATIAL_SOURCE": "Пространственный источник",
}
OBJECT_TYPE_BY_LABEL = {label: key for key, label in OBJECT_TYPE_LABELS.items()}
REVIEW_CSV_COLUMNS = (
    ("object_type", "Тип объекта"),
    ("object_id", "ID объекта"),
    ("admission_status", "Статус допуска"),
    ("official_source", "Официальный источник"),
    ("norm_or_decision", "Норма / решение"),
    ("review_text", "Текст для проверки"),
    ("object_sha256", "SHA-256 объекта"),
    ("agree", "Согласен"),
    ("disagree", "Не согласен"),
    ("comment", "Комментарий"),
)
REVIEW_CSV_FIELDS = tuple(label for _, label in REVIEW_CSV_COLUMNS)


class ExpansionReviewError(RuntimeError):
    """The proposal or a completed review is incomplete or changed."""


class ExpansionActivationBlockedError(ExpansionReviewError):
    """The proposal is not eligible for activation."""


def _normalized_checkbox(value: object) -> bool | None:
    normalized = str(value or "").strip().casefold()
    if normalized in {"true", "да", "yes", "1", "согласен", "agree"}:
        return True
    if normalized in {"false", "нет", "no", "0", "не согласен", "disagree"}:
        return False
    return None


def canonical_review_object_hash(row: dict[str, str]) -> str:
    payload = {
        field: str(row.get(field, "")).strip()
        for field in (
            "object_type",
            "object_id",
            "admission_status",
            "official_source",
            "norm_or_decision",
            "review_text",
        )
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class LegalCoreExpansionReview:
    """Validate and export one exact, non-active expansion proposal."""

    def __init__(self, proposal_path: str | Path = DEFAULT_PROPOSAL):
        self.proposal_path = Path(proposal_path)
        try:
            self.proposal: dict[str, Any] = json.loads(
                self.proposal_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExpansionReviewError("Expansion proposal is invalid") from exc
        self._validate_proposal()

    @property
    def proposal_id(self) -> str:
        return str(self.proposal["proposal_id"])

    @property
    def proposal_sha256(self) -> str:
        payload = {
            "proposal_id": self.proposal_id,
            "jurisdiction": self.proposal["jurisdiction"],
            "source_checked_on": self.proposal["source_checked_on"],
            "activation_gate": self.proposal["activation_gate"],
            "review_objects": [
                row["object_sha256"] for row in self.review_objects()
            ],
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _validate_proposal(self) -> None:
        proposal = self.proposal
        if proposal.get("schema_version") != "1.0":
            raise ExpansionReviewError("Expansion proposal schema is unsupported")
        if proposal.get("jurisdiction") != "KZ":
            raise ExpansionReviewError("Expansion proposal jurisdiction is invalid")
        if proposal.get("status") != "LEGAL_REVIEW_REQUIRED":
            raise ExpansionReviewError("Expansion proposal status must remain pending")
        if proposal.get("review_view_version") != "1.3":
            raise ExpansionReviewError("Expansion review view version is unsupported")
        if proposal.get("activation_gate") != (
            "BLOCKED_PENDING_AUTHOR_LEGAL_APPROVAL_AND_SPATIAL_PROVENANCE"
        ):
            raise ExpansionReviewError("Expansion activation gate is invalid")
        if set(proposal.get("incident_types") or ()) != INCIDENT_TYPES:
            raise ExpansionReviewError("Expansion incident types are incomplete")

        objects = proposal.get("review_objects")
        if not isinstance(objects, list) or not objects:
            raise ExpansionReviewError("Expansion review objects are missing")
        seen: set[tuple[str, str]] = set()
        for item in objects:
            if not isinstance(item, dict):
                raise ExpansionReviewError("Expansion review object is invalid")
            object_type = str(item.get("object_type") or "").strip()
            object_id = str(item.get("object_id") or "").strip()
            key = (object_type, object_id)
            if object_type not in OBJECT_TYPES or not object_id or key in seen:
                raise ExpansionReviewError("Expansion review object is unknown or duplicate")
            seen.add(key)
            source = str(item.get("official_source") or "").strip()
            if not source or any(
                part.strip() and not part.strip().startswith("https://")
                for part in source.split("|")
            ):
                raise ExpansionReviewError(
                    f"Expansion official source must use HTTPS: {object_id}"
                )
            for field in ("norm_or_decision", "review_text", "admission_status"):
                if not str(item.get(field) or "").strip():
                    raise ExpansionReviewError(
                        f"Expansion review field is missing: {object_id}/{field}"
                    )

        counts = Counter(item["object_type"] for item in objects)
        if counts["POLICY_MAPPING"] != 10:
            raise ExpansionReviewError("Expansion must map both contexts exactly")
        mapping_keys = {
            item["object_id"]
            for item in objects
            if item["object_type"] == "POLICY_MAPPING"
        }
        expected_mapping_keys = {
            f"{context}:{incident_type}"
            for context in (
                "ile_alatau_national_park",
                "almaty_water_protection_strip",
            )
            for incident_type in INCIDENT_TYPES
        }
        if mapping_keys != expected_mapping_keys:
            raise ExpansionReviewError("Expansion mapping matrix is incomplete")
        if "kz-oopt-48-1-5-8-other-harm" in json.dumps(
            [
                item
                for item in objects
                if item["object_type"] == "POLICY_MAPPING"
            ],
            ensure_ascii=False,
        ):
            raise ExpansionReviewError("Superseded OOPT card is mapped")

    def review_objects(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for item in self.proposal["review_objects"]:
            row = {
                field: str(item[field]).strip()
                for field in (
                    "object_type",
                    "object_id",
                    "admission_status",
                    "official_source",
                    "norm_or_decision",
                    "review_text",
                )
            }
            row["object_sha256"] = canonical_review_object_hash(row)
            rows.append(row)
        rows.sort(key=lambda row: (row["object_type"], row["object_id"]))
        return rows

    def write_review_csv(self, path: str | Path) -> None:
        with Path(path).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
            writer.writeheader()
            for item in self.review_objects():
                values = {
                    **item,
                    "object_type": OBJECT_TYPE_LABELS[item["object_type"]],
                    "agree": "",
                    "disagree": "",
                    "comment": "",
                }
                writer.writerow(
                    {label: values[key] for key, label in REVIEW_CSV_COLUMNS}
                )

    def validate_completed_review_csv(self, path: str | Path) -> str:
        review_path = Path(path)
        try:
            with review_path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if tuple(reader.fieldnames or ()) != REVIEW_CSV_FIELDS:
                    raise ExpansionReviewError("Expansion review CSV columns are invalid")
                rows = list(reader)
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            raise ExpansionReviewError("Expansion review CSV is invalid") from exc

        expected = {
            (row["object_type"], row["object_id"]): row
            for row in self.review_objects()
        }
        if len(rows) != len(expected):
            raise ExpansionReviewError("Expansion review CSV row count is incorrect")
        seen: set[tuple[str, str]] = set()
        for display_row in rows:
            row = {
                key: str(display_row.get(label, "")).strip()
                for key, label in REVIEW_CSV_COLUMNS
            }
            row["object_type"] = OBJECT_TYPE_BY_LABEL.get(
                row["object_type"], row["object_type"]
            )
            key = (row["object_type"], row["object_id"])
            if key in seen or key not in expected:
                raise ExpansionReviewError("Expansion review contains an unknown row")
            seen.add(key)
            expected_row = expected[key]
            for field in (
                "admission_status",
                "official_source",
                "norm_or_decision",
                "review_text",
                "object_sha256",
            ):
                if row[field] != expected_row[field]:
                    raise ExpansionReviewError(
                        f"Expansion review object changed: {key[0]}/{key[1]}"
                    )
            if (
                _normalized_checkbox(row["agree"]) is not True
                or _normalized_checkbox(row["disagree"]) is not False
            ):
                raise ExpansionReviewError(
                    f"Expansion review is not agreed: {key[0]}/{key[1]}"
                )
        return hashlib.sha256(review_path.read_bytes()).hexdigest()

    def require_activation_ready(self) -> None:
        """Fail closed until reviewed GIS provenance is supplied separately."""
        blocked = [
            row["object_id"]
            for row in self.review_objects()
            if row["admission_status"].startswith("BLOCKED_")
        ]
        if blocked:
            raise ExpansionActivationBlockedError(
                "Expansion remains blocked by spatial provenance: "
                + ", ".join(blocked)
            )
        raise ExpansionActivationBlockedError(
            "Expansion activation requires a separate hash-bound approval record"
        )

