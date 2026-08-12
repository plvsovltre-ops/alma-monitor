import json
import tempfile
import unittest
from pathlib import Path

from scripts.approve_territory_catalog import approve
from territory_catalog import DEFAULT_CATALOG, TerritoryCatalog


class ApproveTerritoryCatalogTests(unittest.TestCase):
    def test_author_can_approve_exact_catalog_for_private_pilot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog_path = Path(temp_dir) / "catalog.json"
            approval_path = Path(temp_dir) / "approval.json"
            catalog_path.write_bytes(DEFAULT_CATALOG.read_bytes())

            digest = approve(
                catalog_path,
                approval_path,
                "Yernar Sailybayev",
                "AUTHOR_AND_LEGAL_EDITOR",
                "2026-08-13",
            )

            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            self.assertEqual(digest, approval["catalog_sha256"])
            self.assertEqual("CONTROLLED_PILOT_APPROVED", approval["decision"])
            TerritoryCatalog(catalog_path, approval_path)

    def test_other_reviewer_cannot_approve(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "not authorized"):
                approve(
                    DEFAULT_CATALOG,
                    Path(temp_dir) / "approval.json",
                    "Language model",
                    "AUTHOR_AND_LEGAL_EDITOR",
                    "2026-08-13",
                )


if __name__ == "__main__":
    unittest.main()
