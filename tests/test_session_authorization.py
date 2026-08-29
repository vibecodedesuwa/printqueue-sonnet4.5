import pathlib
import sys
import types
import unittest


package = sys.modules.setdefault("printqueue", types.ModuleType("printqueue"))
package.__path__ = [str(pathlib.Path(__file__).parents[1] / "printqueue")]

fake_flask = types.ModuleType("flask")
fake_flask.session = {}
fake_flask.request = types.SimpleNamespace(headers={}, cookies={}, path='')
fake_flask.jsonify = lambda value: value
fake_flask.redirect = lambda value: value
fake_flask.url_for = lambda endpoint: endpoint
fake_flask.current_app = types.SimpleNamespace(
    config={"ADMIN_GROUPS": ["admins"], "ADMIN_USERS": ["admin"]}
)
sys.modules.setdefault("flask", fake_flask)

from printqueue.auth import api_key_or_session, kiosk_required


class SessionAuthorizationTests(unittest.TestCase):
    def setUp(self):
        fake_flask.session.clear()
        fake_flask.request.headers = {}
        fake_flask.request.cookies = {}
        fake_flask.request.path = ''
        self.admin_only = api_key_or_session("admin")(lambda: {"ok": True})

    def login_as(self, username, groups=None):
        fake_flask.session["user"] = {
            "username": username,
            "groups": groups or [],
        }

    def test_regular_session_cannot_use_admin_api(self):
        self.login_as("alice")
        response, status = self.admin_only()
        self.assertEqual(status, 403)
        self.assertIn("admin required", response["error"])

    def test_admin_session_can_use_admin_api(self):
        self.login_as("alice", ["admins"])
        self.assertEqual(self.admin_only(), {"ok": True})

    def test_kiosk_api_returns_json_auth_error_instead_of_html_redirect(self):
        fake_flask.request.path = '/kiosk/api/jobs'
        response, status = kiosk_required(lambda: {"ok": True})()
        self.assertEqual(status, 401)
        self.assertIn('authentication required', response['error'])


if __name__ == "__main__":
    unittest.main()
