from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from response_catalog import (
    DEFAULT_APPROVAL,
    DEFAULT_CATALOG,
    FIELD_APPROVAL,
    FIELD_CATALOG,
    ResponseCatalog,
    ResponseCatalogError,
)


class ResponseCatalogTests(unittest.TestCase):
    def _files(self, catalog_mutator=None, approval_mutator=None):
        catalog = json.loads(DEFAULT_CATALOG.read_text(encoding="utf-8"))
        if catalog_mutator:
            catalog_mutator(catalog)
        catalog_text = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
        approval = json.loads(DEFAULT_APPROVAL.read_text(encoding="utf-8"))
        approval.update(
            {
                "catalog_id": catalog["catalog_id"],
                "catalog_sha256": hashlib.sha256(
                    catalog_text.encode("utf-8")
                ).hexdigest(),
            }
        )
        if approval_mutator:
            approval_mutator(approval)
        temp_dir = tempfile.TemporaryDirectory()
        catalog_path = Path(temp_dir.name) / "response.json"
        approval_path = Path(temp_dir.name) / "approval.json"
        catalog_path.write_text(catalog_text, encoding="utf-8")
        approval_path.write_text(
            json.dumps(approval, ensure_ascii=False), encoding="utf-8"
        )
        return temp_dir, catalog_path, approval_path

    def test_checked_in_catalog_has_exact_author_approval(self):
        catalog = ResponseCatalog()

        self.assertEqual(
            "ae1c62c8c77e018dbf7cb303a648c48f79ef2cff28ec971c8c61941a73b340b1",
            catalog.sha256,
        )
        self.assertEqual("kz-alma-human-response-0.1.0", catalog.catalog_id)
        self.assertEqual("Yernar Sailybayev", catalog.approval["reviewer"]["name"])
        self.assertIn("сад", catalog.context_for("orchard_landscape")["why_ru"])
        self.assertIn("eOtinish", catalog.action_for("waste")["next_ru"])

    def test_field_catalog_has_exact_screening_approval(self):
        catalog = ResponseCatalog(FIELD_CATALOG, FIELD_APPROVAL)
        self.assertEqual(
            "dd746bbb8f98d19d908b78a6f9d6059edf70ed30e505e91ed1cebdd582dc0c06",
            catalog.sha256,
        )
        self.assertEqual("kz-alma-human-response-0.2.0", catalog.catalog_id)
        screening = catalog.action_for(
            "construction", "ile_alatau_open_source_screening"
        )
        self.assertIn("официальной проверки", screening["assessment_ru"])
        self.assertIn("eOtinish", screening["next_ru"])

    def test_catalog_edit_after_approval_fails_closed(self):
        temp_dir, catalog_path, approval_path = self._files()
        self.addCleanup(temp_dir.cleanup)
        catalog_path.write_text(
            catalog_path.read_text(encoding="utf-8").replace(
                "Сады здесь важны", "Непроверенный текст", 1
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ResponseCatalogError, "hash does not match"):
            ResponseCatalog(catalog_path, approval_path)

    def test_unauthorized_reviewer_fails_closed(self):
        temp_dir, catalog_path, approval_path = self._files(
            approval_mutator=lambda value: value.update(
                {
                    "reviewer": {
                        "name": "Language model",
                        "capacity": "AUTHOR_AND_LEGAL_EDITOR",
                    }
                }
            )
        )
        self.addCleanup(temp_dir.cleanup)

        with self.assertRaisesRegex(ResponseCatalogError, "not authorized"):
            ResponseCatalog(catalog_path, approval_path)

    def test_unofficial_principle_source_fails_closed(self):
        def replace_source(value):
            value["context_profiles"]["orchard_landscape"]["principles"][0][
                "official_url"
            ] = "https://example.invalid/summary"

        temp_dir, catalog_path, approval_path = self._files(
            catalog_mutator=replace_source
        )
        self.addCleanup(temp_dir.cleanup)

        with self.assertRaisesRegex(ResponseCatalogError, "source is not official"):
            ResponseCatalog(catalog_path, approval_path)

    def test_missing_action_mapping_fails_closed(self):
        temp_dir, catalog_path, approval_path = self._files(
            catalog_mutator=lambda value: value["actions"].pop("water_pollution")
        )
        self.addCleanup(temp_dir.cleanup)

        with self.assertRaisesRegex(ResponseCatalogError, "actions are incomplete"):
            ResponseCatalog(catalog_path, approval_path)


if __name__ == "__main__":
    unittest.main()
