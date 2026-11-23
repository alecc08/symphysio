# Symphysio backend

FastAPI + SQLite (WAL) API for the Symphysio click-and-log tracker.

```bash
uv sync                                  # install pinned deps from uv.lock
uv run uvicorn app.main:app --reload     # http://127.0.0.1:8000  (API only)
uv run pytest                            # tests
uv run ruff check app tests              # lint
```

- Schema and migrations: `migrations/*.sql` (applied automatically on startup).
- Configuration: environment variables only — see `docs/DEPLOYING.md` in the repo root.
