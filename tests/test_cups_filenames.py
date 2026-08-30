import importlib
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


package = sys.modules.setdefault("printqueue", types.ModuleType("printqueue"))
package.__path__ = [str(pathlib.Path(__file__).parents[1] / "printqueue")]

fake_cups = sys.modules.setdefault("cups", types.ModuleType("cups"))
fake_cups.Connection = lambda **_kwargs: None
fake_cups.setUser = lambda _user: None
fake_cups.setPasswordCB = lambda _callback: None


class FakeConnection:
    def __init__(self, attributes):
        self.attributes = attributes

    def getJobs(self, **_kwargs):
        return {21: dict(self.attributes)}

    def getJobAttributes(self, _job_id):
        return dict(self.attributes)


class EmptyConnection:
    def getJobs(self, **_kwargs):
        return {}

    def getJobAttributes(self, _job_id):
        return {}


class FakeDatabase:
    def __init__(self, metadata=None):
        self.metadata = metadata
        self.saved = []

    def get_job_meta(self, _job_id):
        return self.metadata

    def create_job_meta(self, job_id, **values):
        self.saved.append((job_id, values))


class CupsFilenameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = importlib.import_module("printqueue.cups_utils")

    def test_metadata_filename_wins_when_cups_omits_job_name(self):
        connection = FakeConnection({
            "job-originating-user-name": "alice",
            "job-state": 4,
            "time-at-creation": 1,
        })
        database = FakeDatabase({
            "submitted_via": "web",
            "submitted_by": "alice",
            "original_filename": "รายงานประจำเดือน.pdf",
        })
        with patch.object(self.module, "get_cups_connection", return_value=connection), patch.object(
            self.module.subprocess, "run", return_value=types.SimpleNamespace(stdout="")
        ):
            jobs = self.module.get_user_jobs("alice", db=database)
        self.assertEqual(jobs[0]["name"], "รายงานประจำเดือน.pdf")

    def test_document_name_attribute_is_saved_for_future_queries(self):
        connection = FakeConnection({
            "job-originating-user-name": "tablet",
            "document-name-supplied": "meeting-notes.pdf",
            "job-state": 4,
            "time-at-creation": 1,
        })
        database = FakeDatabase()
        with patch.object(self.module, "get_cups_connection", return_value=connection):
            jobs = self.module.get_all_jobs(db=database)
        self.assertEqual(jobs[0]["name"], "meeting-notes.pdf")
        self.assertEqual(database.saved[0][1]["original_filename"], "meeting-notes.pdf")

    def test_withheld_owner_is_recovered_from_lpstat(self):
        connection = FakeConnection({
            "job-originating-user-name": "Withheld",
            "job-name": "Test Page",
            "job-state": 4,
            "time-at-creation": 1,
        })
        lpstat = "es_non01_st515_01-21 ECHOSTORY\\alice 1024 Sun 30 Aug 2026\n"
        with patch.object(self.module, "get_cups_connection", return_value=connection), patch.object(
            self.module.subprocess,
            "run",
            return_value=types.SimpleNamespace(stdout=lpstat),
        ):
            jobs = self.module.get_user_jobs("alice", db=FakeDatabase())
        self.assertEqual(jobs[0]["user"], r"ECHOSTORY\alice")

    def test_lpstat_only_windows_class_job_is_visible(self):
        lpstat = (
            "es_non01_st515_01_windows-57 ECHOSTORY\\alice 2048 "
            "Sun 30 Aug 2026\n"
        )
        with patch.object(
            self.module, "get_cups_connection", return_value=EmptyConnection()
        ), patch.object(
            self.module.subprocess,
            "run",
            return_value=types.SimpleNamespace(stdout=lpstat),
        ):
            jobs = self.module.get_all_jobs(db=FakeDatabase())
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], 57)
        self.assertEqual(jobs[0]["printer"], "es_non01_st515_01_windows")
        self.assertEqual(jobs[0]["user"], r"ECHOSTORY\alice")

    def test_lpstat_is_found_when_service_path_only_contains_venv(self):
        with patch.object(self.module.shutil, "which", return_value=None), patch.object(
            self.module.os.path,
            "isfile",
            side_effect=lambda path: path == "/usr/bin/lpstat",
        ), patch.object(self.module.os, "access", return_value=True):
            self.assertEqual(self.module._system_command("lpstat"), "/usr/bin/lpstat")

    def test_samba_transport_prefix_is_removed_from_real_title(self):
        self.assertEqual(
            self.module._usable_job_name("smbprn.00000032 Test Page"),
            "Test Page",
        )
        self.assertIsNone(
            self.module._usable_job_name(
                "smbprn.00000036 Remote Downlevel Document"
            )
        )

    def test_postscript_title_is_recovered_from_cups_spool(self):
        with tempfile.TemporaryDirectory() as spool_dir:
            spool_path = pathlib.Path(spool_dir) / "d00020-001"
            spool_path.write_bytes(
                b"%!PS-Adobe-3.0\n%%Title: (Family Schedule)\n%%Pages: 1\n"
            )
            with patch.dict(self.module.os.environ, {"CUPS_SPOOL_DIR": spool_dir}):
                self.assertEqual(
                    self.module._spool_document_title(20), "Family Schedule"
                )

    def test_authenticated_windows_owner_is_not_claimable(self):
        connection = FakeConnection({
            "job-originating-user-name": "sataporn",
            "job-name": "Remote Downlevel Document",
            "printer-uri": (
                "ipp://localhost/classes/es_non01_st515_01_windows"
            ),
            "job-state": 4,
            "time-at-creation": 1,
        })
        with patch.dict(self.module.os.environ, {
            "PRINTER_NAME": "es_non01_st515_01",
            "SAMBA_ENABLED": "true",
            "SAMBA_WINDOWS_QUEUE": "es_non01_st515_01_windows",
        }), patch.object(
            self.module, "get_cups_connection", return_value=connection
        ), patch.object(
            self.module, "_get_lpstat_jobs", return_value={}
        ):
            jobs = self.module.get_all_jobs(db=FakeDatabase())
        self.assertFalse(jobs[0]["claimable"])
        self.assertEqual(jobs[0]["name"], "Document #21")

    def test_authenticated_airprint_owner_is_not_claimable(self):
        with patch.dict(self.module.os.environ, {
            "LDAP_ENABLED": "true",
            "SAMBA_ENABLED": "false",
        }), patch.object(
            self.module, "_configured_printer_name", return_value="office_printer"
        ):
            self.assertFalse(self.module._job_is_claimable(
                FakeDatabase(), None, "alice", "office_printer", "ipp"
            ))

    def test_unauthenticated_generic_device_job_remains_claimable(self):
        with patch.dict(self.module.os.environ, {
            "LDAP_ENABLED": "false",
            "SAMBA_ENABLED": "false",
        }), patch.object(
            self.module, "_configured_printer_name", return_value="office_printer"
        ):
            self.assertTrue(self.module._job_is_claimable(
                FakeDatabase(), None, "Living Room iPad", "office_printer", "ipp"
            ))


if __name__ == "__main__":
    unittest.main()
