#!/bin/bash

# Print Queue Manager - Automated Deployment Script
# For Bare-Metal Debian/Ubuntu or Proxmox LXC

set -e

SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
TARGET_DIR=/opt/print-queue-manager
BACKUP_DIR=

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Print Queue Manager - Automated Installation Script    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# ── Step 1: Install System Dependencies ────────────────────────────────────
echo "📦 Step 1: Installing system dependencies..."
apt update
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

echo "✅ System dependencies installed"
echo ""

# ── Step 2: Configure CUPS Basics ──────────────────────────────────────────
echo "🖨️ Step 2: Configuring CUPS..."
systemctl enable cups
systemctl start cups
cupsctl --remote-any
cupsctl --share-printers

if [ -f "$SOURCE_DIR/config/cupsd.conf" ]; then
    cp -a /etc/cups/cupsd.conf "/etc/cups/cupsd.conf.backup.$(date +%Y%m%d_%H%M%S)"
    install -m 0644 "$SOURCE_DIR/config/cupsd.conf" /etc/cups/cupsd.conf
    cupsd -t
    systemctl restart cups
fi

echo "✅ CUPS configured"
echo ""

# ── Step 3: Create Application Directory ───────────────────────────────────
echo "📁 Step 3: Creating application directory..."
if [ -d "$TARGET_DIR" ] && [ "$SOURCE_DIR" != "$TARGET_DIR" ]; then
    echo "⚠️  Directory already exists. Creating backup..."
    BACKUP_DIR="$TARGET_DIR.backup.$(date +%Y%m%d_%H%M%S)"
    mv "$TARGET_DIR" "$BACKUP_DIR"
fi

mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

# Copy the complete application
if [ "$SOURCE_DIR" = "$TARGET_DIR" ]; then
    echo "📋 Running in-place from $TARGET_DIR"
elif [ -f "$SOURCE_DIR/app.py" ] && [ -d "$SOURCE_DIR/printqueue" ]; then
    echo "📋 Copying files from $SOURCE_DIR..."
    cp -a "$SOURCE_DIR/app.py" "$SOURCE_DIR/requirements.txt" .
    cp -a "$SOURCE_DIR/printqueue" "$SOURCE_DIR/templates" "$SOURCE_DIR/static" "$SOURCE_DIR/scripts" "$SOURCE_DIR/config" .
else
    echo "❌ Source files were not found beside install.sh"
    exit 1
fi

# Preserve deployment state during an upgrade
if [ -n "$BACKUP_DIR" ]; then
    [ -f "$BACKUP_DIR/.env" ] && cp -a "$BACKUP_DIR/.env" .
    [ -d "$BACKUP_DIR/data" ] && cp -a "$BACKUP_DIR/data" .
fi

echo "✅ Application files copied"
echo ""

# ── Step 4: Python Virtual Environment ─────────────────────────────────────
echo "🐍 Step 4: Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Python environment ready"
echo ""

# ── Step 5: Configure .env ─────────────────────────────────────────────────
echo "⚙️ Step 5: Configuration setup..."
echo ""
echo "  You will be asked to edit the .env file now."
echo "  Please configure at minimum:"
echo "    - PRINTER_NAME     (your CUPS printer name — run 'lpstat -p' to list)"
echo "    - Authentik SSO    (or set LDAP_ENABLED=true for AD-only auth)"
echo "    - LDAP settings    (if using Active Directory authentication)"
echo ""

if [ ! -f ".env" ]; then
    echo "Creating .env file..."

    # List available printers to help the user
    echo ""
    echo "🖨️  Available CUPS printers:"
    if lpstat -p 2>/dev/null | grep -q "printer"; then
        lpstat -p 2>/dev/null | sed 's/^/   /'
    else
        echo "   (no printers found yet — you can add one after installation)"
    fi
    echo ""

    # Ask for printer name
    read -rp "Enter your CUPS printer name [HP_Smart_Tank_515]: " user_printer
    user_printer="${user_printer:-HP_Smart_Tank_515}"
    echo ""

    cat > .env << EOF
# Flask Secret Key
SECRET_KEY=$(openssl rand -hex 32)

# Authentik OAuth Configuration (FILL THESE IN!)
AUTHENTIK_CLIENT_ID=your-client-id-here
AUTHENTIK_CLIENT_SECRET=your-client-secret-here
AUTHENTIK_METADATA_URL=https://your-authentik-domain.com/application/o/print-queue/.well-known/openid-configuration

