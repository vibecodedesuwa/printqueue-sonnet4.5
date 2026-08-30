#!/bin/bash
# Join the PrintQ host to Active Directory with Samba/Winbind and expose a
# dedicated held CUPS queue for Windows clients over SMB.

set -e

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
# shellcheck source=platform.sh
. "$SCRIPT_DIR/platform.sh"

if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

load_samba_settings() {
    local line key value
    [ -f "$1" ] || return 0
    echo "📄 Loading settings from $1"
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
            PRINTER_NAME|LDAP_TEST_USER|SAMBA_REALM|SAMBA_WORKGROUP|SAMBA_HOSTNAME|SAMBA_JOIN_USER|SAMBA_SHARE_NAME|SAMBA_WINDOWS_QUEUE)
                if [ -z "${!key+x}" ]; then
                    printf -v "$key" '%s' "$value"
                    export "$key"
                fi
                ;;
        esac
    done < "$1"
}

ENV_FILE="${1:-$SCRIPT_DIR/../.env}"
load_samba_settings "$ENV_FILE"
detect_platform

PRINTER_NAME="${PRINTER_NAME:-}"
SAMBA_REALM="${SAMBA_REALM:-}"
SAMBA_WORKGROUP="${SAMBA_WORKGROUP:-}"
SAMBA_HOSTNAME="${SAMBA_HOSTNAME:-}"
SAMBA_JOIN_USER="${SAMBA_JOIN_USER:-Administrator}"
SAMBA_SHARE_NAME="${SAMBA_SHARE_NAME:-PrintQ}"
SAMBA_WINDOWS_QUEUE="${SAMBA_WINDOWS_QUEUE:-${PRINTER_NAME}_windows}"
LDAP_TEST_USER="${LDAP_TEST_USER:-}"

SAMBA_REALM=${SAMBA_REALM,,}
SAMBA_REALM_UPPER=${SAMBA_REALM^^}
SAMBA_WORKGROUP=${SAMBA_WORKGROUP^^}
SAMBA_HOSTNAME=${SAMBA_HOSTNAME,,}

if [ -z "$PRINTER_NAME" ] || [ -z "$SAMBA_REALM" ] || [ -z "$SAMBA_WORKGROUP" ] || [ -z "$SAMBA_HOSTNAME" ]; then
    echo "❌ PRINTER_NAME, SAMBA_REALM, SAMBA_WORKGROUP, and SAMBA_HOSTNAME are required."
    exit 1
fi
if ! [[ "$SAMBA_WORKGROUP" =~ ^[A-Z0-9][A-Z0-9_-]{0,14}$ ]]; then
    echo "❌ SAMBA_WORKGROUP must be the AD NetBIOS name (1-15 letters/numbers)."
    exit 1
fi
if ! [[ "$PRINTER_NAME" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,126}$ ]]; then
    echo "❌ PRINTER_NAME is not a valid CUPS queue name."
    exit 1
fi
if ! [[ "$SAMBA_SHARE_NAME" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$ ]]; then
    echo "❌ SAMBA_SHARE_NAME may contain only letters, numbers, underscore, and hyphen."
    exit 1
fi
if ! [[ "$SAMBA_WINDOWS_QUEUE" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,126}$ ]]; then
    echo "❌ SAMBA_WINDOWS_QUEUE is not a valid CUPS queue name."
    exit 1
fi
case "$SAMBA_HOSTNAME" in
    localhost|localhost.localdomain|*[^a-z0-9.-]*)
        echo "❌ SAMBA_HOSTNAME must be a real lowercase FQDN, not localhost."
        exit 1
        ;;
    *".$SAMBA_REALM") ;;
    *)
        echo "❌ SAMBA_HOSTNAME '$SAMBA_HOSTNAME' must be inside realm '$SAMBA_REALM'."
        exit 1
        ;;
esac
if ! lpstat -p "$PRINTER_NAME" >/dev/null 2>&1; then
    echo "❌ Source CUPS printer '$PRINTER_NAME' does not exist."
    exit 1
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║          Windows Samba/AD Print Share Setup              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "  Realm:          $SAMBA_REALM_UPPER"
echo "  Workgroup:      $SAMBA_WORKGROUP"
echo "  Server FQDN:    $SAMBA_HOSTNAME"
echo "  CUPS source:    $PRINTER_NAME"
echo "  Windows queue:  $SAMBA_WINDOWS_QUEUE"
printf '  Windows share:  \\\\%s\\%s\n' "$SAMBA_HOSTNAME" "$SAMBA_SHARE_NAME"
echo ""

