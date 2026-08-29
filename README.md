# 🖨️ PrintQ — Print Queue Manager (Docker-Based)

A modern, enterprise-grade print queue management system built with Flask, Docker, and Bootstrap 5. Features **Docker-based deployment**, **Dual Auth (Authentik SSO + Active Directory LDAP)**, **Multi-lingual Support (English 🇺🇸 & Thai 🇹🇭)**, **QR Code Mobile Printing**, **Built-in A4 Document Editor**, Kiosk Mode, Web Upload, Email Print, REST API v1, AirPrint/Mopria, and an enhanced "Claim Your Job" system with fixed permission access controls.

---

## ✨ Key Features

| Feature                       | Description                                                                                           |
| ----------------------------- | ----------------------------------------------------------------------------------------------------- |
| 🐳 **Docker-Based Deployment** | Full Docker Compose containerization for web app, CUPS spooler, and mDNS discovery                    |
| 🔐 **Dual Authentication**     | Native support for **Authentik SSO (OpenID Connect)** and **Active Directory (LDAP)** authentication  |
| 🔗 **AD/CUPS Identity Binding** | Automatically binds `user`, `DOMAIN\\user`, and same-domain `user@domain` print jobs to one account   |
| 🪪 **AD-Integrated IPP**       | Android/iOS users authenticate with AD credentials at the IPP layer                                   |
| 🪟 **Windows AD Print Share**  | Optional Samba/Winbind share provides seamless authentication for domain-joined Windows clients       |
| 🌐 **Multi-Lingual (EN/TH)**   | Dynamic English 🇺🇸 & Thai 🇹🇭 language switching across all pages & modals                           |
| 📱 **QR Mobile Quick Print**   | Scan QR code with iOS/Android camera to instantly upload documents/photos for printing                |
| 📝 **Collabora + A4 Editors**| Full Collabora Writer integration through signed WOPI endpoints, plus a lightweight A4 fallback and direct print submission |
| 🤖 **Android & iOS Support**   | AirPrint & Mopria / IPP support for smartphones and tablets (iOS, iPadOS, Android)                    |
| 🙋 **Claim & Release System**  | Unclaimed job pool with fixed owner authorization for AirPrint, Mopria, Web Upload, and Email jobs    |
| 💻 **Kiosk Mode**             | Touch-optimized terminal UI secured with long-lived device token authentication                       |
| 📧 **Email Print**            | Send attachments via IMAP email to print automatically                                                 |
| 🔑 **REST API v1**            | 20+ endpoints with API key authentication, rate limiting, and interactive Swagger UI                  |

---

## 🏗️ Architecture

```
printqueue-sonnet4.5/
├── app.py                     # Entry point (Flask app factory)
├── printqueue/                # Core Python package
│   ├── __init__.py            # Application factory & LDAP/OAuth initialization
│   ├── config.py              # Configuration & Environment loading
│   ├── models.py              # SQLite database manager (API keys, jobs, devices)
│   ├── auth.py                # Authentication decorators (Session, API key, Kiosk token)
│   ├── auth_ad.py             # Active Directory / LDAP authentication module
│   ├── cups_utils.py          # CUPS printer integration & permission engine
│   ├── routes/
│   │   ├── web.py             # Dashboard, landing, login, A4 editor & QR routes
│   │   ├── api_v1.py          # REST API v1 endpoints
│   │   └── upload.py          # Web & QR file upload routes
│   └── services/
│       ├── file_converter.py  # DOCX/Text → PDF conversion (LibreOffice)
│       └── mail_printer.py    # IMAP email polling background service
├── templates/                 # Jinja2 HTML templates
│   ├── base.html              # Base layout (Language switcher, QR modal, Toast notifications)
│   ├── landing.html           # Landing page with EchoStory SSO & AD login options
│   ├── login.html             # Dedicated dual authentication page
│   ├── dashboard.html         # User dashboard (Live AJAX polling, claim pool)
│   ├── editor.html            # Simple A4 Quick Document Editor
│   ├── qr_upload.html         # Mobile QR upload & camera photo capture page
│   ├── admin.html             # Admin management panel
│   └── kiosk.html             # Kiosk device token terminal
├── static/
│   ├── js/i18n.js             # Multi-lingual translation engine (EN/TH)
│   ├── manifest.json          # PWA manifest
│   └── sw.js                  # Service Worker
├── scripts/
│   ├── cups-entrypoint.sh     # Container startup script with AD/LDAP PAM configuration
│   ├── setup-airprint.sh      # AirPrint/Mopria mDNS advertisement setup
│   ├── setup-cups-ldap.sh     # AD/LDAP PAM setup for bare-metal
│   └── setup-windows-samba.sh # Windows SMB printing through Samba/Winbind
├── docker-compose.yml         # Container orchestration (PrintQ + CUPS)
├── Dockerfile                 # Multi-stage Python 3.11 container definition
├── DOCKER_GUIDE.md            # Detailed Docker Deployment & Operations Guide
├── CLIENT_PRINT_GUIDE.md      # Multi-platform client setup guide
└── README.md
```

