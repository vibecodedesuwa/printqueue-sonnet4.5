# 🐳 Docker Deployment & Operation Guide — PrintQ

This guide details how to deploy, configure, and maintain **PrintQ (Print Queue Manager)** using **Docker** and **Docker Compose**, migrating from LXC to a modern containerized environment.

---

## 📌 1. Architecture Overview

PrintQ runs as a multi-container Docker Compose application on a Linux host (host networking is used for CUPS and LAN printer discovery):

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 Client Devices & Browsers              │
                  │ (Windows, Mac, Linux, iOS/iPadOS, Android, Mobile QR) │
                  └───────────────────────────┬────────────────────────────┘
                                              │
                    ┌─────────────────────────┴────────────────────────┐
                    │               Docker Host Network                │
                    │                                                  │
                    │   ┌──────────────────────────────────────────┐   │
                    │   │ PrintQ Container (Flask Web App & API)  │   │
                    │   │ - Port 5000                              │   │
                    │   │ - Dual Auth: Authentik SSO & AD (LDAP)   │   │
                    │   │ - Multi-lingual (EN/TH) & A4 Quick Edit │   │
                    │   │ - QR Code Upload & Claim System          │   │
                    │   └────────────────────┬─────────────────────┘   │
                    │                        │                         │
                    │                        │ Authenticated CUPS API  │
                    │                        ▼                         │
                    │   ┌──────────────────────────────────────────┐   │
                    │   │ CUPS Container (Server & Spooler)        │   │
                    │   │ - Port 631 (IPP)                         │   │
                    │   │ - Port 5353/udp (mDNS Avahi AirPrint)    │   │
                    │   └────────────────────┬─────────────────────┘   │
                    └────────────────────────┼─────────────────────────┘
                                             │
                                             ▼
                               ┌──────────────────────────┐
                               │     Physical Printer     │
                               │ (USB / Network IPP/LPD)  │
                               └──────────────────────────┘
```

---

## 🚀 2. Quick Start

### Step 1: Clone Repository & Create Environment File

```bash
git clone <repo-url>
cd printqueue-sonnet4.5

# Copy default environment configuration
cp .env.example .env
```

### Step 2: Configure Environment Variables (`.env`)

Edit `.env` to match your environment:

```env
SECRET_KEY=generate-a-strong-random-key

# Authentik SSO (OIDC)
AUTHENTIK_CLIENT_ID=your-client-id
AUTHENTIK_CLIENT_SECRET=your-client-secret
AUTHENTIK_METADATA_URL=https://authentik.your-domain.com/application/o/printq/.well-known/openid-configuration

# Active Directory (LDAP) - Set LDAP_ENABLED=true
LDAP_ENABLED=true
LDAP_HOST=ad.company.com
LDAP_PORT=389
LDAP_USE_SSL=false
LDAP_BASE_DN=DC=company,DC=com
LDAP_BIND_DN=CN=print-service,OU=ServiceAccounts,DC=company,DC=com
LDAP_BIND_PASSWORD=SuperSecretPassword
LDAP_DOMAIN=company.com

# CUPS web/application service account
CUPS_USER=print
CUPS_PASSWORD=replace-with-a-strong-password

# Printer Settings
PRINTER_NAME=HP_Smart_Tank_515

# Admin Users & Groups
ADMIN_GROUPS=admins,print-admins,Domain Admins
ADMIN_USERS=admin
```

### Step 3: Launch Containers

```bash
docker compose up -d --build
```

Verify running containers:

```bash
docker compose ps
```

---

## 🔐 3. Authentication Setup

PrintQ supports **Dual Authentication**:

### 1. Authentik SSO (OIDC)
- Configured via `AUTHENTIK_CLIENT_ID`, `AUTHENTIK_CLIENT_SECRET`, and `AUTHENTIK_METADATA_URL`.
- Click **"Login with EchoStory"** on the landing page for single sign-on with RP-Initiated Logout.

### 2. Active Directory (LDAP)
- Configured via `LDAP_ENABLED=true` and `LDAP_HOST`.
- Users log in using their Active Directory credentials directly from the landing page or login modal.
- CUPS owners such as `COMPANY\\alice` and `alice@company.com` are automatically bound to the web account `alice`; no manual device mapping is needed.

### 3. Require Active Directory credentials in CUPS (optional)

The normal compose file supports app-side LDAP login and identity binding. To make the printer itself validate every IPP login against AD, the Linux Docker host must already be domain-joined with SSSD:

```bash
getent passwd 'alice@company.com'
docker compose -f docker-compose.yml -f docker-compose.ad.yml up -d --build
docker exec cups-server setup-airprint
```

The AD overlay shares only the host SSSD responder sockets and Kerberos configuration with CUPS. The setup command assigns the `authenticated` CUPS policy and the indefinite hold default to `PRINTER_NAME`. If `getent` fails on the host, fix the host domain join before starting the overlay.

> CUPS Basic authentication should only be exposed on a trusted network unless TLS is configured. For Kerberos/Negotiate environments, adapt the supplied CUPS policy to `AuthType Negotiate`.

---

## 📱 4. Multi-Platform & Smartphone Client Setup

### 🤖 Android (Smartphone / Tablet)
1. **Option A — QR Code Quick Upload (Recommended)**:
   - Scan the QR code displayed on the Kiosk screen or Dashboard with your camera.
   - Tap **Choose File** or **Take Photo** to upload PDF/Images directly from your mobile device into the print queue.
2. **Option B — Mopria Print Service / Default Print Service**:
   - Install **Mopria Print Service** from Google Play Store.
   - Connect to the same Wi-Fi network.
   - Go to System Settings → Printing → Add Printer → IPP `http://<server-ip>:631/printers/HP_Smart_Tank_515`.
   - Once printed, log into the Web Dashboard to **Claim** & **Release** your print job.

