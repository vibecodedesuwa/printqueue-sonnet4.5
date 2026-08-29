#!/bin/bash
# Build a Caddy binary containing the pinned caddy-certsrv source revision.
set -euo pipefail

PLUGIN_MODULE=github.com/davidventura/caddy-certsrv
PLUGIN_COMMIT=3eb8888623288fd14c89847e12eb058a43bb4a55
OUTPUT=${1:-./caddy-certsrv}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
PLUGIN_PATCH="$PROJECT_DIR/config/caddy/caddy-certsrv.patch"

case "$OUTPUT" in
    /*) ;;
    *) OUTPUT="$(pwd)/${OUTPUT#./}" ;;
esac

if ! command -v go >/dev/null 2>&1; then
    echo "❌ Go is not installed or is not in PATH." >&2
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    echo "❌ Git is not installed or is not in PATH." >&2
    exit 1
fi

if [ ! -f "$PLUGIN_PATCH" ]; then
    echo "❌ The PrintQ caddy-certsrv safety patch is missing: $PLUGIN_PATCH" >&2
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

PATCHED_PLUGIN_DIR=$(mktemp -d)
PATCHED_PLUGIN_PARENT=$(cd "$(dirname "$PATCHED_PLUGIN_DIR")" && pwd)
PATCHED_PLUGIN_DIR=$(cd "$PATCHED_PLUGIN_DIR" && pwd)
cleanup_plugin_source() {
    case "$PATCHED_PLUGIN_DIR" in
        "$PATCHED_PLUGIN_PARENT"/*) rm -rf -- "$PATCHED_PLUGIN_DIR" ;;
        *) echo "⚠️  Refusing to remove unexpected temporary path: $PATCHED_PLUGIN_DIR" >&2 ;;
    esac
}
trap cleanup_plugin_source EXIT

echo "📥 Fetching pinned caddy-certsrv source $PLUGIN_COMMIT ..."
git clone --quiet --no-checkout https://github.com/davidventura/caddy-certsrv.git "$PATCHED_PLUGIN_DIR"
git -C "$PATCHED_PLUGIN_DIR" checkout --quiet "$PLUGIN_COMMIT"
git -C "$PATCHED_PLUGIN_DIR" apply "$PLUGIN_PATCH"

echo "🔨 Building Caddy with the pinned, safety-patched AD CS issuer ..."
"$XCADDY" build --output "$OUTPUT" --with "$PLUGIN_MODULE=$PATCHED_PLUGIN_DIR"

if ! "$OUTPUT" list-modules | grep -qx 'tls.issuance.certsrv'; then
    echo "❌ The resulting binary does not contain tls.issuance.certsrv." >&2
    exit 1
fi

echo "✅ Custom Caddy binary created at $OUTPUT"
echo "   Verify it, then stop Caddy and install it as /usr/bin/caddy."
