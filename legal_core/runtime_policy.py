"""Fail-closed runtime selection policy for ALMA Legal Core cards."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from .catalog import LegalCoreCatalog
from .integrity import IntegrityError, sha256_file
from .public_governance import PublicReleaseGovernance


POLICY_DIR = Path(__file__).resolve().parent / "policies" / "kz" / "0.1.0-rc1"
DEFAULT_POLICY = POLICY_DIR / "policy.json"
DEFAULT_APPROVAL = POLICY_DIR / "approval.json"
FIELD_SCREENING_POLICY_DIR = (
    Path(__file__).resolve().parent / "policies" / "kz" / "0.1.1-screening"
)
FIELD_SCREENING_POLICY = FIELD_SCREENING_POLICY_DIR / "policy.json"
FIELD_SCREENING_APPROVAL = FIELD_SCREENING_POLICY_DIR / "approval.json"
AUTHORIZED_REVIEWER = "Yernar Sailybayev"
AUTHORIZED_CAPACITY = "AUTHOR_AND_LEGAL_EDITOR"
IMMUTABLE_POLICY_STATUS = "AUTHOR_LEGAL_REVIEW_REQUIRED"
SUPPORTED_INCIDENT_TYPES = {
    "construction",
    "logging",
    "soil_damage",
    "waste",
    "water_pollution",
}
SUPPORTED_SCREENING_CONTEXTS = {
    "ile_alatau_open_source_screening",
    "water_open_source_screening",
}


class RuntimePolicyError(RuntimeError):
    """Base error for deterministic runtime policy failures."""


class RuntimePolicyBlockedError(RuntimePolicyError):
    """Raised until the exact runtime policy is approved by the author."""


class UnsupportedIncidentTypeError(RuntimePolicyError):
    """Raised when a field value has no reviewed deterministic mapping."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"Runtime legal {label} is invalid") from exc
    if not isinstance(value, dict):
        raise IntegrityError(f"Runtime legal {label} must be an object")
    return value


