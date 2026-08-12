"""Bind author approval to the exact reviewed territory catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path


AUTHORIZED_REVIEWER = "Yernar Sailybayev"
AUTHORIZED_CAPACITY = "AUTHOR_AND_LEGAL_EDITOR"


def approve(
    catalog_path: Path,
    approval_path: Path,
    reviewer: str,
    capacity: str,
    reviewed_on: str,
) -> str:
    if reviewer != AUTHORIZED_REVIEWER or capacity != AUTHORIZED_CAPACITY:
        raise ValueError("Territory catalog reviewer is not authorized")
    try:
        date.fromisoformat(reviewed_on)
    except ValueError as exc:
        raise ValueError("Territory catalog review date is invalid") from exc

    raw = catalog_path.read_bytes()
    catalog = json.loads(raw.decode("utf-8"))
    if not isinstance(catalog, dict) or catalog.get("status") != "AUTHOR_REVIEW_REQUIRED":
        raise ValueError("Territory catalog is not an approvable proposal")
    catalog_id = catalog.get("catalog_id")
    if not isinstance(catalog_id, str) or not catalog_id:
        raise ValueError("Territory catalog ID is missing")

    digest = hashlib.sha256(raw).hexdigest()
    approval = {
        "schema_version": "1.0",
        "catalog_id": catalog_id,
        "catalog_sha256": digest,
        "approval_scope": "PRIVATE_CONTROLLED_PILOT_ONLY",
        "decision": "CONTROLLED_PILOT_APPROVED",
        "reviewer": {
            "name": reviewer,
            "capacity": capacity,
        },
        "reviewed_on": reviewed_on,
    }
    approval_path.write_text(
        json.dumps(approval, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--capacity", required=True)
    parser.add_argument("--reviewed-on", required=True)
    args = parser.parse_args()
    digest = approve(
        args.catalog,
        args.approval,
        args.reviewer,
        args.capacity,
        args.reviewed_on,
    )
    print(digest)


if __name__ == "__main__":
    main()
