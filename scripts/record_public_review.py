#!/usr/bin/env python3
"""Record an author or independent-lawyer review of exact public objects."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal_core.public_governance import (
    PublicReleaseGovernance,
    build_review_record,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("review_csv", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--role", choices=("author", "independent"), required=True)
    parser.add_argument("--reviewer-name", default="")
    parser.add_argument("--reviewer-reference", default="")
    parser.add_argument("--reviewed-on", required=True)
    parser.add_argument(
        "--review-source-type",
        choices=("ALMA_PROJECT_CONVERSATION", "RESTRICTED_GOOGLE_SHEET"),
        required=True,
    )
    parser.add_argument("--jurisdiction", default="")
    parser.add_argument("--identity-verified", action="store_true")
    parser.add_argument("--independence-verified", action="store_true")
    parser.add_argument("--qualification-verified", action="store_true")
    parser.add_argument(
        "--declare-no-conflict",
        action="store_true",
        help="Required for the independent lawyer.",
    )
    parser.add_argument(
        "--consent-confidential-attestation",
        action="store_true",
        help=(
            "Confirms consent to confidential verification and retention "
            "outside the public repository."
        ),
    )
    parser.add_argument("--confidential-attestation-sha256", default="")
    args = parser.parse_args()
    governance = PublicReleaseGovernance()
    record = build_review_record(
        governance,
        args.review_csv,
        role=args.role,
        reviewer_name=args.reviewer_name,
        reviewer_reference=args.reviewer_reference,
        reviewed_on=args.reviewed_on,
        review_source_type=args.review_source_type,
        jurisdiction=args.jurisdiction,
        identity_verified=(True if args.identity_verified else None),
        independence_verified=(True if args.independence_verified else None),
        qualification_verified=(True if args.qualification_verified else None),
        conflict_of_interest_declared=(False if args.declare_no_conflict else None),
        confidential_attestation_consent=(
            True if args.consent_confidential_attestation else None
        ),
        confidential_attestation_sha256=args.confidential_attestation_sha256,
    )
    args.output.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"recorded={record['decision']}")
    print(f"proposal_sha256={record['proposal_sha256']}")
    print(f"review_csv_sha256={record['review_csv_sha256']}")


if __name__ == "__main__":
    main()
