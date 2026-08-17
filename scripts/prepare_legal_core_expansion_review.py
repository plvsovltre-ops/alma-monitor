#!/usr/bin/env python3
"""Export the exact ALMA Legal Core expansion review table."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal_core.expansion_review import LegalCoreExpansionReview


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("legal-core-expansion-0.2.0-rc1-review.csv"),
    )
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    review = LegalCoreExpansionReview()
    review.write_review_csv(args.output)
    manifest = {
        "schema_version": "1.0",
        "proposal_id": review.proposal_id,
        "proposal_sha256": review.proposal_sha256,
        "review_object_count": len(review.review_objects()),
        "status": "LEGAL_REVIEW_REQUIRED",
        "activation_gate": review.proposal["activation_gate"],
    }
    if args.manifest:
        args.manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
