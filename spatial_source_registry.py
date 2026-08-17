"""Fail-closed registry for open spatial sources used by ALMA."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY = Path(__file__).resolve().parent / "config" / "spatial_sources.json"
DEFAULT_APPROVAL = (
    Path(__file__).resolve().parent / "config" / "spatial_sources.approval.json"
)
AUTHORIZED_REVIEWER = {
    "name": "Yernar Sailybayev",
    "capacity": "AUTHOR_AND_LEGAL_EDITOR",
}
CONTENT_HASH_METHOD = "GPKG_FEATURE_CONTENT_V1"


class SpatialSourceError(RuntimeError):
    """A spatial source is unreviewed, changed, expired, or misclassified."""


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpatialSourceError(f"Spatial source {label} is missing")
    return value.strip()


def _quote_identifier(value: str) -> str:
    """Quote one SQLite identifier obtained from GeoPackage metadata."""
    return '"' + value.replace('"', '""') + '"'


def _geometry_wkb(blob: object) -> bytes:
    """Remove the mutable GeoPackage envelope and return the stored WKB."""
    if not isinstance(blob, bytes):
        raise SpatialSourceError("Spatial source geometry is missing")
    if len(blob) < 8 or blob[:2] != b"GP":
        raise SpatialSourceError("Spatial source geometry is not GeoPackage binary")
    envelope_type = (blob[3] >> 1) & 0b111
    envelope_size = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get(envelope_type)
    if envelope_size is None or len(blob) < 8 + envelope_size:
        raise SpatialSourceError("Spatial source geometry envelope is invalid")
    wkb = blob[8 + envelope_size :]
    if not wkb:
        raise SpatialSourceError("Spatial source geometry WKB is empty")
    return wkb


def _canonical_value(value: object, *, geometry: bool = False) -> object:
    if geometry:
        return {"wkb": _geometry_wkb(value).hex()}
    if value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SpatialSourceError("Spatial source contains a non-finite number")
        return {"float": format(value, ".17g")}
    if isinstance(value, bytes):
        return {"blob_sha256": hashlib.sha256(value).hexdigest()}
    raise SpatialSourceError("Spatial source contains an unsupported value")


def gpkg_feature_content_sha256(path: str | Path) -> str:
    """Hash feature geometry and attributes, independent of SQLite packaging.

    Mergin Maps may rebuild a GeoPackage while applying a changeset. The SQLite
    pages and GeoPackage envelopes can then differ even though every reviewed
    feature is unchanged. This digest intentionally excludes primary-key row
    IDs and non-feature metadata, sorts features deterministically, and hashes
    the WKB plus all reviewed feature attributes.
    """
    path = Path(path)
    if not path.is_file():
        raise SpatialSourceError(f"Spatial source cannot be read: {path.name}")
    try:
        connection = sqlite3.connect(path)
        geometry_layers = connection.execute(
            "SELECT table_name, column_name, geometry_type_name, srs_id "
            "FROM gpkg_geometry_columns ORDER BY table_name"
        ).fetchall()
        if not geometry_layers:
            raise SpatialSourceError("Spatial source contains no feature layer")

        layers = []
        for table_name, geometry_column, geometry_type, srs_id in geometry_layers:
            columns = connection.execute(
                f"PRAGMA table_info({_quote_identifier(table_name)})"
            ).fetchall()
            if not columns:
                raise SpatialSourceError("Spatial source feature table is missing")
            primary_keys = {column[1] for column in columns if column[5]}
            content_columns = [
                column[1] for column in columns if column[1] not in primary_keys
            ]
            if geometry_column not in content_columns:
                raise SpatialSourceError("Spatial source geometry column is missing")

            selection = ", ".join(_quote_identifier(name) for name in content_columns)
            rows = []
            for values in connection.execute(
                f"SELECT {selection} FROM {_quote_identifier(table_name)}"
            ):
                feature = {
                    name: _canonical_value(value, geometry=name == geometry_column)
                    for name, value in zip(content_columns, values)
                }
                rows.append(
                    json.dumps(
                        feature,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
            rows.sort()
            layers.append(
                {
                    "table": table_name,
                    "geometry_column": geometry_column,
                    "geometry_type": geometry_type,
                    "srs_id": srs_id,
                    "columns": content_columns,
                    "features": rows,
                }
            )
    except (OSError, sqlite3.Error) as exc:
        raise SpatialSourceError(f"Spatial source cannot be read: {path.name}") from exc
    finally:
        if "connection" in locals():
            connection.close()

    payload = json.dumps(
        {"schema": "alma-gpkg-feature-content-v1", "layers": layers},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SpatialSourceRegistry:
    """Validate provenance, scope, review age, and reviewed feature content."""

    def __init__(
        self,
        path: str | Path = DEFAULT_REGISTRY,
        approval_path: str | Path = DEFAULT_APPROVAL,
        *,
        today: date | None = None,
    ):
        self.path = Path(path)
        self.approval_path = Path(approval_path)
        self.today = today or date.today()
        try:
            raw = self.path.read_bytes()
            self.registry = json.loads(raw.decode("utf-8"))
            self.approval = json.loads(
                self.approval_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SpatialSourceError("Spatial source registry is invalid") from exc
        if not isinstance(self.registry, dict) or not isinstance(self.approval, dict):
            raise SpatialSourceError("Spatial source registry documents must be objects")
        self.sha256 = hashlib.sha256(raw).hexdigest()
        self._sources: dict[str, dict[str, Any]] = {}
        self._validate()

    def _validate(self) -> None:
        if self.registry.get("schema_version") != "1.1":
            raise SpatialSourceError("Spatial source registry schema is unsupported")
        registry_id = _required_text(self.registry.get("registry_id"), "registry ID")
        if self.registry.get("status") != "OWNER_REVIEW_REQUIRED":
            raise SpatialSourceError("Spatial source registry marker is invalid")
        if self.approval.get("schema_version") != "1.0":
            raise SpatialSourceError("Spatial source approval schema is unsupported")
        if self.approval.get("registry_id") != registry_id:
            raise SpatialSourceError("Spatial source registry and approval IDs differ")
        if self.approval.get("registry_sha256") != self.sha256:
            raise SpatialSourceError("Spatial source approval hash does not match")
        if self.approval.get("decision") != "OPEN_SOURCE_SCREENING_APPROVED":
            raise SpatialSourceError("Spatial source registry is not approved")
        if self.approval.get("reviewer") != AUTHORIZED_REVIEWER:
            raise SpatialSourceError("Spatial source reviewer is not authorized")

        sources = self.registry.get("sources")
        if not isinstance(sources, list) or not sources:
            raise SpatialSourceError("Spatial source registry is empty")
        for source in sources:
            if not isinstance(source, dict):
                raise SpatialSourceError("Spatial source record is invalid")
            source_id = _required_text(source.get("source_id"), "source ID")
            source_file = _required_text(source.get("source_file"), "filename")
            if source_file != Path(source_file).name or not source_file.endswith(".gpkg"):
                raise SpatialSourceError(f"Spatial source filename is invalid: {source_file}")
            if source_file in self._sources:
                raise SpatialSourceError(f"Spatial source filename is duplicated: {source_file}")
            for field in (
                "public_source_url",
                "government_reference_url",
                "acquisition_method_ru",
                "acquired_on",
                "last_reviewed_on",
                "next_review_due",
                "file_sha256",
                "content_hash_method",
                "content_sha256",
                "allowed_use",
                "legal_boundary_status",
                "limitations_ru",
            ):
                _required_text(source.get(field), f"{source_id}.{field}")
            if not source["public_source_url"].startswith("https://"):
                raise SpatialSourceError(f"Spatial source URL is invalid: {source_id}")
            if not source["government_reference_url"].startswith("https://www.gov.kz/"):
                raise SpatialSourceError(
                    f"Spatial government reference is invalid: {source_id}"
                )
            if source["allowed_use"] != "OPEN_SOURCE_SCREENING_CONTEXT_ONLY":
                raise SpatialSourceError(f"Spatial source use is too broad: {source_id}")
            if source["legal_boundary_status"] != "NOT_AN_OFFICIAL_BOUNDARY_ACT":
                raise SpatialSourceError(
                    f"Spatial legal-boundary status is unsafe: {source_id}"
                )
            if source["file_sha256"] != source["file_sha256"].lower() or len(
                source["file_sha256"]
            ) != 64:
                raise SpatialSourceError(f"Spatial source hash is invalid: {source_id}")
            if source["content_hash_method"] != CONTENT_HASH_METHOD:
                raise SpatialSourceError(
                    f"Spatial source content hash method is invalid: {source_id}"
                )
            if source["content_sha256"] != source["content_sha256"].lower() or len(
                source["content_sha256"]
            ) != 64:
                raise SpatialSourceError(
                    f"Spatial source content hash is invalid: {source_id}"
                )
            try:
                last_reviewed = date.fromisoformat(source["last_reviewed_on"])
                next_review = date.fromisoformat(source["next_review_due"])
                date.fromisoformat(source["acquired_on"])
            except ValueError as exc:
                raise SpatialSourceError(
                    f"Spatial source review date is invalid: {source_id}"
                ) from exc
            interval = source.get("review_interval_days")
            if not isinstance(interval, int) or interval < 1 or interval > 90:
                raise SpatialSourceError(
                    f"Spatial source review interval is invalid: {source_id}"
                )
            if (next_review - last_reviewed).days != interval:
                raise SpatialSourceError(
                    f"Spatial source review interval does not match dates: {source_id}"
                )
            self._sources[source_file] = dict(source)

    @property
    def registry_id(self) -> str:
        return self.registry["registry_id"]

    def require_source(self, source_file: str | Path) -> dict[str, Any]:
        path = Path(source_file)
        try:
            record = self._sources[path.name]
        except KeyError as exc:
            raise SpatialSourceError(
                f"Spatial source is not registered: {path.name}"
            ) from exc
        if self.today > date.fromisoformat(record["next_review_due"]):
            raise SpatialSourceError(
                f"Spatial source review is overdue: {record['source_id']}"
            )
        digest = gpkg_feature_content_sha256(path)
        if digest != record["content_sha256"]:
            raise SpatialSourceError(f"Spatial source changed after review: {path.name}")
        return {
            **record,
            "registry_id": self.registry_id,
            "registry_sha256": self.sha256,
        }

    def registered_filename(self, source_file: str | Path) -> bool:
        return Path(source_file).name in self._sources

    def record_for_filename(self, source_file: str | Path) -> dict[str, Any] | None:
        record = self._sources.get(Path(source_file).name)
        return dict(record) if record is not None else None
