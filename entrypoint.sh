#!/bin/sh
# Starts as root, fixes ownership of the host mounts, then drops to PUID:PGID to run the app.
set -e

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

# Docker creates a missing bind-mount source as a root-owned directory.
# That is harmless for cache/, but a tokens.ini directory cannot be fixed from here.
if [ -d /app/tokens.ini ]; then
    echo "ERROR: tokens.ini is a directory. On the host: rmdir tokens.ini && touch tokens.ini" >&2
    exit 1
fi

if [ "$(id -u)" = "0" ]; then
    mkdir -p /app/cache
    chown -R "$PUID:$PGID" /app/cache
    [ -f /app/tokens.ini ] && chown "$PUID:$PGID" /app/tokens.ini
    exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$@"
fi

# Already started as a non-root user (e.g. `user:` set in compose): nothing to fix.
exec "$@"
