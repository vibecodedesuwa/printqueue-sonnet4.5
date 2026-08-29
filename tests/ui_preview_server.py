"""Local-only preview server used for interactive UI verification."""
import os
import sys
import tempfile
import time
import types


class FakeCupsConnection:
    jobs = {
        12: {
            'job-originating-user-name': r'ACME\alice',
            'printer-uri': 'ipp://localhost/printers/Office_Printer',
            'job-state': 4,
            'time-at-creation': int(time.time()) - 180,
            'job-k-octets': 842,
            'job-media-sheets-completed': 0,
        },
        13: {
            'job-originating-user-name': 'iPhone',
            'job-name': 'Travel receipt.jpg',
            'printer-uri': 'ipp://localhost/printers/Office_Printer',
            'job-state': 4,
            'time-at-creation': int(time.time()) - 60,
            'job-k-octets': 315,
            'job-media-sheets-completed': 0,
        },
    }

    def getJobs(self, **_kwargs):
        return {job_id: dict(info) for job_id, info in self.jobs.items()}

    def getJobAttributes(self, job_id):
        return dict(self.jobs[job_id])

    def getPrinters(self):
        return {
            'Office_Printer': {
                'printer-state': 3,
                'printer-state-message': 'Ready',
                'printer-is-accepting-jobs': True,
                'printer-is-shared': True,
                'printer-info': 'Office Printer',
                'printer-location': 'Reception',
            }
        }

    def setJobHoldUntil(self, job_id, _value):
        self.jobs[job_id]['job-state'] = 3

    def cancelJob(self, job_id):
        self.jobs[job_id]['job-state'] = 7

    def printFile(self, *_args, **_kwargs):
        return 14


fake_cups = types.ModuleType('cups')
fake_cups.Connection = lambda **_kwargs: FakeCupsConnection()
fake_cups.setUser = lambda _user: None
fake_cups.setPasswordCB = lambda _callback: None
sys.modules['cups'] = fake_cups

from flask import redirect, session
from printqueue import create_app
from printqueue.config import Config


class PreviewConfig(Config):
    SECRET_KEY = 'local-ui-preview-only'
    DATABASE_PATH = os.path.join(tempfile.mkdtemp(prefix='printq-ui-'), 'preview.db')
    UPLOAD_FOLDER = os.path.join(tempfile.mkdtemp(prefix='printq-upload-'), 'uploads')
    OFFICE_FOLDER = os.path.join(tempfile.mkdtemp(prefix='printq-office-'), 'office')
    PRINTER_NAME = 'Office_Printer'
    LDAP_ENABLED = True
    LDAP_SHOW_IN_WEBUI = True
    LDAP_HOST = 'preview.invalid'
    LDAP_DOMAIN = 'acme.local'
    AUTHENTIK_CLIENT_ID = 'preview'
    AUTHENTIK_CLIENT_SECRET = 'preview'
    AUTHENTIK_METADATA_URL = 'https://preview.invalid/.well-known/openid-configuration'
    MAIL_ENABLED = False
    COLLABORA_ENABLED = True
    COLLABORA_URL = 'https://office.toonshou.in'
    COLLABORA_INTERNAL_URL = 'http://172.16.0.9:9980'
    WOPI_PUBLIC_URL = 'http://127.0.0.1:5055'


app = create_app(PreviewConfig)
app.config['db'].create_job_meta(
    12,
    submitted_via='web',
    original_filename='รายงานประจำเดือน.pdf',
    submitted_by='alice',
)
preview_kiosk_token = app.config['db'].create_kiosk_device('Reception Kiosk')


@app.route('/__preview/dashboard')
def preview_dashboard():
    session['user'] = {
        'username': 'alice',
        'name': 'Alice Example',
        'email': 'alice@acme.local',
        'groups': ['print-admins'],
        'auth_type': 'ad',
    }
    return redirect('/dashboard')


@app.route('/__preview/kiosk')
def preview_kiosk():
    response = redirect('/kiosk/dashboard')
    response.set_cookie('kiosk_device_token', preview_kiosk_token, httponly=True, samesite='Lax')
    return response


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5055, debug=False)