---

## 🚀 Quick Start (Docker)

### 1. Clone & Configure Environment

```bash
git clone <repo-url>
cd printqueue-sonnet4.5

cp .env.example .env
# Edit .env with your Active Directory or Authentik settings
```

### 2. Start Containers

```bash
docker compose up -d --build
```

### 3. Access Web Services

| URL                              | Purpose                                      |
| -------------------------------- | -------------------------------------------- |
| `http://localhost:5000`          | Landing & Login Page                         |
| `http://localhost:5000/dashboard`| User Dashboard & Print Queue                 |
| `http://localhost:5000/editor`   | Collabora Office + lightweight A4 editor     |
| `http://localhost:5000/qr-upload`| Mobile QR Code Quick Print                   |
| `http://localhost:5000/kiosk`    | Kiosk Mode (Device token authenticated)       |
| `http://localhost:5000/api/docs` | Interactive Swagger API Documentation        |
| `http://localhost:631`           | CUPS Printer Server Admin                    |

---

## ⚙️ Environment Variables

| Variable                  | Default               | Description                                           |
| ------------------------- | --------------------- | ----------------------------------------------------- |
| `SECRET_KEY`              |                       | Flask secret key                                      |
| `AUTHENTIK_CLIENT_ID`     |                       | Authentik OAuth client ID                             |
| `AUTHENTIK_CLIENT_SECRET` |                       | Authentik OAuth client secret                         |
| `AUTHENTIK_METADATA_URL`  |                       | OpenID Connect discovery URL                          |
| `LDAP_ENABLED`            | `false`               | Enable Active Directory / LDAP authentication         |
| `LDAP_HOST`               |                       | Active Directory server IP / hostname                 |
| `LDAP_PORT`               | `389`                 | LDAP port (389 for LDAP, 636 for LDAPS)               |
| `LDAP_BASE_DN`            |                       | Active Directory Base DN (e.g. `DC=domain,DC=local`)   |
| `LDAP_BIND_DN`            |                       | Service Account Bind DN                               |
| `LDAP_BIND_PASSWORD`      |                       | Service Account password                              |
| `LDAP_DOMAIN`             |                       | AD DNS domain used to normalize CUPS/LDAP identities  |
| `LDAP_AD_DOMAIN_SID`      |                       | AD domain SID required for Debian/Ubuntu host CUPS auth |
| `LDAP_TLS_REQCERT`        | `demand`              | LDAP TLS certificate policy for host CUPS authentication |
| `SAMBA_ENABLED`           | `false`               | Create an AD-authenticated Windows SMB print share       |
| `SAMBA_REALM`             |                       | AD DNS realm, for example `echo.story`                   |
| `SAMBA_WORKGROUP`         |                       | AD NetBIOS name, for example `ECHO`                      |
| `SAMBA_HOSTNAME`          |                       | Stable PrintQ FQDN inside the AD realm                   |
| `SAMBA_JOIN_USER`         | `Administrator`       | AD account used interactively to join the server         |
| `SAMBA_SHARE_NAME`        | `PrintQ`              | Windows printer share name                               |
| `SAMBA_WINDOWS_QUEUE`     | `<printer>_windows`   | Dedicated locally submitted held CUPS queue              |
| `AIRPRINT_READY_PAPER_SIZES` | common HP sizes   | Sizes reported ready when a USB/HPLIP tray cannot sense media |
| `AIRPRINT_DUPLEX`         | `false`               | Advertise hardware duplex capability to AirPrint          |
| `AIRPRINT_PAPER_MAX`      | `legal-A4`            | AirPrint maximum-paper classification                     |
| `PRINTER_NAME`            | `HP_Smart_Tank_515`   | Target CUPS printer name (must match actual CUPS printer name, e.g. `lpstat -p`) |
| `CUPS_USER`               | `print`               | CUPS service account used by the web application      |
| `CUPS_PASSWORD`           | `print`               | CUPS service password; change this before deployment  |
| `AUTO_PRINT_QR_UPLOADS`   | `true`                | Print QR-page files/photos/A4 immediately; dashboard upload paths remain held |
| `COLLABORA_ENABLED`       | `false`               | Enable the Collabora Office editor                     |
| `COLLABORA_URL`           |                       | Browser-facing Collabora URL                           |
| `COLLABORA_INTERNAL_URL`  |                       | Optional LAN URL used to fetch Collabora discovery     |
| `WOPI_PUBLIC_URL`         |                       | PrintQ URL reachable from the Collabora container      |
| `WOPI_TOKEN_TTL`          | `14400`               | Signed WOPI editor-token lifetime in seconds           |
| `ADMIN_GROUPS`            | `admins,print-admins` | Admin group names (comma-separated)                   |
| `ADMIN_USERS`             | `admin`               | Admin usernames (comma-separated)                     |

