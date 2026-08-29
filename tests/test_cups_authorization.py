import importlib
import os
import pathlib
import sys
import types
import unittest
from unittest.mock import patch


package = sys.modules.setdefault("printqueue", types.ModuleType("printqueue"))
package.__path__ = [str(pathlib.Path(__file__).parents[1] / "printqueue")]


class FakeConnection:
    def __init__(self, owner):
        self.owner = owner
        self.released = []
        self.printed = []

    def getJobs(self, **_kwargs):
        return {12: {"job-originating-user-name": self.owner}}

    def getJobAttributes(self, _job_id):
        return {"job-originating-user-name": self.owner}

    def setJobHoldUntil(self, job_id, value):
        self.released.append((job_id, value))

    def printFile(self, printer, file_path, title, options):
        self.printed.append((printer, file_path, title, options.copy()))
        return 13


class FakeDatabase:
    def get_device_mapping(self, _owner):
        return None

    def get_claimed_owner(self, _job_id):
        return "alice"

    def get_job_meta(self, _job_id):
        return {"submitted_by": "alice"}


class CupsAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_cups = types.ModuleType("cups")
        fake_cups.Connection = lambda **_kwargs: None
        fake_cups.setUser = lambda _user: None
        fake_cups.setPasswordCB = lambda _callback: None
        sys.modules["cups"] = fake_cups
        cls.module = importlib.import_module("printqueue.cups_utils")

    def call_release(self, owner, requesting_user):
        connection = FakeConnection(owner)
        fake_flask = types.ModuleType("flask")
        fake_flask.current_app = types.SimpleNamespace(config={"db": FakeDatabase()})
        with patch.dict(sys.modules, {"flask": fake_flask}), patch.object(
            self.module, "get_cups_connection", return_value=connection
        ), patch.object(self.module, "LDAP_DOMAIN", "acme.local"):
            result = self.module.release_job(12, requesting_user, is_admin=False)
        return result, connection

    def test_claimed_owner_cannot_be_impersonated_by_another_user(self):
        result, connection = self.call_release("alice", "bob")
        self.assertEqual(result, (False, "Permission denied", 403))
        self.assertEqual(connection.released, [])

    def test_ad_cups_owner_variant_is_bound_automatically(self):
        result, connection = self.call_release(r"ACME\Alice", "alice")
        self.assertEqual(result, (True, "Job released", 200))
        self.assertEqual(connection.released, [(12, "no-hold")])

    def test_direct_upload_explicitly_overrides_queue_hold(self):
        connection = FakeConnection("guest")
        with patch.object(self.module, "get_cups_connection", return_value=connection):
            result = self.module.submit_print_job(
                "/tmp/example.pdf", "example.pdf", "PrintQ", hold=False
            )
        self.assertEqual(result, (True, 13))
        self.assertEqual(connection.printed[0][3]["job-hold-until"], "no-hold")

    def test_other_submission_paths_remain_held_by_default(self):
        connection = FakeConnection("alice")
        with patch.object(self.module, "get_cups_connection", return_value=connection):
            self.module.submit_print_job("/tmp/example.pdf", "example.pdf", "PrintQ")
        self.assertEqual(connection.printed[0][3]["job-hold-until"], "indefinite")


if __name__ == "__main__":
    unittest.main()
