# Print Queue Manager - LXC Setup Guide

Complete guide to install and configure the Print Queue Manager with Authentik SSO on Proxmox LXC.

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
#    - Disk: 8 GB minimum
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
    nano
```

### 2.2 Configure CUPS

```bash
# Enable and start CUPS
systemctl enable cups
systemctl start cups

# Allow network access to CUPS
cupsctl --remote-any
cupsctl --share-printers

# Add your user to lpadmin group (if needed)
usermod -aG lpadmin root
```

### 2.3 Configure CUPS to Hold All Jobs by Default

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

# Make it the default printer
lpadmin -d HP_Smart_Tank_515

# Enable the printer
cupsenable HP_Smart_Tank_515
cupsaccept HP_Smart_Tank_515

# Verify printer status
lpstat -p HP_Smart_Tank_515
```

---

## 📦 Part 4: Install Print Queue Manager Application

### 4.1 Create Application Directory

```bash
# Create directory
mkdir -p /opt/print-queue-manager
cd /opt/print-queue-manager

# Download the application files (you'll need to copy them)
# For now, we'll create them manually
```

### 4.2 Copy Application Files

You need to transfer these files to `/opt/print-queue-manager/`:
- `app.py`
- `requirements.txt`
- `templates/base.html`
- `templates/dashboard.html`
- `templates/admin.html`

```bash
# You can use SCP from your local machine:
# scp -r /path/to/print-queue-manager/* root@<LXC-IP>:/opt/print-queue-manager/

# Or create them manually using nano
```

### 4.3 Create Python Virtual Environment

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

# Create .env file
nano .env

# Add the following (replace with your actual values):
SECRET_KEY=$(openssl rand -hex 32)
AUTHENTIK_CLIENT_ID=your-client-id-from-authentik
AUTHENTIK_CLIENT_SECRET=your-client-secret-from-authentik
AUTHENTIK_METADATA_URL=https://your-authentik-domain.com/application/o/print-queue/.well-known/openid-configuration
PRINTER_NAME=HP_Smart_Tank_515
ADMIN_GROUPS=admins,print-admins
ADMIN_USERS=admin,yourusername
FLASK_ENV=production

# Save and exit (Ctrl+X, Y, Enter)
```

**Important:** Replace:
- `your-client-id-from-authentik` with the Client ID from Authentik
- `your-client-secret-from-authentik` with the Client Secret from Authentik
- `your-authentik-domain.com` with your actual Authentik domain
- `yourusername` with your Authentik username

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
# Copy the service file
cp print-queue-manager.service /etc/systemd/system/

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
# Allow CUPS web interface
ufw allow 631/tcp

# Allow Print Queue Manager
ufw allow 5000/tcp

# Allow IPP printing
ufw allow 631/udp
```

### 7.2 Optional: Setup Reverse Proxy with Nginx

```bash
# Install Nginx
apt install -y nginx

# Create nginx config
nano /etc/nginx/sites-available/print-queue

# Add this configuration:
```

```nginx
server {
    listen 80;
    server_name print.yourdomain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
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

## 👥 Part 8: Configure Client Computers

### 8.1 Windows Clients

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

### 8.2 macOS Clients

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

### 8.3 Linux Clients

```bash
# Add printer
lpadmin -p PrintQueue -v ipp://<lxc-ip>:631/printers/HP_Smart_Tank_515 -E

# Or use system-config-printer GUI
```

---

## ✅ Part 9: Testing

### 9.1 Test Print Flow

1. **From a client computer:**
   ```bash
   # Print a test page
   echo "Test print from $(hostname)" | lpr -P PrintQueue
   ```

2. **Access the web interface:**
   - Open browser: `http://<lxc-ip>:5000`
   - You'll be redirected to Authentik
   - Log in with your credentials
   - You should see your print job in "Held" status

3. **Release the job:**
   - Click "Release" button
   - The printer should start printing

### 9.2 Test Admin Access

1. Log in as admin user
2. Click "All Jobs (Admin)" tab
3. You should see all users' jobs
4. Test releasing and canceling jobs

