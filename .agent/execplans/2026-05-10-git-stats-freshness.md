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
- [ ] Validation complete (requires running backend + frontend against a real DB).

## Surprises & Discoveries

- Observation: None yet.
  Evidence: N/A.

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

## Outcomes & Retrospective

**Lesson learned — re-deploy required after schema or backend changes.**
This task added a new DB column and changed backend logic. The Docker container was running the upstream pre-built image (`ericblue/vibefocus:0.1.1`) and did not pick up any local changes until `make docker-run` was explicitly run.

**Broken-network failure mode discovered here.** The old container held port 8000. Stopping it and re-running `make docker-run` left the docker-compose network in a half-initialised state: the container started and passed its internal health check, but the host-side port binding was never programmed, so `localhost:8000` was unreachable. Root cause: compose created the `san-diego_default` network during the first failed attempt; on the second attempt it reused that broken network rather than recreating it. Fix: `docker-compose down` (destroys both container and network) followed by `docker-compose up -d`. This is now documented in `CLAUDE.md` and `PLANS.md`.

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

## Idempotence and Recovery

- The `ALTER TABLE` migration is guarded by the existing `if col_name not in proj_cols` check — safe to restart.
- If the backend restarts mid-operation, no partial state is left; the column either exists or doesn't.
- The auto-refresh on the frontend is a fire-and-forget mutation; if it fails (e.g., backend down), it fails silently with no visible error.

## Artifacts and Notes

To be filled in after implementation.

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
