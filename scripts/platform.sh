#!/bin/bash
# Shared Linux distribution helpers for PrintQ installation scripts.

detect_platform() {
    local os_release_file="${PRINTQ_OS_RELEASE_FILE:-/etc/os-release}"

    if [ ! -r "$os_release_file" ]; then
        echo "❌ Cannot read $os_release_file; this installer requires Linux with os-release metadata." >&2
        return 1
    fi

    # Defaults prevent inherited environment values from affecting detection.
    ID=
    ID_LIKE=
    NAME=
    VERSION_ID=
    # os-release is a shell-compatible, OS-owned data file.
    # shellcheck disable=SC1090
    . "$os_release_file"

    PRINTQ_DISTRO_ID="${ID:-unknown}"
    PRINTQ_DISTRO_NAME="${NAME:-$PRINTQ_DISTRO_ID}"
    PRINTQ_DISTRO_VERSION="${VERSION_ID:-unknown}"

    case " ${ID:-} ${ID_LIKE:-} " in
        *" debian "*)
            PRINTQ_DISTRO_FAMILY=debian
            PRINTQ_PACKAGE_MANAGER=apt-get
            ;;
        *" fedora "*|*" rhel "*|*" centos "*)
            PRINTQ_DISTRO_FAMILY=rhel
            if command -v dnf >/dev/null 2>&1; then
                PRINTQ_PACKAGE_MANAGER=dnf
            elif command -v yum >/dev/null 2>&1; then
                PRINTQ_PACKAGE_MANAGER=yum
            else
                echo "❌ A supported RHEL-family package manager (dnf or yum) was not found." >&2
                return 1
            fi
            ;;
        *)
            echo "❌ Unsupported Linux distribution: ${PRINTQ_DISTRO_NAME} (${PRINTQ_DISTRO_ID})." >&2
            echo "   Supported families: Debian/Ubuntu and Fedora/RHEL/CentOS/AlmaLinux." >&2
            return 1
            ;;
    esac

    export PRINTQ_DISTRO_ID PRINTQ_DISTRO_NAME PRINTQ_DISTRO_VERSION
    export PRINTQ_DISTRO_FAMILY PRINTQ_PACKAGE_MANAGER
}

package_update() {
    case "$PRINTQ_DISTRO_FAMILY" in
        debian) DEBIAN_FRONTEND=noninteractive apt-get update ;;
        rhel) "$PRINTQ_PACKAGE_MANAGER" -y makecache ;;
    esac
}

package_install() {
    case "$PRINTQ_DISTRO_FAMILY" in
        debian) DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$@" ;;
        rhel) "$PRINTQ_PACKAGE_MANAGER" -y install "$@" ;;
    esac
}

package_available() {
    local package_name="$1"
    case "$PRINTQ_DISTRO_FAMILY" in
        debian) apt-cache show "$package_name" >/dev/null 2>&1 ;;
        rhel) "$PRINTQ_PACKAGE_MANAGER" -q list --available "$package_name" >/dev/null 2>&1 ;;
    esac
}

package_install_optional() {
    local package_name
    for package_name in "$@"; do
        if package_available "$package_name"; then
            package_install "$package_name"
        else
            echo "ℹ️  Optional package '$package_name' is not available in enabled repositories; skipping."
        fi
    done
}

service_enable_start() {
    local service_name="$1"
    systemctl enable "$service_name"
    systemctl start "$service_name"
}

primary_ip() {
    local detected_ip
    detected_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    printf '%s\n' "${detected_ip:-127.0.0.1}"
}
