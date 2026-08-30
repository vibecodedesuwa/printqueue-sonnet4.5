"""
Web routes for Print Queue Manager
Handles dashboard, admin, kiosk, login/logout, and API docs.
"""
from flask import Blueprint, render_template, redirect, url_for, session, request, flash, jsonify, current_app

from ..auth import login_required, is_admin, kiosk_required
from ..cups_utils import get_user_jobs, get_all_jobs, get_job_info, release_job, cancel_job, get_printer_status
from ..identity import usernames_match

web_bp = Blueprint('web', __name__)


def _same_user(left, right):
    return usernames_match(left, right, domain=current_app.config.get('LDAP_DOMAIN', ''))


# ─── Authentication & Landing ──────────────────────────────────────────

@web_bp.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('web.dashboard'))
    return render_template('landing.html', user=None)


@web_bp.route('/landing')
def landing():
    return render_template('landing.html', user=session.get('user'))


@web_bp.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('web.dashboard'))
    return render_template(
        'login.html',
        user=None,
        initial_auth_tab='ad' if request.args.get('tab') == 'ad' else 'sso',
    )


@web_bp.route('/login/sso')
def login_sso():
    """Trigger Authentik OAuth authorization redirect."""
    if 'user' in session:
        return redirect(url_for('web.dashboard'))
    import secrets
    oauth_state = secrets.token_urlsafe(32)
    session['oauth_state'] = oauth_state
    redirect_uri = url_for('web.authorize', _external=True)
    authentik = current_app.config['authentik']
    return authentik.authorize_redirect(redirect_uri, state=oauth_state)


@web_bp.route('/login/ad', methods=['POST'])
def login_ad():
    """Authenticate user against Active Directory (LDAP)."""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        flash('Username and password are required', 'error')
        return redirect(url_for('web.login', tab='ad'))

    ad_auth = current_app.config.get('ad_auth')
    if not ad_auth or not ad_auth.is_configured():
        flash('Active Directory server is not configured or reachable. Check LDAP settings in .env', 'error')
        return redirect(url_for('web.login', tab='ad'))

    user_info = ad_auth.authenticate(username, password)
    if user_info:
        session['user'] = {
            'username': user_info['username'],
            'email': user_info.get('email', ''),
            'name': user_info.get('name', username),
            'groups': user_info.get('groups', []),
            'auth_type': 'ad',
        }
        flash(f"Welcome, {session['user']['name']}! (AD Auth)", 'success')
        return redirect(url_for('web.dashboard'))

    flash('Invalid Active Directory username or password', 'error')
    return redirect(url_for('web.login', tab='ad'))


@web_bp.route('/editor')
@login_required
def editor_page():
    """Render the Collabora launcher and lightweight A4 fallback."""
    from .office import list_office_documents
    collabora_enabled = bool(
        current_app.config.get('COLLABORA_ENABLED')
        and current_app.config.get('COLLABORA_URL')
    )
    return render_template(
        'editor.html',
        user=session['user'],
        is_admin=is_admin(),
        collabora_enabled=collabora_enabled,
        collabora_ready=collabora_enabled and bool(current_app.config.get('WOPI_PUBLIC_URL')),
        office_documents=list_office_documents(session['user']['username']) if collabora_enabled else [],
    )


@web_bp.route('/qr-upload')
def qr_upload_page():
    """Render mobile QR code upload page"""
    return render_template('qr_upload.html', user=session.get('user'), is_admin=is_admin())


