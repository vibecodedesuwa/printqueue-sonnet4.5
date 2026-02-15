"""
REST API v1 routes for Print Queue Manager
Token-authenticated API for external applications.
"""
from flask import Blueprint, request, jsonify, current_app
import json

from ..auth import api_key_required, api_key_or_session
from ..cups_utils import (
    get_user_jobs, get_all_jobs, get_job_info,
    release_job, cancel_job, get_printer_status,
    list_printers, submit_print_job
)

api_bp = Blueprint('api_v1', __name__)


# ─── Health (No Auth) ──────────────────────────────────────────────────

@api_bp.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'print-queue-manager',
        'api_version': 'v1'
    })


# ─── Jobs ──────────────────────────────────────────────────────────────

@api_bp.route('/jobs')
@api_key_required('read')
def list_jobs():
    """List print jobs. Filters: ?user=, ?state=, ?unclaimed=true"""
    user_filter = request.args.get('user')
    state_filter = request.args.get('state')
    unclaimed_only = request.args.get('unclaimed', '').lower() == 'true'

    if user_filter:
        jobs = get_user_jobs(user_filter)
    else:
        jobs = get_all_jobs()

    if state_filter:
        jobs = [j for j in jobs if j['state_text'].lower() == state_filter.lower()]

    if unclaimed_only:
        db = current_app.config['db']
        unclaimed_ids = db.get_unclaimed_jobs()
        jobs = [j for j in jobs if j['id'] in unclaimed_ids]

    # Enrich with metadata
    db = current_app.config['db']
    for job in jobs:
        meta = db.get_job_meta(job['id'])
        if meta:
            job['submitted_via'] = meta.get('submitted_via', 'ipp')
            job['claimed_by'] = meta.get('claimed_by')
            job['original_filename'] = meta.get('original_filename')

    response = jsonify({
        'jobs': jobs,
        'total': len(jobs)
    })
    response.headers['X-RateLimit-Remaining'] = str(request.rate_limit_remaining)
    return response


@api_bp.route('/jobs/unclaimed')
@api_key_required('read')
def list_unclaimed_jobs():
    """List unclaimed jobs from IPP/AirPrint submissions"""
    db = current_app.config['db']
    unclaimed_ids = db.get_unclaimed_jobs()
    all_jobs = get_all_jobs()
    unclaimed = [j for j in all_jobs if j['id'] in unclaimed_ids]

    return jsonify({
        'jobs': unclaimed,
        'total': len(unclaimed)
    })


