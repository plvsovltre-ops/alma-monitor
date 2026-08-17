from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
import tempfile
import unittest
from datetime import date
from pathlib import Path

from spatial_source_registry import (
    DEFAULT_APPROVAL,
    DEFAULT_REGISTRY,
    SpatialSourceError,
    SpatialSourceRegistry,
    gpkg_feature_content_sha256,
)


class SpatialSourceRegistryTests(unittest.TestCase):
    @staticmethod
    def _geometry_blob(x=76.95, y=43.20):
        wkb = struct.pack("<BI2d", 1, 1, x, y)
        return b"GP\x00\x01" + struct.pack("<i", 4326) + wkb

    def _write_gpkg(self, path, *, label="reviewed", packaging_marker=None):
        connection = sqlite3.connect(path)
        if packaging_marker is not None:
            connection.execute("CREATE TABLE packaging_note (value TEXT)")
            connection.execute(
                "INSERT INTO packaging_note VALUES (?)", (packaging_marker,)
            )
        connection.execute(
            "CREATE TABLE gpkg_geometry_columns ("
            "table_name TEXT, column_name TEXT, geometry_type_name TEXT, "
            "srs_id INTEGER)"
        )
        connection.execute(
            "INSERT INTO gpkg_geometry_columns VALUES "
            "('reviewed_layer', 'geom', 'POINT', 4326)"
        )
        connection.execute(
            "CREATE TABLE reviewed_layer ("
            "fid INTEGER PRIMARY KEY, geom BLOB, label TEXT)"
        )
        connection.execute(
            "INSERT INTO reviewed_layer (geom, label) VALUES (?, ?)",
            (self._geometry_blob(), label),
        )
        connection.commit()
        connection.close()

    def _files(self, *, source_mutator=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        source_path = root / "Национальный_Природный_Парк.gpkg"
        self._write_gpkg(source_path)
        registry = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        registry["sources"] = [dict(registry["sources"][0])]
        registry["sources"][0]["file_sha256"] = hashlib.sha256(
            source_path.read_bytes()
        ).hexdigest()
        registry["sources"][0]["content_sha256"] = gpkg_feature_content_sha256(
            source_path
        )
        if source_mutator:
            source_mutator(registry["sources"][0])
        registry_text = json.dumps(registry, ensure_ascii=False, indent=2) + "\n"
        registry_path = root / "registry.json"
        registry_path.write_text(registry_text, encoding="utf-8")
        approval = json.loads(DEFAULT_APPROVAL.read_text(encoding="utf-8"))
        approval["registry_sha256"] = hashlib.sha256(
            registry_text.encode("utf-8")
        ).hexdigest()
        approval_path = root / "approval.json"
        approval_path.write_text(json.dumps(approval), encoding="utf-8")
        return registry_path, approval_path, source_path

    def test_checked_in_registry_is_hash_bound_and_screening_only(self):
        registry = SpatialSourceRegistry(today=date(2026, 8, 17))
        self.assertEqual(
            "OPEN_SOURCE_SCREENING_APPROVED", registry.approval["decision"]
        )
        for source in registry.registry["sources"]:
            self.assertEqual(
                "OPEN_SOURCE_SCREENING_CONTEXT_ONLY", source["allowed_use"]
            )
            self.assertEqual(
                "NOT_AN_OFFICIAL_BOUNDARY_ACT", source["legal_boundary_status"]
            )

    def test_exact_file_is_accepted_before_review_due_date(self):
        registry_path, approval_path, source_path = self._files()
        registry = SpatialSourceRegistry(
            registry_path, approval_path, today=date(2026, 9, 16)
        )
        record = registry.require_source(source_path)
        self.assertEqual("OPEN_SOURCE_SCREENING_CONTEXT_ONLY", record["allowed_use"])

    def test_changed_file_fails_closed(self):
        registry_path, approval_path, source_path = self._files()
        connection = sqlite3.connect(source_path)
        connection.execute("UPDATE reviewed_layer SET label = 'changed'")
        connection.commit()
        connection.close()
        registry = SpatialSourceRegistry(
            registry_path, approval_path, today=date(2026, 8, 18)
        )
        with self.assertRaisesRegex(SpatialSourceError, "changed after review"):
            registry.require_source(source_path)

    def test_same_features_in_repackaged_gpkg_are_accepted(self):
        registry_path, approval_path, source_path = self._files()
        repackaged_path = source_path.with_name("repackaged.gpkg")
        self._write_gpkg(repackaged_path, packaging_marker="different SQLite bytes")
        self.assertNotEqual(
            hashlib.sha256(source_path.read_bytes()).hexdigest(),
            hashlib.sha256(repackaged_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            gpkg_feature_content_sha256(source_path),
            gpkg_feature_content_sha256(repackaged_path),
        )
        repackaged_path.replace(source_path)
        registry = SpatialSourceRegistry(
            registry_path, approval_path, today=date(2026, 8, 18)
        )
        registry.require_source(source_path)

    def test_geometry_change_fails_closed(self):
        registry_path, approval_path, source_path = self._files()
        connection = sqlite3.connect(source_path)
        connection.execute(
            "UPDATE reviewed_layer SET geom = ?", (self._geometry_blob(76.96, 43.21),)
        )
        connection.commit()
        connection.close()
        registry = SpatialSourceRegistry(
            registry_path, approval_path, today=date(2026, 8, 18)
        )
        with self.assertRaisesRegex(SpatialSourceError, "changed after review"):
            registry.require_source(source_path)

    def test_overdue_source_fails_closed(self):
        registry_path, approval_path, source_path = self._files()
        registry = SpatialSourceRegistry(
            registry_path, approval_path, today=date(2026, 9, 17)
        )
        with self.assertRaisesRegex(SpatialSourceError, "review is overdue"):
            registry.require_source(source_path)

    def test_source_cannot_be_misclassified_as_official_boundary(self):
        registry_path, approval_path, _ = self._files(
            source_mutator=lambda value: value.update(
                {"legal_boundary_status": "OFFICIAL_BOUNDARY"}
            )
        )
        with self.assertRaisesRegex(SpatialSourceError, "status is unsafe"):
            SpatialSourceRegistry(registry_path, approval_path)

    def test_registry_edit_after_approval_fails_hash_check(self):
        registry_path, approval_path, _ = self._files()
        registry_path.write_text(
            registry_path.read_text(encoding="utf-8").replace(
                "ALAG", "unreviewed source", 1
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(SpatialSourceError, "hash does not match"):
            SpatialSourceRegistry(registry_path, approval_path)


if __name__ == "__main__":
    unittest.main()
