#!/bin/bash

# Print Queue Manager - Automated Deployment Script
# For bare-metal Linux or systemd-based containers.
# Supported: Ubuntu, Debian, Fedora, CentOS Stream, AlmaLinux and compatible
# Debian/RHEL-family distributions.

set -e

SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
TARGET_DIR=/opt/print-queue-manager
BACKUP_DIR=

# shellcheck source=scripts/platform.sh
. "$SOURCE_DIR/scripts/platform.sh"

load_install_settings() {
    local line key value
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        case "$line" in ''|'#'*) continue ;; esac
        key=${line%%=*}
        [ "$key" = "$line" ] && continue
        value=${line#*=}
        case "$value" in
            \"*\") value=${value#\"}; value=${value%\"} ;;
            \'*\') value=${value#\'}; value=${value%\'} ;;
        esac
        case "$key" in
            PRINTER_NAME|LDAP_ENABLED|LDAP_HOST|LDAP_PORT|LDAP_USE_SSL|LDAP_BASE_DN|LDAP_BIND_DN|LDAP_BIND_PASSWORD|LDAP_DOMAIN|LDAP_TEST_USER|LDAP_AD_DOMAIN_SID|LDAP_USER_SEARCH_FILTER|LDAP_TLS_REQCERT|SAMBA_ENABLED|SAMBA_REALM|SAMBA_WORKGROUP|SAMBA_HOSTNAME|SAMBA_JOIN_USER|SAMBA_SHARE_NAME|SAMBA_WINDOWS_QUEUE|AIRPRINT_READY_PAPER_SIZES|AIRPRINT_DUPLEX|AIRPRINT_PAPER_MAX|CUPS_USER|CUPS_PASSWORD)
                printf -v "$key" '%s' "$value"
                export "$key"
                ;;
        esac
    done < "$1"
}

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Print Queue Manager - Automated Installation Script    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

detect_platform
SERVER_IP=$(primary_ip)
echo "🐧 Detected: $PRINTQ_DISTRO_NAME $PRINTQ_DISTRO_VERSION ($PRINTQ_DISTRO_FAMILY family)"
echo ""

# ── Step 1: Install System Dependencies ────────────────────────────────────
echo "📦 Step 1: Installing system dependencies..."
package_update
if [ "$PRINTQ_DISTRO_FAMILY" = "debian" ]; then
    package_install \
        cups cups-client cups-bsd printer-driver-all \
        python3 python3-pip python3-venv python3-dev libcups2-dev \
        gcc git curl nano openssl \
        avahi-daemon avahi-utils \
        libreoffice-writer fonts-noto-core fonts-thai-tlwg libmagic1
else
    package_install \
        cups cups-client cups-devel cups-filters \
        python3 python3-pip python3-devel \
        gcc git curl nano openssl \
        avahi avahi-tools file-libs
    # Fedora and EL8/EL9 provide this RPM, but RHEL-compatible EL10 removed
    # LibreOffice from the base repositories. Document conversion is optional
    # and must not prevent the print server itself from installing.
    package_install_optional libreoffice-writer
    package_install_optional \
        google-noto-sans-fonts google-noto-sans-thai-fonts
fi

if command -v libreoffice >/dev/null 2>&1; then
    LOCAL_OFFICE_CONVERSION=available
else
    LOCAL_OFFICE_CONVERSION=unavailable
    echo "⚠️  LibreOffice is not available from this distribution's enabled repositories."
    echo "   PrintQ will still install, and PDF/image printing plus the Collabora editor will work."
    echo "   Local DOC/DOCX/ODT-to-PDF conversion will remain unavailable until LibreOffice is installed."
fi

echo "✅ System dependencies installed"
echo ""

# ── Step 2: Configure CUPS Basics ──────────────────────────────────────────
echo "🖨️ Step 2: Configuring CUPS..."

wait_for_cups() {
    local attempt
    for attempt in {1..20}; do
        if lpstat -h localhost -r >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done

    echo "❌ The local CUPS scheduler did not become reachable on localhost:631."
    systemctl status cups --no-pager -l || true
    journalctl -u cups --no-pager -n 50 || true
    return 1
}

# The supplied configuration references lpadmin on every distribution. RHEL
# systems do not always create that group with the cups package.
getent -s files group lpadmin >/dev/null 2>&1 || groupadd --system lpadmin

# Modern CUPS reads SystemGroup from cups-files.conf, not cupsd.conf. Preserve
# useful platform defaults while ensuring the PrintQ service group is present.
CUPS_SYSTEM_GROUPS=lpadmin
CUPS_FILES_BACKUP="/etc/cups/cups-files.conf.backup.$(date +%Y%m%d_%H%M%S)"
cp -a /etc/cups/cups-files.conf "$CUPS_FILES_BACKUP"
for cups_admin_group in root sys wheel; do
    if getent -s files group "$cups_admin_group" >/dev/null 2>&1; then
        CUPS_SYSTEM_GROUPS="$CUPS_SYSTEM_GROUPS $cups_admin_group"
    fi
