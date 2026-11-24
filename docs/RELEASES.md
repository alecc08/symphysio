# Releases

## One version of record

[`VERSION`](../VERSION) at the repo root — one line, plain semver. The app reads
it (`app/main.py` → `__version__`, which is also the OpenAPI document's version),
the release workflow tags from it, and the image bakes it into an OCI label.
[CHANGELOG.md](../CHANGELOG.md) keeps one `## [x.y.z] - YYYY-MM-DD` section per
release, in [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

`frontend/package.json` and `backend/pyproject.toml` carry version numbers
because their tooling insists on them. Nothing reads those at runtime, so they
are decoration: bump them when you feel like it, and no test will nag you.

## Cutting a release

There is nothing to run by hand. A release is a merge:

1. In the feature branch, bump `VERSION` and add its `CHANGELOG.md` section.
   Docs, tests and refactors do not bump.
2. Open a PR; CI must be green.
3. Merge to `main`. `release.yml` sees a `VERSION` with no `v<VERSION>` tag,
   tags the merge commit, publishes a GitHub Release whose notes are that
   changelog section, and starts `build.yml` for the tag, which pushes
   `ghcr.io/alecc08/symphysio:<version>`.

A commit that lands on `main` without a version bump is simply not released
yet — it rides along with the next bump. That is deliberate: no PR should be
blocked on a version number, and no release should be cut for a typo fix.

## What the numbers mean here

| Bump | When |
| --- | --- |
| **MAJOR** | Anything that breaks a client: an `/api/v1` contract change, a request or response field removed or retyped. |
| **MINOR** | New endpoints, new fields that old clients can ignore, new UI surfaces, new migrations. |
| **PATCH** | Fixes, dependency bumps, copy, docs. |

Migrations are forward-only (see [DATABASE.md](DATABASE.md)), so a release can
be rolled back by pulling the previous image but **not** by reverting the
database. Pin a version on the deploy host if you want that rollback to be
possible at all.

## Image tags

| Tag | Meaning |
| --- | --- |
| `ghcr.io/alecc08/symphysio:<version>` | What a release published. **Use this in production.** |
| `ghcr.io/alecc08/symphysio:latest` | The tip of `main`, rebuilt on every merge. Convenient, moves under you. |
| `ghcr.io/alecc08/symphysio:<full sha>` | The exact commit, for "which build is this?" |

The package is public: a deploy host needs no registry credentials.

```bash
docker pull ghcr.io/alecc08/symphysio:0.1.2
```

## Rules

- A published tag is never moved or deleted. If `0.1.0` was wrong, release
  `0.1.1` — which is not hypothetical: `v0.1.0` was tagged and released with a
  broken build trigger, so `ghcr.io/...:0.1.0` does not exist and `0.1.1` is the
  image that matches that release.
- The version the running container reports is the truth:
  `curl -s https://<host>/api/v1/openapi.json | python3 -c 'import json,sys;print(json.load(sys.stdin)["info"]["version"])'`
- If the release workflow fails halfway (tag created, no release body), the tag
  already exists, so the next merge will not retry it. Finish it with
  `gh release create v<x.y.z> --notes-file ...` — or tag the fix as `x.y.z+1`.
