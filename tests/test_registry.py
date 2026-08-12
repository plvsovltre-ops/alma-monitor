import importlib
import math
import sys
import types
import unittest
from unittest import mock


class _FakePandas(types.ModuleType):
    class Missing:
        pass

    @staticmethod
    def isna(value):
        return (
            value is None
            or isinstance(value, _FakePandas.Missing)
            or (isinstance(value, float) and math.isnan(value))
        )


class _Column(list):
    def __eq__(self, other):
        return [value == other for value in self]

    def fillna(self, replacement):
        return _Column(replacement if value is None else value for value in self)

    def astype(self, _type):
        return _Column(_type(value) for value in self)


class _Frame:
    def __init__(self, rows, crs="EPSG:4326"):
        self.rows = [dict(row) for row in rows]
        self.crs = crs

    @property
    def columns(self):
        keys = set()
        for row in self.rows:
            keys.update(row)
        return list(keys)

    @property
    def empty(self):
        return not self.rows

    def __getitem__(self, key):
        if isinstance(key, str):
            return _Column(row.get(key) for row in self.rows)
        if isinstance(key, (list, tuple)):
            return _Frame(
                [row for row, keep in zip(self.rows, key) if keep],
                crs=self.crs,
            )
        raise TypeError(key)

    def __setitem__(self, key, values):
        for row, value in zip(self.rows, values):
            row[key] = value

    def iterrows(self):
        yield from enumerate(self.rows)


class _Sheet:
    def __init__(self, ids=()):
        self.ids = list(ids)
        self.appended = []

    def col_values(self, column):
        if column != 2:
            raise AssertionError("Only the incident ID column should be read")
        return ["ID Дела", *self.ids]

    def append_row(self, row):
        self.appended.append(row)
        if len(row) > 1 and row[1]:
            self.ids.append(str(row[1]))


class _Blob:
    def __init__(self, text):
        self.text = text

    def download_as_text(self):
        return self.text


class _Bucket:
    def __init__(self, text):
        self.text = text

    def blob(self, _name):
        return _Blob(self.text)


def _install_import_stubs():
    pandas = _FakePandas("pandas")
    geopandas = types.ModuleType("geopandas")

    pil = types.ModuleType("PIL")
    pil_image = types.ModuleType("PIL.Image")
    pil.Image = pil_image

    google = types.ModuleType("google")
    genai = types.ModuleType("google.genai")
    genai.types = types.SimpleNamespace(GenerateContentConfig=object)
    google.genai = genai
    google.auth = types.ModuleType("google.auth")

    google_cloud = types.ModuleType("google.cloud")
    google_cloud.storage = types.ModuleType("google.cloud.storage")
    google.cloud = google_cloud

    google_api_core = types.ModuleType("google.api_core")
    google_exceptions = types.ModuleType("google.api_core.exceptions")

    class NotFound(Exception):
        pass

    class PreconditionFailed(Exception):
        pass

    google_exceptions.NotFound = NotFound
    google_exceptions.PreconditionFailed = PreconditionFailed
    google_api_core.exceptions = google_exceptions
    google.api_core = google_api_core

    mergin = types.ModuleType("mergin")
    mergin.MerginClient = object

    class ClientError(Exception):
        pass

    mergin.ClientError = ClientError

    stubs = {
        "pandas": pandas,
        "geopandas": geopandas,
        "PIL": pil,
        "PIL.Image": pil_image,
        "google": google,
        "google.genai": genai,
        "google.auth": google.auth,
        "google.cloud": google_cloud,
        "google.cloud.storage": google_cloud.storage,
        "google.api_core": google_api_core,
        "google.api_core.exceptions": google_exceptions,
        "gspread": types.ModuleType("gspread"),
        "mergin": mergin,
    }
    sys.modules.update(stubs)


_install_import_stubs()
main = importlib.import_module("main")


