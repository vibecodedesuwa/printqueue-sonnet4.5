"""
File upload routes for Print Queue Manager
Handles web-based file upload and print submission.
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app, session
import os

from ..auth import login_required, is_admin
from ..cups_utils import get_printer_status, submit_print_job
from ..filenames import clean_display_filename, unique_storage_filename

upload_bp = Blueprint('upload', __name__)


def allowed_file(filename):
    """Check if file extension is allowed"""
    allowed = current_app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


@upload_bp.route('/upload')
@login_required
def upload_page():
    """Render the upload page"""
    return render_template('upload.html',
                           user=session['user'],
                           is_admin=is_admin())


@upload_bp.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and submit to CUPS. Supports both session auth and QR quick upload."""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('upload.upload_page') if 'user' in session else url_for('web.qr_upload_page'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('upload.upload_page') if 'user' in session else url_for('web.qr_upload_page'))

    if not allowed_file(file.filename):
        allowed = ', '.join(current_app.config['ALLOWED_EXTENSIONS'])
        flash(f'File type not allowed. Accepted: {allowed}', 'error')
        return redirect(url_for('upload.upload_page') if 'user' in session else url_for('web.qr_upload_page'))

    # Save uploaded file
    original_filename = clean_display_filename(file.filename)
    filename = unique_storage_filename(original_filename)
    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    # Convert if needed
    from ..services.file_converter import convert_if_needed
    converted_path = convert_if_needed(filepath)

    # Build print options
    options = {}
    copies = request.form.get('copies', '1')
    if copies.isdigit() and int(copies) > 0:
        options['copies'] = copies
    if request.form.get('duplex') in ['on', 'true']:
        options['sides'] = 'two-sided-long-edge'
    if request.form.get('color') == 'bw':
        options['ColorModel'] = 'Gray'
    page_range = request.form.get('page_range', '').strip()
    if page_range:
        options['page-ranges'] = page_range

    # Submit to CUPS
    printer_name = current_app.config['PRINTER_NAME']
    username = session.get('user', {}).get('username')
    submission_source = request.form.get('submission_source', '')
    is_qr_submission = submission_source in {'qr_file_upload', 'qr_a4_editor'}
    auto_print_requested = is_qr_submission and current_app.config.get('AUTO_PRINT_QR_UPLOADS', True)
    printer_status = get_printer_status(printer_name)
    auto_print = auto_print_requested and printer_status.get('safe_to_release', False)
    held_for_printer = auto_print_requested and not auto_print
    success, result = submit_print_job(
        converted_path,
        original_filename,
        printer_name,
        options,
        requesting_user=username,
        hold=not auto_print,
    )

    if success:
        db = current_app.config['db']
        if submission_source == 'qr_a4_editor':
            submitted_via = 'qr_a4'
        elif submission_source == 'qr_file_upload':
            submitted_via = 'qr_mobile'
        else:
            submitted_via = 'web'
        db.create_job_meta(result, submitted_via=submitted_via, original_filename=original_filename, submitted_by=username)
        if username:
            message = (
                f'✅ Job #{result} sent directly to the printer.' if auto_print
                else f'⚠️ Job #{result} is held safely until the printer reconnects.' if held_for_printer
                else f'✅ Job #{result} submitted! It will print once approved.'
            )
            flash(message, 'success')
            return redirect(url_for('web.dashboard'))
        else:
            message = (
                f'✅ Guest job #{result} sent directly to the printer.' if auto_print
                else f'⚠️ Guest job #{result} is held safely until the printer reconnects.' if held_for_printer
                else f'✅ Job #{result} submitted to unclaimed pool! Please claim it on the dashboard or kiosk.'
            )
            flash(message, 'success')
            return redirect(url_for('web.qr_upload_page'))
    else:
        flash(f'❌ Error submitting print job: {result}', 'error')
        return redirect(url_for('upload.upload_page') if 'user' in session else url_for('web.qr_upload_page'))
