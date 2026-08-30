#!/bin/bash
# setup-airprint.sh — Configure CUPS + Avahi for AirPrint/IPP Everywhere/Mopria
#
# Run this on the Docker host or inside the CUPS container.
# Requires: cups, avahi-daemon, avahi-utils

set -e

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)

load_airprint_settings() {
    local line key value
    [ -f "$1" ] || return 0
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
            PRINTER_NAME|CUPS_HOST|CUPS_PORT|AIRPRINT_READY_PAPER_SIZES|AIRPRINT_DUPLEX|AIRPRINT_PAPER_MAX)
                if [ -z "${!key+x}" ]; then
                    printf -v "$key" '%s' "$value"
                    export "$key"
                fi
                ;;
        esac
    done < "$1"
}

load_airprint_settings "${1:-$SCRIPT_DIR/../.env}"

PRINTER_NAME="${PRINTER_NAME:-HP_Smart_Tank_515}"
CUPS_HOST="${CUPS_HOST:-localhost}"
CUPS_PORT="${CUPS_PORT:-631}"
AIRPRINT_READY_PAPER_SIZES="${AIRPRINT_READY_PAPER_SIZES:-A4,A5,A6,B5,Letter,Legal,4x6in,5x7in,EnvelopeDL}"
AIRPRINT_DUPLEX="${AIRPRINT_DUPLEX:-false}"
AIRPRINT_PAPER_MAX="${AIRPRINT_PAPER_MAX:-legal-A4}"
AVAHI_SERVICE_DIR="/etc/avahi/services"

set_printer_retry_policy() {
    local destination="$1" policy
    for policy in retry-job retry-current-job stop-printer; do
        if lpadmin -p "$destination" -o "printer-error-policy=$policy" >/dev/null 2>&1; then
            echo "✅ CUPS error policy for '$destination': $policy"
            return 0
        fi
        echo "ℹ️  CUPS does not support printer-error-policy '$policy' for '$destination'; trying fallback."
    done
    echo "⚠️  Could not set a CUPS error policy for '$destination'; continuing with the existing policy."
    return 0
}

case "$AIRPRINT_DUPLEX" in
    true) AIRPRINT_DUPLEX_TXT=T ;;
    false) AIRPRINT_DUPLEX_TXT=F ;;
    *)
        echo "❌ AIRPRINT_DUPLEX must be true or false." >&2
        exit 1
        ;;
esac
case "$AIRPRINT_PAPER_MAX" in
    '<legal-A4'|legal-A4|tabloid-A3|isoC-A2|'>isoC-A2') ;;
    *)
        echo "❌ AIRPRINT_PAPER_MAX is not a valid AirPrint PaperMax value." >&2
        exit 1
        ;;
esac

echo "🖨️  Setting up AirPrint/IPP Everywhere for printer: $PRINTER_NAME"

# ─── 1. Configure CUPS for network sharing ────────────────────────────
echo "📝 Configuring CUPS..."

if ! lpstat -r >/dev/null 2>&1; then
    echo "❌ CUPS is not running or cannot be reached." >&2
    exit 1
fi

# Make authentication and holding properties part of the queue itself. CUPS
# does not use a named policy until printer-op-policy is explicitly assigned.
if ! lpstat -p "$PRINTER_NAME" >/dev/null 2>&1; then
    echo "❌ Printer '$PRINTER_NAME' does not exist in CUPS." >&2
    echo "   Add it first, then run this script again." >&2
    exit 1
fi
lpadmin -p "$PRINTER_NAME" \
    -o printer-is-shared=true \
    -o printer-op-policy=authenticated \
    -o job-hold-until-default=indefinite
set_printer_retry_policy "$PRINTER_NAME"

# USB/HPLIP printers with manually loaded trays cannot reliably sense paper
# size. Without this CUPS can advertise a single, stale media-ready value (for
# example Legal), causing iOS to hide otherwise supported paper sizes.
if [ -n "$AIRPRINT_READY_PAPER_SIZES" ]; then
    cupsctl "ReadyPaperSizes=$AIRPRINT_READY_PAPER_SIZES"
fi

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
    <txt-record>Duplex=$AIRPRINT_DUPLEX_TXT</txt-record>
    <txt-record>PaperMax=$AIRPRINT_PAPER_MAX</txt-record>
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
