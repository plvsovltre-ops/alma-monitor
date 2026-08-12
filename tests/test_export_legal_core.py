from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from legal_core import canonical_card_hash
from scripts.export_legal_core import ReleaseMetadata, load_cards, write_release


HEADERS = [
    "Официальный источник",
    "Норма",
    "Что говорит карточка",
    "Согласен",
    "Не согласен",
    "Комментарий (необязательно)",
    "Статус",
    "Переработка",
    "rule_id",
    "card_hash",
    "source_id",
    "backend_action",
    "legal_release_gate",
    "review_view_version",
    "official_url",
]
METADATA = ReleaseMetadata(
    release_id="kz-0.1.0-rc1",
    review_date="2026-08-11",
    review_view_version="1.2",
    source_spreadsheet_id="test-sheet",
    source_review_view="ALMA Legal Review — Kazakhstan v1.2",
    expected_card_count=1,
    legal_reviewer_name="Yernar Sailybayev",
    legal_review_date="2026-08-12",
)


def reviewed_values(*, accepted: bool = True) -> list[str]:
    card = {
        "rule_id": "kz-koap-505-1-cleaning",
        "provision": "КоАП РК, часть 1 статьи 505",
        "safe_summary": "Просьба проверить обстоятельства.",
        "source_id": "kz-koap-2014",
        "official_url": "https://www.adilet.zan.kz/rus/docs/K1400000235",
    }
    return [
        "Открыть источник",
        card["provision"],
        card["safe_summary"],
        "TRUE" if accepted else "FALSE",
        "FALSE" if accepted else "TRUE",
        "",
        "СОГЛАСОВАНО ВЛАДЕЛЬЦЕМ" if accepted else "В ПЕРЕРАБОТКУ",
        "",
        card["rule_id"],
        canonical_card_hash(card),
        card["source_id"],
        "ACCEPT_CARD" if accepted else "REWORK_CARD",
        "EDITORIAL_REVIEW_ONLY; LEGAL_RELEASE_BLOCKED",
        "1.2",
        card["official_url"],
    ]


