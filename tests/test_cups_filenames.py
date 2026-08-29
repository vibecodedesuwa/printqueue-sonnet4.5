import importlib
import pathlib
import sys
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


if __name__ == "__main__":
    unittest.main()
