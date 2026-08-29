#!/bin/bash
# Configure the host PAM/NSS stack so CUPS can authenticate AD/LDAP users.
# Debian/Ubuntu use nslcd; Fedora/CentOS/AlmaLinux use SSSD + authselect.

set -e

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
# shellcheck source=platform.sh
. "$SCRIPT_DIR/platform.sh"

if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

load_ldap_settings() {
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
            LDAP_HOST|LDAP_PORT|LDAP_USE_SSL|LDAP_BASE_DN|LDAP_BIND_DN|LDAP_BIND_PASSWORD|LDAP_DOMAIN|LDAP_TEST_USER|LDAP_AD_DOMAIN_SID|LDAP_TLS_REQCERT|PRINTER_NAME)
                if [ -z "${!key+x}" ]; then
                    printf -v "$key" '%s' "$value"
                    export "$key"
                fi
                ;;
        esac
    done < "$1"
}

ENV_FILE="${1:-$SCRIPT_DIR/../.env}"
load_ldap_settings "$ENV_FILE"

LDAP_HOST="${LDAP_HOST:-}"
LDAP_PORT="${LDAP_PORT:-389}"
LDAP_USE_SSL="${LDAP_USE_SSL:-false}"
LDAP_BASE_DN="${LDAP_BASE_DN:-}"
LDAP_BIND_DN="${LDAP_BIND_DN:-}"
LDAP_BIND_PASSWORD="${LDAP_BIND_PASSWORD:-}"
LDAP_TEST_USER="${LDAP_TEST_USER:-}"
LDAP_AD_DOMAIN_SID="${LDAP_AD_DOMAIN_SID:-}"
LDAP_TLS_REQCERT="${LDAP_TLS_REQCERT:-demand}"
PRINTER_NAME="${PRINTER_NAME:-}"

if [ -z "$LDAP_HOST" ] || [ -z "$LDAP_BASE_DN" ]; then
    echo "❌ LDAP_HOST and LDAP_BASE_DN must be set in .env or the environment."
    exit 1
fi
if [[ "$LDAP_BIND_DN" =~ (^|,)CN=CN= ]]; then
    echo "❌ LDAP_BIND_DN appears malformed: '$LDAP_BIND_DN'"
    echo "   It contains CN= twice. It probably should begin with:"
    echo "   CN=${LDAP_BIND_DN#*CN=CN=}"
    exit 1
fi
case "$LDAP_TLS_REQCERT" in demand|hard|allow|try|never) ;; *)
    echo "❌ LDAP_TLS_REQCERT must be demand, hard, allow, try, or never."
    exit 1
esac

detect_platform
if [ "$LDAP_USE_SSL" = "true" ]; then
    LDAP_URI="ldaps://${LDAP_HOST}:${LDAP_PORT}"
else
    LDAP_URI="ldap://${LDAP_HOST}:${LDAP_PORT}"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║          CUPS AD/LDAP Authentication Setup               ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "  Platform:     $PRINTQ_DISTRO_NAME $PRINTQ_DISTRO_VERSION"
echo "  LDAP URI:     $LDAP_URI"
echo "  Base DN:      $LDAP_BASE_DN"
echo "  TLS checking: $LDAP_TLS_REQCERT"
echo "  Bind DN:      ${LDAP_BIND_DN:-(anonymous)}"
echo "  Printer:      ${PRINTER_NAME:-(configure later)}"
echo ""

