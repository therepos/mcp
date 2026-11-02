#!/bin/sh
# Started as root (default): make /data writable for PUID:PGID, then drop to that user,
# so new files in the share belong to it. Started with `user:` set: run as that user.
set -e
if [ "$(id -u)" = "0" ]; then
    PUID="${PUID:-1000}"
    PGID="${PGID:-1000}"
    mkdir -p /data
    chown "$PUID:$PGID" /data
    exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$@"
fi
exec "$@"
