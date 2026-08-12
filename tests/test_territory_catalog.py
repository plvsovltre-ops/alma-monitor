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

PROPOSED_CATALOG = DEFAULT_CATALOG
PROPOSED_APPROVAL = DEFAULT_APPROVAL


class TerritoryCatalogTests(unittest.TestCase):
    def _approved_files(
        self,
        catalog_mutator=None,
        approval_mutator=None,
        catalog_source=DEFAULT_CATALOG,
        approval_source=DEFAULT_APPROVAL,
    ):
        catalog = json.loads(Path(catalog_source).read_text(encoding="utf-8"))
        if catalog_mutator:
            catalog_mutator(catalog)
        catalog_text = json.dumps(
            catalog,
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        approval = json.loads(Path(approval_source).read_text(encoding="utf-8"))
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
            "735a42c23a711df15c12193d85f0bfa89d3476193500e87097c10fcbc1b2e26c",
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

    def test_unknown_incident_route_fails_closed(self):
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
            catalog.route_context(territory, "invented_type")

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

    def test_v02_catalog_is_hash_bound_and_author_approved(self):
        proposal_hash = hashlib.sha256(PROPOSED_CATALOG.read_bytes()).hexdigest()
        approval = json.loads(PROPOSED_APPROVAL.read_text(encoding="utf-8"))

        self.assertEqual(proposal_hash, approval["catalog_sha256"])
        self.assertEqual("CONTROLLED_PILOT_APPROVED", approval["decision"])
        self.assertEqual(
            {
                "name": "Yernar Sailybayev",
                "capacity": "AUTHOR_AND_LEGAL_EDITOR",
            },
            approval["reviewer"],
        )
        self.assertEqual("2026-08-13", approval["reviewed_on"])
        self.assertEqual(proposal_hash, TerritoryCatalog().sha256)

    def test_v02_pending_decision_cannot_activate(self):
        temp_dir, catalog_path, approval_path = self._approved_files(
            catalog_source=PROPOSED_CATALOG,
            approval_source=PROPOSED_APPROVAL,
            approval_mutator=lambda value: value.update(
                {
                    "decision": "AUTHOR_REVIEW_REQUIRED",
                    "reviewer": None,
                    "reviewed_on": None,
                }
            ),
        )
        self.addCleanup(temp_dir.cleanup)
        with self.assertRaisesRegex(TerritoryCatalogError, "not approved"):
            TerritoryCatalog(catalog_path, approval_path)

    def test_v02_proposal_routes_all_five_reviewed_signal_types(self):
        temp_dir, catalog_path, approval_path = self._approved_files(
            catalog_source=PROPOSED_CATALOG,
            approval_source=PROPOSED_APPROVAL,
        )
        self.addCleanup(temp_dir.cleanup)
        catalog = TerritoryCatalog(catalog_path, approval_path)
        expected_routes = {
            "waste": "almaty_land_resources",
            "logging": "almaty_ecology_environment",
            "construction": "almaty_urban_planning_control",
            "soil_damage": "almaty_land_resources",
            "water_pollution": "balkhash_alakol_water_inspection",
        }

        for territory in catalog.catalog["territories"]:
            self.assertEqual(
                expected_routes,
                territory["route_ids_by_incident_type"],
            )
            context = catalog.context_for_source(territory["source_file"])
            for incident_type, route_id in expected_routes.items():
                routed = catalog.route_context(context, incident_type)
                self.assertEqual(route_id, routed["route_id"])
                request = catalog.request_for(incident_type)
                self.assertTrue(request["request_ru"].endswith("О результате прошу сообщить."))
                self.assertTrue(request["request_kz"].endswith("Нәтижесі туралы хабарлауды сұраймын."))

        with self.assertRaisesRegex(
            TerritoryCatalogError,
            "no reviewed authority route",
        ):
            catalog.route_context(context, "срубили деревья")

    def test_v02_proposal_uses_only_reviewed_official_sources(self):
        temp_dir, catalog_path, approval_path = self._approved_files(
            catalog_source=PROPOSED_CATALOG,
            approval_source=PROPOSED_APPROVAL,
        )
        self.addCleanup(temp_dir.cleanup)
        catalog = TerritoryCatalog(catalog_path, approval_path)

        self.assertEqual(
            {
                "almaty_land_resources",
                "almaty_ecology_environment",
                "almaty_urban_planning_control",
                "balkhash_alakol_water_inspection",
            },
            set(catalog.catalog["routes"]),
        )
        for route in catalog.catalog["routes"].values():
            self.assertTrue(route["official_source_url"].startswith("https://"))
            self.assertTrue(route["competence_source_url"].startswith("https://"))
            self.assertEqual("2026-08-13", route["verified_on"])


if __name__ == "__main__":
    unittest.main()
