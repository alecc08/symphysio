# Backups

Your data is one SQLite file. That is the whole point of the deployment model:
there is no database server to snapshot, and no object store to reconcile.

```
/data/symphysio.sqlite      ← the thing to back up
/data/symphysio.sqlite-wal  ← recent writes not yet folded into the main file
/data/symphysio.sqlite-shm  ← WAL index (not data)
```

## The rule

**Never copy the `.sqlite` file alone while the app is running.** With WAL mode a
bare `cp` loses whatever is still in `-wal` — usually the last few hours of
entries — and can produce a torn file. Either:

- use `sqlite3 .backup` (what `scripts/backup.sh` does), or
- stop the container first, or
- snapshot the whole directory (`.sqlite` + `-wal` + `-shm`) on a filesystem that
  can do it atomically.

## Backup

```bash
./scripts/backup.sh                                    # → ./backups/symphysio-<stamp>.sqlite.gz
DB=/data/symphysio.sqlite OUT=/srv/backups KEEP=30 ./scripts/backup.sh
```

What it does, in order:

1. `sqlite3 "$DB" ".backup '$staging'"` — the online backup API: consistent even
   while the app is writing, and it folds the WAL into the copy.
2. `PRAGMA integrity_check` on the **copy**, so a corrupt backup never enters the
   rotation.
3. `gzip -9` into `symphysio-YYYYmmdd-HHMMSS.sqlite.gz`.
4. Prune, keeping the newest `KEEP` dumps (default 30).

Cron, daily at 03:20:

```cron
20 3 * * * DB=/data/symphysio.sqlite OUT=/srv/backups /opt/symphysio/scripts/backup.sh >> /var/log/symphysio-backup.log 2>&1
```

Container-based backup (no sqlite3 on the host):

```bash
docker exec symphysio sh -c 'sqlite3 /data/symphysio.sqlite ".backup /tmp/b.sqlite"' \
  && docker cp symphysio:/tmp/b.sqlite - | gzip > backups/symphysio-$(date -u +%Y%m%d-%H%M%S).sqlite.gz
```

(`sqlite3` is *not* installed in the runtime image — it is not needed by the app —
so the example above uses a container that has it. If yours does not, stop the
service and copy the file.)

Off-machine copies matter more than frequent ones: a single symptom diary on one
disk is one disk failure away from nothing. Push the dumps to object storage, or
`restic`/`borg` the backups directory.

## Restore

```bash
docker compose stop symphysio
gunzip -c backups/symphysio-20261123-162000.sqlite.gz > /tmp/restore.sqlite
sqlite3 /tmp/restore.sqlite 'PRAGMA integrity_check;'      # must print: ok
mv /data/symphysio.sqlite /data/symphysio.sqlite.before    # keep the wreckage
mv /tmp/restore.sqlite /data/symphysio.sqlite
rm -f /data/symphysio.sqlite-wal /data/symphysio.sqlite-shm
sudo chown 10001:10001 /data/symphysio.sqlite              # the container user
docker compose up -d symphysio
```

Then check: `GET /api/v1/export/json` and compare the log counts with what you
expect, and load the app on a phone. A restore that has not been opened in the app
is not a restore.

Notes:

- Deleting `-wal`/`-shm` on restore is correct **only** because the replacement
  database file is a complete snapshot; the WAL belongs to the old file.
- Migrations are forward-only. Restoring an older dump and starting a newer image
  re-applies the migration history from `schema_migrations` inside that dump, so
  an old dump plus new code is fine, but new dump plus old code is not.

## Portability (the other backup)

The in-app exports are for *reading*, and they are also the escape hatch:

| Endpoint | Shape |
| --- | --- |
| `GET /api/v1/export/csv` | one row per log entry: `event_type`, `definition`, `occurred_at_utc`, `occurred_utc`, local time, dose, severity, note — what you hand a physiotherapist or open in a spreadsheet |
| `GET /api/v1/export/json` | `app`, `schema_version`, `exported_at_utc`, `user`, `definitions`, `logs` (by kind), `timeline` — a complete, documented dump |

Export JSON periodically and keep it next to the SQLite dumps: if the schema ever
moves off SQLite, that file is the import target, and it does not depend on
`sqlite3` being available.

## What is not backed up

- Sessions (`sessions` table): restored backups log every device out. Expected.
- `frontend/dist` and the image: rebuild, never back up.
- The dev database `backend/data/`: not production data.