@web_bp.route('/authorize')
def authorize():
    try:
        import hmac
        import requests as http_req

        expected_state = session.pop('oauth_state', None)
        received_state = request.args.get('state', '')
        if not expected_state or not hmac.compare_digest(expected_state, received_state):
            flash('Invalid or expired login request. Please try again.', 'error')
            return redirect(url_for('web.login'))

        if request.args.get('error'):
            flash('Single sign-on was canceled or denied', 'error')
            return redirect(url_for('web.login'))

        code = request.args.get('code')
        if not code:
            flash('No authorization code received', 'error')
            return redirect(url_for('web.login'))

        authentik = current_app.config['authentik']

        # Load OpenID metadata to get endpoints
        metadata = authentik.load_server_metadata()
        token_endpoint = metadata['token_endpoint']
        userinfo_endpoint = metadata['userinfo_endpoint']

        # Exchange code for token (bypass authlib's JWKS verification)
        from ..config import Config
        token_resp = http_req.post(token_endpoint, data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': url_for('web.authorize', _external=True),
            'client_id': Config.AUTHENTIK_CLIENT_ID,
            'client_secret': Config.AUTHENTIK_CLIENT_SECRET,
        }, timeout=15)

        if token_resp.status_code != 200:
            print(f"[AUTH ERROR] Token exchange failed: {token_resp.status_code} {token_resp.text}")
            flash('Token exchange failed', 'error')
            return redirect(url_for('web.login'))

        token_data = token_resp.json()
        access_token = token_data.get('access_token')

        if not access_token:
            print(f"[AUTH ERROR] No access_token in response: {list(token_data.keys())}")
            flash('No access token received', 'error')
            return redirect(url_for('web.login'))

        # Fetch userinfo using access token
        userinfo_resp = http_req.get(userinfo_endpoint, headers={
            'Authorization': f'Bearer {access_token}'
        }, timeout=15)
        if userinfo_resp.status_code != 200:
            flash('Failed to get user information', 'error')
            return redirect(url_for('web.login'))
        user_info = userinfo_resp.json()

        if user_info and (user_info.get('preferred_username') or user_info.get('email')):
            session['user'] = {
                'username': user_info.get('preferred_username') or user_info.get('email'),
                'email': user_info.get('email'),
                'name': user_info.get('name', user_info.get('preferred_username', 'User')),
                'groups': user_info.get('groups', []),
                'auth_type': 'sso',
            }
            # Store id_token for RP-Initiated Logout
            if token_data.get('id_token'):
                session['id_token'] = token_data['id_token']
            flash(f"Welcome, {session['user']['name']}!", 'success')
            return redirect(url_for('web.dashboard'))
        else:
            print(f"[AUTH ERROR] Userinfo response: {user_info}")
            flash('Failed to get user information', 'error')
            return redirect(url_for('web.login'))
    except Exception as e:
        import traceback
        print(f"[AUTH ERROR] OAuth callback failed: {e}")
        traceback.print_exc()
        flash(f'Authentication error: {str(e)}', 'error')
        return redirect(url_for('web.login'))


@web_bp.route('/logout')
def logout():
    """OIDC RP-Initiated Logout: clears local session then redirects to Authentik to end SSO session."""
    id_token = session.pop('id_token', None)
    session.pop('user', None)
    session.clear()

    # Try to redirect to Authentik's end_session_endpoint for full SSO logout
    try:
        authentik = current_app.config['authentik']
        metadata = authentik.load_server_metadata()
        end_session_url = metadata.get('end_session_endpoint')

        if end_session_url:
            from urllib.parse import urlencode
            params = {
                'post_logout_redirect_uri': url_for('web.login', _external=True),
            }
            if id_token:
                params['id_token_hint'] = id_token
            return redirect(f"{end_session_url}?{urlencode(params)}")
    except Exception as e:
        print(f"[LOGOUT] Could not redirect to Authentik logout: {e}")

    # Fallback: just redirect to login
    flash('You have been logged out', 'info')
    return redirect(url_for('web.login'))


# ─── Dashboard ─────────────────────────────────────────────────────────

@web_bp.route('/dashboard')
@login_required
def dashboard():
    username = session['user']['username']
    db = current_app.config['db']
    jobs = get_user_jobs(username, db=db)

    # Get unclaimed jobs for the claim system
    all_jobs = get_all_jobs(db=db)
    # Build unclaimed jobs list, also check auto-match
    unclaimed_jobs = []
    my_jobs_from_devices = []

    for job in all_jobs:
        cups_user = job['user']

        # Check if this CUPS user is mapped to current user via KnownDevice
        mapped_user = db.get_device_mapping(cups_user)
        if _same_user(mapped_user, username) or _same_user(cups_user, username):
            my_jobs_from_devices.append(job)
            continue

        # Only unauthenticated/generic device jobs enter the claim pool.
        # Jobs owned by AD-authenticated IPP or Samba users stay private.
        if job.get('claimable', False):
            # Unknown user, not yet in our tracking — add to meta as unclaimed
            meta = db.get_job_meta(job['id'])
            if not meta:
                db.create_job_meta(job['id'], submitted_via='ipp')
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

    db = current_app.config['db']
    jobs = get_all_jobs(db=db)
    api_keys = db.list_api_keys()
    known_devices = db.list_known_devices()
    email_mappings = db.list_email_mappings()
    kiosk_devices = db.list_kiosk_devices()

    return render_template('admin.html',
                           user=session['user'],
                           jobs=jobs,
                           api_keys=api_keys,
                           known_devices=known_devices,
                           email_mappings=email_mappings,
                           kiosk_devices=kiosk_devices)


# ─── Job Actions (Web) ────────────────────────────────────────────────

@web_bp.route('/api/jobs')
@login_required
def api_jobs():
    db = current_app.config['db']
    if is_admin() and request.args.get('all') == 'true':
        jobs = get_all_jobs(db=db)
    else:
        username = session['user']['username']
        jobs = get_user_jobs(username, db=db)
    return jsonify(jobs)


