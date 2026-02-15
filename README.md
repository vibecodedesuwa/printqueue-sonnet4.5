# 🖨️ PrintQ — Print Queue Manager

A modern, feature-rich print queue management system built with Flask. Supports Kiosk Mode, Web Upload, Email Print, REST API, AirPrint/Mopria, and a "Claim Your Job" system for mobile devices.

## ✨ Features

| Feature               | Description                                                                      |
| --------------------- | -------------------------------------------------------------------------------- |
| **Kiosk Mode**        | Touch-optimized fullscreen UI for approving/denying jobs on a phone/tablet       |
| **Web Upload**        | Drag-and-drop file upload with print options (copies, duplex, color, page range) |
| **Email Print**       | Send attachments via email to print — auto-submitted to queue                    |
| **REST API v1**       | 20+ endpoints with API key authentication, rate limiting, Swagger docs           |
| **AirPrint / Mopria** | Native iOS/Android/macOS/Windows printing via CUPS + Avahi mDNS                  |
| **Claim Your Job**    | Unclaimed job pool for AirPrint/Mopria users — claim via web dashboard           |
| **PWA**               | Add to home screen, offline caching, responsive mobile-first design              |
| **Authentik SSO**     | OpenID Connect authentication via Authentik                                      |
| **Hold & Release**    | All jobs are held until approved via dashboard, kiosk, or API                    |
| **Admin Panel**       | Manage all jobs, API keys, device mappings, email mappings                       |

## 🏗️ Architecture

```
printqueue-sonnet4.5/
├── app.py                     # Entry point (app factory)
├── printqueue/                # Flask application package
│   ├── __init__.py            # App factory
│   ├── config.py              # Environment config
│   ├── models.py              # SQLite models (API keys, jobs, mappings)
│   ├── auth.py                # Auth decorators (session, API key, kiosk)
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
├── templates/                 # Jinja2 templates
│   ├── base.html              # Base layout (dark theme, responsive)
│   ├── dashboard.html         # User dashboard (with claim system)
│   ├── admin.html             # Admin panel (jobs, keys, mappings)
│   ├── kiosk.html             # Kiosk approval screen
│   ├── kiosk_login.html       # Kiosk PIN entry
│   ├── upload.html            # Drag-and-drop upload
│   └── api_docs.html          # Swagger UI
├── static/
│   ├── manifest.json          # PWA manifest
│   ├── sw.js                  # Service worker
│   └── icons/                 # PWA icons
├── config/
│   └── avahi/                 # AirPrint mDNS service files
├── scripts/
│   └── setup-airprint.sh      # AirPrint/Avahi setup automation
├── data/                      # SQLite DB + uploaded files
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── CLIENT_PRINT_GUIDE.md      # Multi-platform setup guide
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

| URL                              | Purpose                     |
| -------------------------------- | --------------------------- |
| `http://localhost:5000`          | Web Dashboard (SSO login)   |
| `http://localhost:5000/kiosk`    | Kiosk Mode (PIN: `1234`)    |
| `http://localhost:5000/upload`   | Upload & Print              |
| `http://localhost:5000/api/docs` | API Documentation (Swagger) |
| `http://localhost:631`           | CUPS Admin                  |

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

## 🔐 Authentication

| Context       | Method                                  |
| ------------- | --------------------------------------- |
| Web Dashboard | Authentik SSO (OpenID Connect)          |
| Kiosk Mode    | 4-digit PIN (`KIOSK_PIN` env var)       |
| REST API      | API key (`Authorization: Bearer <key>`) |
| Email Print   | Sender email mapped to username         |

## 🙋 Claim Your Job System

When printing via AirPrint/Mopria, the system may not identify you. The claim flow:

1. 📱 You print from your phone → CUPS receives the job with a generic username (e.g., "iPhone")
2. 🔍 PrintQ checks the **device mapping** table — if your device is mapped, the job is auto-assigned
3. ❓ If unmapped, the job enters the **unclaimed pool**
4. 🙋 You log into the dashboard and click **"Claim"** on your job
5. ✅ The job is now yours to approve

**Admin tip:** Add recurring devices in **Admin → Device Mapping** so future jobs auto-assign.

## ⚙️ Environment Variables

| Variable                  | Default               | Description                             |
| ------------------------- | --------------------- | --------------------------------------- |
| `SECRET_KEY`              |                       | Flask secret key                        |
| `AUTHENTIK_CLIENT_ID`     |                       | OAuth client ID                         |
| `AUTHENTIK_CLIENT_SECRET` |                       | OAuth client secret                     |
| `AUTHENTIK_METADATA_URL`  |                       | OIDC metadata URL                       |
| `PRINTER_NAME`            | `HP_Smart_Tank_515`   | Default CUPS printer                    |
| `ADMIN_GROUPS`            | `admins,print-admins` | Admin group names                       |
| `ADMIN_USERS`             | `admin`               | Admin usernames                         |
| `KIOSK_PIN`               | `1234`                | Kiosk access PIN                        |
| `MAIL_ENABLED`            | `false`               | Enable email printing                   |
| `MAIL_IMAP_HOST`          |                       | IMAP server host                        |
| `MAIL_IMAP_USER`          |                       | IMAP username                           |
| `MAIL_IMAP_PASS`          |                       | IMAP password                           |
| `UNCLAIMED_JOB_TIMEOUT`   | `24`                  | Hours before unclaimed jobs auto-cancel |

## 📄 License

MIT
