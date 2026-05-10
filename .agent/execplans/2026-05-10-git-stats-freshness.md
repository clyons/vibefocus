# Fix git stats staleness: store absolute commit date + auto-refresh on Code tab open

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository uses `.agent/PLANS.md` as the governing standard for ExecPlans. Keep this document aligned with that contract.

## Purpose / Big Picture

Two compounding problems make the "Last commit" stat unreliable:

1. **Relative time is frozen in the string.** `git log --format="%h %s (%cr)"` bakes in e.g. "3 months ago" at the moment the stats were last refreshed. A project refreshed 30 days ago shows an age that is now 30 days too young.

2. **No automatic refresh trigger.** Stats only update when the user clicks "↻ Refresh stats". A project imported months ago and never revisited silently shows stale data with no indication.

After this change:
- "Last commit" shows the correct age at all times, because the age is computed client-side from a stored ISO timestamp rather than baked into the stored string.
- Opening the Code tab silently refreshes stats if they are more than 12 hours old, so the user always sees near-current data without any polling.

## Progress

- [x] (2026-05-10) Initial planning completed.
- [x] (2026-05-10) Implementation complete — all 7 files edited.
- [x] (2026-05-10) Follow-up root cause found: refreshed stats still showed old commits when the local checkout was behind its remote-tracking branch.
- [x] (2026-05-10) Follow-up implementation updated to preserve and display local-vs-remote discrepancies instead of silently overriding local `HEAD`.
- [x] (2026-05-10) Follow-up validation complete: Python compile, frontend build, Docker redeploy, health check, and live `PQ Reps` refresh verified.
- [x] (2026-05-10 19:13 UTC) Extended analytics git-log sync to include remote-tracking branch history, while excluding tool-owned checkpoint refs from lifecycle/health calculations.
- [x] (2026-05-10 19:13 UTC) Rebuilt the local Docker app, forced a full PQ Reps git-log sync, and confirmed PQ Reps is now active in portfolio health.
- [x] (2026-05-10 19:13 UTC) Updated Project Lifecycle so it opens at the latest date and keeps the project list pinned in the leftmost column while the timeline scrolls horizontally.
- [x] (2026-05-10 19:13 UTC) Added a Portfolio Health legend explaining status dots and the `x/y = commits in last 7d/30d` convention.
- [x] (2026-05-10 19:13 UTC) Validation complete against local build and running Docker app.
- [x] (2026-05-10 19:15 UTC) Made the Project Lifecycle horizontal scroller explicit and visible, rather than relying on the global hidden-until-hover scrollbar styling.
- [x] (2026-05-10 19:21 UTC) Corrected the scroller follow-up: replaced the bottom native lifecycle scrollbar with a visible top range scroller and made Commit Activity scale to fill its container again.

## Surprises & Discoveries

- Observation: "Refresh stats" was current for the local checkout, but the local checkout itself could be stale. `PQ Reps` showed `a8642b0 Add Steno SDK playground...` because `/Users/ciaran/conductor/repos/pq-reps` was on `main...origin/main [behind 51]`.
  Evidence: `git -C /Users/ciaran/conductor/repos/pq-reps status --short --branch` returned `## main...origin/main [behind 51]`, while `git -C /Users/ciaran/conductor/repos/pq-reps log -1 origin/main` returned `6a2346a Persist Vercel sessions and update analytics (#359)`.

- Observation: Docker mounts local repos read-only and the image does not include `ssh`, so the app cannot rely on doing a `git fetch` inside the container.
  Evidence: `docker exec san-diego-vibefocus-1 git -C /Users/ciaran/conductor/repos/pq-reps fetch --dry-run --quiet origin` failed with `error: cannot run ssh: No such file or directory`.

- Observation: API timestamps are serialized without a timezone suffix, so the browser interpreted UTC server times as local wall-clock times and showed `Stats refreshed -1 days ago`.
  Evidence: The API returned `stats_updated_at: "2026-05-10T18:03:09.379649"` while the screenshot was taken around `2026-05-10 2:03 PM` local time.

