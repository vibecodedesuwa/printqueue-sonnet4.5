import pathlib
import unittest


class SambaConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.setup_script = (
            pathlib.Path(__file__).parents[1] / "scripts" / "setup-windows-samba.sh"
        ).read_text(encoding="utf-8")

    def test_windows_submissions_are_forced_held(self):
        forced_option = (
            'cups options = "job-hold-until=indefinite outputorder=normal"'
        )
        self.assertGreaterEqual(self.setup_script.count(forced_option), 2)
        self.assertIn("job-hold-until-default=indefinite", self.setup_script)
        self.assertNotIn('cups options = "raw ', self.setup_script)

    def test_all_destinations_default_to_forward_page_order(self):
        airprint = (
            pathlib.Path(__file__).parents[1] / "scripts" / "setup-airprint.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("outputorder-default=normal", airprint)
        self.assertGreaterEqual(
            self.setup_script.count("outputorder-default=normal"), 2
        )

    def test_a4_is_default_without_removing_other_ready_sizes(self):
        airprint = (
            pathlib.Path(__file__).parents[1] / "scripts" / "setup-airprint.sh"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'AIRPRINT_DEFAULT_MEDIA="${AIRPRINT_DEFAULT_MEDIA:-iso_a4_210x297mm}"',
            airprint,
        )
        self.assertIn('-o media-default="$AIRPRINT_DEFAULT_MEDIA"', airprint)
        self.assertIn("Legal", airprint)
        self.assertGreaterEqual(
            self.setup_script.count('-o media-default="$AIRPRINT_DEFAULT_MEDIA"'),
            2,
        )

    def test_only_explicit_queue_is_loaded_and_mapping_is_preserved(self):
        self.assertIn("load printers = no", self.setup_script)
        self.assertNotIn("load printers = yes", self.setup_script)
        self.assertNotIn("force printername = yes", self.setup_script)
        self.assertIn("printer name = $SAMBA_WINDOWS_QUEUE", self.setup_script)

    def test_spool_path_works_with_distribution_selinux_policy(self):
        self.assertGreaterEqual(self.setup_script.count("path = /var/tmp/"), 2)
        self.assertNotIn("path = /var/spool/samba", self.setup_script)

    def test_windows_destination_serializes_through_source_queue(self):
        self.assertIn('lpadmin -p "$PRINTER_NAME" -c "$SAMBA_WINDOWS_QUEUE"', self.setup_script)
        self.assertIn('lpmove "$SAMBA_WINDOWS_QUEUE" "$PRINTER_NAME"', self.setup_script)
        self.assertIn('lpadmin -x "$SAMBA_WINDOWS_QUEUE"', self.setup_script)
        self.assertNotIn('-v "$DEVICE_URI"', self.setup_script)
        self.assertGreaterEqual(self.setup_script.count('set_printer_retry_policy'), 2)

    def test_cups_policy_exposes_owner_but_keeps_client_metadata_private(self):
        cupsd = (
            pathlib.Path(__file__).parents[1] / "config" / "cupsd.conf"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            cupsd.count("JobPrivateValues job-originating-host-name phone"), 2
        )
        self.assertNotIn("JobPrivateValues none", cupsd)

    def test_service_path_includes_cups_system_utilities(self):
        installer = (
            pathlib.Path(__file__).parents[1] / "install.sh"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'Environment="PATH=/opt/print-queue-manager/venv/bin:'
            '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"',
            installer,
        )


if __name__ == "__main__":
    unittest.main()
