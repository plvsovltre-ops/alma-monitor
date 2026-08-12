import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from territory_catalog import (
    DEFAULT_APPROVAL,
    DEFAULT_CATALOG,
    TerritoryCatalog,
    TerritoryCatalogError,
)


class TerritoryCatalogTests(unittest.TestCase):
    def _approved_files(self, catalog_mutator=None, approval_mutator=None):
        catalog = json.loads(DEFAULT_CATALOG.read_text(encoding="utf-8"))
        if catalog_mutator:
            catalog_mutator(catalog)
        catalog_text = json.dumps(
            catalog,
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        approval = json.loads(DEFAULT_APPROVAL.read_text(encoding="utf-8"))
        approval.update(
            {
                "catalog_id": catalog["catalog_id"],
                "catalog_sha256": hashlib.sha256(
                    catalog_text.encode("utf-8")
                ).hexdigest(),
                "decision": "CONTROLLED_PILOT_APPROVED",
                "reviewer": {
                    "name": "Yernar Sailybayev",
                    "capacity": "AUTHOR_AND_LEGAL_EDITOR",
                },
                "reviewed_on": "2026-08-13",
            }
        )
        if approval_mutator:
            approval_mutator(approval)
        temp_dir = tempfile.TemporaryDirectory()
        catalog_path = Path(temp_dir.name) / "territories.json"
        approval_path = Path(temp_dir.name) / "approval.json"
        catalog_path.write_text(catalog_text, encoding="utf-8")
        approval_path.write_text(
            json.dumps(approval, ensure_ascii=False),
            encoding="utf-8",
        )
        return temp_dir, catalog_path, approval_path

    def test_checked_in_catalog_has_exact_author_approval(self):
        catalog = TerritoryCatalog()

        self.assertEqual(
            "68bb08dabda87343286879be6cb699cda26dfc2bf5d072208a75dbdfa2d5a32a",
            catalog.sha256,
        )
        self.assertEqual(
            "CONTROLLED_PILOT_APPROVED",
            catalog.approval["decision"],
        )
        self.assertEqual(
            {
                "name": "Yernar Sailybayev",
                "capacity": "AUTHOR_AND_LEGAL_EDITOR",
            },
            catalog.approval["reviewer"],
        )
        self.assertEqual("2026-08-13", catalog.approval["reviewed_on"])

    def test_default_catalog_resolves_remizovka_without_model(self):
        temp_dir, catalog_path, approval_path = self._approved_files()
        self.addCleanup(temp_dir.cleanup)
        catalog = TerritoryCatalog(catalog_path, approval_path)

        context = catalog.context_for_source(
            "/tmp/Сады_в_Ремизовке_на_проверке_2024.gpkg"
        )

        self.assertEqual("сад в Ремизовке", context["public_name_ru"])
        context = catalog.route_context(context, "waste")
        self.assertEqual("almaty_land_resources", context["route_id"])
        self.assertEqual(
            "Земельная инспекция Алматы",
            context["authority"]["display_name_ru"],
        )
        self.assertEqual(64, len(context["catalog_sha256"]))

    def test_unknown_source_never_falls_back_to_filename_guess(self):
        temp_dir, catalog_path, approval_path = self._approved_files()
        self.addCleanup(temp_dir.cleanup)
        catalog = TerritoryCatalog(catalog_path, approval_path)

        self.assertIsNone(catalog.context_for_source("Неизвестный_сад.gpkg"))

    def test_request_type_must_have_a_reviewed_template(self):
        temp_dir, catalog_path, approval_path = self._approved_files()
        self.addCleanup(temp_dir.cleanup)
        catalog = TerritoryCatalog(catalog_path, approval_path)

        with self.assertRaisesRegex(
            TerritoryCatalogError,
            "no reviewed request template",
        ):
            catalog.request_for("invented_type")

    def test_unreviewed_incident_route_fails_closed(self):
        temp_dir, catalog_path, approval_path = self._approved_files()
        self.addCleanup(temp_dir.cleanup)
        catalog = TerritoryCatalog(catalog_path, approval_path)
        territory = catalog.context_for_source(
            "Сады_в_Ремизовке_на_проверке_2024.gpkg"
        )

        with self.assertRaisesRegex(
            TerritoryCatalogError,
            "no reviewed authority route",
        ):
            catalog.route_context(territory, "logging")

    def test_unapproved_catalog_fails_closed(self):
        temp_dir, catalog_path, approval_path = self._approved_files(
            approval_mutator=lambda value: value.update(
                {"decision": "AUTHOR_REVIEW_REQUIRED"}
            )
        )
        self.addCleanup(temp_dir.cleanup)
        with self.assertRaisesRegex(TerritoryCatalogError, "not approved"):
            TerritoryCatalog(catalog_path, approval_path)

    def test_unauthorized_reviewer_fails_closed(self):
        temp_dir, catalog_path, approval_path = self._approved_files(
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
        with self.assertRaisesRegex(TerritoryCatalogError, "not authorized"):
            TerritoryCatalog(catalog_path, approval_path)

    def test_duplicate_source_filename_fails_closed(self):
        def duplicate(value):
            value["territories"].append(dict(value["territories"][0]))

        temp_dir, catalog_path, approval_path = self._approved_files(
            catalog_mutator=duplicate
        )
        self.addCleanup(temp_dir.cleanup)
        with self.assertRaisesRegex(TerritoryCatalogError, "duplicated"):
            TerritoryCatalog(catalog_path, approval_path)

    def test_catalog_edit_after_approval_fails_hash_check(self):
        temp_dir, catalog_path, approval_path = self._approved_files()
        self.addCleanup(temp_dir.cleanup)
        value = json.loads(catalog_path.read_text(encoding="utf-8"))
        value["territories"][0]["public_name_ru"] = "другое название"
        catalog_path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

        with self.assertRaisesRegex(TerritoryCatalogError, "hash does not match"):
            TerritoryCatalog(catalog_path, approval_path)

    def test_invalid_review_date_fails_closed(self):
        temp_dir, catalog_path, approval_path = self._approved_files(
            approval_mutator=lambda value: value.update(
                {"reviewed_on": "not-a-date"}
            )
        )
        self.addCleanup(temp_dir.cleanup)

        with self.assertRaisesRegex(TerritoryCatalogError, "date is invalid"):
            TerritoryCatalog(catalog_path, approval_path)


if __name__ == "__main__":
    unittest.main()