- Observation: This host has legacy `docker-compose` but not the newer `docker compose` subcommand.
  Evidence: `docker compose down` failed with `docker: unknown command: docker compose`; `docker-compose down && make docker-run` succeeded.

- Observation: Portfolio health is calculated from `commit_logs`, not from the lightweight project `git_last_commit` stats. A project can show a fresh Last Commit value while analytics remain stale until `/sync-git-log` imports the missing history.
  Evidence: PQ Reps had `git_last_commit_at = 2026-05-09T19:52:12`, but `/api/analytics/health` still showed `0/0 dormant` until a full git-log sync added the remote-tracking commits.

- Observation: The previously rebuilt container did not contain the remote analytics change, so the UI was still backed by the old `sync_git_log()` implementation.
  Evidence: `docker exec victoria-vibefocus-1 sed -n '19,38p' /app/services/git_service.py` showed no fetch and no remote-ref log flags before the rebuild.

- Observation: `git log --all` is too broad for Conductor-managed worktrees because it includes internal checkpoint refs.
  Evidence: `git log --all --format=...` for `/Users/ciaran/conductor/repos/pq-reps` returned `Checkpointer <checkpointer@noreply>` commits dated 2026-05-10 ahead of real project commits.

- Observation: The Docker mount for `/Users` is read-only, so `git fetch --all` cannot update `.git/FETCH_HEAD` inside the container.
  Evidence: Running fetch inside the container printed `error: cannot open '.git/FETCH_HEAD': Read-only file system`. The sync still works for refs already present in the host clone, and failures are intentionally ignored.

- Observation: Global scrollbar styling makes scroll thumbs transparent until hover, which made a native Project Lifecycle scroller look absent.
  Evidence: `frontend/src/index.css` set `::-webkit-scrollbar-thumb { background: transparent; }` and only changed the thumb on `*:hover`; the lifecycle timeline now uses a dedicated `.lifecycle-range` control above the chart.

- Observation: A native horizontal scrollbar at the bottom of Project Lifecycle is not useful because the timeline is taller than the screenshot area. It reads as "no scroller" when the user is viewing the chart header and top rows.
  Evidence: Screenshot `image-v6.png` showed the Project Lifecycle header and upper timeline rows with no visible scroll affordance. The implementation now places a visible range-style scroller directly above the timeline.

- Observation: Commit Activity used fixed 13px cells, so on wider cards the heatmap occupied only part of the chart region and left a large blank area.
  Evidence: Screenshot `image-v5.png` showed the commit grid ending well before the right side of the panel. `CommitHeatmap` now observes its container width and scales grid cells to fill the available chart area.

## Decision Log

- Decision: Add a new `git_last_commit_at` DateTime column rather than embedding the ISO date in the existing string.
  Rationale: Clean separation of concerns — the commit message string stays human-readable; the timestamp is a proper DateTime value usable in sorting, comparisons, and queries. Backward compat: old rows have `git_last_commit_at = NULL`; the frontend falls back to showing the raw string (which may still contain the baked-in relative age until re-refreshed by auto-refresh Fix 2).
  Date/Author: 2026-05-10 / Ciaran Lyons

- Decision: Auto-refresh threshold of 12 hours.
  Rationale: Covers daily use without any noticeable overhead. `git log -1` + GitHub API call takes < 2s total. The user said no polling every 5 minutes; 12 hours is effectively "once per working session".
  Date/Author: 2026-05-10 / Ciaran Lyons

- Decision: Parse the two pieces of info (message + ISO date) from a single `git log` command using `|` as an in-band separator.
  Rationale: Avoids a second subprocess call. A `|` in a commit subject is unusual but possible. Safer alternative if needed: split on the last `|` occurrence, since the date is always the final segment.
  Date/Author: 2026-05-10 / Ciaran Lyons

