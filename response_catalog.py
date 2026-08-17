"""Approved human-facing context and action guidance for ALMA results."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_CATALOG = (
    Path(__file__).resolve().parent / "config" / "response_catalog.json"
)
DEFAULT_APPROVAL = (
    Path(__file__).resolve().parent / "config" / "response_catalog.approval.json"
)
FIELD_CATALOG = (
    Path(__file__).resolve().parent
    / "config"
    / "field"
    / "0.2.0-rc1"
    / "response_catalog.json"
)
FIELD_APPROVAL = FIELD_CATALOG.with_name("response_catalog.approval.json")
AUTHORIZED_REVIEWER = {
    "name": "Yernar Sailybayev",
    "capacity": "AUTHOR_AND_LEGAL_EDITOR",
}
SUPPORTED_CONTEXT_PROFILES = {
    "orchard_landscape",
    "ile_alatau_open_source_screening",
    "water_open_source_screening",
}
SUPPORTED_INCIDENT_TYPES = {
    "construction",
    "logging",
    "soil_damage",
    "waste",
    "water_pollution",
}


class ResponseCatalogError(RuntimeError):
    """Raised when human-response content is not reviewed and usable."""


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResponseCatalogError(f"Response catalog {label} is missing")
    return value.strip()


class ResponseCatalog:
    """Load human-facing text bound to an exact author approval."""

    def __init__(
        self,
        path: str | Path = DEFAULT_CATALOG,
        approval_path: str | Path = DEFAULT_APPROVAL,
    ):
        self.path = Path(path)
        self.approval_path = Path(approval_path)
        try:
            raw = self.path.read_bytes()
            catalog = json.loads(raw.decode("utf-8"))
            approval = json.loads(self.approval_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ResponseCatalogError("Response catalog is invalid") from exc
        if not isinstance(catalog, dict) or not isinstance(approval, dict):
            raise ResponseCatalogError("Response catalog documents must be objects")
        self.catalog = catalog
        self.approval = approval
        self.sha256 = hashlib.sha256(raw).hexdigest()
        self._validate()

    def _validate(self) -> None:
        schema_version = self.catalog.get("schema_version")
        if schema_version not in {"1.0", "1.1"}:
            raise ResponseCatalogError("Response catalog schema is unsupported")
        catalog_id = _required_text(self.catalog.get("catalog_id"), "ID")
        if self.catalog.get("status") != "AUTHOR_REVIEW_REQUIRED":
            raise ResponseCatalogError("Response catalog marker is invalid")
        if self.approval.get("schema_version") != schema_version:
            raise ResponseCatalogError("Response catalog approval schema is unsupported")
        if self.approval.get("catalog_id") != catalog_id:
            raise ResponseCatalogError("Response catalog and approval IDs differ")
        if self.approval.get("catalog_sha256") != self.sha256:
            raise ResponseCatalogError("Response catalog approval hash does not match")
        if self.approval.get("approval_scope") not in {
            "PRIVATE_CONTROLLED_PILOT_ONLY",
            "CONTROLLED_FIELD_SCREENING_ONLY",
        }:
            raise ResponseCatalogError("Response catalog approval scope is invalid")
        if self.approval.get("decision") != "CONTROLLED_PILOT_APPROVED":
            raise ResponseCatalogError("Response catalog is not approved")
        if self.approval.get("reviewer") != AUTHORIZED_REVIEWER:
            raise ResponseCatalogError("Response catalog reviewer is not authorized")
        try:
            date.fromisoformat(_required_text(self.approval.get("reviewed_on"), "review date"))
        except ValueError as exc:
            raise ResponseCatalogError("Response catalog review date is invalid") from exc

        procedural = self.catalog.get("procedural_basis")
        if not isinstance(procedural, dict):
            raise ResponseCatalogError("Response procedural basis is missing")
        for field in ("request_ru", "request_kz", "official_url", "verified_on"):
            _required_text(procedural.get(field), f"procedural_basis.{field}")
        if not procedural["official_url"].startswith(
            "https://adilet.zan.kz/"
        ):
            raise ResponseCatalogError("Response procedural source is not official")
        try:
            date.fromisoformat(procedural["verified_on"])
        except ValueError as exc:
            raise ResponseCatalogError(
                "Response procedural verification date is invalid"
            ) from exc

        profiles = self.catalog.get("context_profiles")
        expected_profiles = (
            SUPPORTED_CONTEXT_PROFILES
            if schema_version == "1.1"
            else {"orchard_landscape"}
        )
        if not isinstance(profiles, dict) or set(profiles) != expected_profiles:
            raise ResponseCatalogError("Response catalog context profiles are incomplete")
        for profile_id, profile in profiles.items():
            if not isinstance(profile, dict):
                raise ResponseCatalogError(f"Response context is invalid: {profile_id}")
            for field in ("why_ru", "why_kz"):
                _required_text(profile.get(field), f"{profile_id}.{field}")
            principles = profile.get("principles")
            if not isinstance(principles, list) or not principles:
                raise ResponseCatalogError(f"Response principles are missing: {profile_id}")
            for index, principle in enumerate(principles):
                if not isinstance(principle, dict):
                    raise ResponseCatalogError(
                        f"Response principle is invalid: {profile_id}.{index}"
                    )
                for field in (
                    "principle_id",
                    "text_ru",
                    "text_kz",
                    "official_url",
                    "verified_on",
                ):
                    _required_text(
                        principle.get(field),
                        f"{profile_id}.{index}.{field}",
                    )
                if not principle["official_url"].startswith(
                    "https://adilet.zan.kz/"
                ):
                    raise ResponseCatalogError(
                        f"Response principle source is not official: {profile_id}.{index}"
                    )
                try:
                    date.fromisoformat(principle["verified_on"])
                except ValueError as exc:
                    raise ResponseCatalogError(
                        f"Response principle verification date is invalid: {profile_id}.{index}"
                    ) from exc

        actions = self.catalog.get("actions")
        if not isinstance(actions, dict) or set(actions) != SUPPORTED_INCIDENT_TYPES:
            raise ResponseCatalogError("Response catalog actions are incomplete")
        for incident_type, action in actions.items():
            if not isinstance(action, dict):
                raise ResponseCatalogError(f"Response action is invalid: {incident_type}")
            for field in ("assessment_ru", "assessment_kz", "next_ru", "next_kz"):
                _required_text(action.get(field), f"{incident_type}.{field}")

        contextual_actions = self.catalog.get("actions_by_context", {})
        expected_contextual = (
            SUPPORTED_CONTEXT_PROFILES - {"orchard_landscape"}
            if schema_version == "1.1"
            else set()
        )
        if not isinstance(contextual_actions, dict) or set(contextual_actions) != expected_contextual:
            raise ResponseCatalogError("Response contextual actions are incomplete")
        for profile_id, profile_actions in contextual_actions.items():
            if not isinstance(profile_actions, dict) or set(profile_actions) != SUPPORTED_INCIDENT_TYPES:
                raise ResponseCatalogError(
                    f"Response contextual action matrix is incomplete: {profile_id}"
                )
            for incident_type, action in profile_actions.items():
                if not isinstance(action, dict):
                    raise ResponseCatalogError(
                        f"Response contextual action is invalid: {profile_id}/{incident_type}"
                    )
                for field in ("assessment_ru", "assessment_kz", "next_ru", "next_kz"):
                    _required_text(
                        action.get(field),
                        f"{profile_id}/{incident_type}.{field}",
                    )

    @property
    def catalog_id(self) -> str:
        return self.catalog["catalog_id"]

    def context_for(self, profile_id: object) -> dict[str, Any]:
        normalized = str(profile_id or "").strip()
        context = self.catalog["context_profiles"].get(normalized)
        if context is None:
            raise ResponseCatalogError(
                f"Territory has no reviewed response context: {normalized or '<empty>'}"
            )
        return {
            "profile_id": normalized,
            **context,
            "procedural_basis": dict(self.catalog["procedural_basis"]),
        }

    def action_for(
        self,
        incident_type: object,
        profile_id: object | None = None,
    ) -> dict[str, str]:
        normalized = str(incident_type or "").strip().lower()
        normalized_profile = str(profile_id or "").strip()
        if normalized_profile and normalized_profile != "orchard_landscape":
            action = (self.catalog.get("actions_by_context") or {}).get(
                normalized_profile, {}
            ).get(normalized)
        else:
            action = self.catalog["actions"].get(normalized)
        if action is None:
            raise ResponseCatalogError(
                f"Incident has no reviewed response action: {normalized or '<empty>'}"
            )
        return dict(action)
