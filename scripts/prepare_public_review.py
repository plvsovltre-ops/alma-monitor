#!/usr/bin/env python3
"""Export the exact 32-object public legal review view as CSV."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal_core.public_governance import PublicReleaseGovernance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    governance = PublicReleaseGovernance()
    governance.write_review_csv(args.output)
    print(f"release_id={governance.release_id}")
    print(f"proposal_sha256={governance.proposal_sha256}")
    print(f"review_objects={len(governance.review_objects())}")


if __name__ == "__main__":
    main()