### 📱 iOS / iPadOS (iPhone / iPad)
1. **AirPrint Zero-Config**:
   - Run setup AirPrint script inside CUPS container:
     ```bash
     docker exec cups-server setup-airprint
     ```
   - Select **Print** in any iOS app → Select printer.
2. **QR Code Quick Upload**:
   - Open iOS Camera app → Scan PrintQ QR Code → Upload document/photo directly.

### 💻 Windows 10/11 & macOS & Linux
- Add network printer using IPP URL: `http://<server-ip>:631/printers/<PRINTER_NAME>`.

---

## 🙋 5. Job Claiming & Release Permission Fix

PrintQ uses a **Hold & Release** queue to prevent wasted paper.

If a job is submitted via AirPrint, Mopria, Web Upload, or Email:
1. The job is placed in **Held** status.
2. If submitted anonymously or via generic device name (e.g. `iPhone`), it appears in the **Unclaimed Jobs Pool**.
3. Log into the Web Dashboard, find your job in **Unclaimed Jobs**, and click **Claim**.
4. Click **Print & Release** to authorize printing.

> **Permission note**: The authorization engine normalizes AD identity variants and verifies the signed-in user against the CUPS owner, claim owner, submitted owner, or an explicit device mapping.

---

## 📄 6. Collabora Office and A4 Editors

PrintQ can use Collabora Online as a full Writer interface and retains the lightweight editor as an offline fallback:
- Access via **A4 Editor** in navbar (`/editor`).
- Create Thai-ready ODT documents or open existing ODT/DOCX files.
- Collabora saves through PrintQ's signed WOPI endpoints; **Save & Print** converts the saved document to PDF and submits it to CUPS.
- Rich text formatting (headings, fonts, bold/italic, alignment, image insertion).
- Live A4 page canvas (210mm x 297mm).
- Click **Print A4 Document** to convert canvas into PDF and submit directly to CUPS.

For the supplied TrueNAS Collabora instance, add this to `.env`:

```env
COLLABORA_ENABLED=true
COLLABORA_URL=https://office.toonshou.in
COLLABORA_INTERNAL_URL=http://172.16.0.9:9980
WOPI_PUBLIC_URL=https://printq.your-domain.com
```

`WOPI_PUBLIC_URL` must resolve to PrintQ from inside the Collabora container. Do not use `localhost`. Add the PrintQ hostname to Collabora's WOPI host allow-list. For reliable Thai rendering, install Noto Sans Thai on the Collabora host or expose it through Collabora's remote font configuration; the PrintQ container installs Noto and TLWG Thai fonts automatically.

---

## 🌐 7. Multi-Lingual Support (Thai & English)

Switch languages anytime using the language selector (🇺🇸 EN / 🇹🇭 TH) in the top navbar:
- Preserves preference in `localStorage` and cookies.
- Translates UI labels, status messages, tables, and modal dialogs dynamically.

---

## 🛠️ 8. Troubleshooting & Maintenance

### Check Logs
```bash
docker compose logs -f print-queue-manager
docker compose logs -f cups
```

### Restart Services
```bash
docker compose restart
```

### CUPS Web Interface
Access CUPS at `http://<server-ip>:631` with `CUPS_USER` and `CUPS_PASSWORD` from `.env` (default user: `print`).