- Decision: For local stats, read the current branch's upstream ref when one exists, falling back to `HEAD` only when no upstream is configured.
  Rationale: This keeps the displayed commit aligned with the latest known remote-tracking branch without mutating the user's checkout.
  Date/Author: 2026-05-10 / Ciaran Lyons

- Decision: When a GitHub URL is present and the local branch matches the repo default branch, prefer GitHub's latest default-branch commit over local git output.
  Rationale: This fixes stale read-only Docker mounts and stale local clones for the common `main` branch case without misrepresenting feature branches as default branch history.
  Date/Author: 2026-05-10 / Ciaran Lyons

- Decision: Preserve local and remote commit fields plus ahead/behind counts, and display a neutral checkout-status row when they differ.
  Rationale: The UI should show the freshest known remote commit, but it should also explain why local `HEAD` is older. Silent replacement hides useful operational context.
  Date/Author: 2026-05-10 / Ciaran Lyons

- Decision: Treat timezone-less API timestamps as UTC in the frontend date formatter and clamp negative elapsed time to zero.
  Rationale: Backend timestamps use `datetime.utcnow()` and serialize without `Z`; browser-local parsing made fresh timestamps look like future dates.
  Date/Author: 2026-05-10 / Ciaran Lyons

- Decision: For analytics git-log sync, include `HEAD`, `--branches`, `--remotes`, and `--tags` rather than `--all`.
  Rationale: This captures local and remote-tracking project history, including PQ Reps remote commits, without counting Conductor checkpoint refs as user work.
  Date/Author: 2026-05-10 / Codex

- Decision: Keep lifecycle project labels outside the horizontally scrolling SVG instead of using SVG text inside the timeline.
  Rationale: The chart now opens scrolled to the latest date by default; separate labels keep project names visible while the date axis and bars scroll.
  Date/Author: 2026-05-10 / Codex

- Decision: Give the lifecycle timeline its own always-visible horizontal scrollbar and a wider minimum timeline width.
  Rationale: The product needs an obvious scroller for historical data; the global hidden scrollbar treatment is too subtle here.
  Date/Author: 2026-05-10 / Codex

- Decision: Use an explicit range input as the lifecycle timeline scroller instead of a native bottom scrollbar.
  Rationale: The scroller must be visible near the chart header, where the user is looking. A bottom scrollbar can sit below many project rows and remain unseen.
  Date/Author: 2026-05-10 / Codex

- Decision: Scale Commit Activity grid cells from measured container width.
  Rationale: The heatmap should fill its card at the selected date range instead of using a fixed pixel grid that leaves unused horizontal space on larger displays.
  Date/Author: 2026-05-10 / Codex

- Decision: Add a compact health legend in the Portfolio Health header.
  Rationale: The project pills show a colored status dot and a terse `x/y` metric; the legend explains that `x/y` means commits in the last 7 days / last 30 days without making every row verbose.
  Date/Author: 2026-05-10 / Codex

## Outcomes & Retrospective

**Lesson learned — re-deploy required after schema or backend changes.**
This task added a new DB column and changed backend logic. The Docker container was running the upstream pre-built image (`ericblue/vibefocus:0.1.1`) and did not pick up any local changes until `make docker-run` was explicitly run.

**Broken-network failure mode discovered here.** The old container held port 8000. Stopping it and re-running `make docker-run` left the docker-compose network in a half-initialised state: the container started and passed its internal health check, but the host-side port binding was never programmed, so `localhost:8000` was unreachable. Root cause: compose created the `san-diego_default` network during the first failed attempt; on the second attempt it reused that broken network rather than recreating it. Fix: `docker-compose down` (destroys both container and network) followed by `docker-compose up -d`. This is now documented in `CLAUDE.md` and `PLANS.md`.

