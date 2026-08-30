# Print Queue Manager — Bare-Metal Linux & LXC Setup Guide

Complete guide to install and configure PrintQ on Ubuntu, Debian, Fedora, CentOS Stream, or AlmaLinux. Proxmox LXC is supported with a Debian/Ubuntu guest. Includes Active Directory (AD) authentication for IPP printing (Android/iOS).

This guide has two paths:
- **Part A: Automated Installation** — Run `install.sh` and follow the interactive prompts
- **Part B: Manual Installation** — Step-by-step for full control or troubleshooting

---

## 📋 Prerequisites

- A supported systemd-based server: Ubuntu, Debian, Fedora, CentOS Stream, or AlmaLinux
- Or a Proxmox server with a Debian/Ubuntu LXC guest
- Authentik instance running and accessible (or Active Directory for AD-only auth)
- Your printer connected via USB or network to the host/container
- (Optional) Active Directory server if you want AD-authenticated IPP printing

---

# Part A: Automated Installation (`install.sh`)

The automated installer handles everything interactively. It will:
1. Install system packages (CUPS, Python, Avahi, LibreOffice, etc.)
2. Configure CUPS for network printing
3. Set up the application directory and Python virtualenv
4. Ask you to configure `.env` (printer name, SSO, AD/LDAP settings)
5. Set up your printer (with optional HP-specific tools)
6. Configure AD authentication for CUPS if `LDAP_ENABLED=true`
7. Set up AirPrint/Mopria mDNS discovery
8. Install and start the systemd service

## A.1 — LXC Container Preparation (Skip for Bare-Metal)

If you are using an LXC container, create and configure it first:

```bash
# In Proxmox web interface:
# 1. Click "Create CT"
# 2. Configure:
#    - CT ID: 100 (or your choice)
#    - Hostname: print-server
#    - Template: Ubuntu 22.04 or Debian 12
#    - Root password: Set a secure password
#    - Disk: 16 GB minimum (LibreOffice + uploads need space)
#    - CPU: 2 cores
#    - Memory: 2048 MB
#    - Network: Bridge to your network (vmbr0)
#    - Check "Unprivileged container" = NO (needed for printer access)
```

```bash
# On Proxmox host, edit the container config for USB printer passthrough
nano /etc/pve/lxc/100.conf

# Add these lines at the end:
lxc.cgroup2.devices.allow: c 180:* rwm
lxc.cgroup2.devices.allow: c 189:* rwm
lxc.mount.entry: /dev/bus/usb dev/bus/usb none bind,optional,create=dir

# Start and enter the container
pct start 100
pct enter 100
```

## A.2 — Download & Run

```bash
git clone <repo-url>
cd printqueue-sonnet4.5
sudo bash install.sh
```

The script will:
1. Install packages
2. Configure CUPS
3. Copy application files to `/opt/print-queue-manager`
4. Set up Python virtualenv
5. **Open `nano` for you to edit `.env`** — this is where you set:
   - `PRINTER_NAME` — your CUPS printer name (the script shows available printers)
   - Authentik SSO settings
   - `LDAP_ENABLED=true` and LDAP settings (if using AD)
