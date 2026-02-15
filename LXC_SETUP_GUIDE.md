# Print Queue Manager - LXC Setup Guide

Complete guide to install and configure PrintQ with all features (Kiosk, API, Email Print, AirPrint/Mopria, Claim System) on Proxmox LXC.

## 📋 Prerequisites

- Proxmox server with LXC support
- Authentik instance running and accessible
- HP Smart Tank 515 printer (or similar consumer printer)
- Your printer connected via USB or network to the LXC container

---

## 🚀 Part 1: Create and Configure LXC Container

### 1.1 Create LXC Container in Proxmox

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

### 1.2 Configure LXC for Printer Access

After creating the container, edit its configuration:

```bash
# On Proxmox host, edit the container config
nano /etc/pve/lxc/100.conf

# Add these lines at the end:
lxc.cgroup2.devices.allow: c 180:* rwm
lxc.cgroup2.devices.allow: c 189:* rwm
lxc.mount.entry: /dev/bus/usb dev/bus/usb none bind,optional,create=dir

# Save and exit (Ctrl+X, Y, Enter)
```

### 1.3 Start the Container

```bash
# Start the container
pct start 100

# Enter the container
pct enter 100
```

---

## 🔧 Part 2: Install System Dependencies

### 2.1 Update System

```bash
# Update package lists
apt update && apt upgrade -y

# Install required packages
apt install -y \
    cups \
    cups-client \
    cups-bsd \
    printer-driver-all \
    hplip \
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
    libmagic1
```

> **New dependencies:**
>
> - `avahi-daemon` + `avahi-utils` — AirPrint/Mopria device discovery via mDNS
> - `libreoffice-writer` — DOCX → PDF conversion for uploaded documents
> - `libmagic1` — File type detection for upload validation

### 2.2 Configure CUPS

```bash
# Enable and start CUPS
systemctl enable cups
systemctl start cups

# Allow network access to CUPS
cupsctl --remote-any
cupsctl --share-printers
cupsctl WebInterface=yes

# Add your user to lpadmin group (if needed)
usermod -aG lpadmin root
```

### 2.3 Enable Avahi (mDNS) for AirPrint/Mopria

```bash
# Enable and start Avahi
systemctl enable avahi-daemon
systemctl start avahi-daemon
```

### 2.4 Configure CUPS to Hold All Jobs by Default

```bash
# Edit CUPS configuration
nano /etc/cups/cupsd.conf

# Find the line "<Limit All>" and add this policy:
# Add this section before </Location>

<Location />
  Order allow,deny
  Allow all
</Location>

<Policy default>
  <Limit Send-Document Send-URI Hold-Job Release-Job Restart-Job Purge-Jobs Set-Job-Attributes Create-Job-Subscription Renew-Subscription Cancel-Subscription Get-Subscription-Attributes Get-Subscriptions Get-Notifications Cancel-Jobs Get-Job-Attributes All>
    Require user @SYSTEM
    Order deny,allow
  </Limit>
</Policy>

# Save and restart CUPS
systemctl restart cups
```

---

## 🖨️ Part 3: Install and Configure HP Smart Tank 515

### 3.1 Connect the Printer

```bash
# If USB: Plug in the printer
# Check if detected
lsusb | grep -i hp

# Should see something like:
# Bus 001 Device 003: ID 03f0:xxxx HP, Inc Smart Tank 510 series
```

### 3.2 Install HP Printer Drivers

```bash
# Install HPLIP (HP Linux Imaging and Printing)
apt install -y hplip hplip-gui

# Run HP setup
hp-setup -i

# Follow the interactive prompts:
# 1. Choose "Network" or "USB" depending on your setup
# 2. Select your HP Smart Tank 515
# 3. Choose recommended driver
# 4. Set printer name: HP_Smart_Tank_515
# 5. Enable sharing
```

### 3.3 Configure Printer to Hold Jobs

