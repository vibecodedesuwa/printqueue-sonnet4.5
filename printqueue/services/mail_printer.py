"""
Email print service for Print Queue Manager
Polls an IMAP inbox for emails with attachments and submits them as print jobs.
"""
import threading
import time
import email
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from imapclient import IMAPClient
    IMAP_AVAILABLE = True
except ImportError:
    IMAP_AVAILABLE = False

from ..cups_utils import submit_print_job
from .file_converter import convert_if_needed, validate_file


ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'doc', 'txt'}


class MailPrinterService:
    """Background service that polls an IMAP inbox for print jobs"""

    def __init__(self, app):
        self.app = app
        self.running = False
        self.thread = None

    def start(self):
        if not IMAP_AVAILABLE:
            print("[MailPrint] imapclient not installed — email printing disabled")
            return

        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        print("[MailPrint] Email print service started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)

    def _poll_loop(self):
        with self.app.app_context():
            interval = self.app.config.get('MAIL_POLL_INTERVAL', 30)
            while self.running:
                try:
                    self._check_inbox()
                except Exception as e:
                    print(f"[MailPrint] Error polling inbox: {e}")
                time.sleep(interval)

    def _check_inbox(self):
        config = self.app.config
        host = config.get('MAIL_IMAP_HOST')
        user = config.get('MAIL_IMAP_USER')
        passwd = config.get('MAIL_IMAP_PASS')
        folder = config.get('MAIL_IMAP_FOLDER', 'INBOX')
        use_ssl = config.get('MAIL_IMAP_SSL', True)
        port = config.get('MAIL_IMAP_PORT', 993)

        if not all([host, user, passwd]):
            return

        with IMAPClient(host, port=port, ssl=use_ssl) as client:
            client.login(user, passwd)
            client.select_folder(folder)

            # Search for unread messages
            messages = client.search(['UNSEEN'])

            for uid in messages:
                try:
                    self._process_message(client, uid)
                except Exception as e:
                    print(f"[MailPrint] Error processing message {uid}: {e}")

    def _process_message(self, client, uid):
        raw_message = client.fetch([uid], ['RFC822'])
        if uid not in raw_message:
            return

        msg = email.message_from_bytes(raw_message[uid][b'RFC822'])
        sender = email.utils.parseaddr(msg['From'])[1]
        subject = msg.get('Subject', 'Untitled')

        print(f"[MailPrint] Processing email from {sender}: {subject}")

        # Find printable attachments
        attachments_processed = 0
        upload_dir = self.app.config.get('UPLOAD_FOLDER', 'data/uploads')
        os.makedirs(upload_dir, exist_ok=True)

        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue

            filename = part.get_filename()
            if not filename:
                continue

            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            if ext not in ALLOWED_EXTENSIONS:
                continue

            # Save attachment
            from werkzeug.utils import secure_filename
            safe_name = secure_filename(filename)
            filepath = os.path.join(upload_dir, f"email_{uid}_{safe_name}")

            with open(filepath, 'wb') as f:
                f.write(part.get_payload(decode=True))

            # Validate
            valid, errors = validate_file(filepath)
            if not valid:
                print(f"[MailPrint] Skipping {filename}: {errors}")
                os.remove(filepath)
                continue

            # Convert if needed
            converted = convert_if_needed(filepath)

            # Map sender to user
            db = self.app.config['db']
            username = db.get_email_mapping(sender) or sender

            # Submit to CUPS
            printer_name = self.app.config.get('PRINTER_NAME', 'HP_Smart_Tank_515')
            success, result = submit_print_job(converted, f"{subject} - {filename}", printer_name)

            if success:
                db.create_job_meta(result, submitted_via='email', original_filename=filename, submitted_by=username)
                attachments_processed += 1
                print(f"[MailPrint] Submitted job #{result} for {filename}")
            else:
                print(f"[MailPrint] Failed to submit {filename}: {result}")

        # Mark as read
        client.set_flags([uid], [b'\\Seen'])

        # Send confirmation reply
        if attachments_processed > 0:
            self._send_reply(sender, subject, attachments_processed)

    def _send_reply(self, to_email, original_subject, job_count):
        """Send a confirmation email"""
        config = self.app.config
        smtp_host = config.get('MAIL_SMTP_HOST')
        smtp_port = config.get('MAIL_SMTP_PORT', 587)
        smtp_user = config.get('MAIL_SMTP_USER')
        smtp_pass = config.get('MAIL_SMTP_PASS')

        if not all([smtp_host, smtp_user, smtp_pass]):
            return

        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = to_email
            msg['Subject'] = f"Re: {original_subject} — Print Job Submitted"

            body = f"""Your print job has been received!

📄 {job_count} file(s) submitted to the print queue.
⏸️ Jobs are held until approved.
🖨️ Visit the dashboard or ask an admin to release your job.

— Print Queue Manager
"""
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            print(f"[MailPrint] Confirmation sent to {to_email}")
        except Exception as e:
            print(f"[MailPrint] Failed to send confirmation: {e}")


def start_mail_polling(app):
    """Start the mail polling service"""
    service = MailPrinterService(app)
    service.start()
    app.config['mail_service'] = service
