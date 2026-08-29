import pathlib
import unittest


class CaddyConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = pathlib.Path(__file__).parents[1]
        cls.config = (project / "config" / "caddy" / "Caddyfile").read_text(
            encoding="utf-8"
        )
        cls.service = (project / "config" / "systemd" / "caddy.service").read_text(
            encoding="utf-8"
        )
        cls.setup_script = (project / "scripts" / "setup-caddy.sh").read_text(
            encoding="utf-8"
        )
        cls.build_script = (project / "scripts" / "build-caddy-certsrv.sh").read_text(
            encoding="utf-8"
        )
        cls.plugin_patch = (
            project / "config" / "caddy" / "caddy-certsrv.patch"
        ).read_text(encoding="utf-8")

    def test_adcs_issuer_uses_keytab_without_password(self):
        self.assertIn("issuer certsrv", self.config)
        self.assertIn("keytab_path {$CERTSRV_KEYTAB_PATH:", self.config)
        self.assertIn("krb5_config {$CERTSRV_KRB5_CONFIG:", self.config)
        self.assertNotIn("password {$CERTSRV_", self.config)

    def test_printq_and_cups_upstreams_are_separate(self):
        self.assertIn("reverse_proxy 127.0.0.1:5000", self.config)
        self.assertIn("reverse_proxy 127.0.0.1:631", self.config)
        self.assertIn("redir @cupsLanding /printers/ 302", self.config)

    def test_source_build_can_install_a_systemd_service(self):
        self.assertIn("User=caddy", self.service)
        self.assertIn("ExecStart=/usr/bin/caddy run", self.service)
        self.assertIn("AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE", self.service)
        self.assertIn("systemctl cat caddy.service", self.setup_script)
        self.assertIn('useradd --system --gid caddy', self.setup_script)

    def test_build_patches_the_upstream_nil_client_failure(self):
        self.assertIn("git -C \"$PATCHED_PLUGIN_DIR\" apply", self.build_script)
        self.assertIn("initialize AD CS Kerberos client", self.plugin_patch)
        self.assertIn('case "krb5_config":', self.plugin_patch)
        self.assertNotIn('log.Printf("certSrv:', self.plugin_patch)


if __name__ == "__main__":
    unittest.main()
