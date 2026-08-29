"""
Configuration module for Print Queue Manager
"""
import os


class Config:
    """Application configuration from environment variables"""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-in-production-please')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_SIZE', 50)) * 1024 * 1024  # MB
    # Enable only when PrintQ is reached through a trusted local reverse proxy.
    TRUST_PROXY = os.environ.get('TRUST_PROXY', 'false').lower() == 'true'

    # Authentik OAuth
    AUTHENTIK_CLIENT_ID = os.environ.get('AUTHENTIK_CLIENT_ID')
    AUTHENTIK_CLIENT_SECRET = os.environ.get('AUTHENTIK_CLIENT_SECRET')
    AUTHENTIK_METADATA_URL = os.environ.get('AUTHENTIK_METADATA_URL')

    # CUPS
    PRINTER_NAME = os.environ.get('PRINTER_NAME', 'HP_Smart_Tank_515')

    # Admin
    ADMIN_GROUPS = os.environ.get('ADMIN_GROUPS', 'admins,print-admins').split(',')
    ADMIN_USERS = os.environ.get('ADMIN_USERS', 'admin').split(',')

    # Active Directory / LDAP
    LDAP_ENABLED = os.environ.get('LDAP_ENABLED', 'false').lower() == 'true'
    LDAP_SHOW_IN_WEBUI = os.environ.get('LDAP_SHOW_IN_WEBUI', 'true').lower() == 'true'
    LDAP_HOST = os.environ.get('LDAP_HOST', '')
    LDAP_PORT = int(os.environ.get('LDAP_PORT', 389))
    LDAP_USE_SSL = os.environ.get('LDAP_USE_SSL', 'false').lower() == 'true'
    LDAP_BASE_DN = os.environ.get('LDAP_BASE_DN', '')
    LDAP_BIND_DN = os.environ.get('LDAP_BIND_DN', '')
    LDAP_BIND_PASSWORD = os.environ.get('LDAP_BIND_PASSWORD', '')
    LDAP_DOMAIN = os.environ.get('LDAP_DOMAIN', '')
    LDAP_USER_SEARCH_FILTER = os.environ.get('LDAP_USER_SEARCH_FILTER', '(&(objectClass=user)(sAMAccountName={username}))')


    # Email Print
    MAIL_ENABLED = os.environ.get('MAIL_ENABLED', 'false').lower() == 'true'
    MAIL_IMAP_HOST = os.environ.get('MAIL_IMAP_HOST', '')
    MAIL_IMAP_PORT = int(os.environ.get('MAIL_IMAP_PORT', 993))
    MAIL_IMAP_USER = os.environ.get('MAIL_IMAP_USER', '')
    MAIL_IMAP_PASS = os.environ.get('MAIL_IMAP_PASS', '')
    MAIL_IMAP_FOLDER = os.environ.get('MAIL_IMAP_FOLDER', 'INBOX')
    MAIL_IMAP_SSL = os.environ.get('MAIL_IMAP_SSL', 'true').lower() == 'true'
    MAIL_POLL_INTERVAL = int(os.environ.get('MAIL_POLL_INTERVAL', 30))
    MAIL_SMTP_HOST = os.environ.get('MAIL_SMTP_HOST', '')
    MAIL_SMTP_PORT = int(os.environ.get('MAIL_SMTP_PORT', 587))
    MAIL_SMTP_USER = os.environ.get('MAIL_SMTP_USER', '')
    MAIL_SMTP_PASS = os.environ.get('MAIL_SMTP_PASS', '')

    # API
    API_RATE_LIMIT = int(os.environ.get('API_RATE_LIMIT', 100))  # requests per minute

    # Claim Your Job
    UNCLAIMED_JOB_TIMEOUT_HOURS = int(os.environ.get('UNCLAIMED_JOB_TIMEOUT', 24))

    # Database
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'data/printqueue.db')

    # File Upload
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'data/uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'doc', 'txt'}

    # Collabora Online / WOPI
    COLLABORA_ENABLED = os.environ.get('COLLABORA_ENABLED', 'false').lower() == 'true'
    COLLABORA_URL = os.environ.get('COLLABORA_URL', '').rstrip('/')
    COLLABORA_INTERNAL_URL = os.environ.get('COLLABORA_INTERNAL_URL', '').rstrip('/')
    COLLABORA_VERIFY_TLS = os.environ.get('COLLABORA_VERIFY_TLS', 'true').lower() == 'true'
    WOPI_PUBLIC_URL = os.environ.get('WOPI_PUBLIC_URL', '').rstrip('/')
    WOPI_TOKEN_TTL = int(os.environ.get('WOPI_TOKEN_TTL', 14400))
    OFFICE_FOLDER = os.environ.get('OFFICE_FOLDER', 'data/office')
