# 🖨️ PrintQ — Print Queue Manager

A modern, feature-rich print queue management system built with Flask and Bootstrap 5. Supports Kiosk Mode with device token authentication, Web Upload, Email Print, REST API, AirPrint/Mopria, and a "Claim Your Job" system for mobile devices.

## ✨ Features

| Feature               | Description                                                                           |
| --------------------- | ------------------------------------------------------------------------------------- |
| **Kiosk Mode**        | Touch-optimized fullscreen UI for approving/denying jobs — secured with device tokens |
| **Web Upload**        | Drag-and-drop file upload with print options (copies, duplex, color, page range)      |
| **Email Print**       | Send attachments via email to print — auto-submitted to queue                         |
| **REST API v1**       | 20+ endpoints with API key authentication, rate limiting, Swagger docs                |
| **AirPrint / Mopria** | Native iOS/Android/macOS/Windows printing via CUPS + Avahi mDNS                       |
| **Claim Your Job**    | Unclaimed job pool for AirPrint/Mopria users — claim via web dashboard                |
| **PWA**               | Add to home screen, offline caching, responsive mobile-first design                   |
| **Authentik SSO**     | OpenID Connect authentication with RP-Initiated Logout                                |
| **Hold & Release**    | All jobs are held until approved via dashboard, kiosk, or API                         |
| **Admin Panel**       | Manage jobs, API keys, device mappings, email mappings, and kiosk devices             |

## 🏗️ Architecture

```
printqueue-sonnet4.5/
├── app.py                     # Entry point (app factory)
├── printqueue/                # Flask application package
│   ├── __init__.py            # App factory
│   ├── config.py              # Environment config
│   ├── models.py              # SQLite models (API keys, jobs, devices, mappings)
│   ├── auth.py                # Auth decorators (session, API key, kiosk token)
│   ├── cups_utils.py          # CUPS integration helpers
│   ├── routes/
│   │   ├── web.py             # Dashboard, admin, kiosk, login routes
│   │   ├── api_v1.py          # REST API v1 endpoints
│   │   └── upload.py          # File upload routes
│   ├── services/
│   │   ├── file_converter.py  # DOCX→PDF conversion (LibreOffice)
│   │   └── mail_printer.py    # IMAP email polling service
│   └── swagger/
│       └── api_v1.yml         # OpenAPI 3.0 specification
├── templates/                 # Jinja2 templates (Bootstrap 5)
│   ├── base.html              # Base layout (dark theme, toasts, modals)
│   ├── dashboard.html         # User dashboard (AJAX polling, claim system)
│   ├── admin.html             # Admin panel (jobs, keys, devices, kiosks)
│   ├── kiosk.html             # Kiosk dashboard (device token auth)
│   ├── kiosk_unauthorized.html # Shown when device not registered
│   ├── upload.html            # Drag-and-drop upload
│   └── api_docs.html          # Swagger UI (dark theme)
├── static/
│   ├── manifest.json          # PWA manifest
│   └── sw.js                  # Service worker
├── config/
│   └── avahi/                 # AirPrint mDNS service files
├── scripts/
│   └── setup-airprint.sh      # AirPrint/Avahi setup automation
├── data/                      # SQLite DB + uploaded files
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── CLIENT_PRINT_GUIDE.md      # Multi-platform print setup
├── CLIENT_SETUP_GUIDE.md      # Network/client configuration
├── LXC_SETUP_GUIDE.md         # Proxmox LXC deployment
└── README.md
```

## 🚀 Quick Start

### 1. Clone and configure

```bash
git clone <repo-url>
cd printqueue-sonnet4.5
cp .env.example .env
# Edit .env with your settings
```

### 2. Run with Docker Compose

```bash
docker-compose up -d --build
```

### 3. Access

| URL                              | Purpose                        |
| -------------------------------- | ------------------------------ |
| `http://localhost:5000`          | Web Dashboard (SSO login)      |
| `http://localhost:5000/kiosk`    | Kiosk Mode (device token auth) |
| `http://localhost:5000/upload`   | Upload & Print                 |
| `http://localhost:5000/api/docs` | API Documentation (Swagger)    |
| `http://localhost:631`           | CUPS Admin                     |

### 4. Enable AirPrint (optional)

```bash
docker exec -it cups-server bash /scripts/setup-airprint.sh
```

## 📱 Client Setup

See **[CLIENT_PRINT_GUIDE.md](CLIENT_PRINT_GUIDE.md)** for step-by-step instructions to connect:

- 📱 iPhone / iPad (AirPrint — zero config)
- 🤖 Android (Mopria / Default Print Service)
- 💻 macOS (AirPrint)
- 🪟 Windows 10/11 (IPP)
- 🐧 Linux (CUPS client)
- 🌐 Web Upload (any browser)
- 📧 Email Print

## 🔐 Authentication

| Context       | Method                                               |
| ------------- | ---------------------------------------------------- |
| Web Dashboard | Authentik SSO (OpenID Connect + RP-Initiated Logout) |
| Kiosk Mode    | Device token cookie (managed via Admin → Kiosks)     |
| REST API      | API key (`Authorization: Bearer <key>`)              |
| Email Print   | Sender email mapped to username                      |

