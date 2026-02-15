"""
File converter service for Print Queue Manager
Handles conversion of uploaded documents to print-ready formats.
"""
import os
import subprocess
import shutil


CONVERTIBLE_TYPES = {
    'docx': 'pdf',
    'doc': 'pdf',
    'txt': 'pdf',
}

DIRECT_PRINT_TYPES = {'pdf', 'png', 'jpg', 'jpeg'}


def convert_if_needed(filepath):
    """Convert file to print-ready format if necessary. Returns path to printable file."""
    ext = filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else ''

    if ext in DIRECT_PRINT_TYPES:
        return filepath

    if ext in CONVERTIBLE_TYPES:
        target_format = CONVERTIBLE_TYPES[ext]
        return convert_to_pdf(filepath)

    # Unknown type — try to print as-is
    return filepath


def convert_to_pdf(filepath):
    """Convert document to PDF using LibreOffice headless"""
    try:
        output_dir = os.path.dirname(filepath)

        # Use LibreOffice to convert
        result = subprocess.run([
            'libreoffice', '--headless', '--convert-to', 'pdf',
            '--outdir', output_dir, filepath
        ], capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            # Compute expected output path
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

            if os.path.exists(pdf_path):
                return pdf_path

        # If conversion failed, return original file
        print(f"LibreOffice conversion failed: {result.stderr}")
        return filepath

    except FileNotFoundError:
        print("LibreOffice not installed — skipping conversion")
        return filepath
    except subprocess.TimeoutExpired:
        print("LibreOffice conversion timed out")
        return filepath
    except Exception as e:
        print(f"Conversion error: {e}")
        return filepath


def validate_file(filepath, max_size_mb=50):
    """Validate file type and size"""
    errors = []

    # Check file exists
    if not os.path.exists(filepath):
        return False, ['File not found']

    # Check size
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    if size_mb > max_size_mb:
        errors.append(f'File too large ({size_mb:.1f}MB, max {max_size_mb}MB)')

    # Check extension
    ext = filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else ''
    all_allowed = DIRECT_PRINT_TYPES | set(CONVERTIBLE_TYPES.keys())
    if ext not in all_allowed:
        errors.append(f'File type .{ext} not supported')

    return len(errors) == 0, errors


def get_safe_filename(filename):
    """Sanitize a filename for safe storage"""
    from werkzeug.utils import secure_filename
    return secure_filename(filename)