```bash
# Set printer to hold all jobs by default
lpadmin -p HP_Smart_Tank_515 -o job-hold-until=indefinite

# Enable printer sharing for AirPrint
lpadmin -p HP_Smart_Tank_515 -o printer-is-shared=true

# Make it the default printer
lpadmin -d HP_Smart_Tank_515

# Enable the printer
cupsenable HP_Smart_Tank_515
cupsaccept HP_Smart_Tank_515

# Verify printer status
lpstat -p HP_Smart_Tank_515
```

### 3.4 Setup AirPrint Advertisement

```bash
# Run the included setup script
cd /opt/print-queue-manager
bash scripts/setup-airprint.sh

# Or manually create the Avahi service file:
cp config/avahi/AirPrint-HP_Smart_Tank_515.service /etc/avahi/services/

# Restart Avahi
systemctl restart avahi-daemon

# Verify the printer is advertised
avahi-browse -t _ipp._tcp
```

After this, iOS devices (AirPrint), Android devices (Mopria/Default Print Service), and macOS will auto-discover the printer on the same network.

---

## 📦 Part 4: Install Print Queue Manager Application

### 4.1 Create Application Directory

```bash
# Create directory
mkdir -p /opt/print-queue-manager
cd /opt/print-queue-manager

# Clone the repository (or copy files)
git clone https://github.com/vibecodedesuwa/printqueue-sonnet4.5.git .
```

### 4.2 Application File Structure

The application now uses a package structure:

```
/opt/print-queue-manager/
├── app.py                        # Entry point
├── printqueue/                   # Flask application package
│   ├── __init__.py               # App factory
│   ├── config.py                 # Environment config
│   ├── models.py                 # SQLite models
│   ├── auth.py                   # Auth decorators
│   ├── cups_utils.py             # CUPS helpers
│   ├── routes/
│   │   ├── web.py                # Web routes
│   │   ├── api_v1.py             # REST API v1
│   │   └── upload.py             # File upload
│   ├── services/
│   │   ├── file_converter.py     # DOCX→PDF
│   │   └── mail_printer.py       # Email print service
│   └── swagger/api_v1.yml        # OpenAPI spec
├── templates/                    # 7 Jinja2 templates
├── static/                       # PWA manifest, service worker, icons
├── config/avahi/                 # AirPrint mDNS service files
├── scripts/setup-airprint.sh     # AirPrint setup automation
├── data/                         # SQLite DB + uploaded files
├── requirements.txt
├── .env
└── print-queue-manager.service   # Systemd unit file
```

### 4.3 Create Data Directories

```bash
mkdir -p /opt/print-queue-manager/data/uploads
```

### 4.4 Create Python Virtual Environment

```bash
cd /opt/print-queue-manager

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🔐 Part 5: Configure Authentik Integration

### 5.1 Create OAuth Application in Authentik

1. Log into your Authentik admin panel
2. Navigate to **Applications** → **Providers**
3. Click **Create** and select **OAuth2/OpenID Provider**

Configure the provider:

```
Name: Print Queue Manager
Authorization flow: default-provider-authorization-implicit-consent
Client Type: Confidential
Client ID: <copy this - you'll need it>
Client Secret: <copy this - you'll need it>
Redirect URIs: http://<your-lxc-ip>:5000/authorize
                https://<your-domain>/authorize (if using reverse proxy)
```

4. Click **Create**
5. Go to **Applications** → **Applications**
6. Click **Create**

Configure the application:

```
Name: Print Queue Manager
Slug: print-queue
Provider: (select the provider you just created)
```

7. Save it

### 5.2 Configure Environment Variables

```bash
cd /opt/print-queue-manager

# Copy the example env file
cp .env.example .env

# Edit with your values
nano .env
```

Set the following variables:

```bash
# Flask
SECRET_KEY=<run: openssl rand -hex 32>

# Authentik SSO
AUTHENTIK_CLIENT_ID=your-client-id-from-authentik
AUTHENTIK_CLIENT_SECRET=your-client-secret-from-authentik
AUTHENTIK_METADATA_URL=https://your-authentik-domain.com/application/o/print-queue/.well-known/openid-configuration

# Printer
PRINTER_NAME=HP_Smart_Tank_515

