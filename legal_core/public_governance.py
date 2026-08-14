"""Two-person, hash-bound governance for an ALMA public legal release."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from .integrity import canonical_card_hash, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOVERNANCE_DIR = (
    PROJECT_ROOT / "governance" / "public" / "kz" / "0.1.0-rc1"
)
DEFAULT_PROPOSAL = GOVERNANCE_DIR / "proposal.json"
DEFAULT_AUTHOR_REVIEW = GOVERNANCE_DIR / "author_review.json"
DEFAULT_INDEPENDENT_REVIEW = GOVERNANCE_DIR / "independent_review.json"
DEFAULT_DECISION = GOVERNANCE_DIR / "decision.json"

AUTHOR_REVIEWER = {
    "name": "Yernar Sailybayev",
    "capacity": "AUTHOR_AND_LEGAL_EDITOR",
}
REVIEW_CSV_COLUMNS = (
    ("object_type", "Тип объекта"),
    ("object_id", "ID объекта"),
    ("official_source", "Официальный источник"),
    ("norm_or_decision", "Норма / решение"),
    ("review_text", "Текст для проверки"),
    ("object_sha256", "SHA-256 объекта"),
    ("agree", "Согласен"),
    ("disagree", "Не согласен"),
    ("comment", "Комментарий"),
)
REVIEW_CSV_FIELDS = tuple(label for _, label in REVIEW_CSV_COLUMNS)
OBJECT_TYPE_LABELS = {
    "LEGAL_CARD": "Карточка нормы",
    "POLICY_MAPPING": "Сопоставление сигнала",
    "AUTHORITY_ROUTE": "Маршрут органа",
    "REQUEST_TEMPLATE": "Просьба",
}
OBJECT_TYPE_BY_LABEL = {label: key for key, label in OBJECT_TYPE_LABELS.items()}
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class PublicGovernanceError(RuntimeError):
    """Raised when a public release is incomplete, changed, or unapproved."""


class PublicReleaseBlockedError(PublicGovernanceError):
    """Raised until both reviewers and the release owner approve exact hashes."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicGovernanceError(f"Public governance {label} is invalid") from exc
    if not isinstance(value, dict):
        raise PublicGovernanceError(f"Public governance {label} must be an object")
    return value


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicGovernanceError(f"Public governance {label} is missing")
    return value.strip()


def _required_https_url(value: object, label: str) -> str:
    url = _required_text(value, label)
    if not url.startswith("https://"):
        raise PublicGovernanceError(f"Public governance {label} must use HTTPS")
    return url


