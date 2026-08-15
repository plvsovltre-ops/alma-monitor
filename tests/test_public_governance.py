from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from legal_core import (
    LegalCoreCatalog,
    PublicGovernanceError,
    PublicReleaseBlockedError,
    PublicReleaseGovernance,
    RuntimeLegalPolicy,
    RuntimePolicyBlockedError,
)
from legal_core.public_governance import (
    DEFAULT_AUTHORSHIP_LICENSING_APPROVAL,
    DEFAULT_PROPOSAL,
    REVIEW_CSV_FIELDS,
    build_public_decision,
    build_review_record,
)


class PublicReleaseGovernanceTests(unittest.TestCase):
    @staticmethod
    def write_json(path: Path, value: dict) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def complete_review_csv(governance: PublicReleaseGovernance, path: Path) -> None:
        governance.write_review_csv(path)
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
            writer.writeheader()
            for row in rows:
                row["Согласен"] = "TRUE"
                row["Не согласен"] = "FALSE"
                writer.writerow(row)

    def approved_governance(self, directory: str) -> PublicReleaseGovernance:
        initial = PublicReleaseGovernance()
        root = Path(directory)
        review_csv = root / "review.csv"
        self.complete_review_csv(initial, review_csv)

        author_path = root / "author.json"
        independent_path = root / "independent.json"
        decision_path = root / "decision.json"
        author = build_review_record(
            initial,
            review_csv,
            role="author",
            reviewer_name="Yernar Sailybayev",
            reviewed_on="2026-08-14",
            review_source_type="ALMA_PROJECT_CONVERSATION",
        )
        independent = build_review_record(
            initial,
            review_csv,
            role="independent",
            reviewer_reference="independent-legal-reviewer-kz-001",
            reviewed_on="2026-08-14",
            review_source_type="RESTRICTED_GOOGLE_SHEET",
            jurisdiction="KZ",
            identity_verified=True,
            independence_verified=True,
            qualification_verified=True,
            conflict_of_interest_declared=False,
            confidential_attestation_consent=True,
            confidential_attestation_sha256="1" * 64,
        )
        self.write_json(author_path, author)
        self.write_json(independent_path, independent)
        self.write_json(
            decision_path,
            {
                "schema_version": "1.0",
                "release_id": initial.release_id,
                "decision": "PUBLIC_LEGAL_RELEASE_BLOCKED",
                "proposal_sha256": initial.proposal_sha256,
            },
        )

        reviewed = PublicReleaseGovernance(
            author_review_path=author_path,
            independent_review_path=independent_path,
            decision_path=decision_path,
        )
        decision = build_public_decision(reviewed, approved_on="2026-08-14")
        self.write_json(decision_path, decision)
        return PublicReleaseGovernance(
            author_review_path=author_path,
            independent_review_path=independent_path,
            decision_path=decision_path,
        )

    def test_checked_in_public_release_is_valid_and_activated(self):
        governance = PublicReleaseGovernance()
        self.assertEqual(32, len(governance.review_objects()))
        governance.require_public_release()
        self.assertEqual("2026-08-15", governance.reviewed_on)

    def test_checked_in_authorship_and_licensing_approval_is_hash_bound(self):
        governance = PublicReleaseGovernance()
        approval = governance.authorship_licensing_approval
        self.assertEqual(
            "AUTHORSHIP_AND_LICENSING_APPROVED",
            approval["decision"],
        )
        self.assertEqual("Apache-2.0", approval["software_license"])
        self.assertEqual("CC-BY-4.0", approval["original_content_license"])
        self.assertFalse(approval["exclusive_rights_transferred"])
        self.assertFalse(approval["organization_transfer_approved"])

    def test_changed_approved_license_document_is_rejected(self):
        approval = json.loads(
            DEFAULT_AUTHORSHIP_LICENSING_APPROVAL.read_text(encoding="utf-8")
        )
        approval["documents"]["AUTHORS"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "approval.json"
            self.write_json(path, approval)
            with self.assertRaisesRegex(
                PublicGovernanceError,
                "licensing document changed",
            ):
                PublicReleaseGovernance(
                    authorship_licensing_approval_path=path,
                )

    def test_review_is_compact_complete_and_source_precedes_norm(self):
        governance = PublicReleaseGovernance()
        counts = Counter(row["object_type"] for row in governance.review_objects())
        self.assertEqual(
            {
                "LEGAL_CARD": 18,
                "POLICY_MAPPING": 5,
                "AUTHORITY_ROUTE": 4,
                "REQUEST_TEMPLATE": 5,
            },
            counts,
        )
        self.assertLess(
            REVIEW_CSV_FIELDS.index("Официальный источник"),
            REVIEW_CSV_FIELDS.index("Норма / решение"),
        )

    def test_incomplete_or_disagreed_row_blocks_approval(self):
        governance = PublicReleaseGovernance()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            governance.write_review_csv(path)
            with self.assertRaisesRegex(PublicReleaseBlockedError, "not agreed"):
                governance.validate_completed_review_csv(path)

            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
                writer.writeheader()
                for index, row in enumerate(rows):
                    row["Согласен"] = "TRUE" if index else "FALSE"
                    row["Не согласен"] = "FALSE" if index else "TRUE"
                    writer.writerow(row)
            with self.assertRaisesRegex(PublicReleaseBlockedError, "not agreed"):
                governance.validate_completed_review_csv(path)

    def test_changed_review_text_or_artifact_hash_is_rejected(self):
        governance = PublicReleaseGovernance()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.complete_review_csv(governance, path)
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["Текст для проверки"] += " changed"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(PublicGovernanceError, "object changed"):
                governance.validate_completed_review_csv(path)

            proposal = json.loads(DEFAULT_PROPOSAL.read_text(encoding="utf-8"))
            proposal["artifacts"]["runtime_policy"]["sha256"] = "0" * 64
            proposal_path = Path(directory) / "proposal.json"
            self.write_json(proposal_path, proposal)
            with self.assertRaisesRegex(PublicGovernanceError, "artifact changed"):
                PublicReleaseGovernance(proposal_path=proposal_path)

    def test_review_object_manifest_cannot_hide_a_governed_change(self):
        with tempfile.TemporaryDirectory() as directory:
            proposal = json.loads(DEFAULT_PROPOSAL.read_text(encoding="utf-8"))
            proposal["review_object_manifest_sha256"] = "0" * 64
            proposal_path = Path(directory) / "proposal.json"
            self.write_json(proposal_path, proposal)
            with self.assertRaisesRegex(PublicGovernanceError, "manifest changed"):
                PublicReleaseGovernance(proposal_path=proposal_path)

    def test_author_reference_cannot_act_as_independent_lawyer(self):
        governance = PublicReleaseGovernance()
        with tempfile.TemporaryDirectory() as directory:
            review_csv = Path(directory) / "review.csv"
            self.complete_review_csv(governance, review_csv)
            with self.assertRaisesRegex(PublicGovernanceError, "must differ"):
                build_review_record(
                    governance,
                    review_csv,
                    role="independent",
                    reviewer_reference="author-yernar-sailybayev",
                    reviewed_on="2026-08-14",
                    review_source_type="RESTRICTED_GOOGLE_SHEET",
                    jurisdiction="KZ",
                    identity_verified=True,
                    independence_verified=True,
                    qualification_verified=True,
                    conflict_of_interest_declared=False,
                    confidential_attestation_consent=True,
                    confidential_attestation_sha256="1" * 64,
                )

    def test_independent_private_verification_and_consent_are_required(self):
        governance = PublicReleaseGovernance()
        with tempfile.TemporaryDirectory() as directory:
            review_csv = Path(directory) / "review.csv"
            self.complete_review_csv(governance, review_csv)
            for kwargs, message in (
                ({"identity_verified": False}, "identity"),
                ({"independence_verified": False}, "independence"),
                ({"qualification_verified": False}, "qualification"),
                ({"conflict_of_interest_declared": None}, "conflict"),
                ({"confidential_attestation_consent": False}, "consent"),
                ({"confidential_attestation_sha256": ""}, "attestation"),
            ):
                values = {
                    "identity_verified": True,
                    "independence_verified": True,
                    "qualification_verified": True,
                    "conflict_of_interest_declared": False,
                    "confidential_attestation_consent": True,
                    "confidential_attestation_sha256": "1" * 64,
                    **kwargs,
                }
                with self.subTest(message=message), self.assertRaisesRegex(
                    PublicGovernanceError, message
                ):
                    build_review_record(
                        governance,
                        review_csv,
                        role="independent",
                        reviewer_reference="independent-legal-reviewer-kz-001",
                        reviewed_on="2026-08-14",
                        review_source_type="RESTRICTED_GOOGLE_SHEET",
                        jurisdiction="KZ",
                        **values,
                    )

    def test_review_source_type_is_restricted(self):
        governance = PublicReleaseGovernance()
        with tempfile.TemporaryDirectory() as directory:
            review_csv = Path(directory) / "review.csv"
            self.complete_review_csv(governance, review_csv)
            with self.assertRaisesRegex(PublicGovernanceError, "source type"):
                build_review_record(
                    governance,
                    review_csv,
                    role="author",
                    reviewer_name="Yernar Sailybayev",
                    reviewed_on="2026-08-14",
                    review_source_type="PUBLIC_URL",
                )

    def test_final_activation_cannot_predate_either_review(self):
        initial = PublicReleaseGovernance()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review_csv = root / "review.csv"
            self.complete_review_csv(initial, review_csv)
            author_path = root / "author.json"
            independent_path = root / "independent.json"
            decision_path = root / "decision.json"
            self.write_json(
                author_path,
                build_review_record(
                    initial,
                    review_csv,
                    role="author",
                    reviewer_name="Yernar Sailybayev",
                    reviewed_on="2026-08-14",
                    review_source_type="ALMA_PROJECT_CONVERSATION",
                ),
            )
            self.write_json(
                independent_path,
                build_review_record(
                    initial,
                    review_csv,
                    role="independent",
                    reviewer_reference="independent-legal-reviewer-kz-001",
                    reviewed_on="2026-08-15",
                    review_source_type="RESTRICTED_GOOGLE_SHEET",
                    jurisdiction="KZ",
                    identity_verified=True,
                    independence_verified=True,
                    qualification_verified=True,
                    conflict_of_interest_declared=False,
                    confidential_attestation_consent=True,
                    confidential_attestation_sha256="1" * 64,
                ),
            )
            self.write_json(
                decision_path,
                {
                    "schema_version": "1.0",
                    "release_id": initial.release_id,
                    "decision": "PUBLIC_LEGAL_RELEASE_BLOCKED",
                    "proposal_sha256": initial.proposal_sha256,
                },
            )
            reviewed = PublicReleaseGovernance(
                author_review_path=author_path,
                independent_review_path=independent_path,
                decision_path=decision_path,
            )
            with self.assertRaisesRegex(PublicGovernanceError, "predates"):
                build_public_decision(reviewed, approved_on="2026-08-14")

    def test_two_approved_reviews_unlock_only_the_exact_public_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            governance = self.approved_governance(directory)
            governance.require_public_release()
            rule_id = governance.active_rule_ids[0]
            card = LegalCoreCatalog().require_card(
                rule_id,
                use_case="public_legal_release",
                public_governance=governance,
            )
            self.assertEqual(rule_id, card["rule_id"])
            with self.assertRaisesRegex(PublicReleaseBlockedError, "outside"):
                governance.require_rule("kz-rule-outside-public-scope")

    def test_public_runtime_is_blocked_without_governance_and_works_with_it(self):
        with self.assertRaisesRegex(RuntimePolicyBlockedError, "two-person"):
            RuntimeLegalPolicy(use_case="public_legal_release")
        with tempfile.TemporaryDirectory() as directory:
            governance = self.approved_governance(directory)
            policy = RuntimeLegalPolicy(
                use_case="public_legal_release",
                public_governance=governance,
            )
            self.assertEqual("public_legal_release", policy.release_mode)
            self.assertEqual(
                "Independent legal reviewer (identity confidential)",
                policy.reviewer_name,
            )
            self.assertEqual("waste", policy.select("waste")["incident_type"])

    def test_independent_public_record_rejects_identity_data(self):
        with tempfile.TemporaryDirectory() as directory:
            governance = self.approved_governance(directory)
            root = Path(directory)
            independent_path = root / "independent.json"
            independent = json.loads(independent_path.read_text(encoding="utf-8"))
            for field, value in (
                ("name", "Private person"),
                ("email", "private@example.test"),
                ("qualification", "Identifying qualification details"),
                ("review_source_url", "https://docs.google.com/private"),
            ):
                with self.subTest(field=field):
                    changed = dict(independent)
                    changed[field] = value
                    self.write_json(independent_path, changed)
                    with self.assertRaisesRegex(
                        PublicGovernanceError,
                        "confidential identity data",
                    ):
                        PublicReleaseGovernance(
                            author_review_path=root / "author.json",
                            independent_review_path=independent_path,
                            decision_path=root / "decision.json",
                        )
            self.write_json(independent_path, independent)

if __name__ == "__main__":
    unittest.main()
