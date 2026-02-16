"""
Configuration module for Print Queue Manager
"""
import os


class Config:
    """Application configuration from environment variables"""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-in-production-please')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_SIZE', 50)) * 1024 * 1024  # MB

    # Authentik OAuth
    AUTHENTIK_CLIENT_ID = os.environ.get('AUTHENTIK_CLIENT_ID')
    AUTHENTIK_CLIENT_SECRET = os.environ.get('AUTHENTIK_CLIENT_SECRET')
    AUTHENTIK_METADATA_URL = os.environ.get('AUTHENTIK_METADATA_URL')

    # CUPS
    PRINTER_NAME = os.environ.get('PRINTER_NAME', 'HP_Smart_Tank_515')

    # Admin
    ADMIN_GROUPS = os.environ.get('ADMIN_GROUPS', 'admins,print-admins').split(',')
    ADMIN_USERS = os.environ.get('ADMIN_USERS', 'admin').split(',')


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
