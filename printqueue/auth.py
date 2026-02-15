"""
Authentication decorators for Print Queue Manager
Supports both session-based auth (Authentik SSO) and API key auth.
"""
from functools import wraps
from flask import session, request, jsonify, redirect, url_for, current_app


def get_current_user():
    """Get current user from session"""
    return session.get('user')


def is_admin():
    """Check if current user is admin"""
    user = session.get('user', {})
    groups = user.get('groups', [])
    config = current_app.config

    admin_groups = config.get('ADMIN_GROUPS', ['admins', 'print-admins'])
    admin_users = config.get('ADMIN_USERS', ['admin'])

    if isinstance(admin_groups, str):
        admin_groups = admin_groups.split(',')
    if isinstance(admin_users, str):
        admin_users = admin_users.split(',')

    return (any(group in admin_groups for group in groups) or
            user.get('username') in admin_users)


def login_required(f):
    """Decorator to require session authentication (web routes)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('web.login'))
        return f(*args, **kwargs)
    return decorated_function


def api_key_required(permission='read'):
    """Decorator to require API key authentication"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')

            if not auth_header.startswith('Bearer '):
                return jsonify({
                    'error': 'Missing or invalid Authorization header',
                    'detail': 'Use: Authorization: Bearer <api_key>'
                }), 401

            raw_key = auth_header[7:]  # Strip 'Bearer '
            db = current_app.config['db']

            # Validate key
            key_info = db.validate_api_key(raw_key)
            if not key_info:
                return jsonify({'error': 'Invalid or revoked API key'}), 401

            # Check rate limit
            allowed, remaining = db.check_rate_limit(
                raw_key,
                limit=current_app.config.get('API_RATE_LIMIT', 100)
            )
            if not allowed:
                return jsonify({'error': 'Rate limit exceeded'}), 429

            # Check permission
            import json
            permissions = json.loads(key_info['permissions']) if isinstance(key_info['permissions'], str) else key_info['permissions']

            if permission == 'admin' and 'admin' not in permissions:
                return jsonify({'error': 'Insufficient permissions (admin required)'}), 403
            elif permission == 'write' and not any(p in permissions for p in ['write', 'admin']):
                return jsonify({'error': 'Insufficient permissions (write required)'}), 403
            elif permission == 'read' and not any(p in permissions for p in ['read', 'write', 'admin']):
                return jsonify({'error': 'Insufficient permissions (read required)'}), 403

            # Attach key info to request
            request.api_key = key_info
            request.api_key_permissions = permissions
            request.rate_limit_remaining = remaining

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def api_key_or_session(permission='read'):
    """Decorator that accepts either API key or session authentication"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')

            if auth_header.startswith('Bearer '):
                # Try API key auth
                return api_key_required(permission)(f)(*args, **kwargs)
            elif 'user' in session:
                # Use session auth
                request.api_key = None
                request.api_key_permissions = ['read', 'write', 'admin'] if is_admin() else ['read', 'write']
                request.rate_limit_remaining = -1
                return f(*args, **kwargs)
            else:
                return jsonify({'error': 'Authentication required'}), 401

        return decorated_function
    return decorator


def kiosk_required(f):
    """Decorator to require kiosk session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('kiosk_authenticated'):
            return redirect(url_for('web.kiosk_login'))
        return f(*args, **kwargs)
    return decorated_function