6. Set up your printer (asks if it's HP or generic)
7. If `LDAP_ENABLED=true` → runs `setup-cups-ldap.sh` to configure AD auth for CUPS
8. Set up AirPrint/Mopria
9. Start the service

## A.3 — Post-Install

1. **Verify the web app**: Open `http://<server-ip>:5000`
2. **Verify printer status**: `lpstat -p`
3. **Test AD auth** (if enabled): `getent passwd <ad-username>`
4. **Test from Android/iOS**: Print a document — should prompt for AD credentials
5. **Set up kiosk, device mappings, etc.** — see Part B.9 below

---

# Part B: Manual Installation (Step-by-Step)

For users who want full control, are customizing the setup, or are troubleshooting.

> **Tip:** Each step notes when `install.sh` automates it.

## B.1 — System Dependencies

> *`install.sh` automates this in Step 1.*

**Debian / Ubuntu:**

```bash
apt update && apt upgrade -y

apt install -y \
    cups \
    cups-client \
    cups-bsd \
    printer-driver-all \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libcups2-dev \
    gcc \
    git \
    curl \
    nano \
    avahi-daemon \
    avahi-utils \
    libreoffice-writer \
    fonts-noto-core \
    fonts-thai-tlwg \
    libmagic1
```

**Fedora / CentOS Stream / AlmaLinux:**

```bash
dnf upgrade -y
dnf install -y \
    cups cups-client cups-devel cups-filters \
    python3 python3-pip python3-devel \
    gcc git curl nano openssl \
    avahi avahi-tools file-libs

# Font package availability varies by enabled repositories.
dnf install -y google-noto-sans-fonts google-noto-sans-thai-fonts || true

# Optional on Fedora and EL8/EL9; this package was removed from EL10.
dnf install -y libreoffice-writer || true
```

> **Package notes:**
> - `avahi-daemon` + `avahi-utils` — AirPrint/Mopria device discovery via mDNS
> - `libreoffice-writer` — DOCX → PDF conversion for uploaded documents
> - `fonts-noto-core` + `fonts-thai-tlwg` — reliable Thai shaping in office-to-PDF conversion
> - `libmagic1` — File type detection for upload validation

> **EL10 note:** RHEL-compatible version 10 distributions do not ship LibreOffice in their base repositories. The automated installer treats it as optional, so PDF/image printing and the Collabora editor remain available. Local DOC/DOCX/ODT-to-PDF conversion requires installing LibreOffice separately from an upstream-supported source.

---

## B.2 — Configure CUPS

> *`install.sh` automates this in Step 2.*

```bash
systemctl enable cups
systemctl start cups

cupsctl --remote-any
cupsctl --share-printers
cupsctl WebInterface=yes

# Install the supplied policy configuration
cp /opt/print-queue-manager/config/cupsd.conf /etc/cups/cupsd.conf
cupsd -t
systemctl restart cups
```

The automated installer waits for the scheduler on `localhost:631` and displays `systemctl`/journal diagnostics if it cannot start. On systems running firewalld, it also opens IPP, mDNS, and TCP port 5000.

---

## B.3 — Install & Configure Your Printer

> *`install.sh` automates this in Step 6.*

### List available printers

```bash
# See what printers CUPS knows about
lpstat -p

# If your printer is USB-connected, check it's detected
lsusb
```

### Add your printer (if not already in CUPS)

**Option 1: CUPS Web UI**
- Go to `http://<server-ip>:631/admin`
- Click "Add Printer" and follow the wizard

**Option 2: Command line**
```bash
# For a network printer (IPP):
lpadmin -p MY_PRINTER -v ipp://printer-ip/ipp/print -E

# For a USB printer:
lpadmin -p MY_PRINTER -v usb://Manufacturer/Model -E
```

**Option 3: HP printers (optional)**
```bash
# Debian / Ubuntu
apt install -y hplip

# Fedora / CentOS Stream / AlmaLinux
dnf install -y hplip
hp-setup -i
```

### Configure printer for hold-and-approve workflow

Replace `YOUR_PRINTER_NAME` with your actual CUPS printer name:

```bash
# Hold all jobs by default and enable sharing
lpadmin -p YOUR_PRINTER_NAME \
    -o job-hold-until-default=indefinite \
    -o printer-is-shared=true

# Enable the printer
cupsenable YOUR_PRINTER_NAME
cupsaccept YOUR_PRINTER_NAME

# Make it the default printer (optional)
lpadmin -d YOUR_PRINTER_NAME

# Verify
lpstat -p YOUR_PRINTER_NAME
```

> **Note:** The printer policy (`default` vs `authenticated`) will be set in Step B.4 depending on whether AD is enabled.

---

## B.4 — Configure AD Authentication for CUPS (Optional)

> *`install.sh` automates this in Step 7 when `LDAP_ENABLED=true`.*

This step configures CUPS to authenticate IPP print requests against Active Directory. Compatible AirPrint/Mopria/Linux/macOS clients can prompt for an AD username and password. The Microsoft IPP Class Driver does not reliably prompt for CUPS HTTP Basic credentials; Windows requires a Samba AD share, Kerberos/Negotiate, or a separate trusted unauthenticated queue.

**Skip this section if you don't use Active Directory.**

### Option 1: Automated (recommended)

```bash
# Make sure .env is configured with LDAP settings first
cd /opt/print-queue-manager
sudo bash scripts/setup-cups-ldap.sh
```

### Option 2: Manual

#### Debian / Ubuntu: install PAM/NSS LDAP packages

```bash
DEBIAN_FRONTEND=noninteractive apt install -y nslcd libnss-ldapd libpam-ldapd
```

#### Configure nslcd

```bash
nano /etc/nslcd.conf
```

```ini
uid nslcd
gid nslcd

uri ldap://ad.domain.local:389
base DC=domain,DC=local

binddn CN=print-service,OU=Services,DC=domain,DC=local
bindpw your-ad-service-password

# Active Directory attribute mappings
pagesize 1000
referrals off
filter passwd (&(objectClass=user)(!(objectClass=computer))(sAMAccountName=*))
map passwd uid sAMAccountName
map passwd uidNumber objectSid:S-1-5-21-YOUR-REAL-DOMAIN-SID
map passwd gidNumber objectSid:S-1-5-21-YOUR-REAL-DOMAIN-SID
map passwd homeDirectory "/home/$sAMAccountName"
map passwd loginShell "/bin/false"
map passwd gecos displayName

filter group (objectClass=group)
map group cn sAMAccountName
map group gidNumber objectSid:S-1-5-21-YOUR-REAL-DOMAIN-SID

ssl off
tls_reqcert never
```

For production LDAPS, change `tls_reqcert` to `demand` and install your AD CA certificate in the system trust store.

The domain SID must be the real value for your AD domain, not a placeholder. Retrieve it from an AD management host with `(Get-ADDomain).DomainSID.Value` in PowerShell and set `LDAP_AD_DOMAIN_SID` in `.env` when using Debian/Ubuntu.

```bash
chmod 600 /etc/nslcd.conf
```

#### Update NSS

```bash
# Add ldap to nsswitch.conf
sed -i -E '/^(passwd|group|shadow):/ { /(^|[[:space:]])ldap([[:space:]]|$)/! s/$/ ldap/; }' /etc/nsswitch.conf
```

#### Restart services

```bash
systemctl enable nslcd
systemctl restart nslcd
systemctl restart cups
```

#### Fedora / CentOS Stream / AlmaLinux: use SSSD

RHEL-family systems use SSSD instead of the removed `nss-pam-ldapd` stack. The automated `setup-cups-ldap.sh` script installs `sssd-ldap`, writes a protected SSSD configuration, and selects the SSSD `authselect` profile. When `LDAP_USE_SSL=false`, the script uses StartTLS because SSSD does not permit password authentication over an unencrypted LDAP connection.

Set `LDAP_TEST_USER` to a real AD `sAMAccountName`. The setup script verifies the LDAP bind and search base before changing SSSD, validates the generated configuration, checks that the domain is online, and confirms that this test account resolves through NSS.

If the machine is already joined to AD/IdM or has a custom `/etc/sssd/sssd.conf`, the script refuses to overwrite it. In that case, verify `getent passwd <ad-user>` works and only apply the CUPS policy:

```bash
lpadmin -p YOUR_PRINTER_NAME -o printer-op-policy=authenticated
systemctl restart cups
```

#### Set printer policy to require authentication

```bash
lpadmin -p YOUR_PRINTER_NAME -o printer-op-policy=authenticated
```

#### Test AD user resolution

```bash
getent passwd <your-ad-username>
# Should return user info from AD
```

> **If AD is NOT enabled**, set the default policy instead:
> ```bash
> lpadmin -p YOUR_PRINTER_NAME -o printer-op-policy=default
> ```

### B.4.1 — Windows AD Printing with Samba/Winbind

The Microsoft IPP Class Driver does not reliably handle CUPS HTTP Basic credential prompts. PrintQ therefore provides an optional Samba domain-member path for Windows. Samba authenticates the signed-in Windows domain user and submits the job locally into a separate held CUPS queue; the original queue keeps its authenticated IPP policy for AirPrint/Mopria.

Prerequisites:

- The PrintQ server must use the AD DNS server.
- Time must be synchronized with the domain.
- The server needs a stable FQDN inside the AD realm, such as `printq.echo.story`.
- An AD account must have permission to join a computer to the domain.
- Windows clients must have a suitable local driver for the physical printer.

Configure `.env`:

```env
SAMBA_ENABLED=true
SAMBA_REALM=echo.story
SAMBA_WORKGROUP=ECHO
SAMBA_HOSTNAME=printq.echo.story
SAMBA_JOIN_USER=Administrator
SAMBA_SHARE_NAME=PrintQ
SAMBA_WINDOWS_QUEUE=es_non01_st515_01_windows
LDAP_TEST_USER=kritthapath
```

`LDAP_TEST_USER` accepts a short `sAMAccountName`, a UPN such as
`nromeiio@echo.story`, or a NetBIOS-qualified name such as
`ECHOSTORY\nromeiio`. The setup script automatically tries the qualified forms
when Winbind does not expose short-name aliases.

Run on an existing installation—no reinstall is required:

```bash
cd /opt/print-queue-manager
sudo bash scripts/setup-windows-samba.sh
```

If `/opt/print-queue-manager` was copied by an older installer and is not a Git
checkout, update your original clone with `git pull`, then copy the updated
`scripts` directory and `install.sh` into `/opt/print-queue-manager` before
running the command. Existing application data and the database are not removed.

The domain join prompts for the join account password; it is not stored in `.env`. On RHEL-family systems, the script switches host PAM/NSS integration from SSSD to Winbind because Winbind is the supported identity provider for a Samba AD-member server. The web application's direct LDAP login remains unchanged.

Verify:

```bash
sudo net ads testjoin
sudo wbinfo --check-secret
getent passwd kritthapath
lpstat -p es_non01_st515_01_windows
sudo testparm -s
```

Connect Windows to:

```text
\\printq.echo.story\PrintQ
```

Remove the old authenticated IPP printer from Windows first. If Windows cannot
attach the share because PrintQ does not host a Windows driver, install the
physical printer's vendor driver and create a **Local Port** whose name is the
same UNC path. See `CLIENT_PRINT_GUIDE.md` for the click-by-click procedure.

If Windows printer actions are slow, compare `time id 'DOMAIN\\user'` with
`time wbinfo --user-groups='DOMAIN\\user'` and inspect the Samba journal. The
generated configuration includes a hidden `[printers]` template for
`samba-bgqd`, keeps SPOOLSS workers warm for five minutes, and caches CUPS
printer and queue queries. Re-run `setup-windows-samba.sh` after updating to
apply these settings to an existing server.

---

## B.5 — Install PrintQ Web App

> *`install.sh` automates this in Steps 3-4.*

```bash
mkdir -p /opt/print-queue-manager
cd /opt/print-queue-manager

git clone <repo-url> .

mkdir -p data/uploads data/office

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## B.6 — Configure .env

> *`install.sh` automates this in Step 5.*

```bash
cp .env.example .env
nano .env
```

Key settings to configure:

```bash
# Must match your CUPS printer name (from lpstat -p)
PRINTER_NAME=YOUR_PRINTER_NAME

# Authentik SSO (required for SSO login)
AUTHENTIK_CLIENT_ID=your-client-id
AUTHENTIK_CLIENT_SECRET=your-client-secret
AUTHENTIK_METADATA_URL=https://authentik.your-domain.com/application/o/printq/.well-known/openid-configuration

# Active Directory / LDAP (set LDAP_ENABLED=true to activate)
# These are used by BOTH the web app AND CUPS IPP authentication
LDAP_ENABLED=false
LDAP_HOST=ad.domain.local
LDAP_PORT=389
LDAP_BASE_DN=DC=domain,DC=local
LDAP_BIND_DN=CN=print-service,OU=Services,DC=domain,DC=local
LDAP_BIND_PASSWORD=your-ad-password
LDAP_DOMAIN=domain.local
LDAP_TEST_USER=an-ad-samaccountname
LDAP_AD_DOMAIN_SID=S-1-5-21-your-real-domain-sid
LDAP_TLS_REQCERT=demand

# CUPS service account (used by the web app — always needed)
CUPS_USER=print
CUPS_PASSWORD=change-this-cups-password

# Admin users and groups
ADMIN_GROUPS=admins,print-admins
ADMIN_USERS=admin
```

---

## B.7 — AirPrint/Mopria Setup

> *`install.sh` automates this in Step 8.*

```bash
systemctl enable avahi-daemon
systemctl start avahi-daemon

cd /opt/print-queue-manager
export PRINTER_NAME=YOUR_PRINTER_NAME
bash scripts/setup-airprint.sh
```

After this, iOS (AirPrint), Android (Mopria/Default Print Service), and macOS will auto-discover the printer.

---

## B.8 — Systemd Service

> *`install.sh` automates this in Step 9.*

```bash
cat > /etc/systemd/system/print-queue-manager.service << 'EOF'
[Unit]
Description=Print Queue Manager
After=network.target cups.service avahi-daemon.service
Requires=cups.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/print-queue-manager
Environment=PATH=/opt/print-queue-manager/venv/bin:/usr/bin:/bin
EnvironmentFile=/opt/print-queue-manager/.env
ExecStart=/opt/print-queue-manager/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable print-queue-manager
systemctl start print-queue-manager
systemctl status print-queue-manager
```

---

## B.9 — Firewall & Network

```bash
# Allow CUPS web interface + IPP printing
ufw allow 631/tcp
ufw allow 631/udp

# Allow Print Queue Manager
ufw allow 5000/tcp

# Allow mDNS (AirPrint/Mopria device discovery)
ufw allow 5353/udp
```

### Optional: Nginx Reverse Proxy

```bash
apt install -y nginx
```

```nginx
# /etc/nginx/sites-available/print-queue
server {
    listen 80;
    server_name print.yourdomain.com;

    client_max_body_size 50M;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /sw.js {
        proxy_pass http://localhost:5000/static/sw.js;
        add_header Service-Worker-Allowed "/";
    }
}
```

```bash
ln -s /etc/nginx/sites-available/print-queue /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx
```

---

## B.10 — Configure Client Devices

### iPhone / iPad (AirPrint — Zero Config)

The printer auto-appears in the Print dialog. If AD is enabled, AirPrint will prompt for credentials. See `CLIENT_PRINT_GUIDE.md` for details.

### Android (Mopria)

Android 8+ auto-discovers via Default Print Service. If AD is enabled, the phone will prompt for AD username/password. See `CLIENT_PRINT_GUIDE.md`.

### Windows

The command below is suitable for a printer policy that does not require HTTP Basic authentication. The Microsoft IPP Class Driver may install an authenticated queue but then fail to submit because it does not reliably display a CUPS Basic credential prompt. Use Samba for seamless Windows AD authentication.

```powershell
# Add printer via IPP (replace YOUR_PRINTER_NAME with your actual printer name)
Add-Printer -Name "Print Queue" -ConnectionName "http://<server-ip>:631/printers/YOUR_PRINTER_NAME"
```

Or manually: Settings → Printers → Add → "The printer I want isn't listed" → `http://<server-ip>:631/printers/YOUR_PRINTER_NAME`

### macOS

System Settings → Printers & Scanners → Add (+) → IP tab → `<server-ip>` → Queue: `printers/YOUR_PRINTER_NAME`

### Linux

```bash
lpadmin -p PrintQ -v ipp://<server-ip>:631/printers/YOUR_PRINTER_NAME -E
```

### Web Upload & Email Print

See `CLIENT_PRINT_GUIDE.md` for web upload, QR code, and email print instructions.

---

## B.11 — Initial Setup After First Login

### Create API Keys
1. Log in as admin at `http://<server-ip>:5000`
2. Go to **Admin** → **API Keys** tab → **+ New Key**

### Map Devices (Claim System)

> **Note:** When AD is enabled, IPP jobs are automatically bound to the AD username. Device mapping is primarily useful when AD is **not** enabled.

1. Print a test page from your phone
2. Check **Admin** → **All Jobs** for the CUPS username
3. Go to **Admin** → **Device Mapping** → **+ Add Mapping**

### Set Up Kiosk Mode
1. Go to **Admin** → **Kiosks** → **Register New**
2. Open the registration URL on the kiosk device's browser

---

## B.12 — Testing

### Test Print Flow

```bash
# Print a test document
echo "Test print from $(hostname)" | lpr -P YOUR_PRINTER_NAME

# Check the web dashboard: http://<server-ip>:5000
# The job should appear as "Held"
# Click "Release" to print
```

### Test AD Authentication (if enabled)

```bash
# Debian / Ubuntu
systemctl status nslcd

# Fedora / CentOS Stream / AlmaLinux
systemctl status sssd

# Verify AD user resolution
getent passwd <ad-username>

# Print from Android/iOS — should prompt for AD credentials
```

### Test AirPrint Discovery

```bash
avahi-browse -t _ipp._tcp
```

### Test API

```bash
curl http://localhost:5000/api/v1/health
curl -H "Authorization: Bearer pq_your-api-key" http://localhost:5000/api/v1/jobs
```

---

## B.13 — Troubleshooting

### Common Issues

**Printer not found:**
```bash
lpstat -p -d
lsusb                  # for USB printers
systemctl restart cups
```

**`cupsctl: Host is down`:**
```bash
systemctl enable --now cups
systemctl status cups --no-pager -l
journalctl -u cups --no-pager -n 50
lpstat -h localhost -r
```

If `lpstat -h localhost -r` works but plain `lpstat -r` does not, check `/etc/cups/client.conf` and the `CUPS_SERVER` environment variable for an old remote server setting.

**AirPrint not discovered on iOS/Android:**
```bash
systemctl status avahi-daemon
ls /etc/avahi/services/
ss -ulnp | grep 5353
systemctl restart avahi-daemon
```

**AD authentication not working:**
```bash
# Debian / Ubuntu
systemctl status nslcd
journalctl -u nslcd -n 20
nslcd -d                      # Run in debug mode (stop service first)
cat /etc/nslcd.conf           # Verify settings

# Fedora / CentOS Stream / AlmaLinux
systemctl status sssd
journalctl -u sssd -n 50
sssctl config-check

# All supported distributions
getent passwd <ad-username>   # Should return user info
```

**AD credential prompt not appearing on Android/iOS:**
```bash
# Verify printer policy is set to 'authenticated'
lpoptions -p YOUR_PRINTER_NAME | grep -o 'printer-op-policy=[a-z]*'

# Should show: printer-op-policy=authenticated
# If not, set it:
lpadmin -p YOUR_PRINTER_NAME -o printer-op-policy=authenticated
systemctl restart cups
```

**Jobs not appearing in queue:**
```bash
tail -f /var/log/cups/error_log
lpstat -o
```

**Web app login fails:**
```bash
journalctl -u print-queue-manager -f
cat /opt/print-queue-manager/.env
```

**Database errors:**
```bash
ls -la /opt/print-queue-manager/data/printqueue.db

# Reset database (⚠️ deletes all API keys and mappings)
rm /opt/print-queue-manager/data/printqueue.db
systemctl restart print-queue-manager
```

---

## B.14 — Monitoring & Maintenance

### View Logs

```bash
journalctl -u print-queue-manager -f        # Real-time
journalctl -u print-queue-manager --since today
tail -f /var/log/cups/error_log              # CUPS logs
journalctl -u nslcd -f                       # AD logs: Debian/Ubuntu
journalctl -u sssd -f                        # AD logs: RHEL-family
```

### Backup

```bash
tar -czf print-queue-backup-$(date +%Y%m%d).tar.gz \
    /opt/print-queue-manager/data \
    /opt/print-queue-manager/.env \
    /etc/cups \
    /etc/avahi/services

# Also back up the applicable identity configuration:
tar -czf print-queue-identity-backup-$(date +%Y%m%d).tar.gz \
    /etc/nslcd.conf /etc/sssd/sssd.conf 2>/dev/null || true
```

### Update

```bash
cd /opt/print-queue-manager
git pull origin main

source venv/bin/activate
pip install -r requirements.txt

systemctl restart print-queue-manager
```

---

## 🎉 You're Done!

Your print queue management system is now ready! Users can:

1. ✅ Print from any device (iPhone, Android, Windows, macOS, Linux)
2. ✅ Authenticate with AD credentials at the IPP layer on compatible clients (if AD enabled)
3. ✅ Log in with Authentik SSO or Active Directory
4. ✅ See their jobs in the web dashboard
5. ✅ Upload files directly via drag-and-drop or QR code
6. ✅ Print via email
7. ✅ Release/cancel jobs from dashboard or kiosk
8. ✅ Use the REST API for automation
9. ✅ Claim jobs submitted from mobile devices (when AD is off)

**Access URLs:**

| URL                              | Purpose                        |
| -------------------------------- | ------------------------------ |
| `http://<server-ip>:5000`        | Dashboard (SSO/AD login)       |
| `http://<server-ip>:5000/kiosk`  | Kiosk Mode (device token auth) |
| `http://<server-ip>:5000/upload` | Upload & Print                 |
| `http://<server-ip>:5000/api/docs` | API Documentation (Swagger)  |
| `http://<server-ip>:631`         | CUPS Web Interface             |

### Caddy HTTPS reverse proxy

The repository includes a ready-to-use Caddy configuration for
`printq.echo.story`. It sends the main site to PrintQ and exposes the CUPS
printer pages at `/printers/`; `/cups` redirects there.

1. Point the DNS record for `printq.echo.story` at the PrintQ server and allow
   inbound TCP ports 80 and 443.
2. Install Go and `xcaddy`, then build and install the custom AD CS binary. The
   setup script creates the `caddy` service account and systemd unit when no
   distribution package has provided them:

   ```bash
   go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest
   bash scripts/build-caddy-certsrv.sh
   ./caddy-certsrv list-modules | grep tls.issuance.certsrv
   sudo systemctl stop caddy 2>/dev/null || true
   sudo install -m 0755 ./caddy-certsrv /usr/bin/caddy
   sudo restorecon -v /usr/bin/caddy 2>/dev/null || true
   /usr/bin/caddy list-modules | grep tls.issuance.certsrv
   ```

   Do not run `xcaddy` without the `build` subcommand from `~/go/bin`. That is
   plugin-development mode and fails there because the directory has no
   `go.mod`.

3. Run the setup once to create the AD CS environment template:

   ```bash
   sudo bash scripts/setup-caddy.sh
   ```

4. Edit `/etc/caddy/certsrv.env`, place the dedicated AD enrollment account's
   keytab at `/etc/caddy/certsrv.keytab`, and restrict it to the Caddy service:

   ```bash
   sudo chown caddy:caddy /etc/caddy/certsrv.keytab
   sudo chmod 0400 /etc/caddy/certsrv.keytab
   sudo bash scripts/setup-caddy.sh
   ```

The setup backs up an existing `/etc/caddy/Caddyfile`, validates the new file
before reloading Caddy, installs a systemd service for source-built Caddy when
needed, enables trusted proxy headers, and binds PrintQ's port 5000 to localhost
so clients cannot bypass the proxy. On firewalld systems it opens ports 80/443
and removes the old public port-5000 rule.

Then use:

- PrintQ: `https://printq.echo.story/`
- CUPS printers: `https://printq.echo.story/printers/`
- Shortcut: `https://printq.echo.story/cups`

CUPS and PrintQ both define `/admin`, so the proxy preserves `/admin` for
PrintQ. Use `http://<server-ip>:631/admin` for CUPS administration. IPP,
AirPrint, Mopria, and Windows/Samba printing also continue to use their native
ports rather than HTTPS port 443.

If Authentik is enabled, register
`https://printq.echo.story/authorize` as its redirect URI. If Collabora is
enabled, set `WOPI_PUBLIC_URL=https://printq.echo.story` in `.env` and restart
PrintQ.

The supplied TLS configuration uses the `caddy-certsrv` keytab mode. Avoid its
password mode: the plugin's validation code logs its configuration structure,
which can expose a configured password in the Caddy journal. The AD CS URL must
use the certificate server's DNS hostname so Kerberos can resolve the correct
HTTP service principal. The account represented by the keytab must have Enroll
permission for the AD CS `WebServer` certificate template.

The PrintQ build script applies a small patch to the pinned issuer source before
building. It prevents an upstream nil-pointer panic when Kerberos configuration
cannot be loaded, avoids logging the issuer's full configuration, and supports
`CERTSRV_KRB5_CONFIG` when Caddy needs a dedicated Kerberos configuration file.
After updating PrintQ, rebuild and reinstall the binary to receive these fixes.
On EL10, setup automatically creates `/etc/caddy/krb5-certsrv.conf` when the
system file uses `dns_canonicalize_hostname = fallback`; Samba, SSSD, and the
host-wide `/etc/krb5.conf` remain unchanged. Set `CERTSRV_KDCS` in
`/etc/caddy/certsrv.env` to a comma-separated list of AD domain-controller DNS
names or addresses so the older Kerberos client does not depend on DNS SRV
discovery.

`CERTSRV_TEMPLATE` defaults to the AD CS internal template name `WebServer`.
That template must be published by the CA and grant the dedicated Caddy account
Read and Enroll. The patched issuer reports a bounded text summary from AD CS
when a request is denied or left pending instead of returning only “No valid
link found.”

---

## 🆘 Quick Reference

```bash
# Restart all services
systemctl restart cups avahi-daemon print-queue-manager

# Also restart nslcd if AD is enabled
systemctl restart nslcd

# Check printer status
lpstat -p -d

# Check pending jobs
lpstat -o

# Clear all jobs (emergency)
cancel -a

# Check AirPrint advertisement
avahi-browse -t _ipp._tcp

# Test print (replace with your printer name)
echo "Test" | lpr -P YOUR_PRINTER_NAME

# Verify AD user resolution
getent passwd <ad-username>

# API health check
curl http://localhost:5000/api/v1/health
```

## 📚 Additional Resources

- CUPS Documentation: https://www.cups.org/doc/
- Authentik Documentation: https://docs.goauthentik.io/
- HPLIP Documentation: https://developers.hp.com/hp-linux-imaging-and-printing
- Avahi Documentation: https://www.avahi.org/
- nslcd Documentation: https://arthurdejong.org/nss-pam-ldapd/
- Client Setup: See `CLIENT_PRINT_GUIDE.md` in the project root