# Collabora Online (set WOPI_PUBLIC_URL to this PrintQ server's reachable URL)
COLLABORA_ENABLED=true
COLLABORA_URL=https://office.toonshou.in
COLLABORA_INTERNAL_URL=http://172.16.0.9:9980
WOPI_PUBLIC_URL=
WOPI_TOKEN_TTL=14400
OFFICE_FOLDER=data/office

# Printer — must match the name in CUPS (run 'lpstat -p' to list)
PRINTER_NAME=${user_printer}

# Admin Configuration
ADMIN_GROUPS=admins,print-admins
ADMIN_USERS=admin

# Active Directory / LDAP
# These settings are used by BOTH the web app (Flask LDAP login)
# AND the CUPS IPP auth layer (nslcd/PAM — Android/iOS AD authentication)
LDAP_ENABLED=false
LDAP_SHOW_IN_WEBUI=true
LDAP_HOST=ad.domain.local
LDAP_PORT=389
LDAP_USE_SSL=false
LDAP_BASE_DN=DC=domain,DC=local
LDAP_BIND_DN=CN=print-service,OU=Services,DC=domain,DC=local
LDAP_BIND_PASSWORD=change-me
LDAP_DOMAIN=domain.local
LDAP_USER_SEARCH_FILTER=(&(objectClass=user)(sAMAccountName={username}))

# CUPS service account (used by the web app to manage jobs — always needed)
CUPS_USER=print
CUPS_PASSWORD=$(openssl rand -hex 16)

# Application Settings
FLASK_ENV=production

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
EOF
    
    echo ""
    echo "⚠️  IMPORTANT: Review and complete the .env file."
    echo "   Pay attention to PRINTER_NAME, Authentik settings, and LDAP settings."
    echo ""
    read -rp "Press Enter to edit .env now, or Ctrl+C to exit and edit later..."
    nano .env
else
    echo "✅ .env file already exists, skipping creation."
    echo "   Verify PRINTER_NAME and LDAP settings are correct."
fi

# Re-read .env for use in later steps
set -a
# shellcheck disable=SC1091
. .env
set +a

echo ""

# ── Step 6: Printer Setup ─────────────────────────────────────────────────
echo "🖨️ Step 6: Printer setup..."
PRINTER_NAME="${PRINTER_NAME:-HP_Smart_Tank_515}"

if lpstat -p "$PRINTER_NAME" >/dev/null 2>&1; then
    echo "✅ Printer '$PRINTER_NAME' found in CUPS"
else
    echo "⚠️  Printer '$PRINTER_NAME' not found in CUPS."
    echo ""
    echo "   Available printers:"
    lpstat -p 2>/dev/null | sed 's/^/   /' || echo "   (none)"
    echo ""
    echo "   You can add your printer now or later."
    echo ""

    read -rp "Is this an HP printer? (y/n): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "   Installing HP printer tools..."
        apt install -y hplip 2>/dev/null || true
        echo ""
        echo "   Starting HP printer setup..."
        echo "   Set the printer name to: $PRINTER_NAME"
        echo ""
        read -rp "Press Enter to continue..."
        hp-setup -i || true
    else
        echo "   Please add your printer using the CUPS web interface:"
        echo "   http://$(hostname -I | awk '{print $1}'):631/admin"
        echo "   Or use: lpadmin -p $PRINTER_NAME -v <device-uri> -E"
        echo ""
        read -rp "Press Enter to continue after adding the printer, or Ctrl+C to exit..."
    fi
fi

# Configure printer hold + sharing
if lpstat -p "$PRINTER_NAME" >/dev/null 2>&1; then
    echo "Configuring printer '$PRINTER_NAME'..."

    # Policy will be set in Step 7 based on LDAP_ENABLED
    lpadmin -p "$PRINTER_NAME" \
        -o job-hold-until-default=indefinite \
        -o printer-is-shared=true
    cupsenable "$PRINTER_NAME" 2>/dev/null || true
    cupsaccept "$PRINTER_NAME" 2>/dev/null || true

    echo "✅ Printer configured (hold-by-default, shared)"
else
    echo "⚠️  Printer '$PRINTER_NAME' still not found. Configure it manually later."
fi
echo ""

# ── Step 7: AD/LDAP CUPS Authentication (Optional) ────────────────────────
echo "🔐 Step 7: AD/LDAP authentication for CUPS..."
LDAP_ENABLED="${LDAP_ENABLED:-false}"

