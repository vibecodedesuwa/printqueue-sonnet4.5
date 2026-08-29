"""Collabora Online integration and the minimal WOPI file host."""
from datetime import datetime, timezone
import json
import os
import re
import threading
import time
from urllib.parse import quote, urlsplit, urlunsplit
import uuid
import zipfile

from flask import (
    Blueprint, abort, current_app, jsonify, make_response, redirect,
    render_template, request, session, url_for,
)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
import requests

from ..auth import is_admin, login_required
from ..cups_utils import submit_print_job
from ..filenames import clean_display_filename
from ..identity import usernames_match
from ..services.file_converter import convert_if_needed


office_bp = Blueprint('office', __name__)
_metadata_lock = threading.RLock()
_discovery_cache = {'url': None, 'loaded_at': 0, 'actions': {}}
_writer_extensions = {'odt', 'docx'}


def _office_folder():
    folder = current_app.config['OFFICE_FOLDER']
    os.makedirs(folder, exist_ok=True)
    return folder


def _meta_path(file_id):
    return os.path.join(_office_folder(), f'{file_id}.json')


def _read_meta(file_id):
    if not re.fullmatch(r'[0-9a-f]{32}', file_id or ''):
        return None
    try:
        with open(_meta_path(file_id), 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _write_meta(meta):
    path = _meta_path(meta['id'])
    temporary = f'{path}.{uuid.uuid4().hex}.tmp'
    with _metadata_lock:
        with open(temporary, 'w', encoding='utf-8') as handle:
            json.dump(meta, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, path)


def _document_path(meta):
    return os.path.join(_office_folder(), f"{meta['id']}.{meta['extension']}")


def _display_filename(value, extension):
    value = clean_display_filename(value, fallback='Untitled document')
    stem = os.path.splitext(value)[0].strip()[:120] or 'Untitled document'
    return f'{stem}.{extension}'


def _can_access(meta, username):
    return bool(meta and (
        is_admin()
        or usernames_match(meta.get('owner'), username, current_app.config.get('LDAP_DOMAIN', ''))
    ))


def list_office_documents(username):
    documents = []
    try:
        names = os.listdir(_office_folder())
    except OSError:
        return documents
    for name in names:
        if not re.fullmatch(r'[0-9a-f]{32}\.json', name):
            continue
        meta = _read_meta(name[:-5])
        if _can_access(meta, username) and os.path.isfile(_document_path(meta)):
            documents.append(meta)
    return sorted(documents, key=lambda item: item.get('modified_at', ''), reverse=True)


def _new_thai_ready_odt(path, title):
    safe_title = (title or 'Untitled document').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    files = {
        'content.xml': f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.3">
 <office:automatic-styles><style:style style:name="P1" style:family="paragraph"><style:text-properties style:font-name="Noto Sans Thai" fo:font-family="Noto Sans Thai" style:font-name-asian="Noto Sans Thai"/></style:style></office:automatic-styles>
 <office:body><office:text><text:h text:outline-level="1" text:style-name="P1">{safe_title}</text:h><text:p text:style-name="P1"/></office:text></office:body>
</office:document-content>''',
        'styles.xml': '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.3"><office:styles><style:default-style style:family="paragraph"><style:text-properties style:font-name="Noto Sans Thai" fo:font-family="Noto Sans Thai" style:font-name-asian="Noto Sans Thai"/></style:default-style></office:styles></office:document-styles>''',
        'META-INF/manifest.xml': '''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/><manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/></manifest:manifest>''',
    }
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('mimetype', 'application/vnd.oasis.opendocument.text', compress_type=zipfile.ZIP_STORED)
        for name, content in files.items():
            archive.writestr(name, content, compress_type=zipfile.ZIP_DEFLATED)


def _create_document(owner, filename, extension, source=None):
    file_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    meta = {
        'id': file_id,
        'owner': owner,
        'name': _display_filename(filename, extension),
        'extension': extension,
        'created_at': now,
        'modified_at': now,
        'lock': None,
    }
    path = _document_path(meta)
    if source is None:
        _new_thai_ready_odt(path, os.path.splitext(meta['name'])[0])
    else:
        source.save(path)
    _write_meta(meta)
    return meta


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='printq-wopi-v1')


