"""
Print Queue Manager — Flask Application Factory
"""
from flask import Flask
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth

from .config import Config
from .models import Database


def create_app(config_class=Config):
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')

    # Load config
    app.secret_key = config_class.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = config_class.MAX_CONTENT_LENGTH
    app.config['ADMIN_GROUPS'] = config_class.ADMIN_GROUPS
    app.config['ADMIN_USERS'] = config_class.ADMIN_USERS
    app.config['PRINTER_NAME'] = config_class.PRINTER_NAME
    app.config['KIOSK_PIN'] = config_class.KIOSK_PIN
    app.config['API_RATE_LIMIT'] = config_class.API_RATE_LIMIT
    app.config['UNCLAIMED_JOB_TIMEOUT_HOURS'] = config_class.UNCLAIMED_JOB_TIMEOUT_HOURS
    app.config['UPLOAD_FOLDER'] = config_class.UPLOAD_FOLDER
    app.config['ALLOWED_EXTENSIONS'] = config_class.ALLOWED_EXTENSIONS

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

    # Ensure upload directory exists
    import os
    os.makedirs(config_class.UPLOAD_FOLDER, exist_ok=True)

    # Register blueprints
    from .routes.web import web_bp
    from .routes.api_v1 import api_bp
    from .routes.upload import upload_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(upload_bp)

    # Start email polling if enabled
    if config_class.MAIL_ENABLED:
        from .services.mail_printer import start_mail_polling
        start_mail_polling(app)

    return app