def _canonical_object_hash(row: dict[str, str]) -> str:
    payload = {
        field: str(row.get(field, "")).strip()
        for field in (
            "object_type",
            "object_id",
            "official_source",
            "norm_or_decision",
            "review_text",
        )
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_checkbox(value: object) -> bool | None:
    normalized = str(value or "").strip().casefold()
    if normalized in {"true", "да", "yes", "1", "согласен", "agree"}:
        return True
    if normalized in {"false", "нет", "no", "0", "не согласен", "disagree"}:
        return False
    return None


class PublicReleaseGovernance:
    """Validate one exact public-release proposal and its two reviews."""

    def __init__(
        self,
        proposal_path: str | Path = DEFAULT_PROPOSAL,
        author_review_path: str | Path = DEFAULT_AUTHOR_REVIEW,
        independent_review_path: str | Path = DEFAULT_INDEPENDENT_REVIEW,
        decision_path: str | Path = DEFAULT_DECISION,
        *,
        project_root: str | Path = PROJECT_ROOT,
    ):
        self.project_root = Path(project_root).resolve()
        self.proposal_path = Path(proposal_path)
        self.author_review_path = Path(author_review_path)
        self.independent_review_path = Path(independent_review_path)
        self.decision_path = Path(decision_path)
        self.proposal = _load_json(self.proposal_path, "proposal")
        self.author_review = _load_json(self.author_review_path, "author review")
        self.independent_review = _load_json(
            self.independent_review_path,
            "independent review",
        )
        self.decision = _load_json(self.decision_path, "decision")
        self.proposal_sha256 = sha256_file(self.proposal_path)
        self._artifacts: dict[str, dict[str, Any]] = {}
        self._validate_proposal()
        self._validate_review_record(self.author_review, "author")
        self._validate_review_record(self.independent_review, "independent")
        self._validate_decision()

    @property
    def release_id(self) -> str:
        return self.proposal["release_id"]

    @property
    def active_rule_ids(self) -> tuple[str, ...]:
        return tuple(self.proposal["review_scope"]["legal_rule_ids"])

    @property
    def independent_reviewer_name(self) -> str:
        reviewer = self.independent_review.get("reviewer") or {}
        return str(reviewer.get("name") or "")

    @property
    def reviewed_on(self) -> str:
        return str(self.decision.get("approved_on") or "")

    def _artifact_path(self, relative_path: str) -> Path:
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise PublicGovernanceError(
                f"Public governance artifact path is unsafe: {relative_path}"
            )
        resolved = (self.project_root / path).resolve()
        if resolved == self.project_root or self.project_root not in resolved.parents:
            raise PublicGovernanceError(
                f"Public governance artifact escapes project root: {relative_path}"
            )
        return resolved

    def _validate_proposal(self) -> None:
        proposal = self.proposal
        if proposal.get("schema_version") != "1.0":
            raise PublicGovernanceError("Public proposal schema is unsupported")
        _required_text(proposal.get("release_id"), "release ID")
        if proposal.get("status") != "PUBLIC_REVIEW_REQUIRED":
            raise PublicGovernanceError("Public proposal status is invalid")
        if proposal.get("jurisdiction") != "KZ":
            raise PublicGovernanceError("Public proposal jurisdiction is unsupported")
        if proposal.get("review_view_version") != "1.0":
            raise PublicGovernanceError("Public review view version is unsupported")
        if proposal.get("authorship") != (
            "ALMA was initiated and originally designed by Yernar Sailybayev "
            "in Almaty, Kazakhstan."
        ):
            raise PublicGovernanceError("Public proposal authorship is invalid")

        artifacts = proposal.get("artifacts")
        expected_artifacts = {
            "legal_cards",
            "legal_sources",
            "legal_owner_review",
            "runtime_policy",
            "runtime_policy_approval",
            "territory_catalog",
            "territory_catalog_approval",
            "response_catalog",
            "response_catalog_approval",
        }
        if not isinstance(artifacts, dict) or set(artifacts) != expected_artifacts:
            raise PublicGovernanceError("Public proposal artifact set is incomplete")
        for artifact_id, artifact in artifacts.items():
            if not isinstance(artifact, dict):
                raise PublicGovernanceError(
                    f"Public proposal artifact is invalid: {artifact_id}"
                )
            relative_path = _required_text(
                artifact.get("path"),
                f"artifact path {artifact_id}",
            )
            expected_hash = _required_text(
                artifact.get("sha256"),
                f"artifact hash {artifact_id}",
            )
            if not SHA256_HEX.fullmatch(expected_hash):
                raise PublicGovernanceError(
                    f"Public proposal artifact hash is invalid: {artifact_id}"
                )
            path = self._artifact_path(relative_path)
            if not path.is_file() or sha256_file(path) != expected_hash:
                raise PublicGovernanceError(
                    f"Public proposal artifact changed: {artifact_id}"
                )
            self._artifacts[artifact_id] = {
                "path": path,
                "document": _load_json(path, f"artifact {artifact_id}"),
                "sha256": expected_hash,
            }

        scope = proposal.get("review_scope")
        expected_scope = {
            "legal_rule_ids",
            "policy_mapping_ids",
            "authority_route_ids",
            "request_template_ids",
        }
        if not isinstance(scope, dict) or set(scope) != expected_scope:
            raise PublicGovernanceError("Public review scope is incomplete")
        for scope_name, identifiers in scope.items():
            if (
                not isinstance(identifiers, list)
                or not identifiers
                or not all(isinstance(item, str) and item.strip() for item in identifiers)
                or identifiers != sorted(set(identifiers))
            ):
                raise PublicGovernanceError(
                    f"Public review scope is invalid: {scope_name}"
                )

        cards = self._artifacts["legal_cards"]["document"].get("cards")
        if not isinstance(cards, list):
            raise PublicGovernanceError("Public legal card artifact is invalid")
        card_ids = {card.get("rule_id") for card in cards if isinstance(card, dict)}
        if not set(scope["legal_rule_ids"]).issubset(card_ids):
            raise PublicGovernanceError("Public review references an unknown legal card")

        policy = self._artifacts["runtime_policy"]["document"]
        mappings = policy.get("mappings")
        if not isinstance(mappings, dict):
            raise PublicGovernanceError("Public runtime policy is invalid")
        if scope["policy_mapping_ids"] != sorted(mappings):
            raise PublicGovernanceError("Public policy review scope is incomplete")
        mapped_rule_ids = {
            rule_id
            for mapping in mappings.values()
            for rule_id in mapping.get("rule_ids", [])
        }
        if set(scope["legal_rule_ids"]) != mapped_rule_ids:
            raise PublicGovernanceError(
                "Public legal card scope must equal the runtime policy rule set"
            )

        territory = self._artifacts["territory_catalog"]["document"]
        routes = territory.get("routes")
        requests = territory.get("request_templates")
        if not isinstance(routes, dict) or not isinstance(requests, dict):
            raise PublicGovernanceError("Public territory catalog is invalid")
        if scope["authority_route_ids"] != sorted(routes):
            raise PublicGovernanceError("Public authority review scope is incomplete")
        if scope["request_template_ids"] != sorted(requests):
            raise PublicGovernanceError("Public request review scope is incomplete")

        objects = self.review_objects()
        if len(objects) != proposal.get("review_object_count"):
            raise PublicGovernanceError("Public review object count is incorrect")
        if len(objects) != 32:
            raise PublicGovernanceError("Initial public review must contain 32 objects")
        review_manifest_sha256 = hashlib.sha256(
            json.dumps(
                objects,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if proposal.get("review_object_manifest_sha256") != review_manifest_sha256:
            raise PublicGovernanceError("Public review object manifest changed")

    def review_objects(self) -> list[dict[str, str]]:
        """Return the exact compact objects shown to both legal reviewers."""
        scope = self.proposal["review_scope"]
        cards_document = self._artifacts["legal_cards"]["document"]
        cards = {card["rule_id"]: card for card in cards_document["cards"]}
        rows: list[dict[str, str]] = []
        for rule_id in scope["legal_rule_ids"]:
            card = cards[rule_id]
            row = {
                "object_type": "LEGAL_CARD",
                "object_id": rule_id,
                "official_source": card["official_url"],
                "norm_or_decision": card["provision"],
                "review_text": card["safe_summary"],
            }
            row["object_sha256"] = _canonical_object_hash(row)
            if card.get("card_hash") != canonical_card_hash(card):
                raise PublicGovernanceError(
                    f"Public legal card hash is invalid: {rule_id}"
                )
            rows.append(row)

        policy = self._artifacts["runtime_policy"]["document"]
        response = self._artifacts["response_catalog"]["document"]
        territory = self._artifacts["territory_catalog"]["document"]
        used_context_ids = sorted(
            {
                territory_item["context_profile_id"]
                for territory_item in territory["territories"]
            }
        )
        contexts = {
            context_id: response["context_profiles"][context_id]
            for context_id in used_context_ids
        }
        principle_sources = {
            principle["official_url"]
            for context in contexts.values()
            for principle in context["principles"]
        }
        for mapping_id in scope["policy_mapping_ids"]:
            mapping = policy["mappings"][mapping_id]
            official_sources = sorted(
                {cards[rule_id]["official_url"] for rule_id in mapping["rule_ids"]}
                | principle_sources
            )
            action = response["actions"][mapping_id]
            row = {
                "object_type": "POLICY_MAPPING",
                "object_id": mapping_id,
                "official_source": " | ".join(official_sources),
                "norm_or_decision": mapping["label_ru"],
                "review_text": json.dumps(
                    {
                        "rule_ids": mapping["rule_ids"],
                        "unknowns_ru": mapping["unknowns_ru"],
                        "context_profiles": contexts,
                        "assessment_ru": action["assessment_ru"],
                        "assessment_kz": action["assessment_kz"],
                        "next_ru": action["next_ru"],
                        "next_kz": action["next_kz"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
            row["object_sha256"] = _canonical_object_hash(row)
            rows.append(row)

        for route_id in scope["authority_route_ids"]:
            route = territory["routes"][route_id]
            territory_coverage = []
            for territory_item in territory["territories"]:
                incident_types = sorted(
                    incident_type
                    for incident_type, configured_route_id in territory_item[
                        "route_ids_by_incident_type"
                    ].items()
                    if configured_route_id == route_id
                )
                if incident_types:
                    territory_coverage.append(
                        {
                            "territory_id": territory_item["territory_id"],
                            "source_file": territory_item["source_file"],
                            "public_name_ru": territory_item["public_name_ru"],
                            "public_name_kz": territory_item["public_name_kz"],
                            "purpose_ru": territory_item["purpose_ru"],
                            "purpose_kz": territory_item["purpose_kz"],
                            "context_profile_id": territory_item[
                                "context_profile_id"
                            ],
                            "incident_types": incident_types,
                        }
                    )
            row = {
                "object_type": "AUTHORITY_ROUTE",
                "object_id": route_id,
                "official_source": route["official_source_url"],
                "norm_or_decision": route["official_name_ru"],
                "review_text": json.dumps(
                    {
                        "official_name_kz": route["official_name_kz"],
                        "competence_source_url": route["competence_source_url"],
                        "forwarding_ru": route["forwarding_ru"],
                        "forwarding_kz": route["forwarding_kz"],
                        "territory_coverage": territory_coverage,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
            row["object_sha256"] = _canonical_object_hash(row)
            rows.append(row)

        procedural_source = response["procedural_basis"]["official_url"]
        for template_id in scope["request_template_ids"]:
            template = territory["request_templates"][template_id]
            row = {
                "object_type": "REQUEST_TEMPLATE",
                "object_id": template_id,
                "official_source": procedural_source,
                "norm_or_decision": json.dumps(
                    {
                        "subject_ru": template["subject_ru"],
                        "subject_kz": template["subject_kz"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "review_text": json.dumps(
                    {
                        "request_ru": template["request_ru"],
                        "request_kz": template["request_kz"],
                        "procedural_request_ru": response["procedural_basis"][
                            "request_ru"
                        ],
                        "procedural_request_kz": response["procedural_basis"][
                            "request_kz"
                        ],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
            row["object_sha256"] = _canonical_object_hash(row)
            rows.append(row)

        rows.sort(key=lambda row: (row["object_type"], row["object_id"]))
        return rows

    def write_review_csv(self, path: str | Path) -> None:
        with Path(path).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
            writer.writeheader()
            for item in self.review_objects():
                values = {
                    **item,
                    "object_type": OBJECT_TYPE_LABELS[item["object_type"]],
                    "agree": "",
                    "disagree": "",
                    "comment": "",
                }
                writer.writerow(
                    {label: values[key] for key, label in REVIEW_CSV_COLUMNS}
                )

    def validate_completed_review_csv(self, path: str | Path) -> str:
        review_path = Path(path)
        try:
            with review_path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if tuple(reader.fieldnames or ()) != REVIEW_CSV_FIELDS:
                    raise PublicGovernanceError("Public review CSV columns are invalid")
                rows = list(reader)
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            raise PublicGovernanceError("Public review CSV is invalid") from exc

        expected = {
            (row["object_type"], row["object_id"]): row
            for row in self.review_objects()
        }
        if len(rows) != len(expected):
            raise PublicGovernanceError("Public review CSV row count is incorrect")
        seen: set[tuple[str, str]] = set()
        for display_row in rows:
            row = {
                key: str(display_row.get(label, "")).strip()
                for key, label in REVIEW_CSV_COLUMNS
            }
            row["object_type"] = OBJECT_TYPE_BY_LABEL.get(
                row["object_type"],
                row["object_type"],
            )
            key = (row["object_type"].strip(), row["object_id"].strip())
            if key in seen or key not in expected:
                raise PublicGovernanceError("Public review CSV contains an unknown row")
            seen.add(key)
            expected_row = expected[key]
            for field in (
                "official_source",
                "norm_or_decision",
                "review_text",
                "object_sha256",
            ):
                if row[field].strip() != expected_row[field]:
                    raise PublicGovernanceError(
                        f"Public review object changed: {key[0]}/{key[1]}"
                    )
            agree = _normalized_checkbox(row["agree"])
            disagree = _normalized_checkbox(row["disagree"])
            if agree is not True or disagree is not False:
                raise PublicReleaseBlockedError(
                    f"Public review is not agreed: {key[0]}/{key[1]}"
                )
        return sha256_file(review_path)

    def _validate_review_record(self, review: dict[str, Any], role: str) -> None:
        if review.get("schema_version") != "1.0":
            raise PublicGovernanceError(f"Public {role} review schema is unsupported")
        if review.get("release_id") != self.release_id:
            raise PublicGovernanceError(f"Public {role} review release ID differs")
        if review.get("proposal_sha256") != self.proposal_sha256:
            raise PublicGovernanceError(f"Public {role} review proposal hash differs")

        if role == "author":
            pending_decision = "AUTHOR_PUBLIC_REVIEW_PENDING"
            approved_decision = "AUTHOR_PUBLIC_RELEASE_APPROVED"
            expected_capacity = "AUTHOR_AND_LEGAL_EDITOR"
        else:
            pending_decision = "INDEPENDENT_REVIEW_PENDING"
            approved_decision = "INDEPENDENT_LAWYER_REVIEW_APPROVED"
            expected_capacity = "INDEPENDENT_LAWYER"

        decision = review.get("decision")
        if decision == pending_decision:
            if role == "author" and review.get("reviewer") != AUTHOR_REVIEWER:
                raise PublicGovernanceError("Pending author identity is invalid")
            if role == "independent" and review.get("reviewer") is not None:
                raise PublicGovernanceError("Pending independent reviewer must be empty")
            return
        if decision != approved_decision:
            raise PublicGovernanceError(f"Public {role} review decision is invalid")

        reviewer = review.get("reviewer")
        if not isinstance(reviewer, dict):
            raise PublicGovernanceError(f"Public {role} reviewer is missing")
        name = _required_text(reviewer.get("name"), f"{role} reviewer name")
        if reviewer.get("capacity") != expected_capacity:
            raise PublicGovernanceError(f"Public {role} reviewer capacity is invalid")
        if role == "author" and reviewer != AUTHOR_REVIEWER:
            raise PublicGovernanceError("Public author reviewer is not authorized")
        if role == "independent":
            if name == AUTHOR_REVIEWER["name"]:
                raise PublicGovernanceError("Independent reviewer must differ from author")
            _required_text(review.get("qualification"), "independent qualification")
            if review.get("conflict_of_interest_declared") is not False:
                raise PublicGovernanceError(
                    "Independent reviewer must declare no conflict of interest"
                )
            if review.get("public_attribution_consent") is not True:
                raise PublicGovernanceError(
                    "Independent reviewer public attribution consent is required"
                )
        try:
            date.fromisoformat(_required_text(review.get("reviewed_on"), "review date"))
        except ValueError as exc:
            raise PublicGovernanceError("Public review date is invalid") from exc
        review_csv_sha256 = _required_text(
            review.get("review_csv_sha256"),
            "review CSV hash",
        )
        if not SHA256_HEX.fullmatch(review_csv_sha256):
            raise PublicGovernanceError("Public review CSV hash is invalid")
        if review.get("reviewed_object_count") != len(self.review_objects()):
            raise PublicGovernanceError("Public reviewed object count is incorrect")
        _required_https_url(review.get("review_source_url"), "review source URL")

    def _validate_decision(self) -> None:
        decision = self.decision
        if decision.get("schema_version") != "1.0":
            raise PublicGovernanceError("Public release decision schema is unsupported")
        if decision.get("release_id") != self.release_id:
            raise PublicGovernanceError("Public release decision ID differs")
        if decision.get("proposal_sha256") != self.proposal_sha256:
            raise PublicGovernanceError("Public release decision proposal hash differs")
        state = decision.get("decision")
        if state == "PUBLIC_LEGAL_RELEASE_BLOCKED":
            return
        if state != "PUBLIC_LEGAL_RELEASE_APPROVED":
            raise PublicGovernanceError("Public release decision is invalid")
        if self.author_review.get("decision") != "AUTHOR_PUBLIC_RELEASE_APPROVED":
            raise PublicGovernanceError(
                "Public release decision lacks the approved author review"
            )
        if (
            self.independent_review.get("decision")
            != "INDEPENDENT_LAWYER_REVIEW_APPROVED"
        ):
            raise PublicGovernanceError(
                "Public release decision lacks the approved independent review"
            )
        if decision.get("activated_by") != AUTHOR_REVIEWER:
            raise PublicGovernanceError("Public release activator is not authorized")
        try:
            approved_on = date.fromisoformat(
                _required_text(decision.get("approved_on"), "approval date")
            )
        except ValueError as exc:
            raise PublicGovernanceError("Public release approval date is invalid") from exc
        review_dates = (
            date.fromisoformat(self.author_review["reviewed_on"]),
            date.fromisoformat(self.independent_review["reviewed_on"]),
        )
        if approved_on < max(review_dates):
            raise PublicGovernanceError(
                "Public release approval predates a legal review"
            )
        if decision.get("author_review_sha256") != sha256_file(self.author_review_path):
            raise PublicGovernanceError("Public author review hash differs")
        if decision.get("independent_review_sha256") != sha256_file(
            self.independent_review_path
        ):
            raise PublicGovernanceError("Public independent review hash differs")

    def require_public_release(self) -> None:
        if self.author_review.get("decision") != "AUTHOR_PUBLIC_RELEASE_APPROVED":
            raise PublicReleaseBlockedError("Public release awaits author approval")
        if (
            self.independent_review.get("decision")
            != "INDEPENDENT_LAWYER_REVIEW_APPROVED"
        ):
            raise PublicReleaseBlockedError(
                "Public release awaits independent lawyer approval"
            )
        if self.decision.get("decision") != "PUBLIC_LEGAL_RELEASE_APPROVED":
            raise PublicReleaseBlockedError("Public legal release is not activated")

    def require_rule(self, rule_id: str) -> None:
        self.require_public_release()
        if rule_id not in self.active_rule_ids:
            raise PublicReleaseBlockedError(
                f"Rule is outside the approved public scope: {rule_id}"
            )


def build_review_record(
    governance: PublicReleaseGovernance,
    review_csv_path: str | Path,
    *,
    role: str,
    reviewer_name: str,
    reviewed_on: str,
    review_source_url: str,
    qualification: str = "",
    conflict_of_interest_declared: bool | None = None,
    public_attribution_consent: bool | None = None,
) -> dict[str, Any]:
    """Create one review record after validating every exact checkbox row."""
    review_csv_sha256 = governance.validate_completed_review_csv(review_csv_path)
    try:
        date.fromisoformat(reviewed_on)
    except ValueError as exc:
        raise PublicGovernanceError("Public review date is invalid") from exc
    _required_https_url(review_source_url, "review source URL")

    base: dict[str, Any] = {
        "schema_version": "1.0",
        "release_id": governance.release_id,
        "proposal_sha256": governance.proposal_sha256,
        "reviewed_on": reviewed_on,
        "review_csv_sha256": review_csv_sha256,
        "reviewed_object_count": len(governance.review_objects()),
        "review_source_url": review_source_url,
    }
    if role == "author":
        if reviewer_name != AUTHOR_REVIEWER["name"]:
            raise PublicGovernanceError("Public author reviewer is not authorized")
        return {
            **base,
            "decision": "AUTHOR_PUBLIC_RELEASE_APPROVED",
            "reviewer": dict(AUTHOR_REVIEWER),
            "statement": (
                "The author and legal editor approved the exact public-release "
                "proposal and all listed review objects."
            ),
        }
    if role != "independent":
        raise PublicGovernanceError("Public review role is unsupported")
    if reviewer_name == AUTHOR_REVIEWER["name"]:
        raise PublicGovernanceError("Independent reviewer must differ from author")
    _required_text(qualification, "independent qualification")
    if conflict_of_interest_declared is not False:
        raise PublicGovernanceError(
            "Independent reviewer must declare no conflict of interest"
        )
    if public_attribution_consent is not True:
        raise PublicGovernanceError(
            "Independent reviewer public attribution consent is required"
        )
    return {
        **base,
        "decision": "INDEPENDENT_LAWYER_REVIEW_APPROVED",
        "reviewer": {
            "name": _required_text(reviewer_name, "independent reviewer name"),
            "capacity": "INDEPENDENT_LAWYER",
        },
        "qualification": qualification.strip(),
        "conflict_of_interest_declared": False,
        "public_attribution_consent": True,
        "statement": (
            "The independent lawyer approved the exact public-release proposal "
            "and all listed review objects without establishing facts or guilt "
            "in any individual observation."
        ),
    }


def build_public_decision(
    governance: PublicReleaseGovernance,
    *,
    approved_on: str,
) -> dict[str, Any]:
    """Bind final activation to the two exact approved review files."""
    if governance.author_review.get("decision") != "AUTHOR_PUBLIC_RELEASE_APPROVED":
        raise PublicReleaseBlockedError("Public release awaits author approval")
    if (
        governance.independent_review.get("decision")
        != "INDEPENDENT_LAWYER_REVIEW_APPROVED"
    ):
        raise PublicReleaseBlockedError("Public release awaits independent approval")
    try:
        approval_date = date.fromisoformat(approved_on)
    except ValueError as exc:
        raise PublicGovernanceError("Public release approval date is invalid") from exc
    review_dates = (
        date.fromisoformat(governance.author_review["reviewed_on"]),
        date.fromisoformat(governance.independent_review["reviewed_on"]),
    )
    if approval_date < max(review_dates):
        raise PublicGovernanceError("Public release approval predates a legal review")
    return {
        "schema_version": "1.0",
        "release_id": governance.release_id,
        "decision": "PUBLIC_LEGAL_RELEASE_APPROVED",
        "proposal_sha256": governance.proposal_sha256,
        "author_review_sha256": sha256_file(governance.author_review_path),
        "independent_review_sha256": sha256_file(governance.independent_review_path),
        "approved_on": approved_on,
        "activated_by": dict(AUTHOR_REVIEWER),
        "statement": (
            "This approval activates only the exact hash-bound public release. "
            "ALMA remains a drafting and citizen-science tool, not legal advice "
            "or a determination of violation or guilt."
        ),
    }