@api_bp.route('/jobs/<int:job_id>')
@api_key_required('read')
def get_job(job_id):
    """Get details of a specific job"""
    job = get_job_info(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    db = current_app.config['db']
    meta = db.get_job_meta(job_id)
    if meta:
        job['submitted_via'] = meta.get('submitted_via', 'ipp')
        job['claimed_by'] = meta.get('claimed_by')
        job['original_filename'] = meta.get('original_filename')

    return jsonify(job)


@api_bp.route('/jobs/<int:job_id>/release', methods=['POST'])
@api_key_required('write')
def api_release_job(job_id):
    """Release a held job"""
    success, message, status = release_job(job_id, is_admin=True)
    return jsonify({
        'success': success,
        'message' if success else 'error': message
    }), 200 if success else status


@api_bp.route('/jobs/<int:job_id>/cancel', methods=['POST'])
@api_key_required('write')
def api_cancel_job(job_id):
    """Cancel a job"""
    success, message, status = cancel_job(job_id, is_admin=True)
    return jsonify({
        'success': success,
        'message' if success else 'error': message
    }), 200 if success else status


@api_bp.route('/jobs/<int:job_id>/claim', methods=['POST'])
@api_key_required('write')
def api_claim_job(job_id):
    """Claim an unclaimed job"""
    data = request.get_json() or {}
    username = data.get('username')
    if not username:
        return jsonify({'error': 'username is required'}), 400

    db = current_app.config['db']
    success, message = db.claim_job(job_id, username)
    return jsonify({
        'success': success,
        'message': message
    }), 200 if success else 409


# ─── Print (File Upload) ──────────────────────────────────────────────

@api_bp.route('/print', methods=['POST'])
@api_key_required('write')
def api_print():
    """Submit a print job via file upload"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Check file extension
    allowed = current_app.config['ALLOWED_EXTENSIONS']
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed:
        return jsonify({
            'error': f'File type not allowed. Accepted: {", ".join(allowed)}'
        }), 400

    # Save file
    import os
    import tempfile
    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)

    from werkzeug.utils import secure_filename
    filename = secure_filename(file.filename)
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    # Convert if needed
    from ..services.file_converter import convert_if_needed
    converted_path = convert_if_needed(filepath)

    # Print options
    options = {}
    copies = request.form.get('copies', '1')
    if copies.isdigit() and int(copies) > 0:
        options['copies'] = copies
    if request.form.get('duplex') == 'true':
        options['sides'] = 'two-sided-long-edge'
    if request.form.get('color') == 'false':
        options['ColorModel'] = 'Gray'
    page_range = request.form.get('page_range', '')
    if page_range:
        options['page-ranges'] = page_range

    # Submit to CUPS
    printer_name = request.form.get('printer') or current_app.config['PRINTER_NAME']
    success, result = submit_print_job(converted_path, filename, printer_name, options)

    if success:
        db = current_app.config['db']
        owner = request.api_key.get('owner', 'api') if request.api_key else 'api'
        db.create_job_meta(result, submitted_via='api', original_filename=filename, submitted_by=owner)

        return jsonify({
            'success': True,
            'job_id': result,
            'message': f'Job #{result} submitted and held for approval'
        }), 201
    else:
        return jsonify({'success': False, 'error': result}), 500


# ─── Printer ───────────────────────────────────────────────────────────

@api_bp.route('/printer/status')
@api_key_required('read')
def api_printer_status():
    """Get default printer status"""
    status = get_printer_status()
    return jsonify(status)


@api_bp.route('/printers')
@api_key_required('read')
def api_list_printers():
    """List all available printers"""
    printers = list_printers()
    return jsonify({'printers': printers, 'total': len(printers)})


# ─── API Key Management (Admin) ───────────────────────────────────────

@api_bp.route('/keys')
@api_key_required('admin')
def list_keys():
    """List all API keys"""
    db = current_app.config['db']
    keys = db.list_api_keys()
    # Parse permissions JSON
    for k in keys:
        if isinstance(k.get('permissions'), str):
            k['permissions'] = json.loads(k['permissions'])
    return jsonify({'keys': keys, 'total': len(keys)})


@api_bp.route('/keys', methods=['POST'])
@api_key_required('admin')
def create_key():
    """Create a new API key"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    name = data.get('name')
    owner = data.get('owner', request.api_key.get('owner', 'admin'))
    permissions = data.get('permissions', ['read'])

    if not name:
        return jsonify({'error': 'name is required'}), 400

    valid_perms = {'read', 'write', 'admin'}
    if not all(p in valid_perms for p in permissions):
        return jsonify({'error': f'Invalid permissions. Valid: {valid_perms}'}), 400

    db = current_app.config['db']
    raw_key = db.create_api_key(name, owner, permissions)

    return jsonify({
        'success': True,
        'key': raw_key,
        'name': name,
        'permissions': permissions,
        'warning': 'Save this key now — it cannot be retrieved later!'
    }), 201


@api_bp.route('/keys/<int:key_id>', methods=['DELETE'])
@api_key_required('admin')
def revoke_key(key_id):
    """Revoke an API key"""
    db = current_app.config['db']
    db.revoke_api_key(key_id)
    return jsonify({'success': True, 'message': f'Key {key_id} revoked'})


# ─── Users ─────────────────────────────────────────────────────────────

@api_bp.route('/users')
@api_key_required('admin')
def list_users():
    """List known users from device mappings and email mappings"""
    db = current_app.config['db']
    devices = db.list_known_devices()
    emails = db.list_email_mappings()

    users = set()
    for d in devices:
        users.add(d['authentik_username'])
    for e in emails:
        users.add(e['username'])

    return jsonify({
        'users': sorted(list(users)),
        'device_mappings': devices,
        'email_mappings': emails
    })


# ─── Device Mapping (Session Auth for Admin UI) ──────────────────────

@api_bp.route('/devices', methods=['POST'])
@api_key_or_session('admin')
def add_device():
    """Add a device-to-user mapping"""
    data = request.get_json()
    if not data or not data.get('cups_username') or not data.get('authentik_username'):
        return jsonify({'error': 'cups_username and authentik_username required'}), 400

    db = current_app.config['db']
    db.add_known_device(data['cups_username'], data['authentik_username'])
    return jsonify({'success': True}), 201


@api_bp.route('/devices/<int:device_id>', methods=['DELETE'])
@api_key_or_session('admin')
def delete_device(device_id):
    """Delete a device mapping"""
    db = current_app.config['db']
    db.delete_known_device(device_id)
    return jsonify({'success': True})


@api_bp.route('/emails', methods=['POST'])
@api_key_or_session('admin')
def add_email():
    """Add an email-to-user mapping"""
    data = request.get_json()
    if not data or not data.get('email') or not data.get('username'):
        return jsonify({'error': 'email and username required'}), 400

    db = current_app.config['db']
    db.add_email_mapping(data['email'], data['username'])
    return jsonify({'success': True}), 201


@api_bp.route('/emails/<path:email>', methods=['DELETE'])
@api_key_or_session('admin')
def delete_email(email):
    """Delete an email mapping"""
    db = current_app.config['db']
    db.delete_email_mapping(email)
    return jsonify({'success': True})

