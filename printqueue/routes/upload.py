"""
File upload routes for Print Queue Manager
Handles web-based file upload and print submission.
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app, session
from werkzeug.utils import secure_filename
import os

from ..auth import login_required, is_admin
from ..cups_utils import submit_print_job

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
@login_required
def upload_file():
    """Handle file upload and submit to CUPS"""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('upload.upload_page'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('upload.upload_page'))

    if not allowed_file(file.filename):
        allowed = ', '.join(current_app.config['ALLOWED_EXTENSIONS'])
        flash(f'File type not allowed. Accepted: {allowed}', 'error')
        return redirect(url_for('upload.upload_page'))

    # Save uploaded file
    filename = secure_filename(file.filename)
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
    if request.form.get('duplex') == 'on':
        options['sides'] = 'two-sided-long-edge'
    if request.form.get('color') == 'bw':
        options['ColorModel'] = 'Gray'
    page_range = request.form.get('page_range', '').strip()
    if page_range:
        options['page-ranges'] = page_range

    # Submit to CUPS
    printer_name = current_app.config['PRINTER_NAME']
    success, result = submit_print_job(converted_path, filename, printer_name, options)

    if success:
        db = current_app.config['db']
        username = session['user']['username']
        db.create_job_meta(result, submitted_via='web', original_filename=filename, submitted_by=username)
        flash(f'✅ Job #{result} submitted! It will print once approved.', 'success')
    else:
        flash(f'❌ Error submitting print job: {result}', 'error')

    return redirect(url_for('web.dashboard'))