**Remote analytics and UI follow-up complete.** PQ Reps now syncs remote-tracking history into `commit_logs` and reports active health. The lifecycle chart keeps project names pinned while the timeline opens at the newest date. Portfolio Health now explains both visual encodings: dot color is status, and `x/y` is 7-day / 30-day commit count.

Validation evidence from 2026-05-10:
- `frontend: npm run build` completed successfully with TypeScript and Vite.
- `docker-compose up -d --build` rebuilt and restarted `victoria-vibefocus-1` on port 8000.
- `POST /api/projects/5aef607b/sync-git-log?fetch_all=true` returned `{ "synced": 115, "total_commits": 874, "health_status": "active" }` for PQ Reps.
- `GET /api/analytics/health` returned PQ Reps as `{ "status": "active", "commits_7d": 19, "commits_30d": 21, "total_commits": 874 }`.
- `GET /api/analytics/focus?days=30` returned PQ Reps with `21` commits and `4602` lines changed.
- `GET /api/analytics/lifecycle?days=3650` returned PQ Reps with `last_commit = 2026-05-09 20:05:56` and `total_commits = 874`.
- `GET /health` returned `{ "status": "ok", "version": "0.1.1" }`.
- Superseded follow-up: The first attempt used a bottom native scrollbar and wider timeline, but screenshots showed that was still not visible enough.
- Follow-up correction: Project Lifecycle now uses a visible top `.lifecycle-range` scroller synchronized with the timeline, and Commit Activity now uses a `ResizeObserver` to fill its container width.
- `frontend: npm run build` completed successfully after the scroller and heatmap-fill corrections.
- `docker-compose up -d --build` rebuilt and restarted `victoria-vibefocus-1`; `GET /health` returned `{ "status": "ok", "version": "0.1.1" }`.

## Context and Orientation

Relevant files:

| File | Role |
|------|------|
| `backend/models.py` | SQLAlchemy ORM — `Project` model |
| `backend/main.py` | Startup migrations via `ALTER TABLE` pattern |
| `backend/schemas.py` | Pydantic schemas — `GitStats`, `ProjectOut` |
| `backend/services/git_service.py` | `get_local_git_stats()` runs `git log`; `refresh_stats()` calls it |
| `frontend/src/types/index.ts` | TypeScript `Project` interface |
| `frontend/src/components/CodeAnalysis.tsx` | Displays stats; has `refreshStats` mutation; `fmtDate()` helper already exists |
| `frontend/src/components/analytics/ProjectLifecycle.tsx` | Portfolio lifecycle chart; now uses a pinned project-label column and horizontally scrolling timeline |
| `frontend/src/components/analytics/CommitHeatmap.tsx` | Commit Activity heatmap; now scales grid cells to fill the available chart width |
| `frontend/src/components/analytics/StallAlerts.tsx` | Portfolio health grid; now includes a compact legend for status dots and commit-count ratios |
| `frontend/src/index.css` | Global app styles; now includes a lifecycle-specific visible scrollbar override |

The startup `lifespan()` in `main.py` already performs idempotent `ALTER TABLE projects ADD COLUMN` migrations — the new column fits this existing pattern exactly.

## Plan of Work

### Part 1 — Store absolute commit timestamp (Fix the frozen relative date)

**`backend/services/git_service.py` — `get_local_git_stats()`**

Change the `git log` format from `%h %s (%cr)` to `%h %s|%aI` (commit subject + ISO author date, pipe-separated). Split on the last `|` to extract:
- `git_last_commit` → `%h %s` (e.g. `"e8040fd Add Strava SDK playground (#12)"`)
- `git_last_commit_at` → parsed `datetime` from `%aI`

Return both fields from the dict. Handle the edge case where `%s` itself contains `|` by splitting on the *last* occurrence: `rsplit('|', 1)`.

**`backend/models.py`**

Add to `Project`:
```python
git_last_commit_at = Column(DateTime, nullable=True)
```