### Kiosk Device Registration

Kiosk mode uses **device token authentication** instead of a shared PIN. This ties access to specific devices via a secure, long-lived cookie.

1. **Admin** → go to **Admin Panel → Kiosks** tab → click **Register New**
2. Enter a **device name** (e.g. "Front Desk iPad") and optionally lock to an **IP address**
3. Copy the generated **one-time registration URL**
4. Open that URL on the **kiosk device's browser** — a secure cookie is set automatically
5. The device can now access `/kiosk` indefinitely — no PIN, no login required
6. To **revoke access**: delete the device from Admin → Kiosks tab (instant lockout)

**Security model:**

- Cookie is `httponly`, `samesite=Lax`, `secure` (when HTTPS)
- Token is hashed with SHA-256 in the database (raw token never stored)
- Optional IP lock per device for network-level restriction
- Revoking a device = immediate access loss

## 🔑 REST API

All endpoints require an API key via `Authorization: Bearer <key>` header.

### Quick Examples

```bash
# List jobs
curl -H "Authorization: Bearer pq_your_key" http://localhost:5000/api/v1/jobs

# Submit a print job
curl -X POST -H "Authorization: Bearer pq_your_key" \
  -F "file=@document.pdf" -F "copies=2" \
  http://localhost:5000/api/v1/print

# Release a job
curl -X POST -H "Authorization: Bearer pq_your_key" \
  http://localhost:5000/api/v1/jobs/42/release

# Claim an unclaimed job
curl -X POST -H "Authorization: Bearer pq_your_key" \
  -H "Content-Type: application/json" \
  -d '{"username": "john"}' \
  http://localhost:5000/api/v1/jobs/42/claim
```

### Endpoints Overview

| Endpoint                    | Method   | Auth  | Description           |
| --------------------------- | -------- | ----- | --------------------- |
| `/api/v1/health`            | GET      | —     | Health check          |
| `/api/v1/jobs`              | GET      | read  | List jobs             |
| `/api/v1/jobs/unclaimed`    | GET      | read  | Unclaimed jobs        |
| `/api/v1/jobs/<id>`         | GET      | read  | Job details           |
| `/api/v1/jobs/<id>/release` | POST     | write | Release job           |
| `/api/v1/jobs/<id>/cancel`  | POST     | write | Cancel job            |
| `/api/v1/jobs/<id>/claim`   | POST     | write | Claim job             |
| `/api/v1/print`             | POST     | write | Upload & print        |
| `/api/v1/printer/status`    | GET      | read  | Printer status        |
| `/api/v1/printers`          | GET      | read  | List printers         |
| `/api/v1/keys`              | GET/POST | admin | API key management    |
| `/api/v1/keys/<id>`         | DELETE   | admin | Revoke key            |
| `/api/v1/users`             | GET      | admin | List known users      |
| `/api/v1/devices`           | POST     | admin | Add device mapping    |
| `/api/v1/devices/<id>`      | DELETE   | admin | Delete device mapping |
| `/api/v1/emails`            | POST     | admin | Add email mapping     |
| `/api/v1/emails/<email>`    | DELETE   | admin | Delete email mapping  |

Full interactive docs: **`/api/docs`** (Swagger UI)

## 🙋 Claim Your Job System

When printing via AirPrint/Mopria, the system may not identify you. The claim flow:

1. 📱 You print from your phone → CUPS receives the job with a generic username (e.g., "iPhone")
2. 🔍 PrintQ checks the **device mapping** table — if your device is mapped, the job is auto-assigned
3. ❓ If unmapped, the job enters the **unclaimed pool**
4. 🙋 You log into the dashboard and click **"Claim"** on your job
5. ✅ The job is now yours to approve/release

**Admin tip:** Add recurring devices in **Admin → Devices** so future jobs auto-assign.

## ⚙️ Environment Variables

| Variable                  | Default               | Description                             |
| ------------------------- | --------------------- | --------------------------------------- |
| `SECRET_KEY`              |                       | Flask secret key                        |
| `AUTHENTIK_CLIENT_ID`     |                       | OAuth client ID                         |
| `AUTHENTIK_CLIENT_SECRET` |                       | OAuth client secret                     |
| `AUTHENTIK_METADATA_URL`  |                       | OIDC metadata URL                       |
| `PRINTER_NAME`            | `HP_Smart_Tank_515`   | Default CUPS printer                    |
| `ADMIN_GROUPS`            | `admins,print-admins` | Admin group names (comma-separated)     |
| `ADMIN_USERS`             | `admin`               | Admin usernames (comma-separated)       |
| `MAIL_ENABLED`            | `false`               | Enable email printing                   |
| `MAIL_IMAP_HOST`          |                       | IMAP server host                        |
| `MAIL_IMAP_USER`          |                       | IMAP username                           |
| `MAIL_IMAP_PASS`          |                       | IMAP password                           |
| `UNCLAIMED_JOB_TIMEOUT`   | `24`                  | Hours before unclaimed jobs auto-cancel |

> **Note:** Kiosk access is no longer configured via environment variables. Kiosk devices are managed through the Admin Panel → Kiosks tab.

## 📄 License

MIT