---

## 🔍 Part 10: Troubleshooting

### Common Issues

**Printer not detected:**
```bash
# Check USB connection
lsusb | grep -i hp

# Check CUPS sees the printer
lpstat -p -d

# Restart CUPS
systemctl restart cups
```

**Jobs not appearing in queue:**
```bash
# Check CUPS logs
tail -f /var/log/cups/error_log

# Verify printer is set to hold jobs
lpstat -p HP_Smart_Tank_515 -l
```

**Authentik login fails:**
```bash
# Check environment variables
cat /opt/print-queue-manager/.env

# Verify Authentik metadata URL is accessible
curl https://your-authentik-domain.com/application/o/print-queue/.well-known/openid-configuration

# Check application logs
journalctl -u print-queue-manager -f
```

**Permission errors:**
```bash
# Ensure CUPS socket is accessible
ls -la /var/run/cups/cups.sock

# Check app can access CUPS
python3 -c "import cups; print(cups.Connection().getPrinters())"
```

### Enable Debug Logging

```bash
# Edit .env
nano /opt/print-queue-manager/.env

# Change to:
FLASK_ENV=development

# Restart service
systemctl restart print-queue-manager

# Watch logs
journalctl -u print-queue-manager -f
```

---

## 🎯 Part 11: Final Configuration

### 11.1 Set Static IP for LXC

```bash
# In Proxmox host
nano /etc/pve/lxc/100.conf

# Add/modify:
net0: name=eth0,bridge=vmbr0,ip=192.168.1.100/24,gw=192.168.1.1
```

### 11.2 Configure Print Queue Groups in Authentik

1. Go to Authentik → **Directory** → **Groups**
2. Create groups:
   - `print-users` (regular users)
   - `print-admins` (admin users)
3. Assign users to appropriate groups

### 11.3 Update Admin Configuration

```bash
nano /opt/print-queue-manager/.env

# Update admin settings:
ADMIN_GROUPS=print-admins,admins
ADMIN_USERS=admin

# Restart
systemctl restart print-queue-manager
```

---

## 📊 Part 12: Monitoring and Maintenance

### View Application Logs

```bash
# Real-time logs
journalctl -u print-queue-manager -f

# Last 100 lines
journalctl -u print-queue-manager -n 100

# Today's logs
journalctl -u print-queue-manager --since today
```

### View CUPS Logs

```bash
# Error log
tail -f /var/log/cups/error_log

# Access log
tail -f /var/log/cups/access_log
```

### Backup Configuration

```bash
# Backup print queue manager
tar -czf print-queue-backup-$(date +%Y%m%d).tar.gz /opt/print-queue-manager

# Backup CUPS configuration
tar -czf cups-backup-$(date +%Y%m%d).tar.gz /etc/cups
```

---

## 🎉 You're Done!

Your print queue management system is now ready! Users can:

1. ✅ Print from any device
2. ✅ Log in with Authentik SSO
3. ✅ See their jobs in the web interface
4. ✅ Release jobs to print
5. ✅ Cancel unwanted jobs
6. ✅ Admins can manage all users' jobs

**Access URLs:**
- Print Queue Manager: `http://<lxc-ip>:5000`
- CUPS Web Interface: `http://<lxc-ip>:631`

**Default Admin Credentials (CUPS):**
- Username: root
- Password: <your-lxc-root-password>

---

## 📚 Additional Resources

- CUPS Documentation: https://www.cups.org/doc/
- Authentik Documentation: https://docs.goauthentik.io/
- HPLIP Documentation: https://developers.hp.com/hp-linux-imaging-and-printing

## 🆘 Need Help?

Common commands for quick reference:

```bash
# Restart everything
systemctl restart cups
systemctl restart print-queue-manager

# Check printer status
lpstat -p -d

# Check pending jobs
lpstat -o

# Clear all jobs (emergency)
cancel -a

# Check if printer is online
lpinfo -v

# Test print
echo "Test" | lpr -P HP_Smart_Tank_515
```
