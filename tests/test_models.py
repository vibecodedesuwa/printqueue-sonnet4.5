import os
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

package = sys.modules.setdefault("printqueue", types.ModuleType("printqueue"))
package.__path__ = [str(pathlib.Path(__file__).parents[1] / "printqueue")]

from printqueue.models import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.temp_dir.name, "printqueue.db"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_job_metadata_is_upserted_by_cups_job_id(self):
        self.db.create_job_meta(42, submitted_via="ipp")
        self.db.create_job_meta(42, submitted_via="web", submitted_by="alice")

        meta = self.db.get_job_meta(42)
        self.assertEqual(meta["submitted_via"], "web")
        self.assertEqual(meta["submitted_by"], "alice")
        with self.db.get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM print_job_meta WHERE cups_job_id = 42"
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_legacy_ipp_owner_remains_claimable(self):
        self.db.create_job_meta(7, submitted_via="ipp", submitted_by=r"ACME\alice")
        self.assertIn(7, self.db.get_unclaimed_jobs())

    def test_device_mapping_accepts_ad_username_variant(self):
        self.db.add_known_device("alice", "alice")
        with patch.dict(os.environ, {"LDAP_DOMAIN": "acme.local"}):
            self.assertEqual(self.db.get_device_mapping(r"ACME\Alice"), "alice")


if __name__ == "__main__":
    unittest.main()
