# Productize local repo scan onboarding

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository uses `.agent/PLANS.md` as the governing standard for ExecPlans. Keep this document aligned with that contract.

## Purpose / Big Picture

Make bulk local repository import understandable and safe for a new VibeFocus user. A user with an existing folder of git repositories should be prompted to scan that folder from the empty dashboard or Settings, see whether a default directory is configured and reachable, and get clear guidance when the directory is absent. Re-running the scan should update existing projects and commit history without creating duplicates or overwriting user-authored descriptions/categories.

This implements the upstream issue `ericblue/vibefocus#1`, "Add bulk import for local git repositories", as a product workflow rather than only a CLI script.

## Progress

- [x] (2026-05-11 01:39Z) Read upstream issue `#1` and existing fork importer/UI.
- [x] (2026-05-11 01:44Z) Created this ExecPlan.
- [x] (2026-05-11 01:52Z) Implemented backend scan config/result behavior and generic importer defaults.
- [x] (2026-05-11 01:56Z) Implemented Settings and empty-dashboard onboarding prompts.
- [x] (2026-05-11 02:07Z) Validated build, backend compilation, importer idempotence, structured errors, and local-source empty database startup.

## Surprises & Discoveries

- Observation: Browsers do not expose a reliable absolute directory path that the FastAPI backend can scan.
  Evidence: The current app runs as a web UI and the backend scan API needs a filesystem path visible to the backend process or Docker mount.

- Observation: Existing fork defaults are owner/workspace-specific.
  Evidence: `Makefile` defaults `PROJECTS_DIR` to `$(HOME)/conductor/repos`, `backend/.env.example` uses `~/conductor/repos`, and `bucket_for()` maps specific GitHub owners to buckets.

- Observation: This workspace did not have frontend or backend dependencies installed before validation.
  Evidence: `make fe-build` initially failed with `tsc: command not found`, and `python3` could not import `sqlalchemy`. Running `npm ci` and creating `backend/venv` with `pip install -r requirements.txt` fixed the local validation environment.

## Decision Log

- Decision: Prompt users to enter or confirm a backend-visible directory path instead of pretending the browser can select one.
  Rationale: The backend must scan a path on its filesystem. A native browser folder picker would not provide a portable absolute path to FastAPI, and in Docker the path must also be mounted.
  Date/Author: 2026-05-11 / Codex

- Decision: Treat missing or unconfigured scan roots as recoverable configuration states with structured API responses and UI copy.
  Rationale: For a new user, "absent directory" usually means they have not configured `PROJECTS_DIR`, entered the wrong path, or forgot the Docker mount. The UI should explain next action instead of only showing a raw 400.
  Date/Author: 2026-05-11 / Codex

- Decision: Default imported projects to generic buckets and only fill blank descriptive fields.
  Rationale: Upstream should not inherit fork-specific owner heuristics, and rescans should preserve user edits.
  Date/Author: 2026-05-11 / Codex

## Outcomes & Retrospective

Implemented an upstream-ready scan/rescan feature with CLI, API, Settings UI, and empty-dashboard entry point. The feature treats scanning as a first-run import path: users enter a backend-visible directory, receive clear configuration status, can opt into recursive scanning or full history, and see created/updated/skipped results. Local-source empty database validation passed through both CLI and HTTP API paths.

## Context and Orientation

Relevant files:

- `backend/import_local_projects.py` contains repository discovery, metadata inference, project upsert, git stats sync, and commit log sync.
- `backend/routers/data.py` exposes `/api/data/scan-config` and `/api/data/scan`.
- `frontend/src/components/SettingsView.tsx` contains the current scan form next to import/export tools.
- `frontend/src/components/Dashboard.tsx` renders the empty portfolio onboarding screen.
- `frontend/src/api/client.ts` and `frontend/src/types/index.ts` define typed frontend API access.
- `Makefile`, `backend/.env.example`, `README.md`, and `INSTALL.md` document CLI/Docker configuration.

The upstream issue acceptance criteria are: `make import-projects PROJECTS_DIR=/path/to/repos` imports repos safely; re-running does not duplicate projects or commits; existing projects are matched by `local_path` or `github_url`; imported projects include local path, GitHub URL when detectable, branch, last commit, dirty status, and recent commit history.

## Plan of Work

1. Backend importer:
   - Remove owner-specific bucket assignment from `backend/import_local_projects.py`.
   - Keep matching by `local_path`, then `github_url`, then title.
   - Preserve user-authored fields by only filling blank descriptions, summaries, GitHub URLs, and tech stacks where appropriate.
   - Return richer scan result data including skipped/error rows when a repository fails.

2. Backend API:
   - Expand `/api/data/scan-config` so the UI knows whether the configured/default directory exists.
   - Expand `/api/data/scan` with `fetch_all` support and clearer error details for unconfigured or missing directories.

3. Frontend API/types:
   - Add typed scan config/result interfaces and client methods.

4. Settings UX:
   - Show a first-run oriented local repo import section.
   - Pre-fill configured path when present.
   - Disable scan until there is a path.
   - Explain what to do when the path is absent, especially for Docker mounts.
   - Show created/updated/skipped/commit counts after scan.

5. Empty dashboard onboarding:
   - Offer a direct "scan a folder of repos" action that sends users to Settings.
   - Keep manual project creation available.

