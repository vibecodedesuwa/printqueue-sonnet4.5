"""Unicode-safe display names and collision-resistant local storage names."""
import os
import re
import unicodedata
import uuid

def clean_display_filename(value, fallback='document'):
    """Keep the user's Unicode filename while removing paths and control characters."""
    value = unicodedata.normalize('NFC', str(value or '')).replace('\\', '/')
    value = value.rsplit('/', 1)[-1]
    value = ''.join(character for character in value if unicodedata.category(character)[0] != 'C')
    value = value.strip().strip('.')
    if not value:
        return fallback

    stem, extension = os.path.splitext(value)
    extension = re.sub(r'[^A-Za-z0-9.]', '', extension)[:12]
    stem = stem.strip()[: max(1, 240 - len(extension))] or fallback
    return f'{stem}{extension}'


def unique_storage_filename(display_name, prefix=None):
    """Generate an ASCII filesystem name without losing the separate display filename."""
    display_name = clean_display_filename(display_name)
    display_stem, display_extension = os.path.splitext(display_name)
    ascii_stem = unicodedata.normalize('NFKD', display_stem).encode('ascii', 'ignore').decode('ascii')
    safe_stem = re.sub(r'[^A-Za-z0-9_-]+', '_', ascii_stem).strip('._-')[:80] or 'document'
    safe_extension = re.sub(r'[^A-Za-z0-9.]', '', display_extension.lower())[:12]
    unique_prefix = prefix or uuid.uuid4().hex
    return f'{unique_prefix}_{safe_stem}{safe_extension}'
