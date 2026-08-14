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
    parser.add_argument("--reviewer-name", required=True)
    parser.add_argument("--reviewed-on", required=True)
    parser.add_argument("--review-source-url", required=True)
    parser.add_argument("--qualification", default="")
    parser.add_argument(
        "--declare-no-conflict",
        action="store_true",
        help="Required for the independent lawyer.",
    )
    parser.add_argument(
        "--consent-public-attribution",
        action="store_true",
        help="Required for the independent lawyer.",
    )
    args = parser.parse_args()
    governance = PublicReleaseGovernance()
    record = build_review_record(
        governance,
        args.review_csv,
        role=args.role,
        reviewer_name=args.reviewer_name,
        reviewed_on=args.reviewed_on,
        review_source_url=args.review_source_url,
        qualification=args.qualification,
        conflict_of_interest_declared=(False if args.declare_no_conflict else None),
        public_attribution_consent=(
            True if args.consent_public_attribution else None
        ),
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
