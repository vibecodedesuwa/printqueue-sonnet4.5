#!/bin/bash
# setup-airprint.sh — Configure CUPS + Avahi for AirPrint/IPP Everywhere/Mopria
#
# Run this on the Docker host or inside the CUPS container.
# Requires: cups, avahi-daemon, avahi-utils

set -e

PRINTER_NAME="${PRINTER_NAME:-HP_Smart_Tank_515}"
CUPS_HOST="${CUPS_HOST:-localhost}"
CUPS_PORT="${CUPS_PORT:-631}"
AVAHI_SERVICE_DIR="/etc/avahi/services"

echo "🖨️  Setting up AirPrint/IPP Everywhere for printer: $PRINTER_NAME"

# ─── 1. Configure CUPS for network sharing ────────────────────────────
echo "📝 Configuring CUPS..."

cupsctl --share-printers
cupsctl WebInterface=yes
cupsctl --remote-any

# Enable printer sharing for the specific printer
lpadmin -p "$PRINTER_NAME" -o printer-is-shared=true 2>/dev/null || true

# ─── 2. Generate Avahi service file for AirPrint ──────────────────────
echo "📡 Generating Avahi mDNS service file..."

mkdir -p "$AVAHI_SERVICE_DIR"

# Get printer info from CUPS
PRINTER_INFO=$(lpstat -l -p "$PRINTER_NAME" 2>/dev/null | head -5)
PRINTER_LOCATION=$(lpstat -l -p "$PRINTER_NAME" 2>/dev/null | grep "Location:" | awk '{print $2}' || echo "Office")
PRINTER_MODEL=$(lpstat -l -p "$PRINTER_NAME" 2>/dev/null | grep "Description:" | cut -d: -f2- | xargs || echo "$PRINTER_NAME")

cat > "$AVAHI_SERVICE_DIR/AirPrint-$PRINTER_NAME.service" <<EOF
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">$PRINTER_MODEL @ %h</name>

  <service>
    <type>_ipp._tcp</type>
    <subtype>_universal._sub._ipp._tcp</subtype>
    <port>631</port>
    <txt-record>txtvers=1</txt-record>
    <txt-record>qtotal=1</txt-record>
    <txt-record>rp=printers/$PRINTER_NAME</txt-record>
    <txt-record>note=${PRINTER_LOCATION:-Office}</txt-record>
    <txt-record>product=(${PRINTER_MODEL})</txt-record>
    <txt-record>ty=$PRINTER_MODEL</txt-record>
    <txt-record>adminurl=http://${CUPS_HOST}:${CUPS_PORT}/printers/$PRINTER_NAME</txt-record>
    <txt-record>pdl=application/octet-stream,application/pdf,image/jpeg,image/png,image/urf</txt-record>
    <txt-record>Color=T</txt-record>
    <txt-record>Duplex=T</txt-record>
    <txt-record>URF=W8,SRGB24,CP1,RS600</txt-record>
    <txt-record>TLS=1.2</txt-record>
  </service>
</service-group>
EOF

echo "✅ AirPrint service file created: $AVAHI_SERVICE_DIR/AirPrint-$PRINTER_NAME.service"

# ─── 3. Restart Avahi if running ──────────────────────────────────────
if command -v systemctl &>/dev/null && systemctl is-active avahi-daemon &>/dev/null; then
    echo "🔄 Restarting Avahi daemon..."
    systemctl restart avahi-daemon
    echo "✅ Avahi restarted"
elif command -v avahi-daemon &>/dev/null; then
    echo "ℹ️  Avahi daemon not managed by systemd. Please restart manually."
fi

# ─── 4. Verify ────────────────────────────────────────────────────────
echo ""
echo "🔍 Verifying AirPrint advertisement..."
if command -v avahi-browse &>/dev/null; then
    echo "Searching for IPP services (5 seconds)..."
    timeout 5 avahi-browse -t _ipp._tcp 2>/dev/null || echo "  (avahi-browse timed out — this is normal if avahi is not running locally)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ AirPrint setup complete!"
echo ""
echo "Your printer should now be discoverable by:"
echo "  📱 iOS/iPadOS — via AirPrint (auto-discovers)"
echo "  🤖 Android   — via Default Print Service or Mopria"
echo "  💻 macOS     — via System Preferences > Printers"
echo "  🪟 Windows   — Add printer via URL: http://${CUPS_HOST}:${CUPS_PORT}/printers/$PRINTER_NAME"
echo "  🐧 Linux     — via CUPS client: http://${CUPS_HOST}:${CUPS_PORT}/printers/$PRINTER_NAME"
echo ""
echo "⚠️  Make sure UDP 5353 (mDNS) and TCP 631 (IPP) are open in your firewall!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
