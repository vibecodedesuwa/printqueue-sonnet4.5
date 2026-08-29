import pathlib
import unittest


class CaddyConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = (
            pathlib.Path(__file__).parents[1] / "config" / "caddy" / "Caddyfile"
        ).read_text(encoding="utf-8")

    def test_adcs_issuer_uses_keytab_without_password(self):
        self.assertIn("issuer certsrv", self.config)
        self.assertIn("keytab_path {$CERTSRV_KEYTAB_PATH:", self.config)
        self.assertNotIn("password {$CERTSRV_", self.config)

    def test_printq_and_cups_upstreams_are_separate(self):
        self.assertIn("reverse_proxy 127.0.0.1:5000", self.config)
        self.assertIn("reverse_proxy 127.0.0.1:631", self.config)
        self.assertIn("redir @cupsLanding /printers/ 302", self.config)


if __name__ == "__main__":
    unittest.main()
