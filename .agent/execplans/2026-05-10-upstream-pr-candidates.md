# Select upstream PR candidates

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository uses `.agent/PLANS.md` as the governing standard for ExecPlans. Keep this document aligned with that contract.

## Purpose / Big Picture

Compare this fork against `ericblue/vibefocus` upstream and choose a small set of broadly useful, self-contained enhancements that can be proposed as upstream pull requests. The desired outcome is not to implement the PRs yet; it is to give a maintainer-friendly shortlist with clear sequencing, ICE scoring, and explicit impact for both upstream maintainers and existing users who pull changes into cloned repositories.

The recommended PRs should feel easy to accept: low migration risk, focused diffs, concrete user benefit, and validation commands that a maintainer can run locally.

## Progress

- [x] (2026-05-10 22:32Z) Fetched `origin` and `upstream`, confirmed this fork is ahead of `upstream/master`.
- [x] (2026-05-10 22:32Z) Reviewed repository ExecPlan requirements and upstream-vs-fork diff.
- [x] (2026-05-10 22:32Z) Selected five candidate PRs and ranked them with ICE scoring.
- [x] (2026-05-10 23:04Z) User selected the analytics readability PR.
- [x] (2026-05-10 23:04Z) Opened upstream draft PR `ericblue/vibefocus#5` from `clyons:codex/analytics-readability-polish`.
- [ ] Implement selected candidate PRs one branch at a time.
- [x] (2026-05-10 23:04Z) Validated analytics PR with `npm ci` in `frontend/` and `make fe-build`.
- [ ] Await maintainer review on `ericblue/vibefocus#5`.

## Surprises & Discoveries

- Observation: This fork is entirely ahead of upstream; `upstream/master` has no commits that are missing from this workspace branch.
  Evidence: `git log --oneline --decorate --graph --left-right upstream/master...HEAD` shows only right-side commits from this fork.

- Observation: The fork contains both generally useful product improvements and local workflow scaffolding.
  Evidence: Product changes include OpenAI support, local repo scanning, Docker persistence, git freshness, and analytics polish. Local workflow changes include `.agent/`, `AGENTS.md`, Conductor config, 1Password scripts, and branch hygiene workflows.

- Observation: Some fork code should be generalized before upstreaming.
  Evidence: `backend/import_local_projects.py` includes owner-specific bucket heuristics, and `.env.example` currently uses a Conductor-specific default `PROJECTS_DIR`.

## Decision Log

- Decision: Score candidates with ICE on a 1-10 scale for Impact, Confidence, and Ease, using `Impact * Confidence * Ease` as the total.
  Rationale: The user explicitly asked to prioritize with ICE, and product usefulness alone is not enough if a PR is hard for the maintainer or clone users to absorb.
  Date/Author: 2026-05-10 / Codex

- Decision: Exclude local workflow and repo-governance changes from the upstream shortlist.
  Rationale: `.agent/`, `AGENTS.md`, Conductor config, 1Password sync scripts, orphan-check, and fork-specific branch rules are useful here but not obviously useful to the broader upstream user base.
  Date/Author: 2026-05-10 / Codex

- Decision: Treat each proposed PR as independently mergeable, even where this fork currently has changes interleaved.
  Rationale: Upstream review is easier when every PR has one user-visible purpose and does not require adopting this fork's workflow.
  Date/Author: 2026-05-10 / Codex

## Outcomes & Retrospective

This planning pass produced five candidate PRs. The strongest candidates are the ones that improve everyday usage without changing data semantics: analytics readability, friendly chat errors, and Docker quality-of-life. Local repo scanning is very high impact but needs generic defaults. OpenAI provider support is broadly valuable but has higher review and dependency risk than the smaller PRs.

The analytics readability candidate was selected first and submitted upstream as draft PR `https://github.com/ericblue/vibefocus/pull/5`.

## Context and Orientation

Remote layout:

- `upstream` points to `git@github.com:ericblue/vibefocus.git`.
- `origin` points to `git@github.com:clyons/vibefocus.git`.
- Target base for upstream proposals is `upstream/master`; target base for this workspace's internal PRs is `origin/master`.

Relevant comparison commands:

    git fetch --all --prune
    git log --oneline --decorate --graph --left-right upstream/master...HEAD
    git diff --stat upstream/master...HEAD
    git diff --name-status upstream/master...HEAD

Broad fork changes observed:

