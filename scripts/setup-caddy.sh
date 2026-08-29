#!/bin/bash
# Install the supplied PrintQ Caddyfile and safely reload Caddy.
set -euo pipefail

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "❌ Run this script as root: sudo bash scripts/setup-caddy.sh" >&2
    exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
SOURCE_CONFIG="$PROJECT_DIR/config/caddy/Caddyfile"
TARGET_CONFIG=/etc/caddy/Caddyfile
SOURCE_DROPIN="$PROJECT_DIR/config/systemd/print-queue-manager-caddy.conf"
TARGET_DROPIN=/etc/systemd/system/print-queue-manager.service.d/20-caddy-local-bind.conf
ENV_FILE=${1:-/opt/print-queue-manager/.env}

if ! command -v caddy >/dev/null 2>&1; then
    echo "❌ Caddy is not installed." >&2
    echo "   Install the official Caddy package for your distribution, then rerun this script:" >&2
    echo "   https://caddyserver.com/docs/install" >&2
    exit 1
fi

if [ ! -f "$SOURCE_CONFIG" ] || [ ! -f "$SOURCE_DROPIN" ]; then
    echo "❌ The repository's Caddy configuration files are incomplete." >&2
    exit 1
fi

install -d -m 0755 /etc/caddy
if [ -f "$TARGET_CONFIG" ] && ! cmp -s "$SOURCE_CONFIG" "$TARGET_CONFIG"; then
    backup_file="${TARGET_CONFIG}.backup.$(date +%Y%m%d-%H%M%S)"
    cp -a "$TARGET_CONFIG" "$backup_file"
    echo "ℹ️  Existing Caddyfile backed up to $backup_file"
fi

install -m 0644 "$SOURCE_CONFIG" "$TARGET_CONFIG"
caddy fmt --overwrite "$TARGET_CONFIG"
caddy validate --config "$TARGET_CONFIG" --adapter caddyfile

# Prevent clients from bypassing Caddy after PrintQ starts trusting forwarded
# HTTPS/host headers. This drop-in is reversible and leaves CUPS port 631 alone.
install -d -m 0755 "$(dirname "$TARGET_DROPIN")"
install -m 0644 "$SOURCE_DROPIN" "$TARGET_DROPIN"
systemctl daemon-reload

if [ -f "$ENV_FILE" ]; then
    if grep -q '^TRUST_PROXY=' "$ENV_FILE"; then
        sed -i 's/^TRUST_PROXY=.*/TRUST_PROXY=true/' "$ENV_FILE"
    else
        printf '\n# Trust the local Caddy reverse proxy.\nTRUST_PROXY=true\n' >> "$ENV_FILE"
    fi
    systemctl restart print-queue-manager
    echo "✅ Enabled trusted proxy headers and bound PrintQ to 127.0.0.1:5000"
else
    echo "⚠️  $ENV_FILE was not found; set TRUST_PROXY=true in PrintQ's environment manually."
fi

systemctl enable --now caddy
systemctl reload caddy

if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-service=http
    firewall-cmd --permanent --add-service=https
    firewall-cmd --permanent --remove-port=5000/tcp >/dev/null 2>&1 || true
    firewall-cmd --reload
    echo "✅ firewalld allows HTTP/HTTPS and no longer exposes PrintQ port 5000"
fi

echo "✅ Caddy is serving PrintQ at https://printq.echo.story"
echo "   CUPS printers: https://printq.echo.story/printers/ (or /cups)"
echo "   CUPS administration remains at http://<server-ip>:631/admin"
