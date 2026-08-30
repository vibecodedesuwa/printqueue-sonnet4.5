import pathlib
import unittest


class CupsRetryPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = pathlib.Path(__file__).parents[1]
        cls.platform = (root / "scripts" / "platform.sh").read_text(encoding="utf-8")
        cls.airprint = (root / "scripts" / "setup-airprint.sh").read_text(encoding="utf-8")

    def test_distribution_helper_uses_supported_policy_fallbacks(self):
        for policy in ("retry-job", "retry-current-job", "stop-printer"):
            self.assertIn(policy, self.platform)
        self.assertIn('set_printer_retry_policy "$PRINTER_NAME"', self.airprint)


if __name__ == "__main__":
    unittest.main()
