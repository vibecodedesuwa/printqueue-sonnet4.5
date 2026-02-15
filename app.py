#!/usr/bin/env python3
"""
Print Queue Manager with Authentik SSO Integration
For consumer printers like HP Smart Tank 515
"""

from flask import Flask, render_template, redirect, url_for, session, request, jsonify, flash
from authlib.integrations.flask_client import OAuth
from functools import wraps
import cups
import os
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-in-production-please')

# Authentik OAuth Configuration
oauth = OAuth(app)
authentik = oauth.register(
    name='authentik',
    client_id=os.environ.get('AUTHENTIK_CLIENT_ID'),
    client_secret=os.environ.get('AUTHENTIK_CLIENT_SECRET'),
    server_metadata_url=os.environ.get('AUTHENTIK_METADATA_URL'),
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# CUPS Configuration
PRINTER_NAME = os.environ.get('PRINTER_NAME', 'HP_Smart_Tank_515')

def login_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_cups_connection():
    """Get CUPS connection"""
    return cups.Connection()

def get_user_jobs(username=None):
    """Get all print jobs, optionally filtered by username"""
    try:
        conn = get_cups_connection()
        jobs = conn.getJobs(which_jobs='not-completed')
        
        job_list = []
        for job_id, job_info in jobs.items():
            # Filter by username if provided
            if username and job_info.get('job-originating-user-name') != username:
                continue
                
            job_list.append({
                'id': job_id,
                'name': job_info.get('job-name', 'Untitled'),
                'user': job_info.get('job-originating-user-name', 'Unknown'),
                'printer': job_info.get('printer-uri', '').split('/')[-1],
                'state': job_info.get('job-state', 0),
                'state_text': get_job_state_text(job_info.get('job-state', 0)),
                'pages': job_info.get('job-media-sheets-completed', 0),
                'time': datetime.fromtimestamp(job_info.get('time-at-creation', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                'size': job_info.get('job-k-octets', 0)
            })
        
        return sorted(job_list, key=lambda x: x['time'], reverse=True)
    except Exception as e:
        print(f"Error getting jobs: {e}")
        return []

def get_job_state_text(state):
    """Convert job state number to text"""
    states = {
        3: 'Pending',
        4: 'Held',
        5: 'Processing',
        6: 'Stopped',
        7: 'Canceled',
        8: 'Aborted',
        9: 'Completed'
    }
    return states.get(state, 'Unknown')

@app.route('/')
def index():
    """Home page - redirect to dashboard or login"""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login')
def login():
    """Initiate Authentik OAuth login"""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    
    redirect_uri = url_for('authorize', _external=True)
    return authentik.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    """OAuth callback"""
    try:
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
            return redirect(url_for('dashboard'))
        else:
            flash('Failed to get user information', 'error')
            return redirect(url_for('login'))
    except Exception as e:
        flash(f'Authentication error: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.pop('user', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard showing user's print jobs"""
    username = session['user']['username']
    jobs = get_user_jobs(username)
    
    return render_template('dashboard.html', 
                         user=session['user'], 
                         jobs=jobs,
                         is_admin=is_admin())

@app.route('/admin')
@login_required
def admin():
    """Admin view showing all print jobs"""
    if not is_admin():
        flash('Access denied - Admin privileges required', 'error')
        return redirect(url_for('dashboard'))
    
    jobs = get_user_jobs()  # Get all jobs
    
    return render_template('admin.html', 
                         user=session['user'], 
                         jobs=jobs)

def is_admin():
    """Check if current user is admin"""
    # Check if user has admin group or specific username
    # Customize this based on your Authentik groups
    user = session.get('user', {})
    groups = user.get('groups', [])
    
    # Check for admin group or specific admin usernames
    admin_groups = os.environ.get('ADMIN_GROUPS', 'admins,print-admins').split(',')
    admin_users = os.environ.get('ADMIN_USERS', 'admin').split(',')
    
    return (any(group in admin_groups for group in groups) or 
            user.get('username') in admin_users)

@app.route('/api/jobs')
@login_required
def api_jobs():
    """API endpoint to get jobs"""
    if is_admin() and request.args.get('all') == 'true':
        jobs = get_user_jobs()
    else:
        username = session['user']['username']
        jobs = get_user_jobs(username)
    
    return jsonify(jobs)

@app.route('/api/job/<int:job_id>/release', methods=['POST'])
@login_required
def release_job(job_id):
    """Release a held job to start printing"""
    try:
        conn = get_cups_connection()
        jobs = conn.getJobs()
        
        if job_id not in jobs:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        job_user = jobs[job_id].get('job-originating-user-name')
        current_user = session['user']['username']
        
        # Allow job owner or admin to release
        if job_user != current_user and not is_admin():
            return jsonify({'success': False, 'error': 'Permission denied'}), 403
        
        # Release the job
        conn.setJobHoldUntil(job_id, 'no-hold')
        
        return jsonify({'success': True, 'message': 'Job released'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/job/<int:job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    """Cancel a job"""
    try:
        conn = get_cups_connection()
        jobs = conn.getJobs()
        
        if job_id not in jobs:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        job_user = jobs[job_id].get('job-originating-user-name')
        current_user = session['user']['username']
        
        # Allow job owner or admin to cancel
        if job_user != current_user and not is_admin():
            return jsonify({'success': False, 'error': 'Permission denied'}), 403
        
        # Cancel the job
        conn.cancelJob(job_id)
        
        return jsonify({'success': True, 'message': 'Job canceled'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/printer/status')
@login_required
def printer_status():
    """Get printer status"""
    try:
        conn = get_cups_connection()
        printers = conn.getPrinters()
        
        printer_info = {}
        if PRINTER_NAME in printers:
            printer = printers[PRINTER_NAME]
            printer_info = {
                'name': PRINTER_NAME,
                'state': printer.get('printer-state', 0),
                'state_text': get_printer_state_text(printer.get('printer-state', 0)),
                'state_message': printer.get('printer-state-message', ''),
                'accepting': printer.get('printer-is-accepting-jobs', False)
            }
        
        return jsonify(printer_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_printer_state_text(state):
    """Convert printer state to text"""
    states = {
        3: 'Idle',
        4: 'Processing',
        5: 'Stopped'
    }
    return states.get(state, 'Unknown')

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'print-queue-manager'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