# Admin
ADMIN_GROUPS=admins,print-admins
ADMIN_USERS=admin,yourusername

# Kiosk Mode
KIOSK_PIN=1234

# Email Print (set MAIL_ENABLED=true to activate)
MAIL_ENABLED=false
MAIL_IMAP_HOST=imap.your-domain.com
MAIL_IMAP_PORT=993
MAIL_IMAP_USER=print@your-domain.com
MAIL_IMAP_PASS=your-email-password
MAIL_IMAP_FOLDER=INBOX
MAIL_SMTP_HOST=smtp.your-domain.com
MAIL_SMTP_PORT=587
MAIL_SMTP_USER=print@your-domain.com
MAIL_SMTP_PASS=your-email-password

# Claim System
UNCLAIMED_JOB_TIMEOUT=24

# Database & Uploads
DATABASE_PATH=data/printqueue.db
UPLOAD_FOLDER=data/uploads
```

**Important:** Replace all placeholder values with your actual credentials.

---

## 🚀 Part 6: Run the Application

### 6.1 Test Run

```bash
cd /opt/print-queue-manager
source venv/bin/activate

# Load environment variables
export $(cat .env | xargs)

# Test run
python3 app.py

# You should see:
# * Running on http://0.0.0.0:5000

# Test in browser: http://<lxc-ip>:5000
# You should be redirected to Authentik login
```

### 6.2 Create Systemd Service

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
```

```bash
# Reload systemd
systemctl daemon-reload

# Enable and start the service
systemctl enable print-queue-manager
systemctl start print-queue-manager

# Check status
systemctl status print-queue-manager

# Check logs
journalctl -u print-queue-manager -f
```

---

## 🌐 Part 7: Configure Network Access

### 7.1 Configure Firewall (if enabled)

```bash
# Allow CUPS web interface + IPP printing
ufw allow 631/tcp
ufw allow 631/udp

# Allow Print Queue Manager
ufw allow 5000/tcp

# Allow mDNS (AirPrint/Mopria device discovery)
ufw allow 5353/udp
```

### 7.2 Optional: Setup Reverse Proxy with Nginx

```bash
# Install Nginx
apt install -y nginx

# Create nginx config
nano /etc/nginx/sites-available/print-queue
```

```nginx
server {
    listen 80;
    server_name print.yourdomain.com;

    client_max_body_size 50M;  # Allow large file uploads

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Service worker must be served from root
    location /sw.js {
        proxy_pass http://localhost:5000/static/sw.js;
        add_header Service-Worker-Allowed "/";
    }
}
```

```bash
# Enable the site
ln -s /etc/nginx/sites-available/print-queue /etc/nginx/sites-enabled/

# Test configuration
nginx -t

# Restart nginx
systemctl restart nginx
```

---

## � Part 8: Configure Client Devices

### 8.1 iPhone / iPad (AirPrint — Zero Config)

AirPrint is built-in — the printer auto-appears in the Print dialog if on the same network. See `CLIENT_PRINT_GUIDE.md` for details.

### 8.2 Android (Mopria)

Android 8+ auto-discovers via Default Print Service. Older versions need the Mopria app. See `CLIENT_PRINT_GUIDE.md`.

### 8.3 Windows Clients

```powershell
# Add printer via PowerShell (as Administrator)
Add-Printer -Name "Print Queue" -ConnectionName "http://<lxc-ip>:631/printers/HP_Smart_Tank_515"

# Or manually:
# 1. Settings → Printers & scanners
# 2. Add a printer or scanner
# 3. The printer I want isn't listed
# 4. Select a shared printer by name
# 5. Enter: http://<lxc-ip>:631/printers/HP_Smart_Tank_515
```

### 8.4 macOS Clients

```bash
# System Preferences → Printers & Scanners
# Click + to add printer
# Select "IP" tab
# Address: <lxc-ip>
# Protocol: Internet Printing Protocol - IPP
# Queue: printers/HP_Smart_Tank_515
# Name: Print Queue
# Click Add
```

### 8.5 Linux Clients