if [ "$LDAP_ENABLED" = "true" ]; then
    echo "   LDAP_ENABLED=true detected — configuring AD authentication for CUPS IPP..."
    echo ""
    echo "   This will allow Android/iOS devices to authenticate with AD credentials"
    echo "   when printing via IPP (AirPrint/Mopria)."
    echo ""

    if [ -f "$TARGET_DIR/scripts/setup-cups-ldap.sh" ]; then
        bash "$TARGET_DIR/scripts/setup-cups-ldap.sh" "$TARGET_DIR/.env"
    else
        echo "❌ setup-cups-ldap.sh not found — run it manually later"
    fi
else
    echo "   LDAP_ENABLED=false — skipping AD authentication setup."
    echo "   IPP printing will not require authentication (jobs appear as unclaimed)."

    # Set default policy (no auth for printing)
    if lpstat -p "$PRINTER_NAME" >/dev/null 2>&1; then
        lpadmin -p "$PRINTER_NAME" -o printer-op-policy=default
        echo "   Printer policy set to 'default'"
    fi
fi
echo ""

# ── Step 8: AirPrint/Mopria mDNS Setup ────────────────────────────────────
echo "📡 Step 8: Setting up AirPrint/Mopria discovery..."
systemctl enable avahi-daemon
systemctl start avahi-daemon

if [ -f "$TARGET_DIR/scripts/setup-airprint.sh" ]; then
    export PRINTER_NAME
    bash "$TARGET_DIR/scripts/setup-airprint.sh" || echo "⚠️  AirPrint setup had warnings — check above"
else
    echo "⚠️  setup-airprint.sh not found — run it manually later"
fi
echo ""

# ── Step 9: Install Systemd Service ───────────────────────────────────────
echo "🔧 Step 9: Installing systemd service..."
cat > /etc/systemd/system/print-queue-manager.service << EOF
[Unit]
Description=Print Queue Manager
After=network.target cups.service
Requires=cups.service

[Service]
Type=notify
User=root
WorkingDirectory=/opt/print-queue-manager
Environment="PATH=/opt/print-queue-manager/venv/bin"
EnvironmentFile=/opt/print-queue-manager/.env
ExecStart=/opt/print-queue-manager/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable print-queue-manager

echo "✅ Systemd service installed"
echo ""

# ── Step 10: Start Services & Verify ───────────────────────────────────────
echo "🚀 Step 10: Starting services..."

# Create data directories
mkdir -p "$TARGET_DIR/data/uploads" "$TARGET_DIR/data/office"

systemctl restart cups
systemctl start print-queue-manager

echo ""
echo "🔍 Checking status..."
sleep 2

if systemctl is-active --quiet print-queue-manager; then
    echo "✅ Print Queue Manager is running!"
else
    echo "❌ Print Queue Manager failed to start. Check logs with:"
    echo "   journalctl -u print-queue-manager -n 50"
    exit 1
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                  Installation Complete!                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Configuration Summary:"
echo "   Printer:       $PRINTER_NAME"
echo "   AD/LDAP Auth:  $LDAP_ENABLED"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. If you haven't configured Authentik yet:"
echo "   - Create OAuth2/OpenID Provider"
echo "   - Set redirect URI to: http://$(hostname -I | awk '{print $1}'):5000/authorize"
echo "   - Copy Client ID and Secret to .env"
echo "   - Restart: systemctl restart print-queue-manager"
echo ""
echo "2. Access the web interface:"
echo "   http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "3. Configure client devices to print to:"
echo "   http://$(hostname -I | awk '{print $1}'):631/printers/$PRINTER_NAME"
echo ""
if [ "$LDAP_ENABLED" = "true" ]; then
echo "4. Test AD authentication:"
echo "   - Print from Android/iOS — you should be prompted for AD credentials"
echo "   - Run: getent passwd <ad-username>"
echo ""
fi
echo "📚 For detailed instructions, see:"
echo "   $TARGET_DIR/BARE_METAL_AND_LXC_GUIDE.md"
echo ""
echo "🔍 Useful commands:"
echo "   systemctl status print-queue-manager   # Check service status"
echo "   journalctl -u print-queue-manager -f   # View logs"
echo "   lpstat -p                              # Check printer status"
echo ""
echo "✨ Happy printing! ✨"
