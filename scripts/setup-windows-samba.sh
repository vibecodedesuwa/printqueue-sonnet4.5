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
            PRINTER_NAME|LDAP_TEST_USER|SAMBA_REALM|SAMBA_WORKGROUP|SAMBA_HOSTNAME|SAMBA_JOIN_USER|SAMBA_SHARE_NAME|SAMBA_WINDOWS_QUEUE|AIRPRINT_DEFAULT_MEDIA)
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

install_samba_selinux_workaround() {
    local policy_dir

    [ "$PRINTQ_DISTRO_FAMILY" = "rhel" ] || return 0
    command -v selinuxenabled >/dev/null 2>&1 || return 0
    selinuxenabled || return 0

    echo "🔐 Installing the narrow Samba spooler SELinux compatibility rule..."
    policy_dir=$(mktemp -d)
    cat > "$policy_dir/printq_samba_spoolss.te" <<'POLICY'
module printq_samba_spoolss 1.0;

require {
    type samba_dcerpcd_t;
    type samba_bgqd_var_run_t;
    class file { getattr open read };
}

# EL10 Samba 4.23 runs rpcd_spoolss in samba_dcerpcd_t, but the stock policy
# can prevent it from reading samba-bgqd.pid while refreshing the CUPS cache.
allow samba_dcerpcd_t samba_bgqd_var_run_t:file { getattr open read };
POLICY
    checkmodule -M -m \
        -o "$policy_dir/printq_samba_spoolss.mod" \
        "$policy_dir/printq_samba_spoolss.te"
    semodule_package \
        -o "$policy_dir/printq_samba_spoolss.pp" \
        -m "$policy_dir/printq_samba_spoolss.mod"
    semodule -i "$policy_dir/printq_samba_spoolss.pp"
    rm -f \
        "$policy_dir/printq_samba_spoolss.te" \
        "$policy_dir/printq_samba_spoolss.mod" \
        "$policy_dir/printq_samba_spoolss.pp"
    rmdir "$policy_dir"
}

prepare_samba_printer_cache() {
    local lock_dir domain_users_name domain_users_sid domain_users_gid cache_file

    [ "$PRINTQ_DISTRO_FAMILY" = "rhel" ] || return 0
    lock_dir=$(smbd -b | awk -F': ' '/^[[:space:]]*LOCKDIR:/ {print $2; exit}')
    if [ -z "$lock_dir" ] || [ ! -d "$lock_dir" ]; then
        echo "❌ Samba's compiled lock directory could not be found."
        return 1
    fi

    domain_users_name="${SAMBA_WORKGROUP}\\domain users"
    domain_users_gid=$(getent group "$domain_users_name" | cut -d: -f3)
    if ! [[ "$domain_users_gid" =~ ^[0-9]+$ ]]; then
        # NSS group enumeration/lookups can be disabled even when Winbind's
        # direct SID mapping is healthy. Resolve the well-known AD group
        # through wbinfo instead of treating that NSS behavior as a failed join.
        domain_users_sid=$(
            wbinfo --name-to-sid "$domain_users_name" 2>/dev/null |
                awk '/SID_DOM_GROUP|SID_ALIAS/ {print $1; exit}'
        )
        if [ -n "$domain_users_sid" ]; then
            domain_users_gid=$(
                wbinfo --sid-to-gid "$domain_users_sid" 2>/dev/null |
                    awk '/^[0-9]+$/ {print; exit}'
            )
        fi
    fi
    if ! [[ "$domain_users_gid" =~ ^[0-9]+$ ]]; then
        echo "❌ Winbind cannot map '$domain_users_name' to a local GID."
        echo "   The Samba printer cache cannot be prepared safely."
        echo "   Verify: wbinfo --name-to-sid '$domain_users_name'"
        return 1
    fi

    echo "✅ Winbind mapped '$domain_users_name' to GID $domain_users_gid"

    cache_file="$lock_dir/printer_list.tdb"
    touch "$cache_file"
    chown root:"$domain_users_gid" "$cache_file"
    chmod 0660 "$cache_file"
    command -v restorecon >/dev/null 2>&1 && restorecon -F "$cache_file" || true
    echo "✅ Samba printer cache prepared at $cache_file"
}

PRINTER_NAME="${PRINTER_NAME:-}"
SAMBA_REALM="${SAMBA_REALM:-}"
SAMBA_WORKGROUP="${SAMBA_WORKGROUP:-}"
SAMBA_HOSTNAME="${SAMBA_HOSTNAME:-}"
SAMBA_JOIN_USER="${SAMBA_JOIN_USER:-Administrator}"
SAMBA_SHARE_NAME="${SAMBA_SHARE_NAME:-PrintQ}"
SAMBA_WINDOWS_QUEUE="${SAMBA_WINDOWS_QUEUE:-${PRINTER_NAME}_windows}"
AIRPRINT_DEFAULT_MEDIA="${AIRPRINT_DEFAULT_MEDIA:-iso_a4_210x297mm}"
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
        krb5-workstation checkpolicy policycoreutils policycoreutils-devel
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

