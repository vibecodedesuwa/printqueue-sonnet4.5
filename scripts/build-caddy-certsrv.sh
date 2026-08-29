#!/bin/bash
# Build a Caddy binary containing the pinned caddy-certsrv source revision.
set -euo pipefail

PLUGIN=github.com/davidventura/caddy-certsrv@3eb8888623288fd14c89847e12eb058a43bb4a55
OUTPUT=${1:-./caddy-certsrv}

case "$OUTPUT" in
    /*) ;;
    *) OUTPUT="$(pwd)/${OUTPUT#./}" ;;
esac

if ! command -v go >/dev/null 2>&1; then
    echo "❌ Go is not installed or is not in PATH." >&2
    exit 1
fi

if command -v xcaddy >/dev/null 2>&1; then
    XCADDY=$(command -v xcaddy)
elif [ -x "$HOME/go/bin/xcaddy" ]; then
    XCADDY="$HOME/go/bin/xcaddy"
else
    echo "❌ xcaddy was not found. Install it with:" >&2
    echo "   go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest" >&2
    exit 1
fi

echo "🔨 Building Caddy with $PLUGIN ..."
"$XCADDY" build --output "$OUTPUT" --with "$PLUGIN"

if ! "$OUTPUT" list-modules | grep -qx 'tls.issuance.certsrv'; then
    echo "❌ The resulting binary does not contain tls.issuance.certsrv." >&2
    exit 1
fi

echo "✅ Custom Caddy binary created at $OUTPUT"
echo "   Verify it, then stop Caddy and install it as /usr/bin/caddy."
