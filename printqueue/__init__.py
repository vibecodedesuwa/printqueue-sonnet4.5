"""
Print Queue Manager — Flask Application Factory
"""
from flask import Flask
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .models import Database


def create_app(config_class=Config):
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')

    # Honour the public HTTPS host/scheme when a local reverse proxy is used.
    # This is opt-in because forwarded headers must never be trusted from an
    # untrusted client connecting directly to Gunicorn.
    if getattr(config_class, 'TRUST_PROXY', False):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_port=1)

    # Load config
    app.secret_key = config_class.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = config_class.MAX_CONTENT_LENGTH
    app.config['ADMIN_GROUPS'] = config_class.ADMIN_GROUPS
    app.config['ADMIN_USERS'] = config_class.ADMIN_USERS
    app.config['PRINTER_NAME'] = config_class.PRINTER_NAME
    app.config['LDAP_DOMAIN'] = config_class.LDAP_DOMAIN

    app.config['API_RATE_LIMIT'] = config_class.API_RATE_LIMIT
    app.config['UNCLAIMED_JOB_TIMEOUT_HOURS'] = config_class.UNCLAIMED_JOB_TIMEOUT_HOURS
    app.config['UPLOAD_FOLDER'] = config_class.UPLOAD_FOLDER
    app.config['ALLOWED_EXTENSIONS'] = config_class.ALLOWED_EXTENSIONS
    app.config['AUTO_PRINT_QR_UPLOADS'] = getattr(config_class, 'AUTO_PRINT_QR_UPLOADS', True)
    app.config['COLLABORA_ENABLED'] = config_class.COLLABORA_ENABLED
    app.config['COLLABORA_URL'] = config_class.COLLABORA_URL
    app.config['COLLABORA_INTERNAL_URL'] = config_class.COLLABORA_INTERNAL_URL
    app.config['COLLABORA_VERIFY_TLS'] = config_class.COLLABORA_VERIFY_TLS
    app.config['WOPI_PUBLIC_URL'] = config_class.WOPI_PUBLIC_URL
    app.config['WOPI_TOKEN_TTL'] = config_class.WOPI_TOKEN_TTL
    app.config['OFFICE_FOLDER'] = config_class.OFFICE_FOLDER

    # Mail config
    app.config['MAIL_ENABLED'] = config_class.MAIL_ENABLED
    app.config['MAIL_IMAP_HOST'] = config_class.MAIL_IMAP_HOST
    app.config['MAIL_IMAP_PORT'] = config_class.MAIL_IMAP_PORT
    app.config['MAIL_IMAP_USER'] = config_class.MAIL_IMAP_USER
    app.config['MAIL_IMAP_PASS'] = config_class.MAIL_IMAP_PASS
    app.config['MAIL_IMAP_FOLDER'] = config_class.MAIL_IMAP_FOLDER
    app.config['MAIL_IMAP_SSL'] = config_class.MAIL_IMAP_SSL
    app.config['MAIL_POLL_INTERVAL'] = config_class.MAIL_POLL_INTERVAL
    app.config['MAIL_SMTP_HOST'] = config_class.MAIL_SMTP_HOST
    app.config['MAIL_SMTP_PORT'] = config_class.MAIL_SMTP_PORT
    app.config['MAIL_SMTP_USER'] = config_class.MAIL_SMTP_USER
    app.config['MAIL_SMTP_PASS'] = config_class.MAIL_SMTP_PASS

    # Initialize database
    db = Database(config_class.DATABASE_PATH)
    app.config['db'] = db

    # Initialize CORS for API
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize OAuth
    oauth = OAuth(app)
    authentik = oauth.register(
        name='authentik',
        client_id=config_class.AUTHENTIK_CLIENT_ID,
        client_secret=config_class.AUTHENTIK_CLIENT_SECRET,
        server_metadata_url=config_class.AUTHENTIK_METADATA_URL,
        client_kwargs={
            'scope': 'openid email profile',
            'token_endpoint_auth_method': 'client_secret_post',
        }
    )
    app.config['oauth'] = oauth
    app.config['authentik'] = authentik

    # Initialize Active Directory / LDAP Auth
    from .auth_ad import ActiveDirectoryAuth
    ad_config = {
        'LDAP_ENABLED': config_class.LDAP_ENABLED,
        'LDAP_HOST': config_class.LDAP_HOST,
        'LDAP_PORT': config_class.LDAP_PORT,
        'LDAP_USE_SSL': config_class.LDAP_USE_SSL,
        'LDAP_BASE_DN': config_class.LDAP_BASE_DN,
        'LDAP_BIND_DN': config_class.LDAP_BIND_DN,
        'LDAP_BIND_PASSWORD': config_class.LDAP_BIND_PASSWORD,
        'LDAP_DOMAIN': config_class.LDAP_DOMAIN,
        'LDAP_USER_SEARCH_FILTER': config_class.LDAP_USER_SEARCH_FILTER
    }
    app.config['ad_auth'] = ActiveDirectoryAuth(ad_config)

    # Context processor to expose ldap_enabled state to all templates
    @app.context_processor
    def inject_globals():
        ad_auth = app.config.get('ad_auth')
        ad_configured = ad_auth.is_configured() if ad_auth else False
        show_ad = config_class.LDAP_ENABLED and config_class.LDAP_SHOW_IN_WEBUI and ad_configured
        return dict(ldap_enabled=show_ad)

    # Ensure upload directory exists
    import os
    os.makedirs(config_class.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(config_class.OFFICE_FOLDER, exist_ok=True)

    # Register blueprints
    from .routes.web import web_bp
    from .routes.api_v1 import api_bp
    from .routes.upload import upload_bp
    from .routes.office import office_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(upload_bp)
    app.register_blueprint(office_bp)

    # Start email polling if enabled
    if config_class.MAIL_ENABLED:
        from .services.mail_printer import start_mail_polling
        start_mail_polling(app)

    return app
