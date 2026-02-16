"""
CUPS utility functions for Print Queue Manager
"""
import cups
import os
import tempfile
from datetime import datetime


PRINTER_NAME = os.environ.get('PRINTER_NAME', 'HP_Smart_Tank_515')


def get_cups_connection():
    """Get CUPS connection"""
    return cups.Connection()


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


def get_printer_state_text(state):
    """Convert printer state to text"""
    states = {
        3: 'Idle',
        4: 'Processing',
        5: 'Stopped'
    }
    return states.get(state, 'Unknown')


def get_user_jobs(username=None, db=None):
    """Get all print jobs, optionally filtered by username.
    If db is provided, overlays real username from app database.
    """
    try:
        conn = get_cups_connection()
        jobs = conn.getJobs(which_jobs='not-completed')

        job_list = []
        for job_id, job_info in jobs.items():
            # Enrich with full attributes (getJobs may return limited data)
            try:
                full_attrs = conn.getJobAttributes(job_id)
                job_info.update(full_attrs)
            except Exception:
                pass

            # Fallback: if pycups didn't return key fields, use command-line tools
            if 'job-originating-user-name' not in job_info or 'job-name' not in job_info:
                try:
                    import subprocess
                    # Try multiple commands to find job info
                    for cmd in [
                        ['lpstat', '-o', '-l'],
                        ['lpstat', '-W', 'all', '-l'],
                        ['lpq', '-l', '-P', PRINTER_NAME],
                    ]:
                        result = subprocess.run(
                            cmd, capture_output=True, text=True, timeout=5
                        )
                        print(f"[LPSTAT DEBUG] cmd={' '.join(cmd)}, output={result.stdout[:300]}")
                        if result.stdout.strip():
                            # Parse for this job
                            for line in result.stdout.split('\n'):
                                if f'-{job_id} ' in line and not line.startswith(' '):
                                    parts = line.split()
                                    print(f"[LPSTAT DEBUG] Matched job #{job_id}: parts={parts}")
                                    if len(parts) >= 2:
                                        if 'job-originating-user-name' not in job_info:
                                            job_info['job-originating-user-name'] = parts[1]
                                        if 'job-name' not in job_info:
                                            job_info['job-name'] = f'Job #{job_id}'
                                # lpq format: "username: Nth  [job N localhost]"
                                elif f'job {job_id}' in line.lower():
                                    parts = line.split(':')
                                    if len(parts) >= 1 and parts[0].strip():
                                        user = parts[0].strip()
                                        print(f"[LPSTAT DEBUG] lpq matched job #{job_id}: user={user}")
                                        if 'job-originating-user-name' not in job_info:
                                            job_info['job-originating-user-name'] = user
                                        if 'job-name' not in job_info:
                                            job_info['job-name'] = f'Job #{job_id}'
                            if 'job-originating-user-name' in job_info:
                                break  # Found it, stop trying commands
                except Exception as e:
                    print(f"[LPSTAT DEBUG] Fallback failed: {e}")

            # Get real username from app database if available
            display_user = job_info.get('job-originating-user-name', 'Unknown')
            submitted_via = 'ipp'
            if db:
                try:
                    meta = db.get_job_meta(job_id)
                    if meta:
                        submitted_via = meta.get('submitted_via', 'ipp')
                        if meta.get('submitted_by'):
                            display_user = meta['submitted_by']
                        elif submitted_via == 'email':
                            display_user = 'Email (unclaimed)'
                        elif submitted_via == 'web':
                            display_user = 'Web (unclaimed)'
                except Exception:
                    pass

            if username and display_user != username:
                # Also check CUPS username for backward compat
                cups_user = job_info.get('job-originating-user-name', '')
                if cups_user != username:
                    continue

            # Handle time — could be int or datetime
            time_created = job_info.get('time-at-creation', 0)
            if isinstance(time_created, (int, float)):
                time_str = datetime.fromtimestamp(time_created).strftime('%Y-%m-%d %H:%M:%S') if time_created > 0 else 'Unknown'
            else:
                time_str = str(time_created)

            job_list.append({
                'id': job_id,
                'name': job_info.get('job-name', 'Untitled'),
                'user': display_user,
                'printer': job_info.get('printer-uri', '').split('/')[-1],
                'state': job_info.get('job-state', 0),
                'state_text': get_job_state_text(job_info.get('job-state', 0)),
                'pages': job_info.get('job-media-sheets-completed', job_info.get('number-of-documents', 0)),
                'time': time_str,
                'size': job_info.get('job-k-octets', 0)
            })

        return sorted(job_list, key=lambda x: x['time'], reverse=True)
    except Exception as e:
        print(f"Error getting jobs: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_all_jobs(db=None):
    """Get all jobs without filtering"""
    return get_user_jobs(username=None, db=db)


def release_job(job_id, username=None, is_admin=False):
    """Release a held job to start printing"""
    try:
        conn = get_cups_connection()
        jobs = conn.getJobs()

        if job_id not in jobs:
            return False, 'Job not found', 404

        if username and not is_admin:
            job_user = jobs[job_id].get('job-originating-user-name')
            if job_user != username:
                return False, 'Permission denied', 403

        conn.setJobHoldUntil(job_id, 'no-hold')
        return True, 'Job released', 200
    except Exception as e:
        return False, str(e), 500


def cancel_job(job_id, username=None, is_admin=False):
    """Cancel a job"""
    try:
        conn = get_cups_connection()
        jobs = conn.getJobs()

        if job_id not in jobs:
            return False, 'Job not found', 404

        if username and not is_admin:
            job_user = jobs[job_id].get('job-originating-user-name')
            if job_user != username:
                return False, 'Permission denied', 403

        conn.cancelJob(job_id)
        return True, 'Job canceled', 200
    except Exception as e:
        return False, str(e), 500


def get_printer_status(printer_name=None):
    """Get printer status"""
    if printer_name is None:
        printer_name = PRINTER_NAME
    try:
        conn = get_cups_connection()
        printers = conn.getPrinters()

        if printer_name in printers:
            printer = printers[printer_name]
            return {
                'name': printer_name,
                'state': printer.get('printer-state', 0),
                'state_text': get_printer_state_text(printer.get('printer-state', 0)),
                'state_message': printer.get('printer-state-message', ''),
                'accepting': printer.get('printer-is-accepting-jobs', False)
            }
        return {'error': f'Printer {printer_name} not found'}
    except Exception as e:
        return {'error': str(e)}


def list_printers():
    """List all available printers"""
    try:
        conn = get_cups_connection()
        printers = conn.getPrinters()
        result = []
        for name, info in printers.items():
            result.append({
                'name': name,
                'state': info.get('printer-state', 0),
                'state_text': get_printer_state_text(info.get('printer-state', 0)),
                'accepting': info.get('printer-is-accepting-jobs', False),
                'shared': info.get('printer-is-shared', False),
                'info': info.get('printer-info', ''),
                'location': info.get('printer-location', '')
            })
        return result
    except Exception as e:
        return []


def submit_print_job(file_path, title='Untitled', printer_name=None, options=None, requesting_user=None):
    """Submit a file to CUPS as a held print job.
    requesting_user is stored in app DB, not in CUPS (requires root).
    """
    if printer_name is None:
        printer_name = PRINTER_NAME
    if options is None:
        options = {}

    # Always hold the job
    options['job-hold-until'] = 'indefinite'

    try:
        conn = get_cups_connection()
        job_id = conn.printFile(printer_name, file_path, title, options)
        return True, job_id
    except Exception as e:
        return False, str(e)


def get_job_info(job_id):
    """Get detailed info about a specific job"""
    try:
        conn = get_cups_connection()
        jobs = conn.getJobs(which_jobs='all')

        if job_id not in jobs:
            return None

        job_info = jobs[job_id]
        return {
            'id': job_id,
            'name': job_info.get('job-name', 'Untitled'),
            'user': job_info.get('job-originating-user-name', 'Unknown'),
            'printer': job_info.get('printer-uri', '').split('/')[-1],
            'state': job_info.get('job-state', 0),
            'state_text': get_job_state_text(job_info.get('job-state', 0)),
            'pages': job_info.get('job-media-sheets-completed', 0),
            'time': datetime.fromtimestamp(
                job_info.get('time-at-creation', 0)
            ).strftime('%Y-%m-%d %H:%M:%S'),
            'size': job_info.get('job-k-octets', 0)
        }
    except Exception as e:
        return None
