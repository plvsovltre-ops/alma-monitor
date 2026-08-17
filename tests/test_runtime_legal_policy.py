from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from legal_core import (
    IntegrityError,
    RuntimeLegalPolicy,
    RuntimePolicyBlockedError,
    UnknownRuleError,
    UnsupportedIncidentTypeError,
)
from legal_core.runtime_policy import (
    DEFAULT_APPROVAL,
    DEFAULT_POLICY,
    FIELD_SCREENING_APPROVAL,
    FIELD_SCREENING_POLICY,
)


class RuntimeLegalPolicyTests(unittest.TestCase):
    @staticmethod
    def rewrite_json(path: Path, value: dict) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def rebind_policy_hash(self, policy_path: Path, approval_path: Path) -> None:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        approval["policy_sha256"] = hashlib.sha256(policy_path.read_bytes()).hexdigest()
        self.rewrite_json(approval_path, approval)

    def write_approved_policy(self, directory: str) -> tuple[Path, Path]:
        policy = json.loads(DEFAULT_POLICY.read_text(encoding="utf-8"))
        approval = json.loads(DEFAULT_APPROVAL.read_text(encoding="utf-8"))

        policy_path = Path(directory) / "policy.json"
        approval_path = Path(directory) / "approval.json"
        policy_path.write_text(
            json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        approval.update(
            {
                "decision": "CONTROLLED_PILOT_APPROVED",
                "reviewer": approval["required_reviewer"],
                "reviewed_on": "2026-08-12",
                "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
            }
        )
        approval_path.write_text(
            json.dumps(approval, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return policy_path, approval_path

    def test_checked_in_policy_records_exact_author_approval(self):
        policy = RuntimeLegalPolicy()
        self.assertEqual("Yernar Sailybayev", policy.reviewer_name)
        self.assertEqual("2026-08-12", policy.reviewed_on)
        self.assertEqual(
            "dff20191ef26409fa23c1c43130961a9987b081b88b35c79605e94441c4c26b6",
            policy.policy_sha256,
        )
        self.assertEqual("waste", policy.select("waste")["incident_type"])

    def test_pending_approval_blocks_the_exact_unchanged_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path = Path(directory) / "policy.json"
            approval_path = Path(directory) / "approval.json"
            policy_path.write_bytes(DEFAULT_POLICY.read_bytes())
            approval = json.loads(DEFAULT_APPROVAL.read_text(encoding="utf-8"))
            approval["decision"] = "AUTHOR_LEGAL_REVIEW_REQUIRED"
            approval["reviewer"] = None
            approval["reviewed_on"] = None
            self.rewrite_json(approval_path, approval)

            with self.assertRaisesRegex(RuntimePolicyBlockedError, "awaits author"):
                RuntimeLegalPolicy(policy_path, approval_path)

    def test_approved_policy_resolves_all_five_exact_field_values(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path, approval_path = self.write_approved_policy(directory)
            policy = RuntimeLegalPolicy(policy_path, approval_path)

            for incident_type in (
                "waste",
                "logging",
                "construction",
                "soil_damage",
                "water_pollution",
            ):
                with self.subTest(incident_type=incident_type):
                    selection = policy.select(incident_type)
                    self.assertEqual(incident_type, selection["incident_type"])
                    self.assertEqual(
                        selection["rule_ids"],
                        [item["rule_id"] for item in selection["citations"]],
                    )

    def test_unknown_or_empty_incident_type_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path, approval_path = self.write_approved_policy(directory)
            policy = RuntimeLegalPolicy(policy_path, approval_path)

            for value in (None, "", "noise", "waste disposal"):
                with self.subTest(value=value), self.assertRaises(
                    UnsupportedIncidentTypeError
                ):
                    policy.select(value)

    def test_field_screening_policy_uses_context_and_never_model_text(self):
        policy = RuntimeLegalPolicy(
            FIELD_SCREENING_POLICY,
            FIELD_SCREENING_APPROVAL,
        )
        park = policy.select("waste", "ile_alatau_open_source_screening")
        water = policy.select("waste", "water_open_source_screening")
        orchard = policy.select("waste", "orchard_landscape")

        self.assertNotEqual(park["rule_ids"], water["rule_ids"])
        self.assertNotEqual(park["rule_ids"], orchard["rule_ids"])
        self.assertIn("kz-water-85-2-protection-zone-spatial-data", water["rule_ids"])
        self.assertNotIn("kz-oopt-48-1-5-8-other-harm", park["rule_ids"])
        self.assertEqual(
            "ile_alatau_open_source_screening", park["context_profile_id"]
        )
        with self.assertRaisesRegex(
            UnsupportedIncidentTypeError, "no reviewed legal mapping"
        ):
            policy.select("waste", "invented_territory_context")

    def test_description_cannot_participate_in_rule_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path, approval_path = self.write_approved_policy(directory)
            policy = RuntimeLegalPolicy(policy_path, approval_path)

            baseline = policy.select("waste")["rule_ids"]
            # There is deliberately no description argument or LLM selection API.
            self.assertEqual(baseline, policy.select(" WASTE ")["rule_ids"])

    def test_policy_edit_after_review_fails_hash_check(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path, approval_path = self.write_approved_policy(directory)
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["mappings"]["waste"]["rule_ids"].append(
                "kz-almaty-green-p42-3-waste-water"
            )
            policy_path.write_text(
                json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(IntegrityError, "hash does not match"):
                RuntimeLegalPolicy(policy_path, approval_path)

    def test_policy_status_cannot_be_changed_after_exact_hash_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path, approval_path = self.write_approved_policy(directory)
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["status"] = "CONTROLLED_PILOT_APPROVED"
            self.rewrite_json(policy_path, policy)
            self.rebind_policy_hash(policy_path, approval_path)

            with self.assertRaisesRegex(IntegrityError, "marker is invalid"):
                RuntimeLegalPolicy(policy_path, approval_path)

    def test_different_reviewer_cannot_approve_runtime_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path, approval_path = self.write_approved_policy(directory)
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            approval["required_reviewer"]["name"] = "Different reviewer"
            approval["reviewer"]["name"] = "Different reviewer"
            approval_path.write_text(
                json.dumps(approval, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(IntegrityError, "not authorized"):
                RuntimeLegalPolicy(policy_path, approval_path)

    def test_approval_cannot_escalate_beyond_private_controlled_pilot(self):
        invalid_values = (
            ("approval_scope", "PUBLIC_USE"),
            ("independent_lawyer_review_status", "APPROVED"),
            ("public_release_status", "PUBLIC_LEGAL_RELEASE_APPROVED"),
        )
        for field, value in invalid_values:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                policy_path, approval_path = self.write_approved_policy(directory)
                approval = json.loads(approval_path.read_text(encoding="utf-8"))
                approval[field] = value
                self.rewrite_json(approval_path, approval)

                with self.assertRaisesRegex(IntegrityError, "status|scope"):
                    RuntimeLegalPolicy(policy_path, approval_path)

    def test_policy_is_bound_to_exact_legal_release_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path, approval_path = self.write_approved_policy(directory)
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            approval["legal_release_artifacts"]["cards.json"] = "0" * 64
            approval_path.write_text(
                json.dumps(approval, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(IntegrityError, "does not bind"):
                RuntimeLegalPolicy(policy_path, approval_path)

    def test_policy_requires_exactly_all_five_field_values(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path, approval_path = self.write_approved_policy(directory)
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["mappings"].pop("water_pollution")
            self.rewrite_json(policy_path, policy)
            self.rebind_policy_hash(policy_path, approval_path)

            with self.assertRaisesRegex(IntegrityError, "types are incomplete"):
                RuntimeLegalPolicy(policy_path, approval_path)

    def test_policy_rejects_unknown_rule_id(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path, approval_path = self.write_approved_policy(directory)
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["mappings"]["waste"]["rule_ids"] = ["invented-rule-id"]
            self.rewrite_json(policy_path, policy)
            self.rebind_policy_hash(policy_path, approval_path)

            with self.assertRaisesRegex(UnknownRuleError, "invented-rule-id"):
                RuntimeLegalPolicy(policy_path, approval_path)

    def test_policy_requires_unknown_facts_for_every_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path, approval_path = self.write_approved_policy(directory)
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["mappings"]["waste"]["unknowns_ru"] = []
            self.rewrite_json(policy_path, policy)
            self.rebind_policy_hash(policy_path, approval_path)

            with self.assertRaisesRegex(IntegrityError, "unknown-fact list"):
                RuntimeLegalPolicy(policy_path, approval_path)

    def test_policy_approval_cannot_predate_legal_release_review(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path, approval_path = self.write_approved_policy(directory)
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            approval["reviewed_on"] = "2026-08-11"
            self.rewrite_json(approval_path, approval)

            with self.assertRaisesRegex(IntegrityError, "predates"):
                RuntimeLegalPolicy(policy_path, approval_path)


if __name__ == "__main__":
    unittest.main()
