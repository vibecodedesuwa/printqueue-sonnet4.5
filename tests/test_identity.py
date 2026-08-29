import pathlib
import sys
import types
import unittest

# Unit-test dependency-free modules without importing the Flask app factory.
package = sys.modules.setdefault("printqueue", types.ModuleType("printqueue"))
package.__path__ = [str(pathlib.Path(__file__).parents[1] / "printqueue")]

from printqueue.identity import canonical_username, username_aliases, usernames_match


class IdentityTests(unittest.TestCase):
    def test_domain_and_sam_account_match(self):
        self.assertTrue(usernames_match(r"ACME\Alice", "alice", domain="acme.local"))

    def test_upn_in_configured_domain_matches(self):
        self.assertTrue(usernames_match("Alice@ACME.LOCAL", "alice", domain="acme.local"))

    def test_upn_from_another_domain_does_not_collapse(self):
        self.assertFalse(usernames_match("alice@other.local", "alice", domain="acme.local"))

    def test_empty_values_never_match(self):
        self.assertFalse(usernames_match(None, ""))

    def test_canonical_username_prefers_account_name(self):
        self.assertEqual(canonical_username(r"ACME\Alice"), "alice")


if __name__ == "__main__":
    unittest.main()
