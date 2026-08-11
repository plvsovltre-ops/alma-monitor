"""Canonical hashes and release-bundle integrity checks for ALMA Legal Core."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit


SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
ADILET_DOCUMENT_PATH = re.compile(r"^/rus/docs/[A-Za-z0-9_]+$")
REQUIRED_RELEASE_FILES = ("cards.json", "manifest.json", "sources.json")


class IntegrityError(RuntimeError):
    """Raised when a card or release bundle is not internally consistent."""


def canonical_official_url(value: str) -> str:
    """Validate an Adilet HTTPS URL and normalize its equivalent host alias."""
    if not isinstance(value, str):
        raise IntegrityError("Official source URL must be a string")
    parts = urlsplit(value.strip())
    netloc = parts.netloc.lower()
    if parts.scheme != "https" or netloc not in {"adilet.zan.kz", "www.adilet.zan.kz"}:
        raise IntegrityError(f"Official source is not an Adilet HTTPS URL: {value}")
    if (
        not ADILET_DOCUMENT_PATH.fullmatch(parts.path)
        or parts.query
        or parts.fragment
    ):
        raise IntegrityError(f"Official source is not an Adilet document URL: {value}")
    return urlunsplit(("https", "adilet.zan.kz", parts.path, parts.query, ""))


def canonical_card_hash(card: Mapping[str, Any]) -> str:
    """Hash the legal fields accepted by the owner review.

    Algorithm: SHA-256 of UTF-8 JSON with sorted keys, no insignificant
    whitespace, Unicode preserved, and the Adilet host canonicalized.
    """
    required = ("rule_id", "provision", "safe_summary", "source_id", "official_url")
    values: dict[str, str] = {}
    for key in required:
        value = card.get(key)
        if not isinstance(value, str) or not value.strip():
            raise IntegrityError(f"Card field {key} must be a non-empty string")
        values[key] = value.strip()
    values["official_url"] = canonical_official_url(values["official_url"])
    payload = json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_sha256sums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise IntegrityError(f"Cannot read release checksums: {path}") from exc
    checksums: dict[str, str] = {}
    for line in lines:
        try:
            digest, name = line.split("  ", 1)
        except ValueError as exc:
            raise IntegrityError(f"Invalid SHA256SUMS line: {line!r}") from exc
        if not SHA256_HEX.fullmatch(digest) or name not in REQUIRED_RELEASE_FILES:
            raise IntegrityError(f"Invalid SHA256SUMS entry: {line!r}")
        if name in checksums:
            raise IntegrityError(f"Duplicate SHA256SUMS entry: {name}")
        checksums[name] = digest
    if set(checksums) != set(REQUIRED_RELEASE_FILES):
        raise IntegrityError("SHA256SUMS must cover cards, manifest, and sources")
    return checksums


def verify_release_bundle(cards_path: str | Path) -> dict[str, Any]:
    """Verify all release checksums and return the parsed manifest."""
    cards_path = Path(cards_path)
    if cards_path.name != "cards.json":
        raise IntegrityError("A Legal Core release entry point must be cards.json")
    release_dir = cards_path.parent
    checksums = _load_sha256sums(release_dir / "SHA256SUMS")
    for name in REQUIRED_RELEASE_FILES:
        artifact = release_dir / name
        if not artifact.is_file():
            raise IntegrityError(f"Release artifact is missing: {name}")
        if sha256_file(artifact) != checksums[name]:
            raise IntegrityError(f"Release checksum mismatch: {name}")

    try:
        manifest = json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError("Release manifest is invalid") from exc
    artifacts = manifest.get("artifacts")
    expected_artifacts = {"cards.json", "sources.json"}
    if not isinstance(artifacts, dict) or set(artifacts) != expected_artifacts:
        raise IntegrityError("Manifest must cover cards.json and sources.json")
    for name in expected_artifacts:
        if artifacts[name] != checksums[name]:
            raise IntegrityError(f"Manifest checksum disagrees with SHA256SUMS: {name}")
    return manifest