```bash
# Add printer
lpadmin -p PrintQueue -v ipp://<lxc-ip>:631/printers/HP_Smart_Tank_515 -E

# Or use system-config-printer GUI
```

### 8.6 Web Upload (Any Device)

Open `http://<lxc-ip>:5000/upload` in any browser, log in, and drag-and-drop a file.

### 8.7 Email Print

Send attachments to your configured print email address (requires `MAIL_ENABLED=true` in `.env`).

---

## 🔑 Part 9: Initial Setup After First Login

### 9.1 Create Your First API Key

1. Log in as admin at `http://<lxc-ip>:5000`
2. Go to **Admin** → **API Keys** tab
3. Click **+ New Key**, set name and permissions
4. Copy the key — it won't be shown again

### 9.2 Map Your Devices (Claim System)

When you print from a phone via AirPrint/Mopria, the CUPS username will be something like "iPhone" or "Galaxy". Map it:

1. Print a test page from your phone
2. Check the **Admin** → **All Jobs** tab for the CUPS username
3. Go to **Admin** → **Device Mapping** tab
4. Click **+ Add Mapping** and enter the CUPS username → your Authentik username

Future jobs from that device will auto-assign to you.

### 9.3 Map Email Addresses (Email Print)

If email printing is enabled:

1. Go to **Admin** → **Email Mapping** tab
2. Click **+ Add Mapping** and map email addresses to usernames

### 9.4 Test Kiosk Mode

1. Open `http://<lxc-ip>:5000/kiosk` on a phone/tablet
2. Enter the PIN (default: `1234`, set via `KIOSK_PIN` env var)
3. Use the Kiosk to approve/deny jobs with big touch buttons

---

## ✅ Part 10: Testing

### 10.1 Test Print Flow

1. **From a client computer:**

   ```bash
   echo "Test print from $(hostname)" | lpr -P PrintQueue
   ```

2. **Access the web interface:**
   - Open browser: `http://<lxc-ip>:5000`
   - Log in with Authentik
   - You should see your job in "Held" status

3. **Release the job:**
   - Click "✓ Release" button → printer starts printing

### 10.2 Test API

```bash
# Health check (no auth)
curl http://<lxc-ip>:5000/api/v1/health

# List jobs
curl -H "Authorization: Bearer pq_your-api-key" http://<lxc-ip>:5000/api/v1/jobs

# Submit a print job
curl -X POST -H "Authorization: Bearer pq_your-api-key" \
  -F "file=@document.pdf" \
  http://<lxc-ip>:5000/api/v1/print
```

### 10.3 Test AirPrint Discovery

```bash
# Verify the printer is advertised via mDNS
avahi-browse -t _ipp._tcp

# Should show your printer
```

### 10.4 Test Web Upload

1. Go to `http://<lxc-ip>:5000/upload`
2. Drag a PDF/DOCX/image onto the drop zone
3. Set print options → Submit
4. Check dashboard for the new held job

---

## 🔍 Part 11: Troubleshooting

### Common Issues

**Printer not detected:**

```bash
lsusb | grep -i hp
lpstat -p -d
systemctl restart cups
```

**AirPrint not discovered on iOS/Android:**

```bash
# Check Avahi is running
systemctl status avahi-daemon

# Check mDNS service file exists
ls /etc/avahi/services/

# Check UDP 5353 is open
ss -ulnp | grep 5353

# Restart Avahi
systemctl restart avahi-daemon
```

**Jobs not appearing in queue:**

```bash
tail -f /var/log/cups/error_log
lpstat -p HP_Smart_Tank_515 -l
```

**Authentik login fails:**

```bash
cat /opt/print-queue-manager/.env
curl https://your-authentik-domain.com/application/o/print-queue/.well-known/openid-configuration
journalctl -u print-queue-manager -f
```

**File upload fails / DOCX conversion errors:**

```bash
# Check LibreOffice is installed
libreoffice --version

# Check upload folder permissions
ls -la /opt/print-queue-manager/data/uploads/
```

**Email print not working:**