---

## 🗺️ Roadmap

These are planned or exploratory directions, not committed release dates:

- **Multiple-printer support** — manage several queues, capabilities, locations,
  routing rules, defaults, and per-printer permissions from one PrintQ server.
- **Generic and vendor-specific drivers** — prefer driverless IPP Everywhere
  where possible, while investigating optional PPD/backend packages for specific
  brands and models whose advanced features require a manufacturer driver.
- **Home Assistant and observability integrations** — expose printer/job health
  through webhooks, MQTT, Prometheus-compatible metrics, and dashboards suitable
  for Home Assistant and Grafana.
- **Distributed PrintQ agent** — a lightweight, mostly Linux edge agent for
  Raspberry Pi and similar devices, connecting local USB/network printers to a
  centralized PrintQ management server with health, capability, and job-status
  reporting.
- **Externally accessible paid guest printing** — expose only the QR workflow
  through a protected Cloudflare path, then authorize printing after PromptPay
  or Stripe payment. Direct printing must remain disabled externally until this
  authorization boundary exists.

---

## 📚 Guides & Documentation

- 🐳 **[DOCKER_GUIDE.md](DOCKER_GUIDE.md)** — Comprehensive Docker deployment and container orchestration guide.
- 📱 **[CLIENT_PRINT_GUIDE.md](CLIENT_PRINT_GUIDE.md)** — Step-by-step setup for Windows, Mac, Linux, iOS/iPadOS, and Android clients.
- 🖥️ **[BARE_METAL_AND_LXC_GUIDE.md](BARE_METAL_AND_LXC_GUIDE.md)** — Guide for installing PrintQ on bare-metal Linux or LXC containers.

The bare-metal installer supports Ubuntu, Debian, Fedora, CentOS Stream, and AlmaLinux. It automatically selects `apt-get`/`nslcd` on Debian-family systems and `dnf`/SSSD on RHEL-family systems.

On EL10, LibreOffice is optional because it is no longer included in the base repositories. PrintQ still installs normally; PDF/image printing and Collabora editing work without the local LibreOffice converter.

---

## 📄 License

MIT