done
if grep -Eq '^[[:space:]]*SystemGroup[[:space:]]+' /etc/cups/cups-files.conf; then
    sed -i -E "s/^[[:space:]]*SystemGroup[[:space:]]+.*/SystemGroup $CUPS_SYSTEM_GROUPS/" /etc/cups/cups-files.conf
else
    printf '\nSystemGroup %s\n' "$CUPS_SYSTEM_GROUPS" >> /etc/cups/cups-files.conf
fi

if [ -f "$SOURCE_DIR/config/cupsd.conf" ]; then
    CUPS_CONFIG_BACKUP="/etc/cups/cupsd.conf.backup.$(date +%Y%m%d_%H%M%S)"
    [ ! -f /etc/cups/cupsd.conf ] || cp -a /etc/cups/cupsd.conf "$CUPS_CONFIG_BACKUP"
    install -m 0644 "$SOURCE_DIR/config/cupsd.conf" /etc/cups/cupsd.conf
    if ! cupsd -t; then
        echo "❌ The supplied CUPS configuration is invalid on this host."
        if [ -f "$CUPS_CONFIG_BACKUP" ]; then
            cp -a "$CUPS_CONFIG_BACKUP" /etc/cups/cupsd.conf
            echo "   Restored the original /etc/cups/cupsd.conf"
        fi
        cp -a "$CUPS_FILES_BACKUP" /etc/cups/cups-files.conf
        echo "   Restored the original /etc/cups/cups-files.conf"
        exit 1
    fi
fi

# Some builds expose a socket unit in addition to cups.service. Activating it
# first avoids a startup race, while systemctl cat keeps this portable where
# cups.socket does not exist.
if systemctl cat cups.socket >/dev/null 2>&1; then
    systemctl start cups.socket
fi
systemctl enable --now cups
wait_for_cups

# Force localhost so a pre-existing /etc/cups/client.conf or CUPS_SERVER
# environment variable cannot redirect cupsctl to an unavailable remote host.
if [ ! -f "$SOURCE_DIR/config/cupsd.conf" ]; then
    cupsctl -h localhost --remote-any --share-printers
    systemctl restart cups
    wait_for_cups
fi

# Open only the ports PrintQ requires when firewalld is already active.
if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port=631/tcp
    firewall-cmd --permanent --add-port=5353/udp
    firewall-cmd --permanent --add-port=5000/tcp
    firewall-cmd --reload
    echo "✅ firewalld allows IPP, mDNS, and the PrintQ web interface"
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
    cp -a "$SOURCE_DIR/app.py" "$SOURCE_DIR/requirements.txt" "$SOURCE_DIR/.env.example" .
    cp -a "$SOURCE_DIR/printqueue" "$SOURCE_DIR/templates" "$SOURCE_DIR/static" "$SOURCE_DIR/scripts" "$SOURCE_DIR/config" .
    for documentation_file in README.md BARE_METAL_AND_LXC_GUIDE.md CLIENT_PRINT_GUIDE.md; do
        [ ! -f "$SOURCE_DIR/$documentation_file" ] || cp -a "$SOURCE_DIR/$documentation_file" .
    done
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
if ! python3 -m venv venv; then
    echo "⚠️  Python's built-in venv module is unavailable; trying virtualenv..."
    package_install_optional python3-virtualenv
    python3 -m virtualenv venv
fi
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
LDAP_TEST_USER=
LDAP_AD_DOMAIN_SID=
LDAP_USER_SEARCH_FILTER=(&(objectClass=user)(sAMAccountName={username}))
LDAP_TLS_REQCERT=demand

# Windows SMB printing with seamless AD authentication
SAMBA_ENABLED=false
SAMBA_REALM=domain.local
SAMBA_WORKGROUP=DOMAIN
SAMBA_HOSTNAME=printq.domain.local
SAMBA_JOIN_USER=Administrator
SAMBA_SHARE_NAME=PrintQ
SAMBA_WINDOWS_QUEUE=

# AirPrint capabilities (HP Smart Tank 515 USB/HPLIP defaults)
AIRPRINT_READY_PAPER_SIZES=A4,A5,A6,B5,Letter,Legal,4x6in,5x7in,EnvelopeDL
AIRPRINT_DUPLEX=false
AIRPRINT_PAPER_MAX=legal-A4

# CUPS service account (used by the web app to manage jobs — always needed)
CUPS_USER=print
CUPS_PASSWORD=$(openssl rand -hex 16)

