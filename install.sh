#!/bin/bash

# Print Queue Manager - Automated Deployment Script
# For Proxmox LXC (Ubuntu/Debian)

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

echo "📦 Step 1: Installing system dependencies..."
apt update
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
    fonts-noto-core \
    fonts-thai-tlwg \
    libmagic1

echo "✅ System dependencies installed"
echo ""

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

echo "📁 Step 3: Creating application directory..."
if [ -d "$TARGET_DIR" ] && [ "$SOURCE_DIR" != "$TARGET_DIR" ]; then
    echo "⚠️  Directory already exists. Creating backup..."
    BACKUP_DIR="$TARGET_DIR.backup.$(date +%Y%m%d_%H%M%S)"
    mv "$TARGET_DIR" "$BACKUP_DIR"
fi

mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

# Copy the complete application, not only the entry point and templates.
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

# Preserve deployment state during an upgrade.
if [ -n "$BACKUP_DIR" ]; then
    [ -f "$BACKUP_DIR/.env" ] && cp -a "$BACKUP_DIR/.env" .
    [ -d "$BACKUP_DIR/data" ] && cp -a "$BACKUP_DIR/data" .
fi

echo "✅ Application files copied"
echo ""

echo "🐍 Step 4: Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Python environment ready"
echo ""

echo "⚙️ Step 5: Configuration setup..."

if [ ! -f ".env" ]; then
    echo "Creating .env file..."
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

# Printer Configuration
PRINTER_NAME=HP_Smart_Tank_515

# Admin Configuration
ADMIN_GROUPS=admins,print-admins
ADMIN_USERS=admin

# Active Directory / LDAP
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

# Application Settings
FLASK_ENV=production
EOF
    
    echo "⚠️  IMPORTANT: Edit /opt/print-queue-manager/.env with your Authentik credentials"
    echo ""
    read -p "Press Enter to edit .env now, or Ctrl+C to exit and edit later..."
    nano .env
else
    echo "✅ .env file already exists, skipping..."
fi

echo ""

echo "🔧 Step 6: Installing systemd service..."
cat > /etc/systemd/system/print-queue-manager.service << EOF
[Unit]
Description=Print Queue Manager
After=network.target cups.service

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

echo "🖨️ Step 7: Printer setup..."
echo "Would you like to set up your HP Smart Tank 515 now?"
read -p "(y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting HP printer setup..."
    echo "Follow the interactive prompts to configure your printer."
    echo "Set the printer name to: HP_Smart_Tank_515"
    echo ""
    read -p "Press Enter to continue..."
    
    hp-setup -i
    
    echo ""
    echo "Configuring printer to hold jobs by default..."
    lpadmin -p HP_Smart_Tank_515 \
        -o job-hold-until-default=indefinite \
        -o printer-op-policy=authenticated \
        -o printer-is-shared=true
    cupsenable HP_Smart_Tank_515
    cupsaccept HP_Smart_Tank_515
    
    echo "✅ Printer configured"
else
    echo "⚠️  Skipping printer setup. Run 'hp-setup -i' manually later."
fi

echo ""

echo "🚀 Step 8: Starting services..."
systemctl start print-queue-manager

echo "✅ Services started"
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
echo "📋 Next Steps:"
echo ""
echo "1. Make sure you've configured Authentik:"
echo "   - Create OAuth2/OpenID Provider"
echo "   - Set redirect URI to: http://$(hostname -I | awk '{print $1}'):5000/authorize"
echo "   - Copy Client ID and Secret to .env"
echo ""
echo "2. If you haven't edited .env yet, do it now:"
echo "   nano /opt/print-queue-manager/.env"
echo "   systemctl restart print-queue-manager"
echo ""
echo "3. Access the web interface:"
echo "   http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "4. Configure client computers to use the printer:"
echo "   http://$(hostname -I | awk '{print $1}'):631/printers/HP_Smart_Tank_515"
echo ""
echo "📚 For detailed instructions, see:"
echo "   /opt/print-queue-manager/LXC_SETUP_GUIDE.md"
echo ""
echo "🔍 Useful commands:"
echo "   systemctl status print-queue-manager   # Check service status"
echo "   journalctl -u print-queue-manager -f   # View logs"
echo "   lpstat -p                              # Check printer status"
echo ""
echo "✨ Happy printing! ✨"
