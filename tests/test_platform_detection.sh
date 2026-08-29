#!/bin/bash
set -e

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
# shellcheck source=../scripts/platform.sh
. "$REPO_DIR/scripts/platform.sh"

TEST_DIR=$(mktemp -d)
trap 'case "$TEST_DIR" in /tmp/*) rm -rf -- "$TEST_DIR" ;; esac' EXIT

# Let RHEL-family detection find a package manager without requiring dnf on
# the machine that runs this pure detection test.
dnf() { :; }

assert_platform() {
    local expected_id="$1" expected_family="$2" id_like="$3"
    cat > "$TEST_DIR/os-release" <<EOF
ID=$expected_id
ID_LIKE="$id_like"
NAME="Test $expected_id"
VERSION_ID="1"
EOF
    PRINTQ_OS_RELEASE_FILE="$TEST_DIR/os-release"
    detect_platform
    [ "$PRINTQ_DISTRO_ID" = "$expected_id" ]
    [ "$PRINTQ_DISTRO_FAMILY" = "$expected_family" ]
}

assert_platform ubuntu debian debian
assert_platform debian debian debian
assert_platform fedora rhel fedora
assert_platform centos rhel "rhel fedora"
assert_platform almalinux rhel "rhel centos fedora"

echo "platform detection tests: OK"
