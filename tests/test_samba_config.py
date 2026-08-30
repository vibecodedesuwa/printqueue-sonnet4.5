import pathlib
import unittest


class SambaConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.setup_script = (
            pathlib.Path(__file__).parents[1] / "scripts" / "setup-windows-samba.sh"
        ).read_text(encoding="utf-8")

    def test_windows_submissions_are_forced_held(self):
        forced_option = 'cups options = "raw job-hold-until=indefinite"'
        self.assertGreaterEqual(self.setup_script.count(forced_option), 2)
        self.assertIn("job-hold-until-default=indefinite", self.setup_script)
        self.assertNotIn("cups options = raw\n", self.setup_script)

    def test_only_explicit_queue_is_loaded_and_mapping_is_preserved(self):
        self.assertIn("load printers = no", self.setup_script)
        self.assertNotIn("load printers = yes", self.setup_script)
        self.assertNotIn("force printername = yes", self.setup_script)
        self.assertIn("printer name = $SAMBA_WINDOWS_QUEUE", self.setup_script)

    def test_spool_path_works_with_distribution_selinux_policy(self):
        self.assertGreaterEqual(self.setup_script.count("path = /var/tmp/"), 2)
        self.assertNotIn("path = /var/spool/samba", self.setup_script)


if __name__ == "__main__":
    unittest.main()
