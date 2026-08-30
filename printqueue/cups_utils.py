"""
CUPS utility functions for Print Queue Manager
"""
import cups
import logging
import os
import subprocess
import re
import shutil
from datetime import datetime

from .identity import usernames_match


PRINTER_NAME = os.environ.get('PRINTER_NAME', 'HP_Smart_Tank_515')
LDAP_DOMAIN = os.environ.get('LDAP_DOMAIN', '')
logger = logging.getLogger(__name__)


def _system_command(name):
    """Resolve a system utility even when systemd supplies a venv-only PATH."""
    resolved = shutil.which(name)
    if resolved:
        return resolved
    for directory in ('/usr/local/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin'):
        candidate = f'{directory}/{name}'
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return name


def get_cups_connection():
    """Get a CUPS connection, optionally using configured service credentials."""
    server = os.environ.get('CUPS_SERVER', '').strip()
    user = os.environ.get('CUPS_USER', '').strip()
    password = os.environ.get('CUPS_PASSWORD', '')

    if user:
        cups.setUser(user)
    if password:
        # pycups invokes this callback only if the server requests credentials.
        cups.setPasswordCB(lambda _prompt: password)

    if server:
        host, separator, port = server.rpartition(':')
        if separator and port.isdigit():
            return cups.Connection(host=host, port=int(port))
        return cups.Connection(host=server)
    return cups.Connection()


def _same_user(left, right):
    return usernames_match(left, right, domain=LDAP_DOMAIN)


def _configured_printer_name():
    """Prefer the active Flask configuration, with an environment fallback."""
    try:
        from flask import current_app, has_app_context
        if has_app_context():
            return current_app.config.get('PRINTER_NAME', PRINTER_NAME)
    except ImportError:
        pass
    return PRINTER_NAME


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


def _as_reason_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(',') if item.strip() and item.strip() != 'none']
    return [str(item).strip() for item in value if str(item).strip() and str(item).strip() != 'none']


def _printer_status_payload(printer_name, printer):
    """Translate raw CUPS attributes into an actionable connectivity state."""
    state = printer.get('printer-state', 0)
    message = str(printer.get('printer-state-message', '') or '').strip()
    reasons = _as_reason_list(printer.get('printer-state-reasons'))
    device_uri = str(printer.get('device-uri', '') or '')
    is_usb = device_uri.startswith(('hp:/usb/', 'usb:'))
    searchable = f"{message} {' '.join(reasons)}".casefold()
    disconnect_markers = (
        'unable to open device', 'device unavailable', 'device not found',
        'not connected', 'offline-report', 'backend-failed', 'no such device',
    )
    disconnected = any(marker in searchable for marker in disconnect_markers)
    unavailable = disconnected or state == 5

    if disconnected and is_usb:
        status_code = 'usb_disconnected'
        display_message = 'USB printer disconnected — jobs will remain held'
    elif disconnected:
        status_code = 'printer_disconnected'
        display_message = 'Printer connection lost — jobs will remain held'
    elif state == 5:
        status_code = 'printer_stopped'
        display_message = message or 'Printer stopped — jobs will remain held'
    elif state == 4:
        status_code = 'printer_busy'
        display_message = message or 'Printing in progress'
    else:
        status_code = 'printer_ready'
        display_message = message or 'Printer ready and accepting jobs'

    return {
        'name': printer_name,
        'state': state,
        'state_text': get_printer_state_text(state),
        'state_message': message,
        'state_reasons': reasons,
        'device_uri': device_uri,
        'transport': 'usb' if is_usb else 'other',
        'accepting': printer.get('printer-is-accepting-jobs', False),
        'connected': not disconnected,
        'safe_to_release': not unavailable,
        'status_code': status_code,
        'display_message': display_message,
        'jobs_safe': True,
    }


def _usable_job_name(value, job_id=None):
    """Return a meaningful document name, rejecting common CUPS placeholders."""
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    # Samba names temporary spool files smbprn.NNNNNNNN. Some clients append
    # the real document title, so discard the transport prefix but keep that
    # useful suffix.
    value = re.sub(r'^smbprn\.\d+\s*', '', value, flags=re.IGNORECASE).strip()
    if not value:
        return None
    normalized = value.casefold()
    generic = {
        'untitled', 'unknown', 'stdin', '(stdin)', 'print job', 'print_job',
        'document', 'remote downlevel document',
    }
    if normalized in generic or (job_id is not None and normalized == f'job #{job_id}'.casefold()):
        return None
    return value