# Application Settings
FLASK_ENV=production
AUTO_PRINT_QR_UPLOADS=true

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

# Read only the settings needed by this installer. Do not source .env: LDAP
# filters legitimately contain shell metacharacters such as '&' and '('.
load_install_settings .env

# CUPS Basic authentication uses PAM, so the web application's service
# credentials must correspond to a real local account.
if [ -z "${CUPS_USER:-}" ] || [ -z "${CUPS_PASSWORD:-}" ]; then
    echo "❌ CUPS_USER and CUPS_PASSWORD must both be set in .env"
    exit 1
fi
case "$CUPS_USER" in
    *$'\n'*|*:*)
        echo "❌ CUPS_USER may not contain a newline or colon."
        exit 1
        ;;
esac
if ! [[ "$CUPS_USER" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]]; then
    echo "❌ CUPS_USER must be a valid lowercase Linux service-account name."
    exit 1
fi
case "$CUPS_PASSWORD" in
    *$'\n'*) echo "❌ CUPS_PASSWORD may not contain a newline."; exit 1 ;;
esac
if getent passwd "$CUPS_USER" >/dev/null 2>&1 && ! getent -s files passwd "$CUPS_USER" >/dev/null 2>&1; then
    echo "❌ CUPS_USER '$CUPS_USER' resolves from a directory service, not /etc/passwd."
    echo "   Choose a unique local service-account name; its password will be managed by PrintQ."
    exit 1
fi
getent -s files group lpadmin >/dev/null 2>&1 || groupadd --system lpadmin
if ! getent -s files passwd "$CUPS_USER" >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$CUPS_USER"
fi
usermod -a -G lpadmin "$CUPS_USER"
printf '%s:%s\n' "$CUPS_USER" "$CUPS_PASSWORD" | chpasswd
echo "✅ Local CUPS service account '$CUPS_USER' is ready"

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
        package_install_optional hplip
        echo ""
        echo "   Starting HP printer setup..."
        echo "   Set the printer name to: $PRINTER_NAME"
        echo ""
        read -rp "Press Enter to continue..."
        hp-setup -i || true
    else
        echo "   Please add your printer using the CUPS web interface:"
        echo "   http://${SERVER_IP}:631/admin"
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
    set_printer_retry_policy "$PRINTER_NAME"
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
SAMBA_ENABLED="${SAMBA_ENABLED:-false}"

if [ "$LDAP_ENABLED" = "true" ] && [ "$SAMBA_ENABLED" != "true" ]; then
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
elif [ "$LDAP_ENABLED" = "true" ]; then
    echo "   SAMBA_ENABLED=true — Samba/Winbind will provide PAM/NSS AD authentication."
    echo "   Skipping the separate SSSD/nslcd configuration."
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

# ── Step 7b: Windows SMB/AD Printing (Optional) ───────────────────────────
echo "🪟 Step 7b: Windows SMB/AD printing..."
if [ "$SAMBA_ENABLED" = "true" ]; then
    if [ -f "$TARGET_DIR/scripts/setup-windows-samba.sh" ]; then
        bash "$TARGET_DIR/scripts/setup-windows-samba.sh" "$TARGET_DIR/.env"
    else
        echo "❌ setup-windows-samba.sh not found — update the deployment and rerun"
        exit 1
    fi
else
    echo "   SAMBA_ENABLED=false — skipping the Windows SMB print share."
fi
echo ""

# ── Step 8: AirPrint/Mopria mDNS Setup ────────────────────────────────────
echo "📡 Step 8: Setting up AirPrint/Mopria discovery..."
service_enable_start avahi-daemon

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
Type=simple
User=root
WorkingDirectory=/opt/print-queue-manager
Environment="PATH=/opt/print-queue-manager/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
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
echo "   Local Office:  $LOCAL_OFFICE_CONVERSION"
echo "   Windows SMB:   $SAMBA_ENABLED"
if [ "$SAMBA_ENABLED" = "true" ]; then
    printf '   Windows Share: \\\\%s\\%s\n' "$SAMBA_HOSTNAME" "${SAMBA_SHARE_NAME:-PrintQ}"
fi
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. If you haven't configured Authentik yet:"
echo "   - Create OAuth2/OpenID Provider"
echo "   - Set redirect URI to: http://${SERVER_IP}:5000/authorize"
echo "   - Copy Client ID and Secret to .env"
echo "   - Restart: systemctl restart print-queue-manager"
echo ""
echo "2. Access the web interface:"
echo "   http://${SERVER_IP}:5000"
echo ""
echo "3. Configure client devices to print to:"
echo "   http://${SERVER_IP}:631/printers/$PRINTER_NAME"
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
