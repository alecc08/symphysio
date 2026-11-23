#!/usr/bin/env bash
# Safe SQLite backup: uses sqlite3's online .backup (consistent even while the
# app is writing), gzip-compresses, verifies, and prunes old dumps.
#
#   ./scripts/backup.sh                       # -> ./backups/symphysio-YYYYmmdd-HHMMSS.sqlite.gz
#   DB=/data/symphysio.sqlite OUT=/srv/backups KEEP=30 ./scripts/backup.sh
#
# Cron example (daily at 03:20):
#   20 3 * * * DB=/data/symphysio.sqlite OUT=/srv/backups /path/to/scripts/backup.sh >> /var/log/symphysio-backup.log 2>&1
set -euo pipefail

DB="${DB:-./data/symphysio.sqlite}"
OUT="${OUT:-./backups}"
KEEP="${KEEP:-30}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"

command -v sqlite3 >/dev/null || { echo "sqlite3 is required" >&2; exit 1; }
[[ -f "$DB" ]] || { echo "database not found: $DB" >&2; exit 1; }

mkdir -p "$OUT"
staging="$(mktemp -t symphysio-backup-XXXXXX.sqlite)"
trap 'rm -f "$staging"' EXIT

sqlite3 "$DB" ".backup '$staging'"
sqlite3 "$staging" "PRAGMA integrity_check;" | grep -qx ok

gzip -9 -c "$staging" > "$OUT/symphysio-$STAMP.sqlite.gz"
echo "wrote $OUT/symphysio-$STAMP.sqlite.gz ($(du -h "$OUT/symphysio-$STAMP.sqlite.gz" | cut -f1))"

# Prune, keeping the newest $KEEP dumps.
ls -1t "$OUT"/symphysio-*.sqlite.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  echo "pruning $old"
  rm -f "$old"
done