def _spool_document_title(job_id):
    """Recover a Windows title embedded in a local PostScript/PJL spool."""
    spool_root = os.environ.get('CUPS_SPOOL_DIR', '/var/spool/cups')
    path = os.path.join(spool_root, f'd{int(job_id):05d}-001')
    try:
        with open(path, 'rb') as spool_file:
            header = spool_file.read(256 * 1024).decode('latin-1', errors='ignore')
    except (OSError, TypeError, ValueError):
        return None

    patterns = (
        r'(?im)^%%Title:\s*(?:\((.*?)\)|(.*?))\s*$',
        r'(?im)^@PJL\s+JOB\s+NAME\s*=\s*"([^"]+)"',
    )
    for pattern in patterns:
        match = re.search(pattern, header)
        if match:
            for candidate in match.groups():
                title = _usable_job_name(candidate, job_id)
                if title:
                    return title
    return None


def _cups_job_name(job_info, job_id=None):
    """Use all known IPP attributes because clients do not consistently set job-name."""
    for key in ('job-name', 'document-name-supplied', 'document-name'):
        value = _usable_job_name(job_info.get(key), job_id)
        if value:
            return value
    return None


def _usable_job_owner(value):
    """Return a real CUPS owner, rejecting privacy/redaction placeholders."""
    if value is None:
        return None
    owner = str(value).strip()
    if not owner or owner.casefold() in {
        'withheld', 'unknown', 'anonymous', 'none', 'not supplied',
    }:
        return None
    return owner


def _parse_lpstat_jobs(output):
    """Parse destination/job/owner rows emitted by ``lpstat -o``."""
    jobs = {}
    for line in (output or '').splitlines():
        if not line or line[0].isspace():
            continue
        match = re.match(r'^(\S+)-(\d+)\s+(\S+)\s+(\d+)(?:\s+.*)?$', line)
        if not match:
            continue
        destination, job_id, owner, size = match.groups()
        jobs[int(job_id)] = {
            'job-originating-user-name': owner,
            'printer-uri': f'ipp://localhost/printers/{destination}',
            'job-k-octets': (int(size) + 1023) // 1024,
        }
    return jobs