echo "🖨️  Creating the dedicated held Windows CUPS class..."
# Never create a second queue pointing at the same USB device. CUPS schedules
# backends per destination, so duplicate HPLIP queues can open the USB device
# concurrently and fail with HPMUD_R_IO_ERROR (stat=12). A one-member class
# preserves a distinct held destination while the source queue remains the only
# owner of the physical backend.
if lpstat -p "$SAMBA_WINDOWS_QUEUE" >/dev/null 2>&1; then
    echo "🔄 Migrating the old duplicate Windows queue to a CUPS class..."
    if lpstat -W not-completed -o "$SAMBA_WINDOWS_QUEUE" 2>/dev/null | grep -q .; then
        lpmove "$SAMBA_WINDOWS_QUEUE" "$PRINTER_NAME"
        echo "✅ Pending Windows jobs moved safely to '$PRINTER_NAME'"
    fi
    lpadmin -x "$SAMBA_WINDOWS_QUEUE"
fi

lpadmin -p "$PRINTER_NAME" -c "$SAMBA_WINDOWS_QUEUE"
lpadmin -p "$PRINTER_NAME" \
    -o media-default="$AIRPRINT_DEFAULT_MEDIA" \
    -o media="$AIRPRINT_DEFAULT_MEDIA" \
    -o outputorder-default=normal
set_printer_retry_policy "$PRINTER_NAME"
lpadmin -p "$SAMBA_WINDOWS_QUEUE" \
    -o job-hold-until-default=indefinite \
    -o media-default="$AIRPRINT_DEFAULT_MEDIA" \
    -o media="$AIRPRINT_DEFAULT_MEDIA" \
    -o outputorder-default=normal \
    -o printer-is-shared=false \
    -o printer-op-policy=default
set_printer_retry_policy "$SAMBA_WINDOWS_QUEUE"
cupsenable "$SAMBA_WINDOWS_QUEUE"
cupsaccept "$SAMBA_WINDOWS_QUEUE"

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
    # Only publish the explicitly configured PrintQ share.
    load printers = no
    # Keep SPOOLSS available for Windows Local Port clients. EL10 Samba 4.23
    # runs this through rpcd_spoolss; setup prepares its cache and installs the
    # narrow SELinux access it requires above.
    map to guest = never

# Hidden template used by Samba's SPOOLSS/client-driver print paths. Individual
# queues are still exposed explicitly.
[printers]
    comment = PrintQ CUPS printer template
    # Use the distribution-supported temporary spool location. On enforcing
    # SELinux systems, a custom /var/spool/samba directory can make
    # Samba fail to stat its spool file and return WERR_INVALID_NAME.
    path = /var/tmp/
    printable = yes
    browseable = no
    guest ok = no
    read only = yes
    create mask = 0600
    use client driver = yes
    # Preserve the client's document format so CUPS can detect and convert a
    # generic Type 3 PostScript job through the physical queue's HPLIP filters.
    cups options = "job-hold-until=indefinite outputorder=normal"

[$SAMBA_SHARE_NAME]
    comment = PrintQ AD-authenticated Windows queue
    path = /var/tmp/
    printer name = $SAMBA_WINDOWS_QUEUE
    printable = yes
    browseable = yes
    guest ok = no
    read only = yes
    create mask = 0600
    use client driver = yes
    # Keep the explicit CUPS queue mapping above. "force printername" makes
    # Samba submit to the share name ($SAMBA_SHARE_NAME) instead, which fails
    # with WERR_INVALID_NAME when no CUPS queue has that name.
    # Force every Windows submission to remain visible in CUPS and PrintQ.
    # Some Windows drivers explicitly submit no-hold and otherwise override the
    # queue's job-hold-until-default value.
    cups options = "job-hold-until=indefinite outputorder=normal"
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
install_samba_selinux_workaround
prepare_samba_printer_cache
service_enable_start "$SMB_SERVICE"
if systemctl cat samba-bgqd.service >/dev/null 2>&1; then
    systemctl enable samba-bgqd.service
fi

# setup-windows-samba.sh is intentionally rerunnable. Fully stop the printing
# processes so workers consume the new configuration, cache, and SELinux rule.
systemctl stop "$SMB_SERVICE"
if systemctl cat samba-bgqd.service >/dev/null 2>&1; then
    systemctl stop samba-bgqd.service
fi
pkill -TERM -x rpcd_spoolss >/dev/null 2>&1 || true

systemctl restart "$WINBIND_SERVICE"
systemctl start "$SMB_SERVICE"
if systemctl cat samba-bgqd.service >/dev/null 2>&1; then
    systemctl start samba-bgqd.service
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
echo "   CUPS class: $SAMBA_WINDOWS_QUEUE (held; feeds $PRINTER_NAME)"
echo "   IPP queue:  $PRINTER_NAME (authenticated AirPrint/Mopria)"