def _make_token(meta, user):
    return _serializer().dumps({'file_id': meta['id'], 'user': user['username'], 'name': user.get('name') or user['username']})


def _token_payload(file_id):
    token = request.args.get('access_token', '')
    if not token and request.headers.get('Authorization', '').startswith('Bearer '):
        token = request.headers['Authorization'][7:]
    try:
        payload = _serializer().loads(token, max_age=current_app.config['WOPI_TOKEN_TTL'])
    except (BadSignature, SignatureExpired):
        abort(401)
    if payload.get('file_id') != file_id:
        abort(403)
    return payload


def _discovery_actions():
    base = current_app.config.get('COLLABORA_INTERNAL_URL') or current_app.config['COLLABORA_URL']
    discovery_url = f"{base.rstrip('/')}/hosting/discovery"
    if _discovery_cache['url'] == discovery_url and time.time() - _discovery_cache['loaded_at'] < 300:
        return _discovery_cache['actions']

    from xml.etree import ElementTree
    response = requests.get(
        discovery_url,
        timeout=8,
        verify=current_app.config.get('COLLABORA_VERIFY_TLS', True),
    )
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    actions = {}
    for action in root.iter('action'):
        if action.attrib.get('name') == 'edit' and action.attrib.get('ext') in _writer_extensions:
            action_url = action.attrib.get('urlsrc')
            public_url = current_app.config.get('COLLABORA_URL')
            if action_url and public_url:
                discovered = urlsplit(action_url)
                public = urlsplit(public_url)
                action_url = urlunsplit((public.scheme, public.netloc, discovered.path, discovered.query, discovered.fragment))
            actions[action.attrib['ext']] = action_url
    _discovery_cache.update(url=discovery_url, loaded_at=time.time(), actions=actions)
    return actions


@office_bp.post('/editor/office/new')
@login_required
def new_office_document():
    if not current_app.config.get('COLLABORA_ENABLED') or not current_app.config.get('WOPI_PUBLIC_URL'):
        return jsonify({'error': 'Collabora or WOPI_PUBLIC_URL is not configured'}), 503
    meta = _create_document(session['user']['username'], request.form.get('title', ''), 'odt')
    return redirect(url_for('office.edit_office_document', file_id=meta['id']))


@office_bp.post('/editor/office/upload')
@login_required
def upload_office_document():
    if not current_app.config.get('COLLABORA_ENABLED') or not current_app.config.get('WOPI_PUBLIC_URL'):
        return jsonify({'error': 'Collabora or WOPI_PUBLIC_URL is not configured'}), 503
    uploaded = request.files.get('file')
    extension = (os.path.splitext(uploaded.filename or '')[1].lstrip('.').lower() if uploaded else '')
    if not uploaded or extension not in _writer_extensions:
        return jsonify({'error': 'Choose an ODT or DOCX document'}), 400
    meta = _create_document(session['user']['username'], uploaded.filename, extension, uploaded)
    return redirect(url_for('office.edit_office_document', file_id=meta['id']))


@office_bp.get('/editor/office/<file_id>')
@login_required
def edit_office_document(file_id):
    meta = _read_meta(file_id)
    if not _can_access(meta, session['user']['username']):
        abort(404)
    public_wopi = current_app.config.get('WOPI_PUBLIC_URL')
    if not public_wopi:
        return redirect(url_for('web.editor_page', setup='wopi'))
    try:
        action_url = _discovery_actions().get(meta['extension'])
    except (requests.RequestException, ValueError):
        action_url = None
    if not action_url:
        return render_template('office_editor.html', user=session['user'], document=meta, error='Collabora discovery is unavailable or does not advertise this file type.'), 503
    token = _make_token(meta, session['user'])
    wopi_url = f"{public_wopi}/wopi/files/{meta['id']}"
    separator = '' if action_url.endswith(('?', '&')) else ('&' if '?' in action_url else '?')
    iframe_url = f"{action_url}{separator}WOPISrc={quote(wopi_url, safe='')}&closebutton=1"
    token_ttl = (int(time.time()) + current_app.config['WOPI_TOKEN_TTL']) * 1000
    return render_template(
        'office_editor.html', user=session['user'], document=meta,
        iframe_url=iframe_url, access_token=token, access_token_ttl=token_ttl,
    )