**`backend/main.py`**

Add to the `for col_name, col_type in [...]` migration list:
```python
("git_last_commit_at", "DATETIME"),
```

**`backend/schemas.py`**

Add `git_last_commit_at: datetime | None = None` to both `GitStats` and `ProjectOut`.

**`frontend/src/types/index.ts`**

Add `git_last_commit_at: string | null` to the `Project` interface (after `git_last_commit`).

**`frontend/src/components/CodeAnalysis.tsx` — display**

Update the Last commit `StatRow` to append the computed age when `git_last_commit_at` is available:

```tsx
{project.git_last_commit && (
  <StatRow
    label="Last commit"
    value={project.git_last_commit_at
      ? `${project.git_last_commit} (${fmtDate(project.git_last_commit_at)})`
      : project.git_last_commit}
    mono
  />
)}
```

This is backward compatible: old rows with `git_last_commit_at = null` keep showing the stored string (which may have the old baked-in relative age). Once auto-refresh fires they'll get the new format.

---

### Part 2 — Auto-refresh on Code tab open when stale (Fix the no-trigger problem)

**`frontend/src/components/CodeAnalysis.tsx` — auto-refresh effect**

Add a `useEffect` at the top of `CodeAnalysis`. On mount, if the project has a `local_path` or `github_url`, check `stats_updated_at`. If it is null or more than 12 hours ago, fire `refreshStats.mutate()` silently (no UI state change needed — the existing `isPending` indicator on the button will reflect it).

```tsx
useEffect(() => {
  const hasSource = !!(project.local_path || project.github_url)
  if (!hasSource) return
  const staleThreshold = 12 * 60 * 60 * 1000  // 12 hours in ms
  const lastUpdated = project.stats_updated_at ? new Date(project.stats_updated_at).getTime() : 0
  if (Date.now() - lastUpdated > staleThreshold) {
    refreshStats.mutate()
  }
}, [project.id])
```

The dependency is `project.id` only — fires once per project open, not on every re-render.

### Part 3 — Prefer remote/default branch commit when local checkout is behind

**`backend/services/git_service.py` — local git stats**

Use `git rev-parse --abbrev-ref --symbolic-full-name @{upstream}` to find the checked-out branch's upstream ref. Run the last-commit `git log` against that ref when present, falling back to `HEAD` if the branch has no upstream.

**`backend/services/git_service.py` — GitHub fallback**

When a `github_url` is present, fetch the repo default branch and latest commit from the GitHub public API. If the local branch matches the default branch, override the last-commit fields with GitHub's latest default-branch commit. Keep local branch and uncommitted status from the local checkout. Also persist:

- `git_local_last_commit` / `git_local_last_commit_at`
- `git_remote_last_commit` / `git_remote_last_commit_at`
- `git_remote_branch`
- `git_ahead_count` / `git_behind_count`

Use GitHub's compare API when available so stale remote-tracking refs do not undercount how far behind the local checkout is.

**`frontend/src/components/CodeAnalysis.tsx` — discrepancy display**

When ahead/behind counts are non-zero, show a neutral `Checkout status` row such as `local checkout is behind remote by 51 commits`, plus a `Local HEAD` row when it differs from the displayed latest commit.

**`frontend/src/components/CodeAnalysis.tsx` — timestamp display**

Normalize timezone-less API timestamps as UTC before computing relative ages, and clamp negative differences to zero so fresh UTC timestamps render as `today` instead of `-1 days ago`.

## Concrete Steps

From repository root:

```bash
# After edits, verify Python compiles cleanly
cd backend && python -m py_compile main.py models.py schemas.py services/git_service.py

# Build frontend
cd ../frontend && npm run build
```

## Validation and Acceptance

1. **Schema migration**: Start the backend against an existing database. The `projects` table gains a `git_last_commit_at` column without error. Existing rows have `NULL` in that column.

