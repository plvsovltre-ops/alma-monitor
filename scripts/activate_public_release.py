#!/usr/bin/env python3
"""Activate a public release only after both exact review records exist."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal_core.public_governance import (
    PublicReleaseGovernance,
    build_public_decision,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--approved-on", required=True)
    args = parser.parse_args()
    governance = PublicReleaseGovernance()
    decision = build_public_decision(governance, approved_on=args.approved_on)
    args.output.write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"decision={decision['decision']}")
    print(f"proposal_sha256={decision['proposal_sha256']}")


if __name__ == "__main__":
    main()