def _get_lpstat_jobs(which_jobs='not-completed'):
    """Read jobs from the scheduler CLI, including CUPS class destinations."""
    try:
        result = subprocess.run(
            [_system_command('lpstat'), '-W', which_jobs, '-o', '-l'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return _parse_lpstat_jobs(result.stdout)
    except Exception as exc:
        logger.debug("lpstat job discovery failed: %s", exc)
        return {}


def _get_connection_jobs(conn, which_jobs='not-completed'):
    """Return pycups jobs merged with destinations only visible to lpstat."""
    jobs = dict(conn.getJobs(which_jobs=which_jobs))
    lpstat_jobs = _get_lpstat_jobs(which_jobs)
    for job_id, cli_info in lpstat_jobs.items():
        jobs.setdefault(job_id, {}).update({
            key: value for key, value in cli_info.items()
            if key not in jobs.get(job_id, {})
        })
    return jobs, lpstat_jobs


def _destination_has_authenticated_owner(printer_name, submitted_via):
    """Return whether the destination authenticates the reported job owner."""
    if submitted_via != 'ipp':
        return False
    printer_name = str(printer_name or '')
    source_queue = _configured_printer_name()
    windows_queue = os.environ.get(
        'SAMBA_WINDOWS_QUEUE', f'{source_queue}_windows'
    ).strip() or f'{source_queue}_windows'
    ldap_enabled = os.environ.get('LDAP_ENABLED', 'false').lower() == 'true'
    samba_enabled = os.environ.get('SAMBA_ENABLED', 'false').lower() == 'true'
    return (
        (ldap_enabled and printer_name == source_queue)
        or (samba_enabled and printer_name == windows_queue)
    )


def _job_is_claimable(db, meta, cups_owner, printer_name, submitted_via):
    """Return whether a job belongs in the shared claim pool."""
    mapped_user = None
    if db:
        try:
            mapped_user = db.get_device_mapping(cups_owner or '')
        except Exception:
            pass
    claimed_user = meta.get('claimed_by') if meta else None
    submitted_by = meta.get('submitted_by') if meta else None
    if any((mapped_user, claimed_user, submitted_by)):
        return False
    return not _destination_has_authenticated_owner(printer_name, submitted_via)


def get_user_jobs(username=None, db=None):
    """Get all print jobs, optionally filtered by username.
    If db is provided, overlays real username from app database.
    """
    try:
        conn = get_cups_connection()
        # pycups can omit jobs submitted to a CUPS class, notably the dedicated
        # Samba/Windows destination. Merge the scheduler's own view so those
        # jobs remain visible on the dashboard and kiosk.
        jobs, lpstat_jobs = _get_connection_jobs(conn)

        job_list = []
        for job_id, job_info in jobs.items():
            # Enrich with full attributes (getJobs may return limited data)
            try:
                full_attrs = conn.getJobAttributes(job_id)
                job_info.update(full_attrs)
            except Exception:
                pass

            # CUPS privacy defaults return the literal value "Withheld" to
            # unauthenticated readers. Prefer the owner reported locally by
            # lpstat so matching AirPrint and Samba identities auto-bind.
            if not _usable_job_owner(job_info.get('job-originating-user-name')):
                cli_owner = _usable_job_owner(
                    lpstat_jobs.get(job_id, {}).get('job-originating-user-name')
                )
                if cli_owner:
                    job_info['job-originating-user-name'] = cli_owner

            # Fallback: if pycups didn't return key fields, use command-line tools
            if not _usable_job_owner(job_info.get('job-originating-user-name')) or not _cups_job_name(job_info, job_id):
                try:
                    # Try multiple commands to find job info
                    for cmd in [
                        [_system_command('lpstat'), '-o', '-l'],
                        [_system_command('lpstat'), '-W', 'all', '-l'],
                        [_system_command('lpq'), '-l', '-P', _configured_printer_name()],
                    ]:
                        result = subprocess.run(
                            cmd, capture_output=True, text=True, timeout=5
                        )
                        if result.stdout.strip():
                            # Parse for this job
                            lines = result.stdout.split('\n')
                            for index, line in enumerate(lines):
                                if f'-{job_id} ' in line and not line.startswith(' '):
                                    parts = line.split()
                                    if len(parts) >= 2:
                                        if not _usable_job_owner(job_info.get('job-originating-user-name')):
                                            job_info['job-originating-user-name'] = parts[1]
                                # lpq format: "username: Nth  [job N localhost]"
                                elif f'job {job_id}' in line.lower():
                                    parts = line.split(':')
                                    if len(parts) >= 1 and parts[0].strip():
                                        user = parts[0].strip()
                                        if not _usable_job_owner(job_info.get('job-originating-user-name')):
                                            job_info['job-originating-user-name'] = user
                                        if not _cups_job_name(job_info, job_id):
                                            for detail in lines[index + 1:]:
                                                if not detail.strip():
                                                    continue
                                                candidate = re.sub(r'\s+\d+\s+bytes\s*$', '', detail.strip(), flags=re.IGNORECASE)
                                                if _usable_job_name(candidate, job_id):
                                                    job_info['job-name'] = candidate
                                                break
                            if _usable_job_owner(job_info.get('job-originating-user-name')):
                                break  # Found it, stop trying commands
                except Exception as exc:
                    logger.debug("CUPS CLI fallback failed: %s", exc)

            # Get real username from app database if available
            display_user = _usable_job_owner(job_info.get('job-originating-user-name')) or 'Unknown'
            submitted_via = 'ipp'
            meta = None
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

            cups_name = _cups_job_name(job_info, job_id) or _spool_document_title(job_id)
            metadata_name = _usable_job_name(meta.get('original_filename'), job_id) if meta else None
            display_name = metadata_name or cups_name or f'Document #{job_id}'

            printer_name = job_info.get('printer-uri', '').split('/')[-1]
            claimable = _job_is_claimable(
                db,
                meta,
                _usable_job_owner(job_info.get('job-originating-user-name')),
                printer_name,
                submitted_via,
            )

            # Preserve a good CUPS-supplied name locally. Later CUPS queries may omit it.
            if db and cups_name and not metadata_name:
                try:
                    db.create_job_meta(
                        job_id,
                        submitted_via=submitted_via,
                        original_filename=cups_name,
                        submitted_by=meta.get('submitted_by') if meta else None,
                    )
                except Exception:
                    logger.debug("Could not persist filename for CUPS job %s", job_id, exc_info=True)

            if username and not _same_user(display_user, username):
                # Also check CUPS username for backward compat
                cups_user = job_info.get('job-originating-user-name', '')
                if not _same_user(cups_user, username):
                    continue

            # Handle time — could be int or datetime
            time_created = job_info.get('time-at-creation', 0)
            if isinstance(time_created, (int, float)):
                time_str = datetime.fromtimestamp(time_created).strftime('%Y-%m-%d %H:%M:%S') if time_created > 0 else 'Unknown'
            else:
                time_str = str(time_created)

            job_list.append({
                'id': job_id,
                'name': display_name,
                'original_filename': metadata_name or cups_name,
                'user': display_user,
                'printer': printer_name,
                'state': job_info.get('job-state', 0),
                'state_text': get_job_state_text(job_info.get('job-state', 0)),
                'pages': job_info.get('job-media-sheets-completed', job_info.get('number-of-documents', 0)),
                'time': time_str,
                'size': job_info.get('job-k-octets', 0),
                'claimable': claimable,
            })

        return sorted(job_list, key=lambda x: x['time'], reverse=True)
    except Exception:
        logger.exception("Error getting CUPS jobs")
        return []


def get_all_jobs(db=None):
    """Get all jobs without filtering"""
    return get_user_jobs(username=None, db=db)


def _get_job_owner(conn, job_id, jobs_dict):
    """Get the originating username for a CUPS job, with lpstat fallback."""
    # Try pycups first
    try:
        attrs = conn.getJobAttributes(job_id)
        owner = _usable_job_owner(attrs.get('job-originating-user-name', ''))
        if owner:
            return owner
    except Exception:
        pass

    owner = _usable_job_owner(
        jobs_dict.get(job_id, {}).get('job-originating-user-name', '')
    )
    if owner:
        return owner

    # Fallback: parse lpstat output (same as get_user_jobs)
    try:
        owner = _usable_job_owner(
            _get_lpstat_jobs().get(job_id, {}).get('job-originating-user-name')
        )
        if owner:
            return owner
    except Exception as exc:
        logger.debug("lpstat owner fallback failed: %s", exc)

    return ''


def release_job(job_id, username=None, is_admin=False):
    """Release a held job to start printing"""
    try:
        conn = get_cups_connection()
        jobs, _lpstat_jobs = _get_connection_jobs(conn)

        if job_id not in jobs:
            return False, 'Job not found', 404

        if username and not is_admin:
            job_user = _get_job_owner(conn, job_id, jobs)
            from flask import current_app
            db = current_app.config.get('db')
            
            is_authorized = False
            if _same_user(job_user, username):
                is_authorized = True
            elif db:
                mapped_user = db.get_device_mapping(job_user)
                claimed_user = db.get_claimed_owner(job_id)
                meta = db.get_job_meta(job_id)
                submitted_by = meta.get('submitted_by') if meta else None

                if any(_same_user(owner, username) for owner in (mapped_user, claimed_user, submitted_by)):
                    is_authorized = True

            if not is_authorized:
                return False, 'Permission denied', 403

        printer_status = get_printer_status()
        if not printer_status.get('safe_to_release', False):
            message = printer_status.get('display_message', 'Printer unavailable')
            return False, f'{message}. Job remains held.', 409

        conn.setJobHoldUntil(job_id, 'no-hold')
        return True, 'Job released', 200
    except Exception as e:
        return False, str(e), 500


def cancel_job(job_id, username=None, is_admin=False):
    """Cancel a job"""
    try:
        conn = get_cups_connection()
        jobs, _lpstat_jobs = _get_connection_jobs(conn)

        if job_id not in jobs:
            return False, 'Job not found', 404

        if username and not is_admin:
            job_user = _get_job_owner(conn, job_id, jobs)
            from flask import current_app
            db = current_app.config.get('db')

            is_authorized = False
            if _same_user(job_user, username):
                is_authorized = True
            elif db:
                mapped_user = db.get_device_mapping(job_user)
                claimed_user = db.get_claimed_owner(job_id)
                meta = db.get_job_meta(job_id)
                submitted_by = meta.get('submitted_by') if meta else None

                if any(_same_user(owner, username) for owner in (mapped_user, claimed_user, submitted_by)):
                    is_authorized = True

            if not is_authorized:
                return False, 'Permission denied', 403

        conn.cancelJob(job_id)
        return True, 'Job canceled', 200
    except Exception as e:
        return False, str(e), 500


def get_printer_status(printer_name=None):
    """Get printer status"""
    if printer_name is None:
        printer_name = _configured_printer_name()
    try:
        conn = get_cups_connection()
        printers = conn.getPrinters()

        if printer_name in printers:
            printer = dict(printers[printer_name])
            try:
                printer.update(conn.getPrinterAttributes(printer_name))
            except Exception:
                pass
            return _printer_status_payload(printer_name, printer)
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


def submit_print_job(file_path, title='Untitled', printer_name=None, options=None, requesting_user=None, hold=True):
    """Submit a file to CUPS, held by default unless the caller opts into direct printing.
    requesting_user is stored in app DB, not in CUPS (requires root).
    """
    if printer_name is None:
        printer_name = _configured_printer_name()
    if options is None:
        options = {}

    # Set this explicitly so a direct app submission can override the printer's
    # queue-wide indefinite hold default without changing IPP/AirPrint behavior.
    options['job-hold-until'] = 'indefinite' if hold else 'no-hold'
    # Keep document order intuitive: page 1, then 2, then 3. Callers can still
    # explicitly request reverse order when a face-up output tray needs it.
    options.setdefault('outputorder', 'normal')

    try:
        conn = get_cups_connection()
        job_id = conn.printFile(printer_name, file_path, title, options)
        return True, job_id
    except Exception as e:
        return False, str(e)


def get_job_info(job_id, db=None):
    """Get detailed info about a specific job"""
    try:
        conn = get_cups_connection()
        jobs, lpstat_jobs = _get_connection_jobs(conn, which_jobs='all')

        if job_id not in jobs:
            return None

        job_info = jobs[job_id]
        try:
            job_info.update(conn.getJobAttributes(job_id))
        except Exception:
            pass
        meta = db.get_job_meta(job_id) if db else None
        cups_name = _cups_job_name(job_info, job_id) or _spool_document_title(job_id)
        metadata_name = _usable_job_name(meta.get('original_filename'), job_id) if meta else None
        display_owner = _usable_job_owner(
            job_info.get('job-originating-user-name')
        ) or _usable_job_owner(
            lpstat_jobs.get(job_id, {}).get('job-originating-user-name')
        ) or 'Unknown'
        printer_name = job_info.get('printer-uri', '').split('/')[-1]
        submitted_via = meta.get('submitted_via', 'ipp') if meta else 'ipp'
        claimable = _job_is_claimable(
            db, meta, display_owner, printer_name, submitted_via
        )
        return {
            'id': job_id,
            'name': metadata_name or cups_name or f'Document #{job_id}',
            'original_filename': metadata_name or cups_name,
            'user': display_owner,
            'printer': printer_name,
            'state': job_info.get('job-state', 0),
            'state_text': get_job_state_text(job_info.get('job-state', 0)),
            'pages': job_info.get('job-media-sheets-completed', 0),
            'time': datetime.fromtimestamp(
                job_info.get('time-at-creation', 0)
            ).strftime('%Y-%m-%d %H:%M:%S'),
            'size': job_info.get('job-k-octets', 0),
            'claimable': claimable,
        }
    except Exception as e:
        return None