echo "📦 Installing Samba AD-member packages..."
package_update
if [ "$PRINTQ_DISTRO_FAMILY" = "rhel" ]; then
    package_install \
        realmd oddjob-mkhomedir samba samba-client samba-common-tools \
        samba-winbind samba-winbind-clients samba-winbind-krb5-locator \
        krb5-workstation
else
    package_install \
        realmd samba smbclient winbind libnss-winbind libpam-winbind \
        samba-common-bin krb5-user
fi

echo "🔎 Checking AD DNS discovery..."
if ! realm discover "$SAMBA_REALM"; then
    echo "❌ The AD realm could not be discovered."
    echo "   Configure this server to use the AD DNS server, then retry."
    exit 1
fi
if [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" != "yes" ]; then
    echo "⚠️  System time is not reported as synchronized. Kerberos normally requires"
    echo "   the PrintQ server and domain controller clocks to be within five minutes."
fi

if [ "$(hostname -f 2>/dev/null || hostname)" != "$SAMBA_HOSTNAME" ]; then
    echo "🔧 Setting the server hostname to $SAMBA_HOSTNAME..."
    hostnamectl set-hostname "$SAMBA_HOSTNAME"
fi
if ! getent hosts "$SAMBA_HOSTNAME" >/dev/null 2>&1; then
    echo "⚠️  $SAMBA_HOSTNAME does not resolve yet. The AD join may register it dynamically,"
    echo "   but a stable forward and reverse DNS record is strongly recommended."
fi

mkdir -p /etc/samba
if [ -f /etc/samba/smb.conf ]; then
    cp -a /etc/samba/smb.conf "/etc/samba/smb.conf.printq-backup.$(date +%Y%m%d_%H%M%S)"
fi

if net ads testjoin >/dev/null 2>&1; then
    echo "✅ This server is already joined to an AD domain"
else
    echo "🔐 Joining $SAMBA_REALM_UPPER as $SAMBA_JOIN_USER..."
    echo "   The realm tool will prompt for the AD join account password."
    realm join \
        --membership-software=samba \
        --client-software=winbind \
        --user="$SAMBA_JOIN_USER" \
        "$SAMBA_REALM"
fi

# A Samba server backed by AD must use Winbind rather than SSSD. realmd normally
# selects this profile; explicitly stop the old PrintQ SSSD provider afterward.
systemctl disable --now sssd >/dev/null 2>&1 || true
if [ "$PRINTQ_DISTRO_FAMILY" = "rhel" ]; then
    if authselect current 2>/dev/null | grep -q 'Profile ID: winbind'; then
        echo "✅ authselect is already using the Winbind profile"
    else
        echo "🔧 Switching PAM/NSS from SSSD to Winbind..."
        authselect select winbind with-mkhomedir --force
    fi
fi

echo "🖨️  Creating the dedicated held Windows CUPS queue..."
DEVICE_LINE=$(lpstat -v "$PRINTER_NAME" | head -n 1)
DEVICE_URI=${DEVICE_LINE#*: }
if [ -z "$DEVICE_URI" ] || [ "$DEVICE_URI" = "$DEVICE_LINE" ]; then
    echo "❌ Could not determine the device URI for '$PRINTER_NAME'."
    exit 1
fi

SOURCE_PPD="/etc/cups/ppd/${PRINTER_NAME}.ppd"
if [ -f "$SOURCE_PPD" ]; then
    lpadmin -p "$SAMBA_WINDOWS_QUEUE" -E -v "$DEVICE_URI" -P "$SOURCE_PPD"
elif [[ "$DEVICE_URI" = ipp://* || "$DEVICE_URI" = ipps://* ]]; then
    lpadmin -p "$SAMBA_WINDOWS_QUEUE" -E -v "$DEVICE_URI" -m everywhere
else
    echo "❌ The source queue has no reusable PPD and is not driverless IPP."
    echo "   Add the Windows queue manually, then rerun this script."
    exit 1
fi
lpadmin -p "$SAMBA_WINDOWS_QUEUE" \
    -o job-hold-until-default=indefinite \
    -o printer-is-shared=false \
    -o printer-op-policy=default
cupsenable "$SAMBA_WINDOWS_QUEUE"
cupsaccept "$SAMBA_WINDOWS_QUEUE"

mkdir -p /var/spool/samba
chmod 1777 /var/spool/samba
restorecon -RF /var/spool/samba 2>/dev/null || true

cat > /etc/samba/smb.conf <<EOF
# Auto-generated by PrintQ. Re-run setup-windows-samba.sh to update.
[global]
    workgroup = $SAMBA_WORKGROUP
    realm = $SAMBA_REALM_UPPER
    security = ADS
    server role = member server
    server min protocol = SMB2
    kerberos method = secrets and keytab
    dns proxy = no

    idmap config * : backend = tdb
    idmap config * : range = 10000-999999
    idmap config $SAMBA_WORKGROUP : backend = rid
    idmap config $SAMBA_WORKGROUP : range = 1000000-199999999
    winbind use default domain = yes
    winbind refresh tickets = yes
    winbind offline logon = yes
    template shell = /sbin/nologin
    template homedir = /home/%U

    printing = cups
    printcap name = cups
    printcap cache time = 60
    lpq cache time = 30
    load printers = no
    rpcd_spoolss:idle_seconds = 300
    rpcd_spoolss:num_workers = 5
    map to guest = never

# samba-bgqd and rpcd_spoolss use this special hidden template to maintain
# Samba's CUPS printer cache. Individual queues are still exposed explicitly.
[printers]
    comment = PrintQ CUPS printer template
    path = /var/spool/samba
    printable = yes
    browseable = no
    guest ok = no
    read only = yes
    create mask = 0600
    use client driver = yes
    cups options = "raw job-hold-until=indefinite"

[$SAMBA_SHARE_NAME]
    comment = PrintQ AD-authenticated Windows queue
    path = /var/spool/samba
    printer name = $SAMBA_WINDOWS_QUEUE
    printable = yes
    browseable = yes
    guest ok = no
    read only = yes
    create mask = 0600
    use client driver = yes
    force printername = yes
    # Force every Windows submission to remain visible in CUPS and PrintQ.
    # Some Windows drivers explicitly submit no-hold and otherwise override the
    # queue's job-hold-until-default value.
    cups options = "raw job-hold-until=indefinite"
EOF

if ! testparm -s /etc/samba/smb.conf >/dev/null; then
    echo "❌ Generated Samba configuration failed validation."
    exit 1
fi

if [ "$PRINTQ_DISTRO_FAMILY" = "rhel" ]; then
    WINBIND_SERVICE=winbind
    SMB_SERVICE=smb
else
    WINBIND_SERVICE=winbind
    SMB_SERVICE=smbd
fi
service_enable_start "$WINBIND_SERVICE"
service_enable_start "$SMB_SERVICE"
if systemctl cat samba-bgqd.service >/dev/null 2>&1; then
    systemctl enable samba-bgqd.service
fi

# setup-windows-samba.sh is intentionally rerunnable. Restart existing daemons
# so they all consume the newly generated configuration immediately.
systemctl restart "$WINBIND_SERVICE"
systemctl restart "$SMB_SERVICE"
if systemctl cat samba-bgqd.service >/dev/null 2>&1; then
    systemctl restart samba-bgqd.service
fi

if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-service=samba
    firewall-cmd --reload
fi

echo "🔎 Verifying the AD trust and identity mapping..."
wbinfo --check-secret
if [ -n "$LDAP_TEST_USER" ]; then
    TEST_IDENTITIES=("$LDAP_TEST_USER")
    if [[ "$LDAP_TEST_USER" != *'\'* && "$LDAP_TEST_USER" != *@* ]]; then
        TEST_IDENTITIES+=("${SAMBA_WORKGROUP}\\${LDAP_TEST_USER}")
        TEST_IDENTITIES+=("${LDAP_TEST_USER}@${SAMBA_REALM}")
    fi

    RESOLVED_TEST_USER=
    for TEST_IDENTITY in "${TEST_IDENTITIES[@]}"; do
        if getent passwd "$TEST_IDENTITY" >/dev/null; then
            RESOLVED_TEST_USER=$TEST_IDENTITY
            break
        fi
    done

    if [ -z "$RESOLVED_TEST_USER" ]; then
        echo "❌ Winbind cannot resolve LDAP_TEST_USER '$LDAP_TEST_USER'."
        echo "   Check SAMBA_REALM, SAMBA_WORKGROUP, AD DNS, and the domain join."
        exit 1
    fi
    getent passwd "$RESOLVED_TEST_USER"
    if [ "$RESOLVED_TEST_USER" != "$LDAP_TEST_USER" ]; then
        echo "✅ Winbind resolved '$LDAP_TEST_USER' as '$RESOLVED_TEST_USER'"
    fi
fi

# Keep authenticated IPP on the original queue; Samba authentication protects
# the separate Windows queue before it submits locally to CUPS.
lpadmin -p "$PRINTER_NAME" -o printer-op-policy=authenticated
systemctl restart cups

echo ""
echo "✅ Windows Samba/AD printing is ready"
echo "   Connect domain-joined Windows computers to:"
printf '   \\\\%s\\%s\n' "$SAMBA_HOSTNAME" "$SAMBA_SHARE_NAME"
echo ""
echo "   CUPS queue: $SAMBA_WINDOWS_QUEUE (held, local Samba submissions)"
echo "   IPP queue:  $PRINTER_NAME (authenticated AirPrint/Mopria)"
