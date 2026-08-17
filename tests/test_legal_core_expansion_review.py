from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from legal_core.expansion_review import (
    DEFAULT_PROPOSAL,
    REVIEW_CSV_FIELDS,
    ExpansionActivationBlockedError,
    ExpansionReviewError,
    LegalCoreExpansionReview,
)


class LegalCoreExpansionReviewTests(unittest.TestCase):
    @staticmethod
    def write_json(path: Path, value: dict) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def complete_csv(review: LegalCoreExpansionReview, path: Path) -> None:
        review.write_review_csv(path)
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
            writer.writeheader()
            for row in rows:
                row["Согласен"] = "TRUE"
                row["Не согласен"] = "FALSE"
                writer.writerow(row)

    def test_checked_in_proposal_is_complete_and_not_active(self):
        review = LegalCoreExpansionReview()
        counts = Counter(row["object_type"] for row in review.review_objects())
        self.assertEqual(42, len(review.review_objects()))
        self.assertEqual(23, counts["LEGAL_CARD"])
        self.assertEqual(10, counts["POLICY_MAPPING"])
        self.assertEqual(2, counts["CONTEXT_PROFILE"])
        self.assertEqual(2, counts["AUTHORITY_ROUTE"])
        self.assertEqual(2, counts["REQUEST_TEMPLATE_FAMILY"])
        self.assertEqual(2, counts["SPATIAL_SOURCE"])
        self.assertEqual(1, counts["LEGAL_CARD_STATUS"])
        with self.assertRaises(ExpansionActivationBlockedError):
            review.require_activation_ready()

        manifest_path = DEFAULT_PROPOSAL.with_name("review_manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(review.proposal_id, manifest["proposal_id"])
        self.assertEqual(review.proposal_sha256, manifest["proposal_sha256"])
        self.assertEqual(len(review.review_objects()), manifest["review_object_count"])

    def test_mapping_matrix_is_exact_for_both_contexts(self):
        review = LegalCoreExpansionReview()
        mappings = {
            row["object_id"]
            for row in review.review_objects()
            if row["object_type"] == "POLICY_MAPPING"
        }
        self.assertEqual(
            {
                f"{context}:{incident_type}"
                for context in (
                    "ile_alatau_national_park",
                    "almaty_water_protection_strip",
                )
                for incident_type in (
                    "waste",
                    "logging",
                    "construction",
                    "soil_damage",
                    "water_pollution",
                )
            },
            mappings,
        )

    def test_official_source_precedes_norm_and_approval_columns_are_simple(self):
        self.assertLess(
            REVIEW_CSV_FIELDS.index("Официальный источник"),
            REVIEW_CSV_FIELDS.index("Норма / решение"),
        )
        self.assertIn("Согласен", REVIEW_CSV_FIELDS)
        self.assertIn("Не согласен", REVIEW_CSV_FIELDS)

    def test_completed_unchanged_review_is_accepted(self):
        review = LegalCoreExpansionReview()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.complete_csv(review, path)
            digest = review.validate_completed_review_csv(path)
            self.assertEqual(64, len(digest))

    def test_missing_or_disagreed_review_is_rejected(self):
        review = LegalCoreExpansionReview()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            review.write_review_csv(path)
            with self.assertRaisesRegex(ExpansionReviewError, "not agreed"):
                review.validate_completed_review_csv(path)

            self.complete_csv(review, path)
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows.pop()
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ExpansionReviewError, "row count"):
                review.validate_completed_review_csv(path)

    def test_tampered_review_text_is_rejected(self):
        review = LegalCoreExpansionReview()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.complete_csv(review, path)
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["Текст для проверки"] += " изменено"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ExpansionReviewError, "object changed"):
                review.validate_completed_review_csv(path)

    def test_non_https_source_is_rejected(self):
        proposal = json.loads(DEFAULT_PROPOSAL.read_text(encoding="utf-8"))
        proposal["review_objects"][0]["official_source"] = "http://example.test"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proposal.json"
            self.write_json(path, proposal)
            with self.assertRaisesRegex(ExpansionReviewError, "must use HTTPS"):
                LegalCoreExpansionReview(path)

    def test_duplicate_object_is_rejected(self):
        proposal = json.loads(DEFAULT_PROPOSAL.read_text(encoding="utf-8"))
        proposal["review_objects"].append(proposal["review_objects"][0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proposal.json"
            self.write_json(path, proposal)
            with self.assertRaisesRegex(ExpansionReviewError, "duplicate"):
                LegalCoreExpansionReview(path)

    def test_superseded_article_48_card_cannot_be_mapped(self):
        proposal = json.loads(DEFAULT_PROPOSAL.read_text(encoding="utf-8"))
        for item in proposal["review_objects"]:
            if item["object_type"] == "POLICY_MAPPING":
                item["review_text"] += " kz-oopt-48-1-5-8-other-harm"
                break
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proposal.json"
            self.write_json(path, proposal)
            with self.assertRaisesRegex(ExpansionReviewError, "Superseded"):
                LegalCoreExpansionReview(path)


if __name__ == "__main__":
    unittest.main()