- AI provider changes in `backend/database.py`, `backend/routers/chat.py`, `backend/services/chat_service.py`, `backend/services/agent_analyzer.py`, `backend/requirements.txt`, `README.md`, and `INSTALL.md`.
- Local repo scanning in `backend/import_local_projects.py`, `backend/routers/data.py`, `frontend/src/components/SettingsView.tsx`, `Makefile`, and env/docs files.
- Docker persistence and runtime changes in `Dockerfile`, `docker-compose.yml`, `Makefile`, `backend/database.py`, `backend/main.py`, `README.md`, and `INSTALL.md`.
- Git freshness changes in `backend/models.py`, `backend/schemas.py`, `backend/main.py`, `backend/services/git_service.py`, `backend/routers/data.py`, `frontend/src/components/CodeAnalysis.tsx`, and `frontend/src/types/index.ts`.
- Analytics polish in `frontend/src/components/analytics/CommitHeatmap.tsx`, `frontend/src/components/analytics/ProjectLifecycle.tsx`, `frontend/src/components/analytics/StallAlerts.tsx`, and `frontend/src/index.css`.

Changes not recommended for upstream in this pass:

- `.agent/**`, `AGENTS.md`, and `setup.sh`: agent workflow scaffolding, not product behavior.
- `conductor.json`: Conductor-specific.
- `docs/operations/1password-env-sync.md` and `scripts/*1password*`: operator-specific secrets workflow.
- `.github/workflows/orphan-check.yml`, `.github/workflows/pr-quality.yml`, and `.github/pull_request_template.md`: useful here, but they encode contribution policy and should be a separate maintainer conversation.

## Plan of Work

Candidate PRs, ranked by ICE:

| Rank | Candidate PR | Impact | Confidence | Ease | ICE | Why it belongs upstream |
|---:|---|---:|---:|---:|---:|---|
| 1 | Analytics readability polish | 6 | 9 | 9 | 486 | Frontend-only improvements to heatmap sizing, lifecycle scrolling, and health legend make existing analytics easier to use with minimal maintainer risk. |
| 2 | Friendly streaming chat error handling | 5 | 9 | 10 | 450 | Users should see actionable AI-provider errors instead of silent stream failures; small diff, no migration, no new dependency. |
| 3 | Durable Docker local runtime | 8 | 8 | 7 | 448 | Makes the Docker path fit how users actually run a local portfolio app: detached, healthchecked, configurable ports/data/projects, and restart-friendly. |
| 4 | Local repo scan/rescan | 9 | 7 | 6 | 378 | Turns an empty install into a populated portfolio by scanning local git repos from Settings or CLI; high activation value, but needs generic defaults. |
| 5 | OpenAI provider support | 9 | 6 | 5 | 270 | Expands the addressable user base beyond Anthropic-only users, but adds provider-selection logic, dependencies, and model/API review burden. |

### PR 1: Analytics readability polish

Scope:

- Make `CommitHeatmap` adapt cell size to available width instead of forcing horizontal overflow.
- Make `ProjectLifecycle` preserve project labels while the timeline scrolls and add a range control for long histories.
- Add a compact legend to `StallAlerts` explaining status dots and `7d/30d` commit counts.
- Keep the PR frontend-only. Do not include local-vs-remote git source selection, `git fetch`, remote-tracking refs, or schema changes in this PR.

Files to change:

- `frontend/src/components/analytics/CommitHeatmap.tsx`
- `frontend/src/components/analytics/ProjectLifecycle.tsx`
- `frontend/src/components/analytics/StallAlerts.tsx`
- `frontend/src/index.css`

Maintainer impact:

- Low review burden: no backend, no database, no external dependency.
- Easy to verify by opening Analytics with sample commit data and resizing the browser.
- Minimal long-term maintenance because it uses browser-native `ResizeObserver` and existing React state.

Impact on cloned repos tracking upstream:

- Pulling users only rebuild frontend assets.
- No env changes, no database migration, no data movement.
- Existing analytics behavior remains; it becomes easier to read on smaller and wider screens.
- The PR does not change whether commit analytics come from local `HEAD`, remote-tracking branches, GitHub API data, or all refs. That is a separate product/data semantics decision.

### PR 2: Friendly streaming chat error handling

Scope:

- Wrap the chat SSE stream in `backend/routers/chat.py` so provider/authentication errors are emitted as SSE `error` events and the stream closes cleanly.
- Teach `frontend/src/api/client.ts` to surface SSE `error` events as thrown errors.
- Sanitize obvious API-key/authentication errors so the UI tells the user to check configuration without leaking secret values.

Files to change:

- `backend/routers/chat.py`
- `frontend/src/api/client.ts`

Maintainer impact:

- Very small review surface.
- No new settings, no new dependency, no data model changes.
- Improves supportability because users report concrete setup errors instead of vague chat failures.

Impact on cloned repos tracking upstream:

- Existing valid chat sessions behave the same.
- Misconfigured clones get clearer errors after pulling.
- No action required unless their AI key is invalid, in which case the failure is easier to diagnose.

### PR 3: Durable Docker local runtime

Scope:

- Add detached, restart-friendly Docker compose behavior with healthcheck.
- Add `make docker-run`, `make docker-status`, `make docker-restart`, and stronger `make docker-test` behavior.
- Support configurable `VIBEFOCUS_PORT`, `VIBEFOCUS_DATA`, and `PROJECTS_DIR`.
- Keep existing users safe by either preserving upstream's current `./data` default or documenting/migrating from `./data/vibefocus.db` to the new default before changing it.

Files to change:

- `Dockerfile`
- `docker-compose.yml`
- `Makefile`
- `backend/main.py`
- `README.md`
- `INSTALL.md`
- `backend/.env.example`

Maintainer impact:

- Moderate review surface, mostly ops/docs.
- Maintainer should decide whether the default data path stays `./data` for backwards compatibility or moves to `~/.vibefocus/data` with explicit migration notes.
- Healthcheck and restart behavior reduce Docker support issues.

Impact on cloned repos tracking upstream:

- If defaults are kept compatible, users pull and continue using existing `./data`.
- If the default data path changes, users with existing Docker data need a clear one-command migration or release note, otherwise VibeFocus can appear empty after update.
- Users gain a safer redeploy path: pull latest, rebuild/restart, data remains outside the image.

### PR 4: Local repo scan/rescan

Scope:

- Add a CLI and API endpoint to scan a configured directory for git repositories.
- Add a Settings UI section for one-click rescan, optional custom root, and recursive scan.
- Populate project name, description, GitHub URL, local path, rough stack, priority, and commit log from local repos.
- Remove fork-specific owner-to-bucket heuristics before upstreaming; default unknown repos to existing generic buckets.

Files to change:

- `backend/import_local_projects.py`
- `backend/routers/data.py`
- `backend/services/git_service.py`
- `Makefile`
- `frontend/src/components/SettingsView.tsx`
- `README.md`
- `INSTALL.md`
- `backend/.env.example`

Maintainer impact:

- Moderate review burden because it creates projects and writes commit logs.
- Needs careful idempotence review so repeated scans update existing projects without duplicates.
- Should include a small temporary-directory smoke test or manual validation evidence.

Impact on cloned repos tracking upstream:

- Existing data is additive; no destructive migration.
- Users can set `PROJECTS_DIR` and import existing repos without hand-entering every project.
- Repeated scans may update project metadata, so the PR should avoid overwriting user-authored descriptions or categories unless blank.

### PR 5: OpenAI provider support

Scope:

- Make Anthropic optional and add OpenAI API key/provider settings.
- Add OpenAI streaming chat support while preserving Anthropic as the default when `ANTHROPIC_API_KEY` exists.
- Add OpenAI-backed code analysis with read-only local file tools.
- Update docs and env examples to explain provider selection.

Files to change:

- `backend/database.py`
- `backend/routers/chat.py`
- `backend/services/chat_service.py`
- `backend/services/agent_analyzer.py`
- `backend/requirements.txt`
- `backend/.env.example`
- `README.md`
- `INSTALL.md`

Maintainer impact:

- Highest review burden among the recommended candidates because it adds SDK surface area and two AI execution paths.
- Needs provider-selection tests or at least explicit smoke validation for Anthropic-only, OpenAI-only, and no-key configurations.
- Maintainer must choose acceptable default model names and whether OpenAI code-analysis parity is required in the first PR.

Impact on cloned repos tracking upstream:

- Anthropic users should not need to change anything if provider auto-detection preserves current behavior.
- OpenAI users can run VibeFocus without creating an Anthropic account.
- Users must reinstall backend dependencies after pulling because requirements change.

Recommended sequencing:

1. Start with PR 2 or PR 1 to build maintainer trust with small, obvious wins.
2. Send PR 3 after deciding backwards-compatible Docker data behavior.
3. Send PR 4 after genericizing scan defaults and proving repeated scans are idempotent.
4. Send PR 5 last, or split it into chat-only first and code-analysis later if the maintainer is cautious about provider scope.

## Concrete Steps