class RegistryTests(unittest.TestCase):
    def test_normalize_replaces_missing_and_non_finite_values(self):
        values = [
            None,
            float("nan"),
            float("inf"),
            float("-inf"),
            _FakePandas.Missing(),
        ]
        self.assertEqual([main.normalize_sheet_value(value) for value in values], [""] * 5)

    def test_append_registry_row_skips_duplicate_incident_id(self):
        sheet = _Sheet(ids=["case-1"])
        appended = main.append_registry_row(
            sheet,
            ["2026-08-10", "case-1", None, float("nan")],
        )
        self.assertFalse(appended)
        self.assertEqual(sheet.appended, [])

    def test_append_registry_row_rejects_missing_incident_id(self):
        sheet = _Sheet()
        for missing_id in (None, float("nan"), "   "):
            with self.subTest(missing_id=missing_id):
                with self.assertRaisesRegex(ValueError, "Incident ID is required"):
                    main.append_registry_row(
                        sheet,
                        ["2026-08-10", missing_id, "cadastre"],
                    )
        self.assertEqual(sheet.appended, [])

    def test_log_to_google_sheet_reports_registry_failure(self):
        with mock.patch.object(
            main,
            "open_registry_sheet",
            side_effect=RuntimeError("Sheets unavailable"),
        ):
            self.assertFalse(main.log_to_google_sheet(["date", "case-1"]))

    def test_reconcile_restores_only_missing_processed_incidents(self):
        incidents = _Frame(
            [
                {"is_sent": 1, "unique-id": "existing", "incident_type": "waste"},
                {"is_sent": 1, "unique-id": "missing", "incident_type": None},
                {"is_sent": 1, "unique-id": None, "incident_type": "logging"},
                {"is_sent": 0, "unique-id": "new", "incident_type": "logging"},
            ]
        )
        sheet = _Sheet(ids=["existing"])
        with mock.patch.object(main, "open_registry_sheet", return_value=sheet), mock.patch.object(
            main,
            "get_coordinates",
            return_value="43.000000, 76.000000",
        ):
            self.assertTrue(main.reconcile_google_sheet(incidents))

        self.assertEqual(len(sheet.appended), 1)
        self.assertEqual(sheet.appended[0][1], "missing")
        self.assertEqual(sheet.appended[0][3], "")

    def test_processed_project_does_not_load_gemini_or_send_email(self):
        incidents = _Frame([{"is_sent": 1, "unique-id": "case-1"}])
        photos = _Frame([])
        client = mock.Mock()
        with mock.patch.object(main.os.path, "exists", return_value=False), mock.patch.object(
            main.gpd,
            "read_file",
            side_effect=[incidents, photos],
            create=True,
        ), mock.patch.object(main, "reconcile_google_sheet", return_value=True), mock.patch.object(
            main,
            "get_env",
        ) as get_env, mock.patch.object(main, "send_email_with_attachments") as send_email:
            self.assertTrue(main.process_project(client))

        get_env.assert_not_called()
        send_email.assert_not_called()

    def test_invalid_watcher_state_is_not_treated_as_success(self):
        with self.assertRaisesRegex(RuntimeError, "state object is invalid"):
            main.read_last_scanned_version(_Bucket("not valid json"))

    def test_main_does_not_advance_state_after_registry_failure(self):
        lock = (mock.Mock(), 7)
        with mock.patch.object(main, "get_env", return_value="configured"), mock.patch.object(
            main,
            "MerginClient",
            return_value=mock.Mock(),
        ), mock.patch.object(
            main,
            "get_state_bucket",
            return_value=mock.Mock(),
        ), mock.patch.object(
            main,
            "get_project_version",
            side_effect=["v2", "v2"],
        ), mock.patch.object(
            main,
            "read_last_scanned_version",
            side_effect=["v1", "v1"],
        ), mock.patch.object(
            main,
            "acquire_watcher_lock",
            return_value=lock,
        ), mock.patch.object(
            main,
            "process_project",
            return_value=False,
        ), mock.patch.object(
            main,
            "write_last_scanned_version",
        ) as write_state, mock.patch.object(main, "release_watcher_lock") as release_lock:
            with self.assertRaisesRegex(RuntimeError, "synchronization is incomplete"):
                main.main()

        write_state.assert_not_called()
        release_lock.assert_called_once_with(lock)


if __name__ == "__main__":
    unittest.main()
