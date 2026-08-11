from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.export_legal_core import load_cards


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


class ExportLegalCoreTests(unittest.TestCase):
    def write_csv(self, path: Path, *, accepted: bool = True) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["ALMA Legal Core — быстрая проверка карточек v1.2"])
            writer.writerow(["Инструкция"])
            writer.writerow(["Правило LLM"])
            writer.writerow(["Авторство"])
            writer.writerow(HEADERS)
            writer.writerow(
                [
                    "Открыть источник",
                    "КоАП РК, часть 1 статьи 505",
                    "Просьба проверить обстоятельства.",
                    "TRUE" if accepted else "FALSE",
                    "FALSE" if accepted else "TRUE",
                    "",
                    "СОГЛАСОВАНО ВЛАДЕЛЬЦЕМ" if accepted else "В ПЕРЕРАБОТКУ",
                    "",
                    "kz-koap-505-1-cleaning",
                    "sha256:" + "a" * 64,
                    "kz-koap-2014",
                    "ACCEPT_CARD" if accepted else "REWORK_CARD",
                    "EDITORIAL_REVIEW_ONLY; LEGAL_RELEASE_BLOCKED",
                    "1.2",
                    "https://www.adilet.zan.kz/rus/docs/K1400000235",
                ]
            )

    def test_export_finds_header_after_instruction_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            self.write_csv(path)
            cards = load_cards(path)
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
                load_cards(path)


if __name__ == "__main__":
    unittest.main()
