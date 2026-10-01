#!/bin/sh
# Periodic PostgreSQL backups. Runs forever inside the db-backup container.
# Uses the standard libpq variables (PGHOST, PGUSER, PGPASSWORD, PGDATABASE) plus
# BACKUP_INTERVAL_HOURS (default 24) and BACKUP_KEEP_DAYS (default 7).
set -u

BACKUP_DIR="${BACKUP_DIR:-/backups}"
INTERVAL_HOURS="${BACKUP_INTERVAL_HOURS:-24}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"

mkdir -p "$BACKUP_DIR"

backup() {
  ts="$(date -u +%Y%m%d-%H%M%S)"
  name="${PGDATABASE}-${ts}.dump"
  tmp="$BACKUP_DIR/$name.partial"

  if pg_dump --format=custom --file="$tmp"; then
    mv "$tmp" "$BACKUP_DIR/$name"
    ln -sfn "$name" "$BACKUP_DIR/latest.dump"
    size="$(du -h "$BACKUP_DIR/$name" | cut -f1)"
    echo "backup ok: $name ($size)"
    find "$BACKUP_DIR" -maxdepth 1 -name "${PGDATABASE}-*.dump" -mtime "+${KEEP_DAYS}" -delete
    return 0
  fi

  rm -f "$tmp"
  echo "backup FAILED: pg_dump returned an error" >&2
  return 1
}

until pg_isready -q; do
  echo "waiting for the database..."
  sleep 3
done

while true; do
  backup || true
  echo "next backup in ${INTERVAL_HOURS}h"
  sleep $((INTERVAL_HOURS * 3600))
done