class RuntimeLegalPolicy:
    """Resolve an exact incident type to author-reviewed Legal Core cards.

    Free text is never used for rule selection. The policy must be approved by
    Yernar Sailybayev and bound to the exact policy and Legal Core artifacts.
    """

    def __init__(
        self,
        policy_path: str | Path = DEFAULT_POLICY,
        approval_path: str | Path = DEFAULT_APPROVAL,
        catalog: LegalCoreCatalog | None = None,
        *,
        use_case: str = "controlled_pilot",
        public_governance: PublicReleaseGovernance | None = None,
    ):
        self.policy_path = Path(policy_path)
        self.approval_path = Path(approval_path)
        self.policy = _load_json(self.policy_path, "policy")
        self.approval = _load_json(self.approval_path, "approval")
        self.catalog = catalog or LegalCoreCatalog()
        if use_case not in {"controlled_pilot", "public_legal_release"}:
            raise ValueError(f"Unsupported Legal Core use case: {use_case}")
        if use_case == "public_legal_release" and public_governance is None:
            raise RuntimePolicyBlockedError(
                "Public runtime policy requires two-person release governance"
            )
        self.use_case = use_case
        self.public_governance = public_governance
        self._validate()

    def _validate(self) -> None:
        schema_version = self.policy.get("schema_version")
        if schema_version not in {"1.0", "1.1"}:
            raise IntegrityError("Runtime legal policy schema is unsupported")
        policy_id = self.policy.get("policy_id")
        release_id = self.policy.get("legal_release_id")
        if not isinstance(policy_id, str) or not policy_id:
            raise IntegrityError("Runtime legal policy ID is missing")
        if release_id != self.catalog.release.get("release", {}).get("id"):
            raise IntegrityError("Runtime policy and Legal Core release IDs differ")

        approval = self.approval
        if approval.get("schema_version") != schema_version:
            raise IntegrityError("Runtime legal approval schema is unsupported")
        if approval.get("policy_id") != policy_id:
            raise IntegrityError("Runtime policy and approval IDs differ")
        required = approval.get("required_reviewer")
        if required != {
            "name": AUTHORIZED_REVIEWER,
            "capacity": AUTHORIZED_CAPACITY,
        }:
            raise IntegrityError("Runtime legal policy reviewer is not authorized")
        allowed_scope = {
            "1.0": "PRIVATE_CONTROLLED_PILOT_ONLY",
            "1.1": "CONTROLLED_FIELD_SCREENING_ONLY",
        }[schema_version]
        if approval.get("approval_scope") != allowed_scope:
            raise IntegrityError("Runtime legal approval scope is invalid")
        allowed_independent_status = {
            "1.0": "INDEPENDENT_LAWYER_REVIEW_PENDING",
            "1.1": "INDEPENDENT_LAWYER_REVIEW_REPORTED_CONFIDENTIAL",
        }[schema_version]
        if approval.get("independent_lawyer_review_status") != allowed_independent_status:
            raise IntegrityError("Runtime legal independent review status is invalid")
        if approval.get("public_release_status") != "PUBLIC_LEGAL_RELEASE_BLOCKED":
            raise IntegrityError("Runtime legal public release status is invalid")

        expected_policy_hash = hashlib.sha256(self.policy_path.read_bytes()).hexdigest()
        if approval.get("policy_sha256") != expected_policy_hash:
            raise IntegrityError("Runtime legal policy approval hash does not match")

        release_dir = self.catalog.release_path.parent
        expected_release_artifacts = {
            name: sha256_file(release_dir / name)
            for name in ("cards.json", "review.json")
        }
        if approval.get("legal_release_artifacts") != expected_release_artifacts:
            raise IntegrityError(
                "Runtime policy approval does not bind the Legal Core release"
            )

        mappings = self.policy.get("mappings")
        if not isinstance(mappings, dict) or not mappings:
            raise IntegrityError("Runtime legal policy has no incident mappings")
        if set(mappings) != SUPPORTED_INCIDENT_TYPES:
            raise IntegrityError("Runtime legal policy incident types are incomplete")
        for incident_type, mapping in mappings.items():
            if (
                not isinstance(incident_type, str)
                or incident_type != incident_type.strip().lower()
            ):
                raise IntegrityError("Runtime incident type is not canonical")
            if not isinstance(mapping, dict):
                raise IntegrityError(f"Runtime mapping is invalid: {incident_type}")
            if not isinstance(mapping.get("label_ru"), str) or not mapping[
                "label_ru"
            ].strip():
                raise IntegrityError(f"Runtime mapping label is invalid: {incident_type}")
            rule_ids = mapping.get("rule_ids")
            if (
                not isinstance(rule_ids, list)
                or not rule_ids
                or len(rule_ids) > 8
            ):
                raise IntegrityError(f"Runtime rule list is invalid: {incident_type}")
            if not all(isinstance(rule_id, str) and rule_id for rule_id in rule_ids):
                raise IntegrityError(f"Runtime rule ID is invalid: {incident_type}")
            if len(rule_ids) != len(set(rule_ids)):
                raise IntegrityError(f"Runtime rule list is invalid: {incident_type}")
            unknowns = mapping.get("unknowns_ru")
            if (
                not isinstance(unknowns, list)
                or not unknowns
                or not all(
                    isinstance(item, str) and item.strip() for item in unknowns
                )
            ):
                raise IntegrityError(f"Runtime unknown-fact list is invalid: {incident_type}")
            # Resolve every configured ID now. A missing, changed, or blocked
            # card blocks the entire policy before any incident is processed.
            self.catalog.citations(
                rule_ids,
                use_case=self.use_case,
                public_governance=self.public_governance,
            )

        context_mappings = self.policy.get("context_mappings", {})
        if schema_version == "1.0":
            if context_mappings:
                raise IntegrityError("Legacy runtime policy cannot add context mappings")
        else:
            if not isinstance(context_mappings, dict) or set(context_mappings) != SUPPORTED_SCREENING_CONTEXTS:
                raise IntegrityError("Runtime legal screening contexts are incomplete")
            for context_id, context_rules in context_mappings.items():
                if not isinstance(context_rules, dict) or set(context_rules) != SUPPORTED_INCIDENT_TYPES:
                    raise IntegrityError(
                        f"Runtime legal screening matrix is incomplete: {context_id}"
                    )
                for incident_type, mapping in context_rules.items():
                    self._validate_mapping(
                        f"{context_id}:{incident_type}",
                        mapping,
                    )

        # The policy is the immutable object that the reviewer approved. Its
        # original proposal marker remains unchanged so its SHA-256 stays the
        # exact value cited in the approval. The separate approval record is
        # the only object that can unlock controlled-pilot use.
        if self.policy.get("status") != IMMUTABLE_POLICY_STATUS:
            raise IntegrityError("Runtime legal policy marker is invalid")
        if approval.get("decision") != "CONTROLLED_PILOT_APPROVED":
            raise RuntimePolicyBlockedError(
                "Runtime legal policy awaits author/legal-editor approval"
            )
        reviewer = approval.get("reviewer")
        if reviewer != {
            "name": AUTHORIZED_REVIEWER,
            "capacity": AUTHORIZED_CAPACITY,
        }:
            raise IntegrityError("Runtime legal approval reviewer is invalid")
        try:
            reviewed_on = date.fromisoformat(approval.get("reviewed_on"))
        except (TypeError, ValueError) as exc:
            raise IntegrityError("Runtime legal approval date is invalid") from exc
        release_reviewed_on = date.fromisoformat(
            self.catalog.review_record["reviewed_on"]
        )
        if reviewed_on < release_reviewed_on:
            raise IntegrityError(
                "Runtime legal approval predates the Legal Core release review"
            )

    @property
    def policy_id(self) -> str:
        return self.policy["policy_id"]

    @property
    def legal_release_id(self) -> str:
        return self.policy["legal_release_id"]

    @property
    def policy_sha256(self) -> str:
        return self.approval["policy_sha256"]

    @property
    def reviewer_name(self) -> str:
        if self.public_governance is not None:
            return self.public_governance.independent_reviewer_name
        return self.approval["reviewer"]["name"]

    @property
    def reviewed_on(self) -> str:
        if self.public_governance is not None:
            return self.public_governance.reviewed_on
        return self.approval["reviewed_on"]

    @property
    def release_mode(self) -> str:
        return self.use_case

    @property
    def governance_release_id(self) -> str:
        if self.public_governance is None:
            return ""
        return self.public_governance.release_id

    @property
    def governance_proposal_sha256(self) -> str:
        if self.public_governance is None:
            return ""
        return self.public_governance.proposal_sha256

    def _validate_mapping(self, label: str, mapping: object) -> None:
        if not isinstance(mapping, dict):
            raise IntegrityError(f"Runtime mapping is invalid: {label}")
        if not isinstance(mapping.get("label_ru"), str) or not mapping["label_ru"].strip():
            raise IntegrityError(f"Runtime mapping label is invalid: {label}")
        rule_ids = mapping.get("rule_ids")
        if (
            not isinstance(rule_ids, list)
            or not rule_ids
            or len(rule_ids) > 8
            or not all(isinstance(rule_id, str) and rule_id for rule_id in rule_ids)
            or len(rule_ids) != len(set(rule_ids))
        ):
            raise IntegrityError(f"Runtime rule list is invalid: {label}")
        unknowns = mapping.get("unknowns_ru")
        if not isinstance(unknowns, list) or not unknowns or not all(
            isinstance(item, str) and item.strip() for item in unknowns
        ):
            raise IntegrityError(f"Runtime unknown-fact list is invalid: {label}")
        self.catalog.citations(
            rule_ids,
            use_case=self.use_case,
            public_governance=self.public_governance,
        )

    def select(
        self,
        incident_type: object,
        context_profile_id: object | None = None,
    ) -> dict[str, Any]:
        normalized = str(incident_type or "").strip().lower()
        context_id = str(context_profile_id or "").strip()
        if context_id in (self.policy.get("context_mappings") or {}):
            mapping = self.policy["context_mappings"][context_id].get(normalized)
        elif context_id and context_id != "orchard_landscape":
            raise UnsupportedIncidentTypeError(
                f"Territory context has no reviewed legal mapping: {context_id}"
            )
        else:
            mapping = self.policy["mappings"].get(normalized)
        if mapping is None:
            raise UnsupportedIncidentTypeError(
                f"Incident type has no reviewed legal mapping: {normalized or '<empty>'}"
            )
        citations = self.catalog.citations(
            mapping["rule_ids"],
            use_case=self.use_case,
            public_governance=self.public_governance,
        )
        return {
            "incident_type": normalized,
            "context_profile_id": context_id or "orchard_landscape",
            "label_ru": mapping["label_ru"],
            "rule_ids": list(mapping["rule_ids"]),
            "unknowns_ru": list(mapping["unknowns_ru"]),
            "citations": citations,
        }
