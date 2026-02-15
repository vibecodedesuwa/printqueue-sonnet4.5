#!/bin/bash

# Print Queue Manager - Automated Deployment Script
# For Proxmox LXC (Ubuntu/Debian)

set -e

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
    nano

echo "✅ System dependencies installed"
echo ""

echo "🖨️ Step 2: Configuring CUPS..."
systemctl enable cups
systemctl start cups
cupsctl --remote-any
cupsctl --share-printers

echo "✅ CUPS configured"
echo ""

echo "📁 Step 3: Creating application directory..."
if [ -d "/opt/print-queue-manager" ]; then
    echo "⚠️  Directory already exists. Creating backup..."
    mv /opt/print-queue-manager /opt/print-queue-manager.backup.$(date +%Y%m%d_%H%M%S)
fi

mkdir -p /opt/print-queue-manager
cd /opt/print-queue-manager

# Check if we're in the source directory
if [ -f "../app.py" ]; then
    echo "📋 Copying files from current directory..."
    cp -r ../app.py ../requirements.txt ../templates ./ 2>/dev/null || true
else
    echo "⚠️  Source files not found in parent directory"
    echo "Please manually copy the application files to /opt/print-queue-manager/"
    echo "Required files:"
    echo "  - app.py"
    echo "  - requirements.txt"
    echo "  - templates/ (directory)"
    exit 1
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

# Printer Configuration
PRINTER_NAME=HP_Smart_Tank_515

# Admin Configuration
ADMIN_GROUPS=admins,print-admins
ADMIN_USERS=admin

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
    lpadmin -p HP_Smart_Tank_515 -o job-hold-until=indefinite
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