verify_ldap_bind() {
    local password_file ldap_output ldap_status
    local -a ldap_args

    echo "🔎 Verifying the LDAP bind, TLS connection, and search base..."
    ldap_args=(-LLL -x -o nettimeout=10 -H "$LDAP_URI")
    if [ "$PRINTQ_DISTRO_FAMILY" = "rhel" ] && [ "$LDAP_USE_SSL" != "true" ]; then
        ldap_args+=(-ZZ)
    fi

    password_file=
    if [ -n "$LDAP_BIND_DN" ]; then
        if [ -z "$LDAP_BIND_PASSWORD" ]; then
            echo "❌ LDAP_BIND_DN is set but LDAP_BIND_PASSWORD is empty."
            return 1
        fi
        password_file=$(mktemp)
        chmod 600 "$password_file"
        printf '%s' "$LDAP_BIND_PASSWORD" > "$password_file"
        ldap_args+=(-D "$LDAP_BIND_DN" -y "$password_file")
    fi
    ldap_args+=(-b "$LDAP_BASE_DN" -s base '(objectClass=*)' dn)

    set +e
    ldap_output=$(LDAPTLS_REQCERT="$LDAP_TLS_REQCERT" ldapsearch "${ldap_args[@]}" 2>&1)
    ldap_status=$?
    set -e
    [ -z "$password_file" ] || rm -f -- "$password_file"

    if [ "$ldap_status" -ne 0 ]; then
        echo "❌ LDAP preflight failed; SSSD was not changed."
        printf '%s\n' "$ldap_output" | tail -n 8
        echo ""
        echo "   Check LDAP_BIND_DN, LDAP_BIND_PASSWORD, and LDAP_BASE_DN."
        if [ "$LDAP_USE_SSL" != "true" ] && [ "$PRINTQ_DISTRO_FAMILY" = "rhel" ]; then
            echo "   This RHEL-family path requires StartTLS on port $LDAP_PORT."
            echo "   If AD uses LDAPS instead, set LDAP_USE_SSL=true and LDAP_PORT=636."
            echo "   With a private AD CA, install that CA in the AlmaLinux trust store."
        fi
        return 1
    fi
    echo "✅ LDAP bind, TLS, and search base verified"
}

configure_debian_ldap() {
    if ! [[ "$LDAP_AD_DOMAIN_SID" =~ ^S-1-5-21-([0-9]+-){2}[0-9]+$ ]]; then
        echo "❌ Debian/Ubuntu CUPS authentication requires LDAP_AD_DOMAIN_SID."
        echo "   On a Windows AD management host, run:"
        echo "   (Get-ADDomain).DomainSID.Value"
        echo "   Then add LDAP_AD_DOMAIN_SID=S-1-5-21-... to .env."
        exit 1
    fi
    echo "📦 Installing nslcd + PAM/NSS LDAP packages..."
    package_update
    package_install nslcd libnss-ldapd libpam-ldapd ldap-utils
    verify_ldap_bind

    [ ! -f /etc/nslcd.conf ] || cp -a /etc/nslcd.conf "/etc/nslcd.conf.printq-backup.$(date +%Y%m%d_%H%M%S)"
    cat > /etc/nslcd.conf <<EOF
# Auto-generated by PrintQ. Edit with care.
uid nslcd
gid nslcd
uri ${LDAP_URI}
base ${LDAP_BASE_DN}
EOF
    if [ -n "$LDAP_BIND_DN" ] && [ -n "$LDAP_BIND_PASSWORD" ]; then
        printf 'binddn %s\nbindpw %s\n' "$LDAP_BIND_DN" "$LDAP_BIND_PASSWORD" >> /etc/nslcd.conf
    fi
    cat >> /etc/nslcd.conf <<EOF

# Active Directory attribute mappings
pagesize 1000
referrals off
filter passwd (&(objectClass=user)(!(objectClass=computer))(sAMAccountName=*))
map passwd uid sAMAccountName
map passwd uidNumber objectSid:${LDAP_AD_DOMAIN_SID}
map passwd gidNumber objectSid:${LDAP_AD_DOMAIN_SID}
map passwd homeDirectory "/home/\$sAMAccountName"
map passwd loginShell "/bin/false"
map passwd gecos displayName
filter group (objectClass=group)
map group cn sAMAccountName
map group gidNumber objectSid:${LDAP_AD_DOMAIN_SID}
EOF
    printf '\nssl %s\ntls_reqcert %s\n' "$([ "$LDAP_USE_SSL" = true ] && echo on || echo off)" "$LDAP_TLS_REQCERT" >> /etc/nslcd.conf
    chmod 600 /etc/nslcd.conf

    sed -i -E '/^(passwd|group|shadow):/ { /(^|[[:space:]])ldap([[:space:]]|$)/! s/$/ ldap/; }' /etc/nsswitch.conf
    service_enable_start nslcd
    systemctl restart nslcd
}