@web_bp.route('/api/jobs/unclaimed')
@login_required
def api_unclaimed_jobs():
    db = current_app.config['db']
    username = session['user']['username']
    all_jobs = get_all_jobs(db=db)
    unclaimed_jobs = []
    for job in all_jobs:
        cups_user = job['user']
        mapped_user = db.get_device_mapping(cups_user)
        if _same_user(mapped_user, username) or _same_user(cups_user, username):
            continue
        if job.get('claimable', False):
            meta = db.get_job_meta(job['id'])
            if not meta:
                db.create_job_meta(job['id'], submitted_via='ipp')
            unclaimed_jobs.append(job)
    return jsonify(unclaimed_jobs)


@web_bp.route('/api/job/<int:job_id>/release', methods=['POST'])
@login_required
def api_release_job(job_id):
    username = session['user']['username']

    success, message, status = release_job(job_id, username, is_admin())
    return jsonify({'success': success, 'message' if success else 'error': message}), status if not success else 200


@web_bp.route('/api/job/<int:job_id>/cancel', methods=['POST'])
@login_required
def api_cancel_job(job_id):
    username = session['user']['username']

    success, message, status = cancel_job(job_id, username, is_admin())
    return jsonify({'success': success, 'message' if success else 'error': message}), status if not success else 200


@web_bp.route('/api/job/<int:job_id>/claim', methods=['POST'])
@login_required
def api_claim_job(job_id):
    username = session['user']['username']
    db = current_app.config['db']
    job = get_job_info(job_id, db=db)
    if not job:
        return jsonify({'success': False, 'message': 'Job not found'}), 404
    if not job.get('claimable', False):
        return jsonify({
            'success': False,
            'message': 'This authenticated job already belongs to its submitting user',
        }), 409
    success, message = db.claim_job(job_id, username)
    return jsonify({'success': success, 'message': message}), 200 if success else 409


@web_bp.route('/api/printer/status')
@login_required
def api_printer_status():
    status = get_printer_status()
    return jsonify(status)


# ─── Kiosk Mode (Device Token Auth) ────────────────────────────────

@web_bp.route('/kiosk')
def kiosk_entry():
    """Kiosk entry — if device is authorized, go to dashboard. Otherwise show unauthorized page."""
    token = request.cookies.get('kiosk_device_token')
    if token:
        db = current_app.config['db']
        device = db.validate_kiosk_token(token, client_ip=request.remote_addr)
        if device:
            return redirect(url_for('web.kiosk_dashboard'))
    return redirect(url_for('web.kiosk_unauthorized'))


@web_bp.route('/kiosk/unauthorized')
def kiosk_unauthorized():
    """Shown when a device doesn't have a valid kiosk token."""
    return render_template('kiosk_unauthorized.html')


@web_bp.route('/kiosk/register/<token>')
def kiosk_register(token):
    """One-time registration URL. Sets a long-lived device token cookie."""
    db = current_app.config['db']
    device = db.validate_kiosk_token(token, client_ip=None)  # Skip IP check for registration
    if not device:
        return render_template('kiosk_unauthorized.html', error='Invalid or expired registration link.')

    resp = redirect(url_for('web.kiosk_dashboard'))
    # Set cookie for 10 years (effectively permanent)
    resp.set_cookie(
        'kiosk_device_token', token,
        max_age=10 * 365 * 24 * 3600,
        httponly=True,
        samesite='Lax',
        secure=request.is_secure,
    )
    return resp


@web_bp.route('/kiosk/dashboard')
@kiosk_required
def kiosk_dashboard():
    db = current_app.config['db']
    jobs = get_all_jobs(db=db)
    printer = get_printer_status()
    device = getattr(request, 'kiosk_device', {})
    return render_template('kiosk.html', jobs=jobs, printer=printer, device=device)


@web_bp.route('/kiosk/api/jobs')
@kiosk_required
def kiosk_api_jobs():
    db = current_app.config['db']
    jobs = get_all_jobs(db=db)
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


# ─── Kiosk Device Admin Endpoints ─────────────────────────────────

@web_bp.route('/api/admin/kiosk-devices', methods=['POST'])
@login_required
def create_kiosk_device():
    if not is_admin():
        return jsonify({'error': 'Admin required'}), 403
    data = request.get_json()
    name = data.get('name', '').strip()
    allowed_ip = data.get('allowed_ip', '').strip() or None
    if not name:
        return jsonify({'error': 'Device name is required'}), 400

    db = current_app.config['db']
    raw_token = db.create_kiosk_device(name, allowed_ip=allowed_ip)
    registration_url = url_for('web.kiosk_register', token=raw_token, _external=True)
    return jsonify({'token': raw_token, 'registration_url': registration_url})


@web_bp.route('/api/admin/kiosk-devices/<int:device_id>', methods=['DELETE'])
@login_required
def delete_kiosk_device(device_id):
    if not is_admin():
        return jsonify({'error': 'Admin required'}), 403
    db = current_app.config['db']
    db.delete_kiosk_device(device_id)
    return jsonify({'success': True})


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
