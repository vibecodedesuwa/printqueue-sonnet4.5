"""
File converter service for Print Queue Manager
Handles conversion of uploaded documents to print-ready formats.
"""
import os
import subprocess


CONVERTIBLE_TYPES = {
    'docx': 'pdf',
    'doc': 'pdf',
    'odt': 'pdf',
    'txt': 'pdf',
}

DIRECT_PRINT_TYPES = {'pdf'}
IMAGE_TYPES = {'png', 'jpg', 'jpeg'}


def convert_if_needed(filepath):
    """Convert file to print-ready format if necessary. Returns path to printable file."""
    ext = filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else ''

    if ext in DIRECT_PRINT_TYPES:
        return filepath

    if ext in IMAGE_TYPES:
        return convert_image_to_pdf(filepath)

    if ext in CONVERTIBLE_TYPES:
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


def convert_image_to_pdf(filepath, dpi=300, margin_mm=5):
    """Place a JPEG/PNG on an A4 PDF before handing it to CUPS.

    cups-filters' direct image-to-raster path can stall in
    cfFilterImageToRaster with some HPLIP queues. A PDF also makes page size,
    orientation, EXIF rotation, and alpha handling deterministic.
    """
    try:
        from PIL import Image, ImageOps

        with Image.open(filepath) as source:
            image = ImageOps.exif_transpose(source)
            image.load()

            if image.mode in ('RGBA', 'LA') or (
                    image.mode == 'P' and 'transparency' in image.info):
                rgba = image.convert('RGBA')
                background = Image.new('RGB', rgba.size, 'white')
                background.paste(rgba, mask=rgba.getchannel('A'))
                image = background
            else:
                image = image.convert('RGB')

            portrait = image.height >= image.width
            a4_mm = (210, 297) if portrait else (297, 210)
            page_size = tuple(round(mm * dpi / 25.4) for mm in a4_mm)
            margin_px = round(margin_mm * dpi / 25.4)
            printable_size = (
                page_size[0] - (2 * margin_px),
                page_size[1] - (2 * margin_px),
            )
            image.thumbnail(printable_size, Image.Resampling.LANCZOS)

            page = Image.new('RGB', page_size, 'white')
            position = (
                (page_size[0] - image.width) // 2,
                (page_size[1] - image.height) // 2,
            )
            page.paste(image, position)

            output_path = f"{os.path.splitext(filepath)[0]}.printq.pdf"
            page.save(output_path, 'PDF', resolution=dpi, quality=95)
            return output_path
    except Exception as exc:
        # Returning the original would silently re-enter the filter path known
        # to hang. Surface a useful error to the caller instead.
        raise RuntimeError(f"Unable to prepare image for printing: {exc}") from exc

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
    all_allowed = DIRECT_PRINT_TYPES | IMAGE_TYPES | set(CONVERTIBLE_TYPES.keys())
    if ext not in all_allowed:
        errors.append(f'File type .{ext} not supported')

    return len(errors) == 0, errors


def get_safe_filename(filename):
    """Sanitize a filename for safe storage"""
    from werkzeug.utils import secure_filename
    return secure_filename(filename)
