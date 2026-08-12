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


class _Row(dict):
    @property
    def geometry(self):
        return self.get("geometry")


class _Frame:
    def __init__(self, rows, crs="EPSG:4326"):
        self.rows = [_Row(row) for row in rows]
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
    def __init__(self, text=None):
        self.text = text

    def download_as_text(self):
        if self.text is None:
            raise main.NotFound("missing")
        return self.text

    def upload_from_string(self, text, **_kwargs):
        self.text = text


class _Bucket:
    def __init__(self, text=None):
        self.blobs = {main.STATE_OBJECT: _Blob(text)} if text is not None else {}

    def blob(self, name):
        return self.blobs.setdefault(name, _Blob())


def _install_import_stubs():
    pandas = _FakePandas("pandas")
    geopandas = types.ModuleType("geopandas")

    pil = types.ModuleType("PIL")
    pil_image = types.ModuleType("PIL.Image")
    pil.Image = pil_image

    google = types.ModuleType("google")
    genai = types.ModuleType("google.genai")
    genai.types = types.SimpleNamespace(
        GenerateContentConfig=lambda **kwargs: types.SimpleNamespace(**kwargs)
    )
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
        bucket = _Bucket()
        with mock.patch.object(main.os.path, "exists", return_value=False), mock.patch.object(
            main.gpd,
            "read_file",
            side_effect=[incidents, photos],
            create=True,
        ), mock.patch.object(main, "reconcile_google_sheet", return_value=True), mock.patch.object(
            main,
            "get_env",
        ) as get_env, mock.patch.object(main, "send_email_with_attachments") as send_email:
            self.assertTrue(main.process_project(client, bucket))

        get_env.assert_not_called()
        send_email.assert_not_called()

    def test_completed_legacy_incident_without_id_is_ignored(self):
        incidents = _Frame([{"is_sent": 1, "unique-id": None}])
        photos = _Frame([])
        client = mock.Mock()

        with mock.patch.object(main.os.path, "exists", return_value=False), mock.patch.object(
            main.gpd,
            "read_file",
            side_effect=[incidents, photos],
            create=True,
        ), mock.patch.object(main, "reconcile_google_sheet", return_value=True), mock.patch.object(
            main,
            "send_email_with_attachments",
        ) as send_email:
            self.assertTrue(main.process_project(client, _Bucket()))

        send_email.assert_not_called()

    def test_successful_incident_is_completed_without_mergin_write(self):
        incidents = _Frame(
            [
                {
                    "is_sent": 0,
                    "unique-id": "case-1",
                    "incident_type": "waste",
                    "description": "field observation",
                    "volunteer_email": "volunteer@example.com",
                    "geometry": None,
                }
            ]
        )
        photos = _Frame([])
        bucket = _Bucket()
        mergin_client = mock.Mock(spec=["download_project", "project_info"])
        model_client = mock.Mock()
        model_client.models.generate_content.side_effect = [
            types.SimpleNamespace(text="available"),
            types.SimpleNamespace(text="RU result"),
            types.SimpleNamespace(text="KZ result"),
        ]

        with mock.patch.object(main.os.path, "exists", return_value=False), mock.patch.object(
            main.gpd,
            "read_file",
            side_effect=[incidents, photos],
            create=True,
        ), mock.patch.object(main.glob, "glob", return_value=[]), mock.patch.object(
            main,
            "reconcile_google_sheet",
            return_value=True,
        ), mock.patch.object(main, "get_env", return_value="configured"), mock.patch.object(
            main.genai,
            "Client",
            return_value=model_client,
            create=True,
        ), mock.patch.object(
            main,
            "read_downloaded_project_version",
            return_value="v125",
        ), mock.patch.object(
            main,
            "get_coordinates",
            return_value="43.197466, 76.937677",
        ), mock.patch.object(
            main,
            "load_knowledge_base",
            return_value="approved test knowledge",
        ), mock.patch.object(
            main,
            "send_email_with_attachments",
        ) as send_email, mock.patch.object(
            main,
            "log_to_google_sheet",
            return_value=True,
        ):
            self.assertTrue(main.process_project(mergin_client, bucket))

        send_email.assert_called_once()
        state = main.read_incident_state(bucket, "case-1")
        self.assertEqual(state["status"], main.INCIDENT_STATUS_COMPLETED)
        self.assertEqual(state["source_project_version"], "v125")
        self.assertEqual(state["response_ru"], "RU result")
        self.assertEqual(state["response_kz"], "KZ result")
        self.assertFalse(hasattr(mergin_client, "push_project"))

    def test_incident_state_uses_opaque_path_and_round_trips(self):
        bucket = _Bucket()
        uid = "{private-field-id}"

        state = main.write_incident_state(
            bucket,
            uid,
            main.INCIDENT_STATUS_PROCESSING,
            source_project_version="v125",
        )

        object_name = main.incident_state_object(uid)
        self.assertNotIn(uid, object_name)
        self.assertEqual(main.read_incident_state(bucket, uid), state)

    def test_incident_storage_key_is_safe_for_untrusted_id(self):
        key = main.incident_storage_key("../../field/incident\n")

        self.assertEqual(len(key), 64)
        self.assertNotIn("/", key)
        self.assertNotIn("..", key)
        self.assertNotIn("\n", key)

    def test_downloaded_project_version_comes_from_local_metadata(self):
        metadata = main.json.dumps({"version": "v125"})
        with mock.patch("builtins.open", mock.mock_open(read_data=metadata)):
            self.assertEqual(main.read_downloaded_project_version(), "v125")

    def test_downloaded_project_version_rejects_missing_version(self):
        with mock.patch("builtins.open", mock.mock_open(read_data="{}")):
            with self.assertRaisesRegex(RuntimeError, "has no version"):
                main.read_downloaded_project_version()

    def test_downloaded_project_version_rejects_non_object_metadata(self):
        with mock.patch("builtins.open", mock.mock_open(read_data="[]")):
            with self.assertRaisesRegex(RuntimeError, "metadata is invalid"):
                main.read_downloaded_project_version()

    def test_invalid_incident_state_is_not_treated_as_new_work(self):
        bucket = _Bucket()
        uid = "case-1"
        bucket.blob(main.incident_state_object(uid)).text = "not json"

        with self.assertRaisesRegex(RuntimeError, "Incident state is invalid"):
            main.read_incident_state(bucket, uid)

    def test_non_object_incident_state_is_not_treated_as_new_work(self):
        bucket = _Bucket()
        uid = "case-1"
        bucket.blob(main.incident_state_object(uid)).text = "[]"

        with self.assertRaisesRegex(RuntimeError, "Incident state is invalid"):
            main.read_incident_state(bucket, uid)

    def test_unknown_incident_state_status_fails_closed(self):
        bucket = _Bucket()
        uid = "case-1"
        bucket.blob(main.incident_state_object(uid)).text = main.json.dumps(
            {
                "schema_version": main.INCIDENT_STATE_SCHEMA_VERSION,
                "incident_id": uid,
                "status": "mystery",
            }
        )

        with self.assertRaisesRegex(RuntimeError, "status is unsupported"):
            main.read_incident_state(bucket, uid)

    def test_unknown_incident_state_status_cannot_be_written(self):
        with self.assertRaisesRegex(ValueError, "status is unsupported"):
            main.write_incident_state(_Bucket(), "case-1", "mystery")

    def test_delivery_started_is_quarantined_once_without_resending_email(self):
        incidents = _Frame([{"is_sent": 0, "unique-id": "case-1"}])
        photos = _Frame([])
        bucket = _Bucket()
        main.write_incident_state(
            bucket,
            "case-1",
            main.INCIDENT_STATUS_DELIVERY_STARTED,
        )
        client = mock.Mock()

        with mock.patch.object(main.os.path, "exists", return_value=False), mock.patch.object(
            main.gpd,
            "read_file",
            side_effect=[incidents, photos],
            create=True,
        ), mock.patch.object(main, "reconcile_google_sheet", return_value=True), mock.patch.object(
            main,
            "send_email_with_attachments",
        ) as send_email:
            self.assertTrue(main.process_project(client, bucket))

        send_email.assert_not_called()
        state = main.read_incident_state(bucket, "case-1")
        self.assertEqual(state["status"], main.INCIDENT_STATUS_DELIVERY_UNCERTAIN)

    def test_delivery_uncertain_does_not_fail_every_future_scan(self):
        incidents = _Frame([{"is_sent": 0, "unique-id": "case-1"}])
        photos = _Frame([])
        bucket = _Bucket()
        main.write_incident_state(
            bucket,
            "case-1",
            main.INCIDENT_STATUS_DELIVERY_UNCERTAIN,
        )

        with mock.patch.object(main.os.path, "exists", return_value=False), mock.patch.object(
            main.gpd,
            "read_file",
            side_effect=[incidents, photos],
            create=True,
        ), mock.patch.object(main, "reconcile_google_sheet", return_value=True), mock.patch.object(
            main,
            "send_email_with_attachments",
        ) as send_email:
            self.assertTrue(main.process_project(mock.Mock(), bucket))

        send_email.assert_not_called()

    def test_completed_incident_does_not_resend_email(self):
        incidents = _Frame([{"is_sent": 0, "unique-id": "case-1"}])
        photos = _Frame([])
        bucket = _Bucket()
        main.write_incident_state(
            bucket,
            "case-1",
            main.INCIDENT_STATUS_COMPLETED,
        )
        client = mock.Mock()

        with mock.patch.object(main.os.path, "exists", return_value=False), mock.patch.object(
            main.gpd,
            "read_file",
            side_effect=[incidents, photos],
            create=True,
        ), mock.patch.object(main, "reconcile_google_sheet", return_value=True), mock.patch.object(
            main,
            "send_email_with_attachments",
        ) as send_email:
            self.assertTrue(main.process_project(client, bucket))

        send_email.assert_not_called()

    def test_unprocessed_incident_without_id_fails_closed(self):
        incidents = _Frame([{"is_sent": 0, "unique-id": None}])
        photos = _Frame([])
        client = mock.Mock()

        with mock.patch.object(main.os.path, "exists", return_value=False), mock.patch.object(
            main.gpd,
            "read_file",
            side_effect=[incidents, photos],
            create=True,
        ), mock.patch.object(main, "reconcile_google_sheet", return_value=True):
            with self.assertRaisesRegex(ValueError, "Unprocessed incident ID is required"):
                main.process_project(client, _Bucket())

    def test_duplicate_incident_id_fails_closed(self):
        incidents = _Frame(
            [
                {"is_sent": 0, "unique-id": "case-1"},
                {"is_sent": 0, "unique-id": "case-1"},
            ]
        )
        photos = _Frame([])
        client = mock.Mock()

        with mock.patch.object(main.os.path, "exists", return_value=False), mock.patch.object(
            main.gpd,
            "read_file",
            side_effect=[incidents, photos],
            create=True,
        ), mock.patch.object(main, "reconcile_google_sheet", return_value=True):
            with self.assertRaisesRegex(ValueError, "Duplicate incident ID"):
                main.process_project(client, _Bucket())

    def test_sync_safety_source_contains_no_mergin_write_calls(self):
        with open(main.__file__, encoding="utf-8") as source_file:
            source = source_file.read()

        self.assertNotIn("push_project(", source)
        self.assertNotIn("incidents.to_file(", source)

    def test_invalid_watcher_state_is_not_treated_as_success(self):
        with self.assertRaisesRegex(RuntimeError, "state object is invalid"):
            main.read_last_scanned_version(_Bucket("not valid json"))

    def test_non_object_watcher_state_is_not_treated_as_success(self):
        with self.assertRaisesRegex(RuntimeError, "state object is invalid"):
            main.read_last_scanned_version(_Bucket("[]"))

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

    def test_main_records_the_version_that_was_actually_downloaded(self):
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
            return_value=True,
        ), mock.patch.object(
            main,
            "read_downloaded_project_version",
            return_value="v3",
        ), mock.patch.object(
            main,
            "write_last_scanned_version",
        ) as write_state, mock.patch.object(main, "release_watcher_lock") as release_lock:
            main.main()

        write_state.assert_called_once_with(mock.ANY, "v3")
        release_lock.assert_called_once_with(lock)


if __name__ == "__main__":
    unittest.main()