Planning commands already run from repository root:

    git fetch --all --prune
    git log --oneline --decorate --graph --left-right upstream/master...HEAD --max-count=80
    git diff --stat upstream/master...HEAD
    git diff --name-status upstream/master...HEAD
    git diff upstream/master...HEAD -- backend/routers/chat.py backend/services/chat_service.py backend/services/agent_analyzer.py backend/.env.example README.md INSTALL.md
    git diff upstream/master...HEAD -- backend/import_local_projects.py backend/routers/data.py frontend/src/components/SettingsView.tsx frontend/src/api/client.ts backend/main.py
    git diff upstream/master...HEAD -- backend/database.py docker-compose.yml Dockerfile Makefile INSTALL.md README.md setup.sh
    git diff upstream/master...HEAD -- backend/models.py backend/schemas.py backend/services/git_service.py frontend/src/components/CodeAnalysis.tsx frontend/src/components/analytics/CommitHeatmap.tsx frontend/src/components/analytics/ProjectLifecycle.tsx frontend/src/components/analytics/StallAlerts.tsx frontend/src/types/index.ts

For each selected candidate:

1. Create a fresh branch from current upstream:

       git fetch upstream
       git switch -c clyons/upstream-<candidate-slug> upstream/master

2. Cherry-pick or manually port only the files required for that candidate.
3. Remove fork-specific defaults, paths, and policies.
4. Run validation commands listed below.
5. Draft a PR against `ericblue/vibefocus:master` with:
   - What changed.
   - User-visible impact.
   - Migration notes, if any.
   - Validation evidence.

## Validation and Acceptance

Default validation for any selected frontend candidate:

    make fe-build

Expected result: TypeScript completes and Vite builds production assets without errors.

Default validation for any selected backend candidate:

    cd backend && python -m py_compile main.py import_local_projects.py services/*.py routers/*.py

Expected result: command exits `0`. If the selected PR does not include `backend/import_local_projects.py`, omit that file from the command.

Task-specific acceptance:

- Analytics readability polish: Analytics remains usable at narrow and wide browser widths; lifecycle labels stay visible while scrolling.
- Friendly chat errors: invalid or missing API key produces an actionable UI error and closes the stream instead of hanging.
- Durable Docker local runtime: `make docker-run` starts a healthy container, `make docker-status` reports health, and redeploy does not remove the SQLite database.
- Local repo scan/rescan: scanning a temp directory with two git repos creates two projects; scanning again updates them without duplicates.
- OpenAI provider support: Anthropic-only, OpenAI-only, and no-provider configurations produce the expected chat behavior and user-facing errors.

## Idempotence and Recovery

Each candidate should be developed on a separate branch and can be abandoned by deleting only that branch. Do not combine unrelated candidates in one branch.

Do not overwrite `.env.local` or any env file with whole-file writes. Env examples may be edited with normal patches because they do not contain credentials. Real local env files should be updated only by targeted edits or appends.

Database-affecting candidates must use additive schema changes only. Existing SQLite databases should continue to open after pulling. If a candidate changes where Docker stores data, provide a backwards-compatible default or explicit migration command.

Docker recovery note for this host: use `docker-compose` if the newer `docker compose` subcommand is unavailable. If a failed compose run leaves a broken network after a port conflict, stop the old container, run `docker-compose down`, then start clean.

## Artifacts and Notes

Comparison summary:

    47 files changed, 3253 insertions(+), 155 deletions(-)

The largest broadly useful areas are OpenAI provider support, local repo scanning, Docker runtime improvements, git freshness, and analytics polish. The selected shortlist intentionally favors low-friction upstream review over transplanting every fork feature.

Submitted PR:

    https://github.com/ericblue/vibefocus/pull/5

Validation for submitted analytics PR:

    npm ci
    make fe-build

Result: build completed successfully. Vite emitted the existing large chunk warning.

## Interfaces and Dependencies

Important interfaces touched by candidate PRs:

- FastAPI routers: `backend/routers/chat.py`, `backend/routers/data.py`
- Settings: `backend/database.py`
- AI services: `backend/services/chat_service.py`, `backend/services/agent_analyzer.py`
- Git services: `backend/services/git_service.py`
- SQLAlchemy model: `backend/models.py`
- Pydantic schemas: `backend/schemas.py`
- Frontend API client: `frontend/src/api/client.ts`
- Settings UI: `frontend/src/components/SettingsView.tsx`
- Analytics UI: `frontend/src/components/analytics/*.tsx`
- Docker and Make targets: `Dockerfile`, `docker-compose.yml`, `Makefile`

External dependencies requiring maintainer attention:

- OpenAI provider support adds Python OpenAI-related dependencies.
- Local repo scan relies on the `git` CLI being available in the runtime environment.
- Docker healthcheck relies on Python's standard library `urllib.request`, not curl.

## Change Log

- 2026-05-10: Created the upstream PR candidate selection plan from template.
- 2026-05-10: Submitted analytics readability candidate as upstream draft PR `ericblue/vibefocus#5`.