```bash
# Verify MAIL_ENABLED=true in .env
# Check IMAP connection
python3 -c "
from imapclient import IMAPClient
c = IMAPClient('imap.your-domain.com', ssl=True)
c.login('print@your-domain.com', 'your-password')
print(c.select_folder('INBOX'))
"
```

**Database errors:**

```bash
# Check database exists and is writable
ls -la /opt/print-queue-manager/data/printqueue.db

# Reset database (⚠️ deletes all API keys and mappings)
rm /opt/print-queue-manager/data/printqueue.db
systemctl restart print-queue-manager
```

### Enable Debug Logging

```bash
nano /opt/print-queue-manager/.env
# Add:
FLASK_ENV=development

systemctl restart print-queue-manager
journalctl -u print-queue-manager -f
```

---

## 🎯 Part 12: Final Configuration

### 12.1 Set Static IP for LXC

```bash
# In Proxmox host
nano /etc/pve/lxc/100.conf

# Add/modify:
net0: name=eth0,bridge=vmbr0,ip=192.168.1.100/24,gw=192.168.1.1
```

### 12.2 Configure Groups in Authentik

1. Go to Authentik → **Directory** → **Groups**
2. Create groups:
   - `print-users` (regular users)
   - `print-admins` (admin users)
3. Assign users to appropriate groups

### 12.3 Update Admin Configuration

```bash
nano /opt/print-queue-manager/.env

# Update admin settings:
ADMIN_GROUPS=print-admins,admins
ADMIN_USERS=admin

# Restart
systemctl restart print-queue-manager
```

---

## 📊 Part 13: Monitoring and Maintenance

### View Application Logs

```bash
journalctl -u print-queue-manager -f        # Real-time
journalctl -u print-queue-manager -n 100     # Last 100 lines
journalctl -u print-queue-manager --since today
```

### View CUPS Logs

```bash
tail -f /var/log/cups/error_log
tail -f /var/log/cups/access_log
```

### Backup Configuration

```bash
# Backup everything (app + database + uploads + CUPS)
tar -czf print-queue-backup-$(date +%Y%m%d).tar.gz \
    /opt/print-queue-manager/data \
    /opt/print-queue-manager/.env \
    /etc/cups \
    /etc/avahi/services
```

### Update the Application

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
2. ✅ Log in with Authentik SSO
3. ✅ See their jobs in the web dashboard
4. ✅ Upload files directly via drag-and-drop
5. ✅ Print via email
6. ✅ Release/cancel jobs from dashboard or kiosk
7. ✅ Use the REST API for automation
8. ✅ Claim jobs submitted from mobile devices
9. ✅ Admins manage API keys, device mappings, email mappings

**Access URLs:**

| URL                             | Purpose                        |
| ------------------------------- | ------------------------------ |
| `http://<lxc-ip>:5000`          | Dashboard (SSO login)          |
| `http://<lxc-ip>:5000/kiosk`    | Kiosk Mode (PIN: `1234`)       |
| `http://<lxc-ip>:5000/upload`   | Upload & Print                 |
| `http://<lxc-ip>:5000/api/docs` | API Documentation (Swagger UI) |
| `http://<lxc-ip>:631`           | CUPS Web Interface             |

---

## 🆘 Quick Reference

```bash
# Restart all services
systemctl restart cups avahi-daemon print-queue-manager

# Check printer status
lpstat -p -d

# Check pending jobs
lpstat -o

# Clear all jobs (emergency)
cancel -a

# Check AirPrint advertisement
avahi-browse -t _ipp._tcp

# Test print
echo "Test" | lpr -P HP_Smart_Tank_515

# API health check
curl http://localhost:5000/api/v1/health
```

## 📚 Additional Resources

- CUPS Documentation: https://www.cups.org/doc/
- Authentik Documentation: https://docs.goauthentik.io/
- HPLIP Documentation: https://developers.hp.com/hp-linux-imaging-and-printing
- Avahi Documentation: https://www.avahi.org/
- Client Setup: See `CLIENT_PRINT_GUIDE.md` in the project root
