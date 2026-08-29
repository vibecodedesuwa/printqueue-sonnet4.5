#!/bin/sh
set -eu

cups_user="${CUPS_USER:-print}"
cups_password="${CUPS_PASSWORD:-print}"

if ! id "$cups_user" >/dev/null 2>&1; then
    echo "CUPS_USER '$cups_user' does not exist in the image" >&2
    exit 1
fi

printf '%s:%s\n' "$cups_user" "$cups_password" | chpasswd
exec "$@"