2. **Fresh stats format**: On a project with `local_path` set, click "↻ Refresh stats". The stored `git_last_commit` value is now just `"<sha> <message>"` (no `(%cr)` suffix). The `git_last_commit_at` field is a non-null ISO datetime. The UI shows e.g. `"e8040fd Add Strava SDK playground (#12) (3 months ago)"` where the age is computed client-side.

3. **Age stays current**: Without clicking refresh, reload the page. The displayed age increments correctly (e.g., if it was "3 months ago" yesterday, today it still says "3 months ago" or "3 months and 1 day ago" — not frozen at the time of last refresh).

4. **Auto-refresh fires on tab open**: On a project whose `stats_updated_at` is null or >12h old, open the Code tab. Within ~2s the stats silently update (the "↻ Refresh stats" button briefly shows "Refreshing..."). The `stats_updated_at` footer line updates to "today".

5. **Auto-refresh does not fire when fresh**: On a project just manually refreshed, close and re-open the Code tab. No second refresh fires.

6. **Backward compat**: Projects with old `git_last_commit` strings (containing baked-in `(X days ago)`) that have no `git_last_commit_at` still render without error — just showing the raw legacy string.

7. **Behind local checkout**: With `/Users/ciaran/conductor/repos/pq-reps` on `main...origin/main [behind 51]`, refreshing stats stores the GitHub/default-branch commit rather than local `HEAD` commit `a8642b0 Add Steno SDK playground with 15 exploration panels (#312)`.

8. **Timezone display**: A UTC server timestamp without a `Z` suffix renders as `today`, not `-1 days ago`.

9. **Discrepancy display**: The Code tab shows `Checkout status` when ahead/behind counts are non-zero, and shows the stale `Local HEAD` commit separately from the latest known remote commit.

## Idempotence and Recovery

- The `ALTER TABLE` migration is guarded by the existing `if col_name not in proj_cols` check — safe to restart.
- If the backend restarts mid-operation, no partial state is left; the column either exists or doesn't.
- The auto-refresh on the frontend is a fire-and-forget mutation; if it fails (e.g., backend down), it fails silently with no visible error.

## Artifacts and Notes

- `python3 -m py_compile main.py models.py schemas.py services/git_service.py routers/data.py` passed.
- `npm run build` passed; Vite emitted the existing large chunk warning.
- `docker-compose down && make docker-run` rebuilt and restarted `san-diego-vibefocus-1`.
- `curl http://localhost:8000/health` returned `{"status":"ok","version":"0.1.1"}`.
- `POST /api/projects/5aef607b/refresh-stats` returned `git_last_commit: "6a2346a Persist Vercel sessions and update analytics (#359)"`, `git_local_last_commit: "a8642b0 Add Steno SDK playground with 15 exploration panels (#312)"`, `git_remote_branch: "origin/main"`, and `git_behind_count: 51`.

## Interfaces and Dependencies

```python
# git_service.get_local_git_stats() — before
{ "git_last_commit": "e8040fd Add Strava (#12) (3 months ago)", ... }

# git_service.get_local_git_stats() — after
{ "git_last_commit": "e8040fd Add Strava (#12)", "git_last_commit_at": datetime(...), ... }
```

```typescript
// Project interface — new field
git_last_commit_at: string | null  // ISO datetime
```

## Change Log

- 2026-05-10: Created the plan from template.
- 2026-05-10: Added follow-up for behind local checkouts, GitHub default-branch commit preference, and timezone-less UTC timestamp display.
- 2026-05-10: Added local-vs-remote discrepancy persistence and UI display.
- 2026-05-10: Updated with remote analytics sync behavior, lifecycle pinned labels, portfolio health legend, Docker deployment, and validation evidence.
- 2026-05-10: Added visible Project Lifecycle scrollbar follow-up.
- 2026-05-10: Corrected follow-up with a top lifecycle range scroller and responsive Commit Activity fill.
