"""Reviewed territory names and deterministic authority routes for ALMA."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from spatial_source_registry import SpatialSourceRegistry, SpatialSourceError


DEFAULT_CATALOG = (
    Path(__file__).resolve().parent / "config" / "territory_catalog.json"
)
DEFAULT_APPROVAL = (
    Path(__file__).resolve().parent / "config" / "territory_catalog.approval.json"
)
FIELD_CATALOG = (
    Path(__file__).resolve().parent
    / "config"
    / "field"
    / "0.2.0-rc1"
    / "territory_catalog.json"
)
FIELD_APPROVAL = FIELD_CATALOG.with_name("territory_catalog.approval.json")
AUTHORIZED_REVIEWER = {
    "name": "Yernar Sailybayev",
    "capacity": "AUTHOR_AND_LEGAL_EDITOR",
}


class TerritoryCatalogError(RuntimeError):
    """Raised when a territory or authority route is not reviewed and usable."""


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TerritoryCatalogError(f"Territory catalog {label} is missing")
    return value.strip()


class TerritoryCatalog:
    """Load a small local catalog without an API or a model call."""

    def __init__(
        self,
        path: str | Path = DEFAULT_CATALOG,
        approval_path: str | Path = DEFAULT_APPROVAL,
        spatial_registry: SpatialSourceRegistry | None = None,
    ):
        self.path = Path(path)
        self.approval_path = Path(approval_path)
        try:
            raw = self.path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TerritoryCatalogError("Territory catalog is invalid") from exc
        if not isinstance(value, dict):
            raise TerritoryCatalogError("Territory catalog must be an object")
        self.catalog = value
        self.sha256 = hashlib.sha256(raw).hexdigest()
        try:
            approval = json.loads(self.approval_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TerritoryCatalogError("Territory catalog approval is invalid") from exc
        if not isinstance(approval, dict):
            raise TerritoryCatalogError("Territory catalog approval must be an object")
        self.approval = approval
        self.spatial_registry = spatial_registry or SpatialSourceRegistry()
        self._territories: dict[str, dict[str, Any]] = {}
        self._validate()

    def _validate(self) -> None:
        schema_version = self.catalog.get("schema_version")
        if schema_version not in {"1.0", "1.1"}:
            raise TerritoryCatalogError("Territory catalog schema is unsupported")
        _required_text(self.catalog.get("catalog_id"), "ID")
        if self.catalog.get("status") != "AUTHOR_REVIEW_REQUIRED":
            raise TerritoryCatalogError("Territory catalog marker is invalid")
        if self.approval.get("schema_version") != schema_version:
            raise TerritoryCatalogError("Territory catalog approval schema is unsupported")
        if self.approval.get("catalog_id") != self.catalog.get("catalog_id"):
            raise TerritoryCatalogError("Territory catalog and approval IDs differ")
        if self.approval.get("catalog_sha256") != self.sha256:
            raise TerritoryCatalogError("Territory catalog approval hash does not match")
        if self.approval.get("approval_scope") not in {
            "PRIVATE_CONTROLLED_PILOT_ONLY",
            "CONTROLLED_FIELD_SCREENING_ONLY",
        }:
            raise TerritoryCatalogError("Territory catalog approval scope is invalid")
        if self.approval.get("decision") != "CONTROLLED_PILOT_APPROVED":
            raise TerritoryCatalogError("Territory catalog is not approved")
        if self.approval.get("reviewer") != AUTHORIZED_REVIEWER:
            raise TerritoryCatalogError("Territory catalog reviewer is not authorized")
        reviewed_on = _required_text(self.approval.get("reviewed_on"), "review date")
        try:
            date.fromisoformat(reviewed_on)
        except ValueError as exc:
            raise TerritoryCatalogError(
                "Territory catalog review date is invalid"
            ) from exc

        routes = self.catalog.get("routes")
        if not isinstance(routes, dict) or not routes:
            raise TerritoryCatalogError("Territory catalog has no authority routes")
        for route_id, route in routes.items():
            _required_text(route_id, "route ID")
            if not isinstance(route, dict):
                raise TerritoryCatalogError(f"Territory route is invalid: {route_id}")
            for field in (
                "display_name_ru",
                "display_name_kz",
                "official_name_ru",
                "official_name_kz",
                "forwarding_ru",
                "forwarding_kz",
                "official_source_url",
                "competence_source_url",
                "verified_on",
            ):
                _required_text(route.get(field), f"{route_id}.{field}")

        requests = self.catalog.get("request_templates")
        if not isinstance(requests, dict) or not requests:
            raise TerritoryCatalogError("Territory catalog has no request templates")
        for incident_type, request in requests.items():
            if not isinstance(request, dict):
                raise TerritoryCatalogError(
                    f"Territory request template is invalid: {incident_type}"
                )
            for field in ("subject_ru", "subject_kz", "request_ru", "request_kz"):
                _required_text(request.get(field), f"{incident_type}.{field}")

        request_families = self.catalog.get("request_template_families", {})
        if not isinstance(request_families, dict):
            raise TerritoryCatalogError("Territory request template families are invalid")
        for family_id, family in request_families.items():
            _required_text(family_id, "request template family ID")
            if not isinstance(family, dict) or set(family) != set(requests):
                raise TerritoryCatalogError(
                    f"Territory request template family is incomplete: {family_id}"
                )
            for incident_type, request in family.items():
                if not isinstance(request, dict):
                    raise TerritoryCatalogError(
                        f"Territory request template is invalid: {family_id}/{incident_type}"
                    )
                for field in ("subject_ru", "subject_kz", "request_ru", "request_kz"):
                    _required_text(
                        request.get(field),
                        f"{family_id}/{incident_type}.{field}",
                    )

        territories = self.catalog.get("territories")
        if not isinstance(territories, list) or not territories:
            raise TerritoryCatalogError("Territory catalog has no territories")
        for territory in territories:
            if not isinstance(territory, dict):
                raise TerritoryCatalogError("Territory catalog entry is invalid")
            source_file = _required_text(territory.get("source_file"), "source file")
            if source_file != Path(source_file).name or not source_file.endswith(".gpkg"):
                raise TerritoryCatalogError(
                    f"Territory source filename is invalid: {source_file}"
                )
            if source_file in self._territories:
                raise TerritoryCatalogError(
                    f"Territory source filename is duplicated: {source_file}"
                )
            for field in (
                "territory_id",
                "public_name_ru",
                "public_name_kz",
                "purpose_ru",
                "purpose_kz",
                "context_profile_id",
            ):
                _required_text(territory.get(field), f"{source_file}.{field}")
            route_ids = territory.get("route_ids_by_incident_type")
            if not isinstance(route_ids, dict) or not route_ids:
                raise TerritoryCatalogError(
                    f"Territory authority routes are missing: {source_file}"
                )
            if not set(route_ids).issubset(requests):
                raise TerritoryCatalogError(
                    f"Territory incident route type is invalid: {source_file}"
                )
            for incident_type, route_id in route_ids.items():
                if route_id not in routes:
                    raise TerritoryCatalogError(
                        f"Territory route is unknown: {route_id}"
                    )
                if incident_type not in requests:
                    raise TerritoryCatalogError(
                        f"Territory request template is missing: {incident_type}"
                    )
            reference_fields = territory.get("reference_fields")
            if (
                not isinstance(reference_fields, list)
                or not reference_fields
                or not all(
                    isinstance(field, str) and field.strip()
                    for field in reference_fields
                )
                or len(reference_fields) != len(set(reference_fields))
            ):
                raise TerritoryCatalogError(
                    f"Territory reference fields are invalid: {source_file}"
                )
            priority = territory.get("priority")
            if not isinstance(priority, int) or priority < 0:
                raise TerritoryCatalogError(
                    f"Territory priority is invalid: {source_file}"
                )
            spatial_source_id = territory.get("spatial_source_id")
            if spatial_source_id is not None:
                _required_text(spatial_source_id, f"{source_file}.spatial_source_id")
                record = self.spatial_registry.record_for_filename(source_file)
                if record is None or record["source_id"] != spatial_source_id:
                    raise TerritoryCatalogError(
                        f"Territory spatial source is not registered: {source_file}"
                    )
                if territory.get("spatial_use") != (
                    "OPEN_SOURCE_SCREENING_CONTEXT_ONLY"
                ):
                    raise TerritoryCatalogError(
                        f"Territory spatial use is unsafe: {source_file}"
                    )
                family_id = _required_text(
                    territory.get("request_template_family_id"),
                    f"{source_file}.request_template_family_id",
                )
                if family_id not in request_families:
                    raise TerritoryCatalogError(
                        f"Territory request template family is unknown: {family_id}"
                    )
            self._territories[source_file] = dict(territory)

    @property
    def catalog_id(self) -> str:
        return self.catalog["catalog_id"]

    def context_for_source(self, source_file: str | Path) -> dict[str, Any] | None:
        source_name = Path(source_file).name
        territory = self._territories.get(source_name)
        if territory is None:
            return None
        return {
            **territory,
            "catalog_id": self.catalog_id,
            "catalog_sha256": self.sha256,
        }

    def route_context(
        self,
        territory: dict[str, Any],
        incident_type: object,
    ) -> dict[str, Any]:
        normalized = str(incident_type or "").strip().lower()
        route_id = territory["route_ids_by_incident_type"].get(normalized)
        if route_id is None:
            raise TerritoryCatalogError(
                "Territory has no reviewed authority route for incident type: "
                f"{normalized or '<empty>'}"
            )
        return {
            **territory,
            "route_id": route_id,
            "authority": dict(self.catalog["routes"][route_id]),
        }

    def validate_source_file(
        self,
        source_file: str | Path,
        territory: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not territory.get("spatial_source_id"):
            return None
        try:
            record = self.spatial_registry.require_source(source_file)
        except SpatialSourceError as exc:
            raise TerritoryCatalogError(str(exc)) from exc
        if record["source_id"] != territory["spatial_source_id"]:
            raise TerritoryCatalogError(
                f"Territory spatial source ID changed: {Path(source_file).name}"
            )
        return record

    def request_for(
        self,
        incident_type: object,
        territory: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        normalized = str(incident_type or "").strip().lower()
        family_id = (territory or {}).get("request_template_family_id")
        if family_id:
            families = self.catalog.get("request_template_families") or {}
            family = families.get(family_id)
            if not isinstance(family, dict):
                raise TerritoryCatalogError(
                    f"Territory request template family is missing: {family_id}"
                )
            request = family.get(normalized)
        else:
            request = self.catalog["request_templates"].get(normalized)
        if request is None:
            raise TerritoryCatalogError(
                f"Incident type has no reviewed request template: {normalized or '<empty>'}"
            )
        return dict(request)