class ExportLegalCoreTests(unittest.TestCase):
    def write_csv(
        self,
        path: Path,
        *,
        accepted: bool = True,
        mutate_after_hash: bool = False,
        invalid_checkbox: bool = False,
        invalid_gate: bool = False,
        hostile_url: bool = False,
    ) -> None:
        values = reviewed_values(accepted=accepted)
        if mutate_after_hash:
            values[2] = "Текст изменён после согласования."
        if invalid_checkbox:
            values[3] = "ДА"
        if invalid_gate:
            values[12] = "NOT_LEGAL_RELEASE_BLOCKED"
        if hostile_url:
            values[14] = "https://user@adilet.zan.kz/rus/docs/K1400000235"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["ALMA Legal Core — быстрая проверка карточек v1.2"])
            writer.writerow(["Инструкция"])
            writer.writerow(["Правило LLM"])
            writer.writerow(["Авторство"])
            writer.writerow(HEADERS)
            writer.writerow(values)

    def test_export_finds_header_after_instruction_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.write_csv(path)
            cards = load_cards(path, METADATA)
        self.assertEqual(1, len(cards))
        self.assertEqual(6, cards[0]["source_sheet_row"])
        self.assertEqual(
            "https://www.adilet.zan.kz/rus/docs/K1400000235",
            cards[0]["official_url"],
        )

    def test_export_rejects_disagreed_card(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.write_csv(path, accepted=False)
            with self.assertRaisesRegex(ValueError, "owner acceptance"):
                load_cards(path, METADATA)

    def test_export_rejects_content_changed_after_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.write_csv(path, mutate_after_hash=True)
            with self.assertRaisesRegex(ValueError, "does not match reviewed content"):
                load_cards(path, METADATA)

    def test_export_rejects_unknown_checkbox_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.write_csv(path, invalid_checkbox=True)
            with self.assertRaisesRegex(ValueError, "invalid checkbox"):
                load_cards(path, METADATA)

    def test_export_rejects_substring_release_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.write_csv(path, invalid_gate=True)
            with self.assertRaisesRegex(ValueError, "must stay blocked"):
                load_cards(path, METADATA)

    def test_export_rejects_adilet_userinfo_url(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.write_csv(path, hostile_url=True)
            with self.assertRaisesRegex(ValueError, "not an Adilet HTTPS URL"):
                load_cards(path, METADATA)

    def test_export_rejects_missing_card_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.write_csv(path)
            with self.assertRaisesRegex(ValueError, "Expected 2 cards, found 1"):
                load_cards(path, replace(METADATA, expected_card_count=2))

    def test_legal_review_cannot_predate_owner_review(self):
        metadata = replace(
            METADATA,
            review_date="2026-08-12",
            legal_review_date="2026-08-11",
        )
        with self.assertRaisesRegex(ValueError, "cannot precede owner review"):
            metadata.validate()

    def test_export_rejects_one_source_id_for_two_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.write_csv(path)
            cards = load_cards(path, METADATA)
            second = dict(cards[0])
            second["rule_id"] = "kz-test-conflicting-source"
            second["official_url"] = "https://adilet.zan.kz/rus/docs/K2500000178"
            second["card_hash"] = canonical_card_hash(second)
            with self.assertRaisesRegex(ValueError, "multiple documents"):
                write_release(
                    cards + [second],
                    Path(directory) / "release",
                    replace(METADATA, expected_card_count=2),
                )

    def test_export_refuses_to_overwrite_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.write_csv(path)
            cards = load_cards(path, METADATA)
            output = Path(directory) / "release"
            write_release(cards, output, METADATA)
            with self.assertRaises(FileExistsError):
                write_release(cards, output, METADATA)

    def test_release_metadata_is_not_hardcoded(self):
        metadata = ReleaseMetadata(
            release_id="kz-0.2.0-rc1",
            review_date="2026-08-12",
            review_view_version="1.3",
            source_spreadsheet_id="next-sheet",
            source_review_view="ALMA Legal Review — Kazakhstan v1.3",
            expected_card_count=1,
            legal_reviewer_name="Yernar Sailybayev",
            legal_review_date="2026-08-12",
        )
        values = reviewed_values()
        values[13] = "1.3"
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "review.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(HEADERS)
                writer.writerow(values)
            cards = load_cards(csv_path, metadata)
            output = Path(directory) / "release"
            write_release(cards, output, metadata)
            document = json.loads((output / "cards.json").read_text(encoding="utf-8"))
        self.assertEqual("kz-0.2.0-rc1", document["release"]["id"])
        self.assertEqual("2026-08-12", document["release"]["generated_on"])

    def test_release_records_author_review_for_controlled_pilot_only(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "review.csv"
            self.write_csv(csv_path)
            cards = load_cards(csv_path, METADATA)
            output = Path(directory) / "release"
            write_release(cards, output, METADATA)

            review = json.loads((output / "review.json").read_text(encoding="utf-8"))
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual("Yernar Sailybayev", review["reviewer"]["name"])
        self.assertEqual("AUTHOR_AND_LEGAL_EDITOR", review["reviewer"]["capacity"])
        self.assertEqual("CONTROLLED_PILOT_APPROVED", review["decision"])
        self.assertEqual("CONTROLLED_PILOT_ONLY", review["scope"])
        self.assertEqual(
            "INDEPENDENT_LAWYER_REVIEW_PENDING",
            review["independent_lawyer_review_status"],
        )
        self.assertEqual(
            "PUBLIC_LEGAL_RELEASE_BLOCKED",
            review["public_release_status"],
        )
        self.assertEqual(
            "AUTHOR_LEGAL_REVIEW_APPROVED",
            cards[0]["review"]["legal_editor_status"],
        )
        self.assertEqual("CONTROLLED_PILOT_APPROVED", manifest["status"])

    def test_documented_direct_cli_command_runs(self):
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "review.csv"
            self.write_csv(csv_path)
            output = Path(directory) / "release"
            result = subprocess.run(
                [
                    sys.executable,
                    str(repository / "scripts" / "export_legal_core.py"),
                    str(csv_path),
                    str(output),
                    "--release-id",
                    "kz-0.1.0-rc1",
                    "--review-date",
                    "2026-08-11",
                    "--review-view-version",
                    "1.2",
                    "--source-spreadsheet-id",
                    "test-sheet",
                    "--source-review-view",
                    "test-view",
                    "--expected-card-count",
                    "1",
                    "--legal-reviewer-name",
                    "Yernar Sailybayev",
                    "--legal-review-date",
                    "2026-08-12",
                ],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((output / "SHA256SUMS").is_file())


if __name__ == "__main__":
    unittest.main()
