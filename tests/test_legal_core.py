from __future__ import annotations

import copy
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from legal_core import (
    CardBlockedError,
    FactState,
    LegalCoreCatalog,
    SourceChangedError,
    UnknownRuleError,
    normalize_fact_state,
)
from legal_core.catalog import DEFAULT_RELEASE


RELEASE_DIR = DEFAULT_RELEASE.parent


class LegalCoreReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(DEFAULT_RELEASE.read_text(encoding="utf-8"))
        cls.cards = cls.document["cards"]

    def test_release_has_accepted_unique_cards(self):
        self.assertEqual(122, len(self.cards))
        self.assertEqual(len(self.cards), len({card["rule_id"] for card in self.cards}))
        for card in self.cards:
            self.assertRegex(card["rule_id"], r"^kz-[a-z0-9-]+$")
            self.assertRegex(card["card_hash"], r"^sha256:[0-9a-f]{64}$")
            self.assertRegex(card["official_url"], r"^https://(www\.)?adilet\.zan\.kz/")
            self.assertEqual("OWNER_ACCEPTED", card["review"]["owner_status"])
            self.assertEqual("PILOT_ELIGIBLE", card["review"]["pilot_status"])
            self.assertEqual("LAWYER_REVIEW_PENDING", card["review"]["lawyer_status"])
            self.assertEqual(
                "PUBLIC_LEGAL_RELEASE_BLOCKED",
                card["review"]["public_release_status"],
            )

    def test_unknown_article_is_not_substituted(self):
        catalog = LegalCoreCatalog()
        with self.assertRaises(UnknownRuleError):
            catalog.citations(["kz-invented-article"])

    def test_citation_text_comes_from_the_card(self):
        catalog = LegalCoreCatalog()
        rule_id = catalog.rule_ids()[0]
        card = catalog.require_card(rule_id)
        citation = catalog.citations([rule_id])[0]
        self.assertEqual(card["provision"], citation["provision"])
        self.assertEqual(card["official_url"], citation["official_url"])
        self.assertEqual(card["safe_summary"], citation["safe_summary"])

    def test_public_legal_release_is_blocked(self):
        catalog = LegalCoreCatalog()
        with self.assertRaises(CardBlockedError):
            catalog.require_card(
                catalog.rule_ids()[0],
                use_case="public_legal_release",
            )

    def test_changed_source_blocks_card(self):
        changed = copy.deepcopy(self.document)
        changed["cards"][0]["review"]["source_change_status"] = (
            "SOURCE_CHANGED_UNREVIEWED"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cards.json"
            path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
            catalog = LegalCoreCatalog(path)
            with self.assertRaises(SourceChangedError):
                catalog.require_card(catalog.rule_ids()[0])

    def test_unknown_fact_stays_unknown(self):
        self.assertEqual(FactState.UNKNOWN, normalize_fact_state(None))
        self.assertEqual(FactState.UNKNOWN, normalize_fact_state("UNKNOWN"))
        self.assertNotEqual(FactState.ABSENT, normalize_fact_state(None))

    def test_manifest_checksums_match_release_files(self):
        manifest = json.loads((RELEASE_DIR / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest["artifacts"].items():
            actual = hashlib.sha256((RELEASE_DIR / name).read_bytes()).hexdigest()
            self.assertEqual(expected, actual, name)
        checksum_lines = (RELEASE_DIR / "SHA256SUMS").read_text(encoding="ascii").splitlines()
        self.assertEqual(3, len(checksum_lines))
        for line in checksum_lines:
            self.assertRegex(line, r"^[0-9a-f]{64}  (cards|manifest|sources)\.json$")


if __name__ == "__main__":
    unittest.main()
