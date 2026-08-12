from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from legal_core import (
    CardBlockedError,
    FactState,
    IntegrityError,
    LegalCoreCatalog,
    SourceChangedError,
    UnknownRuleError,
    normalize_fact_state,
)
from legal_core.catalog import DEFAULT_RELEASE
from scripts.export_legal_core import ReleaseMetadata, write_release


RELEASE_DIR = DEFAULT_RELEASE.parent
METADATA = ReleaseMetadata(
    release_id="kz-0.1.0-rc1",
    review_date="2026-08-11",
    review_view_version="1.2",
    source_spreadsheet_id="test-sheet",
    source_review_view="ALMA Legal Review — Kazakhstan v1.2",
    expected_card_count=122,
    legal_reviewer_name="Yernar Sailybayev",
    legal_review_date="2026-08-12",
)


class LegalCoreReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(DEFAULT_RELEASE.read_text(encoding="utf-8"))
        cls.cards = cls.document["cards"]

    def write_modified_release(self, directory: str, cards: list[dict]) -> Path:
        output = Path(directory) / "release"
        write_release(cards, output, METADATA)
        return output / "cards.json"

    @staticmethod
    def rewrite_bundle_checksums(release_dir: Path) -> None:
        """Rebuild checksums to test semantic gates, not only file integrity."""
        manifest_path = release_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name in ("cards.json", "review.json", "sources.json"):
            manifest["artifacts"][name] = hashlib.sha256(
                (release_dir / name).read_bytes()
            ).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        checksums = {
            name: hashlib.sha256((release_dir / name).read_bytes()).hexdigest()
            for name in ("cards.json", "manifest.json", "review.json", "sources.json")
        }
        (release_dir / "SHA256SUMS").write_text(
            "".join(f"{checksums[name]}  {name}\n" for name in sorted(checksums)),
            encoding="ascii",
        )

    def test_release_has_accepted_unique_cards(self):
        catalog = LegalCoreCatalog()
        self.assertEqual(122, len(self.cards))
        self.assertEqual(122, len(catalog.rule_ids()))
        self.assertEqual(len(self.cards), len({card["rule_id"] for card in self.cards}))
        for card in self.cards:
            self.assertRegex(card["rule_id"], r"^kz-[a-z0-9-]+$")
            self.assertRegex(card["card_hash"], r"^sha256:[0-9a-f]{64}$")
            self.assertRegex(card["official_url"], r"^https://(www\.)?adilet\.zan\.kz/")
            self.assertEqual("OWNER_ACCEPTED", card["review"]["owner_status"])
            self.assertEqual("PILOT_ELIGIBLE", card["review"]["pilot_status"])
            self.assertEqual(
                "AUTHOR_LEGAL_REVIEW_APPROVED",
                card["review"]["legal_editor_status"],
            )
            self.assertEqual(
                "INDEPENDENT_LAWYER_REVIEW_PENDING",
                card["review"]["independent_lawyer_status"],
            )
            self.assertEqual(
                "PUBLIC_LEGAL_RELEASE_BLOCKED",
                card["review"]["public_release_status"],
            )

    def test_unknown_article_is_not_substituted(self):
        catalog = LegalCoreCatalog()
        with self.assertRaises(UnknownRuleError):
            catalog.citations(["kz-invented-article"])

    def test_citation_text_comes_from_the_card(self):
        catalog = LegalCoreCatalog()
        rule_id = catalog.rule_ids()[0]
        card = catalog.require_card(rule_id)
        citation = catalog.citations([rule_id])[0]
        self.assertEqual(card["provision"], citation["provision"])
        self.assertEqual(card["official_url"], citation["official_url"])
        self.assertEqual(card["safe_summary"], citation["safe_summary"])

    def test_public_legal_release_is_blocked(self):
        catalog = LegalCoreCatalog()
        with self.assertRaises(CardBlockedError):
            catalog.require_card(
                catalog.rule_ids()[0],
                use_case="public_legal_release",
            )

    def test_public_release_requires_independent_lawyer_approval(self):
        changed = copy.deepcopy(self.cards)
        changed[0]["review"]["public_release_status"] = (
            "PUBLIC_LEGAL_RELEASE_APPROVED"
        )
        changed[0]["review"]["independent_lawyer_status"] = (
            "INDEPENDENT_LAWYER_REVIEW_PENDING"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, changed)
            catalog = LegalCoreCatalog(path)
            with self.assertRaises(CardBlockedError):
                catalog.require_card(
                    changed[0]["rule_id"],
                    use_case="public_legal_release",
                )

    def test_card_edits_cannot_unlock_public_release(self):
        changed = copy.deepcopy(self.cards)
        changed[0]["review"]["public_release_status"] = (
            "PUBLIC_LEGAL_RELEASE_APPROVED"
        )
        changed[0]["review"]["independent_lawyer_status"] = (
            "INDEPENDENT_LAWYER_REVIEW_APPROVED"
        )
        changed[0]["review"]["source_change_status"] = "UNCHANGED"
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, changed)
            catalog = LegalCoreCatalog(path)
            with self.assertRaises(CardBlockedError):
                catalog.require_card(
                    changed[0]["rule_id"],
                    use_case="public_legal_release",
                )

    def test_controlled_pilot_requires_author_legal_review(self):
        changed = copy.deepcopy(self.cards)
        changed[0]["review"]["legal_editor_status"] = (
            "LEGAL_EDITOR_REVIEW_REQUIRED"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, changed)
            catalog = LegalCoreCatalog(path)
            with self.assertRaises(CardBlockedError):
                catalog.require_card(changed[0]["rule_id"])

    def test_vague_pilot_use_case_is_rejected(self):
        catalog = LegalCoreCatalog()
        with self.assertRaisesRegex(ValueError, "Unsupported Legal Core use case"):
            catalog.require_card(catalog.rule_ids()[0], use_case="pilot")

    def test_changed_source_blocks_card(self):
        changed = copy.deepcopy(self.cards)
        changed[0]["review"]["source_change_status"] = (
            "SOURCE_CHANGED_UNREVIEWED"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, changed)
            catalog = LegalCoreCatalog(path)
            with self.assertRaises(SourceChangedError):
                catalog.require_card(changed[0]["rule_id"])

    def test_unknown_source_status_blocks_card(self):
        changed = copy.deepcopy(self.cards)
        changed[0]["review"]["source_change_status"] = "UNRECOGNIZED"
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, changed)
            catalog = LegalCoreCatalog(path)
            with self.assertRaises(SourceChangedError):
                catalog.require_card(changed[0]["rule_id"])

    def test_missing_source_status_blocks_card(self):
        changed = copy.deepcopy(self.cards)
        del changed[0]["review"]["source_change_status"]
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, changed)
            catalog = LegalCoreCatalog(path)
            with self.assertRaises(SourceChangedError):
                catalog.require_card(changed[0]["rule_id"])

    def test_tampered_release_fails_checksum_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, copy.deepcopy(self.cards))
            document = json.loads(path.read_text(encoding="utf-8"))
            document["cards"][0]["safe_summary"] = "TAMPERED AFTER MANIFEST"
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(IntegrityError, "checksum mismatch"):
                LegalCoreCatalog(path)

    def test_card_hash_blocks_tamper_even_if_bundle_checksums_are_rebuilt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, copy.deepcopy(self.cards))
            release_dir = path.parent
            document = json.loads(path.read_text(encoding="utf-8"))
            document["cards"][0]["safe_summary"] = "TAMPERED AND RECHECKSUMMED"
            path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest_path = release_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["cards.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            checksums = {
                name: hashlib.sha256((release_dir / name).read_bytes()).hexdigest()
                for name in (
                    "cards.json",
                    "manifest.json",
                    "review.json",
                    "sources.json",
                )
            }
            (release_dir / "SHA256SUMS").write_text(
                "".join(f"{checksums[name]}  {name}\n" for name in sorted(checksums)),
                encoding="ascii",
            )
            with self.assertRaisesRegex(IntegrityError, "card hash mismatch"):
                LegalCoreCatalog(path)

    def test_unknown_fact_stays_unknown(self):
        self.assertEqual(FactState.UNKNOWN, normalize_fact_state(None))
        self.assertEqual(FactState.UNKNOWN, normalize_fact_state("UNKNOWN"))
        self.assertNotEqual(FactState.ABSENT, normalize_fact_state(None))

    def test_manifest_checksums_match_release_files(self):
        manifest = json.loads((RELEASE_DIR / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest["artifacts"].items():
            actual = hashlib.sha256((RELEASE_DIR / name).read_bytes()).hexdigest()
            self.assertEqual(expected, actual, name)
        checksum_lines = (RELEASE_DIR / "SHA256SUMS").read_text(encoding="ascii").splitlines()
        self.assertEqual(4, len(checksum_lines))
        for line in checksum_lines:
            self.assertRegex(
                line,
                r"^[0-9a-f]{64}  (cards|manifest|review|sources)\.json$",
            )

    def test_review_record_binds_author_approval_to_release(self):
        catalog = LegalCoreCatalog()
        review = catalog.review_record
        manifest = json.loads(
            (RELEASE_DIR / "manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual("Yernar Sailybayev", review["reviewer"]["name"])
        self.assertEqual("AUTHOR_AND_LEGAL_EDITOR", review["reviewer"]["capacity"])
        self.assertEqual("CONTROLLED_PILOT_APPROVED", review["decision"])
        self.assertEqual("CONTROLLED_PILOT_ONLY", review["scope"])
        self.assertEqual(
            {
                name: manifest["artifacts"][name]
                for name in ("cards.json", "sources.json")
            },
            review["reviewed_artifacts"],
        )

    def test_tampered_review_record_fails_checksum_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, copy.deepcopy(self.cards))
            review_path = path.parent / "review.json"
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["decision"] = "PUBLIC_LEGAL_RELEASE_APPROVED"
            review_path.write_text(json.dumps(review), encoding="utf-8")

            with self.assertRaisesRegex(IntegrityError, "checksum mismatch"):
                LegalCoreCatalog(path)

    def test_rechecksummed_review_cannot_claim_independent_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, copy.deepcopy(self.cards))
            release_dir = path.parent
            review_path = release_dir / "review.json"
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["reviewer"]["capacity"] = "INDEPENDENT_LAWYER"
            review["independent_lawyer_review_status"] = (
                "INDEPENDENT_LAWYER_REVIEW_APPROVED"
            )
            review["public_release_status"] = "PUBLIC_LEGAL_RELEASE_APPROVED"
            review_path.write_text(
                json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.rewrite_bundle_checksums(release_dir)

            with self.assertRaisesRegex(IntegrityError, "capacity is unsupported"):
                LegalCoreCatalog(path)

    def test_rechecksummed_manifest_cannot_disagree_with_author_review(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, copy.deepcopy(self.cards))
            release_dir = path.parent
            manifest_path = release_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["legal_reviewer_name"] = "Different reviewer"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.rewrite_bundle_checksums(release_dir)

            with self.assertRaisesRegex(
                IntegrityError,
                "legal review metadata is inconsistent",
            ):
                LegalCoreCatalog(path)

    def test_rechecksummed_bundle_rejects_a_different_reviewer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, copy.deepcopy(self.cards))
            release_dir = path.parent
            review_path = release_dir / "review.json"
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["reviewer"]["name"] = "Different reviewer"
            review_path.write_text(
                json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest_path = release_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["legal_reviewer_name"] = "Different reviewer"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.rewrite_bundle_checksums(release_dir)

            with self.assertRaisesRegex(IntegrityError, "reviewer is not authorized"):
                LegalCoreCatalog(path)

    def test_rechecksummed_author_review_cannot_unlock_public_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_modified_release(directory, copy.deepcopy(self.cards))
            release_dir = path.parent
            review_path = release_dir / "review.json"
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["independent_lawyer_review_status"] = (
                "INDEPENDENT_LAWYER_REVIEW_APPROVED"
            )
            review["public_release_status"] = "PUBLIC_LEGAL_RELEASE_APPROVED"
            review_path.write_text(
                json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest_path = release_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["independent_lawyer_review_status"] = (
                "INDEPENDENT_LAWYER_REVIEW_APPROVED"
            )
            manifest["public_legal_release_status"] = (
                "PUBLIC_LEGAL_RELEASE_APPROVED"
            )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.rewrite_bundle_checksums(release_dir)

            with self.assertRaisesRegex(
                IntegrityError,
                "cannot be asserted by this release",
            ):
                LegalCoreCatalog(path)


if __name__ == "__main__":
    unittest.main()