6. Docs and Makefile:
   - Replace fork-specific default paths with generic `PROJECTS_DIR=/path/to/repos`.
   - Document absent-directory behavior and Docker mount expectations.

7. Local empty database validation:
   - Run the backend from source with a temporary SQLite database, not Docker.
   - Point `DATABASE_URL` at a temporary empty `.db` file and `PROJECTS_DIR` at temporary git repos.
   - Start or import through the local Python environment so table creation/migrations run against an empty database.
   - Verify the scan endpoint or CLI creates projects from scratch, and verify a second scan updates without duplicating commit logs.

## Concrete Steps

From repository root:

    gh issue view 1 --repo ericblue/vibefocus --json number,title,body,comments,state,url
    make fe-build
    cd backend && python -m py_compile main.py import_local_projects.py services/*.py routers/*.py

Create a temporary pair of git repositories and run:

    cd backend
    . venv/bin/activate
    DATABASE_URL=sqlite:////tmp/vibefocus-empty-scan.db python import_local_projects.py --root /tmp/vibefocus-scan-smoke
    DATABASE_URL=sqlite:////tmp/vibefocus-empty-scan.db python import_local_projects.py --root /tmp/vibefocus-scan-smoke

Expected result: first run creates repos and imports commits; second run updates the same projects without duplicate commit rows.

Run the local backend against the same empty database:

    cd backend
    . venv/bin/activate
    DATABASE_URL=sqlite:////tmp/vibefocus-empty-api.db PROJECTS_DIR=/tmp/vibefocus-scan-smoke PORT=8011 python main.py
    curl -sf http://localhost:8011/health
    curl -sf http://localhost:8011/api/data/scan-config
    curl -sf -X POST 'http://localhost:8011/api/data/scan?recursive=false'

Expected result: local source startup creates/migrates an empty database, `scan-config` reports the temp repo folder as ready, and `scan` imports the repos without Docker.

## Validation and Acceptance

Acceptance criteria:

- Empty dashboard gives new users a clear choice between scanning an existing folder and manually creating one project.
- Settings scan form clearly asks for a backend-visible directory, pre-fills configured `PROJECTS_DIR` when available, and shows actionable guidance when absent.
- `/api/data/scan-config` reports configured raw path, resolved path, existence, and whether scanning is ready.
- `/api/data/scan` returns structured 400 detail when no root is configured or the requested directory is missing.
- Re-running scans updates existing projects matched by local path or GitHub URL and does not duplicate commit logs.
- Imported projects include local path, inferred GitHub URL when possible, branch, last commit, dirty status, and recent commit history.
- Running from source against an empty SQLite database can scan a configured local folder without Docker.

Validation commands:

    make fe-build
    cd backend && python -m py_compile main.py import_local_projects.py services/*.py routers/*.py
    cd backend && DATABASE_URL=sqlite:////tmp/vibefocus-empty-scan.db python import_local_projects.py --root /tmp/vibefocus-scan-smoke

## Idempotence and Recovery

Importer scans are intended to be safe to re-run. Project matching uses local path and GitHub URL before falling back to name, and commit sync skips existing commit SHAs per project. If a scan root is wrong, no database writes should occur because the API and CLI validate the root before scanning.

For partial scan failures, individual repository errors should be returned as skipped rows while other repositories continue importing when possible.

## Artifacts and Notes

- Upstream issue: `https://github.com/ericblue/vibefocus/issues/1`
- `make fe-build` passed after `npm ci`. Vite emitted the existing large chunk warning.
- `cd backend && ./venv/bin/python -m py_compile main.py import_local_projects.py services/*.py routers/*.py` passed.
- CLI empty database smoke:
  - First run against `/tmp/vibefocus-empty-scan.db`: `2 created`, `2 commits added`.
  - Second run against the same DB: `2 updated`, `0 commits added`.
  - Count check: `{'projects': 2, 'commits': 2}`.
- Local API empty database smoke:
  - Started source backend with `DATABASE_URL=sqlite:////tmp/vibefocus-empty-api.db`, `PROJECTS_DIR=/tmp/vibefocus-scan-smoke`, and `PORT=8011`.
  - `GET /health` returned `{"status":"ok","version":"0.1.1"}`.
  - `GET /api/data/scan-config` returned `ready: true`.
  - First `POST /api/data/scan` returned `created: 2`, `updated: 0`, `skipped: 0`, `commits_added: 2`.
  - Second `POST /api/data/scan` returned `created: 0`, `updated: 2`, `skipped: 0`, `commits_added: 0`.
  - Count check: `{'projects': 2, 'commits': 2}`.
- Structured error smoke:
  - Missing path returns `400` with `code: scan_root_missing`.
  - Empty/unconfigured path returns `400` with `code: scan_root_required`.

## Interfaces and Dependencies

Backend interfaces:

- `scan_repos(db, root: Path, recursive: bool = False, fetch_all: bool = False) -> dict`
- `GET /api/data/scan-config`
- `POST /api/data/scan?root=...&recursive=false&fetch_all=false`

Frontend interfaces:

- `api.data.scanConfig()`
- `api.data.scan({ root, recursive, fetch_all })`
- `ScanConfig`, `ScanResult`, and `ScanProjectResult` TypeScript interfaces.

No new external dependencies are planned.

## Change Log

- 2026-05-11: Created the plan from template.
- 2026-05-11: Implemented and validated local repo scan onboarding, Settings UX, generic importer behavior, and local-source empty DB smoke tests.