@office_bp.post('/editor/office/<file_id>/print')
@login_required
def print_office_document(file_id):
    meta = _read_meta(file_id)
    if not _can_access(meta, session['user']['username']):
        abort(404)
    source_path = _document_path(meta)
    converted_path = convert_if_needed(source_path)
    if os.path.splitext(converted_path)[1].lower() not in {'.pdf', '.png', '.jpg', '.jpeg'}:
        return jsonify({'error': 'LibreOffice could not convert this document to a printable format'}), 503
    copies = request.form.get('copies', '1')
    options = {'copies': copies} if copies.isdigit() and 1 <= int(copies) <= 99 else {'copies': '1'}
    success, result = submit_print_job(
        converted_path, meta['name'], current_app.config['PRINTER_NAME'], options,
        requesting_user=session['user']['username'],
    )
    if not success:
        return jsonify({'error': result}), 502
    current_app.config['db'].create_job_meta(
        result, submitted_via='collabora', original_filename=meta['name'],
        submitted_by=session['user']['username'],
    )
    return jsonify({'success': True, 'job_id': result})


@office_bp.route('/wopi/files/<file_id>', methods=['GET', 'POST'])
def wopi_file_info(file_id):
    payload = _token_payload(file_id)
    meta = _read_meta(file_id)
    if not meta or not os.path.isfile(_document_path(meta)):
        abort(404)

    if request.method == 'POST':
        override = request.headers.get('X-WOPI-Override', '').upper()
        requested_lock = request.headers.get('X-WOPI-Lock', '')
        current_lock = meta.get('lock') or ''
        if override in {'LOCK', 'REFRESH_LOCK'}:
            if current_lock and current_lock != requested_lock:
                response = make_response('', 409)
                response.headers['X-WOPI-Lock'] = current_lock
                return response
            meta['lock'] = requested_lock
            _write_meta(meta)
            return '', 200
        if override == 'UNLOCK':
            if current_lock != requested_lock:
                response = make_response('', 409)
                response.headers['X-WOPI-Lock'] = current_lock
                return response
            meta['lock'] = None
            _write_meta(meta)
            return '', 200
        if override == 'GET_LOCK':
            response = make_response('', 200)
            response.headers['X-WOPI-Lock'] = current_lock
            return response
        return jsonify({'error': 'Unsupported WOPI operation'}), 501

    path = _document_path(meta)
    modified = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()
    origin = current_app.config['WOPI_PUBLIC_URL']
    return jsonify({
        'BaseFileName': meta['name'],
        'OwnerId': meta['owner'],
        'Size': os.path.getsize(path),
        'UserId': payload['user'],
        'UserFriendlyName': payload.get('name') or payload['user'],
        'UserCanWrite': True,
        'UserCanNotWriteRelative': True,
        'SupportsLocks': True,
        'SupportsUpdate': True,
        'SupportsRename': False,
        'LastModifiedTime': modified,
        'Version': str(os.stat(path).st_mtime_ns),
        'BreadcrumbBrandName': 'PrintQ',
        'BreadcrumbFolderName': 'A4 Editor',
        'BreadcrumbFolderUrl': f'{origin}/editor',
        'PostMessageOrigin': origin,
    })


@office_bp.route('/wopi/files/<file_id>/contents', methods=['GET', 'POST'])
def wopi_file_contents(file_id):
    _token_payload(file_id)
    meta = _read_meta(file_id)
    if not meta:
        abort(404)
    path = _document_path(meta)
    if request.method == 'GET':
        with open(path, 'rb') as handle:
            response = make_response(handle.read())
        response.headers['Content-Type'] = 'application/octet-stream'
        response.headers['X-WOPI-ItemVersion'] = str(os.stat(path).st_mtime_ns)
        return response

    requested_lock = request.headers.get('X-WOPI-Lock', '')
    if meta.get('lock') and meta['lock'] != requested_lock:
        response = make_response('', 409)
        response.headers['X-WOPI-Lock'] = meta['lock']
        return response
    temporary = f'{path}.{uuid.uuid4().hex}.tmp'
    with open(temporary, 'wb') as handle:
        handle.write(request.get_data(cache=False))
    os.replace(temporary, path)
    meta['modified_at'] = datetime.now(timezone.utc).isoformat()
    _write_meta(meta)
    return jsonify({'LastModifiedTime': meta['modified_at']})
