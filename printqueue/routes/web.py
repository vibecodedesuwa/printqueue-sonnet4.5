"""
Web routes for Print Queue Manager
Handles dashboard, admin, kiosk, login/logout, and API docs.
"""
from flask import Blueprint, render_template, redirect, url_for, session, request, flash, jsonify, current_app

from ..auth import login_required, is_admin, kiosk_required
from ..cups_utils import get_user_jobs, get_all_jobs, release_job, cancel_job, get_printer_status

web_bp = Blueprint('web', __name__)


# ─── Authentication ────────────────────────────────────────────────────

@web_bp.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('web.dashboard'))
    return redirect(url_for('web.login'))


@web_bp.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('web.dashboard'))
    redirect_uri = url_for('web.authorize', _external=True)
    authentik = current_app.config['authentik']
    return authentik.authorize_redirect(redirect_uri)


@web_bp.route('/authorize')
def authorize():
    try:
        authentik = current_app.config['authentik']
        token = authentik.authorize_access_token()
        user_info = token.get('userinfo')

        if user_info:
            session['user'] = {
                'username': user_info.get('preferred_username') or user_info.get('email'),
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'groups': user_info.get('groups', [])
            }
            flash(f"Welcome, {session['user']['name']}!", 'success')
            return redirect(url_for('web.dashboard'))
        else:
            flash('Failed to get user information', 'error')
            return redirect(url_for('web.login'))
    except Exception as e:
        flash(f'Authentication error: {str(e)}', 'error')
        return redirect(url_for('web.login'))


@web_bp.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('web.login'))


# ─── Dashboard ─────────────────────────────────────────────────────────

@web_bp.route('/dashboard')
@login_required
def dashboard():
    username = session['user']['username']
    jobs = get_user_jobs(username)
    db = current_app.config['db']

    # Get unclaimed jobs for the claim system
    all_jobs = get_all_jobs()
    unclaimed_job_ids = db.get_unclaimed_jobs()

    # Build unclaimed jobs list, also check auto-match
    unclaimed_jobs = []
    my_jobs_from_devices = []

    for job in all_jobs:
        cups_user = job['user']

        # Check if this CUPS user is mapped to current user via KnownDevice
        mapped_user = db.get_device_mapping(cups_user)
        if mapped_user == username:
            my_jobs_from_devices.append(job)
            continue

        # Check if it's unclaimed
        if job['id'] in unclaimed_job_ids:
            unclaimed_jobs.append(job)
        elif not mapped_user and cups_user != username:
            # Unknown user, not yet in our tracking — add to meta as unclaimed
            meta = db.get_job_meta(job['id'])
            if not meta:
                db.create_job_meta(job['id'], submitted_via='ipp', submitted_by=cups_user)
                unclaimed_jobs.append(job)

    # Combine user's own jobs + device-mapped jobs
    combined_jobs = jobs + [j for j in my_jobs_from_devices if j not in jobs]

    return render_template('dashboard.html',
                           user=session['user'],
                           jobs=combined_jobs,
                           unclaimed_jobs=unclaimed_jobs,
                           is_admin=is_admin())


@web_bp.route('/admin')
@login_required
def admin():
    if not is_admin():
        flash('Access denied — Admin privileges required', 'error')
        return redirect(url_for('web.dashboard'))

    jobs = get_all_jobs()
    db = current_app.config['db']
    api_keys = db.list_api_keys()
    known_devices = db.list_known_devices()
    email_mappings = db.list_email_mappings()

    return render_template('admin.html',
                           user=session['user'],
                           jobs=jobs,
                           api_keys=api_keys,
                           known_devices=known_devices,
                           email_mappings=email_mappings)


# ─── Job Actions (Web) ────────────────────────────────────────────────

@web_bp.route('/api/jobs')
@login_required
def api_jobs():
    if is_admin() and request.args.get('all') == 'true':
        jobs = get_all_jobs()
    else:
        username = session['user']['username']
        jobs = get_user_jobs(username)
    return jsonify(jobs)


@web_bp.route('/api/job/<int:job_id>/release', methods=['POST'])
@login_required
def api_release_job(job_id):
    username = session['user']['username']
    db = current_app.config['db']

    # Check if user claimed this job
    claimed_owner = db.get_claimed_owner(job_id)
    effective_user = claimed_owner or username

    success, message, status = release_job(job_id, effective_user, is_admin())
    return jsonify({'success': success, 'message' if success else 'error': message}), status if not success else 200


@web_bp.route('/api/job/<int:job_id>/cancel', methods=['POST'])
@login_required
def api_cancel_job(job_id):
    username = session['user']['username']
    db = current_app.config['db']

    claimed_owner = db.get_claimed_owner(job_id)
    effective_user = claimed_owner or username

    success, message, status = cancel_job(job_id, effective_user, is_admin())
    return jsonify({'success': success, 'message' if success else 'error': message}), status if not success else 200


@web_bp.route('/api/job/<int:job_id>/claim', methods=['POST'])
@login_required
def api_claim_job(job_id):
    username = session['user']['username']
    db = current_app.config['db']
    success, message = db.claim_job(job_id, username)
    return jsonify({'success': success, 'message': message}), 200 if success else 409


@web_bp.route('/api/printer/status')
@login_required
def api_printer_status():
    status = get_printer_status()
    return jsonify(status)


# ─── Kiosk Mode ────────────────────────────────────────────────────────

@web_bp.route('/kiosk')
def kiosk_login():
    if session.get('kiosk_authenticated'):
        return redirect(url_for('web.kiosk_dashboard'))
    return render_template('kiosk_login.html')


@web_bp.route('/kiosk/auth', methods=['POST'])
def kiosk_auth():
    pin = request.form.get('pin', '')
    if pin == current_app.config['KIOSK_PIN']:
        session['kiosk_authenticated'] = True
        return redirect(url_for('web.kiosk_dashboard'))
    flash('Invalid PIN', 'error')
    return redirect(url_for('web.kiosk_login'))


@web_bp.route('/kiosk/dashboard')
@kiosk_required
def kiosk_dashboard():
    jobs = get_all_jobs()
    printer = get_printer_status()
    return render_template('kiosk.html', jobs=jobs, printer=printer)


@web_bp.route('/kiosk/api/jobs')
@kiosk_required
def kiosk_api_jobs():
    jobs = get_all_jobs()
    printer = get_printer_status()
    return jsonify({'jobs': jobs, 'printer': printer})


@web_bp.route('/kiosk/api/job/<int:job_id>/release', methods=['POST'])
@kiosk_required
def kiosk_release_job(job_id):
    success, message, status = release_job(job_id, is_admin=True)
    return jsonify({'success': success, 'message' if success else 'error': message}), status if not success else 200


@web_bp.route('/kiosk/api/job/<int:job_id>/cancel', methods=['POST'])
@kiosk_required
def kiosk_cancel_job(job_id):
    success, message, status = cancel_job(job_id, is_admin=True)
    return jsonify({'success': success, 'message' if success else 'error': message}), status if not success else 200


# ─── API Documentation ────────────────────────────────────────────────

@web_bp.route('/api/docs')
def api_docs():
    return render_template('api_docs.html')


@web_bp.route('/api/v1/openapi.json')
def openapi_spec():
    import yaml
    import os
    spec_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'swagger', 'api_v1.yml')
    with open(spec_path, 'r') as f:
        spec = yaml.safe_load(f)
    return jsonify(spec)


# ─── Health ────────────────────────────────────────────────────────────

@web_bp.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'print-queue-manager'})