configure_rhel_ldap() {
    echo "📦 Installing SSSD + LDAP authentication packages..."
    package_update
    package_install openldap-clients sssd sssd-ldap sssd-tools authselect oddjob-mkhomedir
    verify_ldap_bind

    mkdir -p /etc/sssd
    if [ -f /etc/sssd/sssd.conf ] && ! grep -q 'Auto-generated by PrintQ' /etc/sssd/sssd.conf; then
        echo "❌ Existing non-PrintQ SSSD configuration detected at /etc/sssd/sssd.conf."
        echo "   Refusing to replace a possible realm/IdM configuration. If the host"
        echo "   already resolves AD users, set the CUPS printer policy manually:"
        echo "   lpadmin -p '$PRINTER_NAME' -o printer-op-policy=authenticated"
        exit 1
    fi
    [ ! -f /etc/sssd/sssd.conf ] || cp -a /etc/sssd/sssd.conf "/etc/sssd/sssd.conf.printq-backup.$(date +%Y%m%d_%H%M%S)"
    cat > /etc/sssd/sssd.conf <<EOF
# Auto-generated by PrintQ. Edit with care.
[sssd]
services = nss, pam
domains = printq_ldap

[domain/printq_ldap]
id_provider = ldap
auth_provider = ldap
chpass_provider = ldap
ldap_uri = ${LDAP_URI}
ldap_search_base = ${LDAP_BASE_DN}
ldap_schema = ad
ldap_id_mapping = true
ldap_user_name = sAMAccountName
ldap_group_name = sAMAccountName
cache_credentials = true
enumerate = false
use_fully_qualified_names = false
fallback_homedir = /home/%u
default_shell = /sbin/nologin
ldap_tls_reqcert = ${LDAP_TLS_REQCERT}
# SSSD refuses password authentication over an unencrypted LDAP connection.
# LDAP_USE_SSL=false therefore means LDAP + StartTLS on RHEL-family systems.
ldap_id_use_start_tls = $([ "$LDAP_USE_SSL" = true ] && echo false || echo true)
EOF
    if [ -n "$LDAP_BIND_DN" ] && [ -n "$LDAP_BIND_PASSWORD" ]; then
        printf 'ldap_default_bind_dn = %s\nldap_default_authtok_type = password\nldap_default_authtok = %s\n' \
            "$LDAP_BIND_DN" "$LDAP_BIND_PASSWORD" >> /etc/sssd/sssd.conf
    fi
    chmod 600 /etc/sssd/sssd.conf

    if ! sssctl config-check; then
        echo "❌ The generated SSSD configuration did not pass validation."
        exit 1
    fi

    if authselect current 2>/dev/null | grep -q 'Profile ID: sssd'; then
        echo "✅ authselect is already using the SSSD profile"
    else
        authselect select sssd with-mkhomedir
    fi
    service_enable_start oddjobd
    service_enable_start sssd
    systemctl restart sssd
    sss_cache -E
    sleep 2
    if ! sssctl domain-status printq_ldap; then
        echo "❌ SSSD domain 'printq_ldap' is offline."
        journalctl -u sssd --no-pager -n 50 || true
        exit 1
    fi
}

if [ "$PRINTQ_DISTRO_FAMILY" = "debian" ]; then
    configure_debian_ldap
else
    configure_rhel_ldap
fi

echo "✅ Host identity and PAM authentication configured"
echo ""

if [ -n "$LDAP_TEST_USER" ]; then
    echo "🔎 Verifying AD identity '$LDAP_TEST_USER' through NSS..."
    if ! getent passwd "$LDAP_TEST_USER"; then
        echo "❌ LDAP_TEST_USER '$LDAP_TEST_USER' was not found below LDAP_BASE_DN."
        echo "   Confirm the user's sAMAccountName and that the search base contains the account."
        exit 1
    fi
    echo "✅ AD identity resolution verified"
else
    echo "⚠️  LDAP_TEST_USER is empty; skipping end-to-end getent verification."
    echo "   Set it to an AD sAMAccountName in .env and rerun this script."
fi

if [ ! -f /etc/pam.d/cups ]; then
    echo "❌ /etc/pam.d/cups is missing; CUPS cannot authenticate through PAM/SSSD."
    exit 1
fi

if [ -n "$PRINTER_NAME" ]; then
    echo "🖨️  Applying the authenticated CUPS policy to '$PRINTER_NAME'..."
    if lpstat -p "$PRINTER_NAME" >/dev/null 2>&1; then
        lpadmin -p "$PRINTER_NAME" -o printer-op-policy=authenticated
        systemctl restart cups
        echo "✅ Printer policy set to 'authenticated'"
    else
        echo "⚠️  Printer not found. After adding it, run:"
        echo "   lpadmin -p '$PRINTER_NAME' -o printer-op-policy=authenticated"
    fi
fi

echo ""
echo "🔍 Verify an account with: getent passwd <ad-username>"
echo "✅ CUPS AD/LDAP authentication setup complete"
