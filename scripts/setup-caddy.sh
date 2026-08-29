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
SOURCE_CERTSRV_ENV="$PROJECT_DIR/config/caddy/certsrv.env.example"
CERTSRV_ENV=/etc/caddy/certsrv.env
SOURCE_DROPIN="$PROJECT_DIR/config/systemd/print-queue-manager-caddy.conf"
TARGET_DROPIN=/etc/systemd/system/print-queue-manager.service.d/20-caddy-local-bind.conf
CADDY_DROPIN_SOURCE="$PROJECT_DIR/config/systemd/caddy-certsrv.conf"
CADDY_DROPIN_TARGET=/etc/systemd/system/caddy.service.d/20-certsrv-environment.conf
CADDY_SERVICE_SOURCE="$PROJECT_DIR/config/systemd/caddy.service"
CADDY_SERVICE_TARGET=/etc/systemd/system/caddy.service
ENV_FILE=${1:-/opt/print-queue-manager/.env}

if ! command -v caddy >/dev/null 2>&1; then
    echo "❌ Caddy is not installed." >&2
    echo "   Install the official Caddy package for your distribution, then rerun this script:" >&2
    echo "   https://caddyserver.com/docs/install" >&2
    exit 1
fi

if ! caddy list-modules | grep -qx 'tls.issuance.certsrv'; then
    echo "❌ This Caddy binary does not contain tls.issuance.certsrv." >&2
    echo "   Build it first with: bash scripts/build-caddy-certsrv.sh" >&2
    exit 1
fi

if [ ! -f "$SOURCE_CONFIG" ] || [ ! -f "$SOURCE_CERTSRV_ENV" ] || \
   [ ! -f "$SOURCE_DROPIN" ] || [ ! -f "$CADDY_DROPIN_SOURCE" ] || \
   [ ! -f "$CADDY_SERVICE_SOURCE" ]; then
    echo "❌ The repository's Caddy configuration files are incomplete." >&2
    exit 1
fi

# A source-built xcaddy binary does not install the service account or systemd
# unit that distribution packages normally provide. Create only what is absent,
# leaving a packaged Caddy installation untouched.
if ! getent group caddy >/dev/null 2>&1; then
    groupadd --system caddy
fi

if ! id caddy >/dev/null 2>&1; then
    nologin_shell=$(command -v nologin || printf '/sbin/nologin')
    useradd --system --gid caddy --create-home --home-dir /var/lib/caddy \
        --shell "$nologin_shell" --comment "Caddy web server" caddy
fi

install -d -o caddy -g caddy -m 0750 /var/lib/caddy
install -d -o root -g caddy -m 0755 /etc/caddy

if ! systemctl cat caddy.service >/dev/null 2>&1; then
    install -m 0644 "$CADDY_SERVICE_SOURCE" "$CADDY_SERVICE_TARGET"
    command -v restorecon >/dev/null 2>&1 && restorecon -v "$CADDY_SERVICE_TARGET" >/dev/null 2>&1 || true
    systemctl daemon-reload
    echo "✅ Installed the Caddy systemd service for the xcaddy build"
fi

if [ ! -f "$CERTSRV_ENV" ]; then
    install -m 0600 "$SOURCE_CERTSRV_ENV" "$CERTSRV_ENV"
    echo "❌ Created $CERTSRV_ENV. Edit it for your AD CS server, then rerun this script." >&2
    exit 1
fi

# This is a root-owned configuration file. Export its values so the same
# environment-variable expansion used by systemd is available to validation.
set -a
# shellcheck disable=SC1090
. "$CERTSRV_ENV"
set +a

for required_name in CERTSRV_URL CERTSRV_REALM CERTSRV_USERNAME CERTSRV_KEYTAB_PATH; do
    if [ -z "${!required_name:-}" ]; then
        echo "❌ $required_name is missing from $CERTSRV_ENV" >&2
        exit 1
    fi
done

if [ ! -r "$CERTSRV_KEYTAB_PATH" ]; then
    echo "❌ Caddy's AD keytab is not readable: $CERTSRV_KEYTAB_PATH" >&2
    exit 1
fi

if id caddy >/dev/null 2>&1 && ! runuser -u caddy -- test -r "$CERTSRV_KEYTAB_PATH"; then
    echo "❌ The caddy service account cannot read $CERTSRV_KEYTAB_PATH" >&2
    echo "   Run: chown caddy:caddy '$CERTSRV_KEYTAB_PATH' && chmod 0400 '$CERTSRV_KEYTAB_PATH'" >&2
    exit 1
fi

if [ -f "$TARGET_CONFIG" ] && ! cmp -s "$SOURCE_CONFIG" "$TARGET_CONFIG"; then
    backup_file="${TARGET_CONFIG}.backup.$(date +%Y%m%d-%H%M%S)"
    cp -a "$TARGET_CONFIG" "$backup_file"
    echo "ℹ️  Existing Caddyfile backed up to $backup_file"
fi

install -m 0644 "$SOURCE_CONFIG" "$TARGET_CONFIG"
caddy fmt --overwrite "$TARGET_CONFIG"
caddy validate --config "$TARGET_CONFIG" --adapter caddyfile

install -d -m 0755 "$(dirname "$CADDY_DROPIN_TARGET")"
install -m 0644 "$CADDY_DROPIN_SOURCE" "$CADDY_DROPIN_TARGET"

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

systemctl daemon-reload
systemctl enable caddy
systemctl restart caddy

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
