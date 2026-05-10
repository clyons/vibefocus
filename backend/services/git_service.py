"""
Git (local) and GitHub (public API) stats services.
Both are lightweight and run on-demand — no background polling.
"""

from __future__ import annotations
import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx

from schemas import GitStats


# ── Git log sync ─────────────────────────────────────────────────────────────

def sync_git_log(local_path: str, since: datetime | None = None, fetch_all: bool = False) -> list[dict]:
    """
    Parse git log with numstat and return list of commit dicts.
    If since is provided, only fetch commits after that date.
    If fetch_all is True, fetch entire history; otherwise default to 365 days.
    """
    path = Path(local_path).expanduser().resolve()
    if not path.exists():
        return []

    cmd = [
        "git", "log",
        "--format=__COMMIT__%H|%h|%an|%ae|%aI|%s",
        "--numstat",
    ]

    if since:
        cmd.append(f"--since={since.isoformat()}")
    elif not fetch_all:
        cmd.append("--since=365 days ago")

    try:
        result = subprocess.run(
            cmd, cwd=str(path),
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    commits = []
    current: dict | None = None

    for line in result.stdout.splitlines():
        if line.startswith("__COMMIT__"):
            if current:
                commits.append(current)
            parts = line[len("__COMMIT__"):].split("|", 5)
            if len(parts) < 6:
                current = None
                continue
            try:
                committed_at = datetime.fromisoformat(parts[4])
            except ValueError:
                committed_at = datetime.utcnow()
            current = {
                "sha": parts[0],
                "short_sha": parts[1],
                "author_name": parts[2],
                "author_email": parts[3],
                "committed_at": committed_at,
                "message": parts[5],
                "files_changed": 0,
                "insertions": 0,
                "deletions": 0,
            }
        elif current and line.strip():
            # numstat line: insertions\tdeletions\tfilename
            stat_parts = line.split("\t")
            if len(stat_parts) >= 3:
                try:
                    ins = int(stat_parts[0]) if stat_parts[0] != "-" else 0
                    dels = int(stat_parts[1]) if stat_parts[1] != "-" else 0
                    current["files_changed"] += 1
                    current["insertions"] += ins
                    current["deletions"] += dels
                except ValueError:
                    pass

    if current:
        commits.append(current)

    return commits


# ── Local git stats ──────────────────────────────────────────────────────────

def _parse_git_commit(log_raw: str) -> tuple[str | None, datetime | None]:
    """Parse '<short sha> <subject>|<ISO date>' from git log output."""
    if not log_raw:
        return None, None

    parts = log_raw.rsplit("|", 1)
    git_last_commit = parts[0].strip() or None
    git_last_commit_at = None
    if len(parts) == 2:
        try:
            git_last_commit_at = datetime.fromisoformat(parts[1].strip())
        except ValueError:
            pass
    return git_last_commit, git_last_commit_at


def _parse_ahead_behind(raw: str) -> tuple[int | None, int | None]:
    parts = raw.split()
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


def get_local_git_stats(local_path: str) -> dict:
    """
    Run git commands against the local path and return raw stats.
    Safe — all commands are read-only.
    """
    path = Path(local_path).expanduser().resolve()
    if not path.exists():
        return {}

    def run(cmd: list[str]) -> str:
        try:
            result = subprocess.run(
                cmd, cwd=str(path),
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    # Current branch
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    local_sha = run(["git", "rev-parse", "HEAD"])

    # Prefer the current branch's upstream ref when present. A local checkout can
    # be behind origin/main, especially when mounted read-only in Docker.
    upstream = run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])

    # Last commit: "abc1234 Fix auth token refresh" + separate ISO date.
    local_log_raw = run(["git", "log", "--format=%h %s|%aI", "-1", "HEAD"])
    local_last_commit, local_last_commit_at = _parse_git_commit(local_log_raw)

    remote_last_commit = None
    remote_last_commit_at = None
    ahead_count = None
    behind_count = None
    if upstream:
        remote_log_raw = run(["git", "log", "--format=%h %s|%aI", "-1", upstream])
        remote_last_commit, remote_last_commit_at = _parse_git_commit(remote_log_raw)
        ahead_count, behind_count = _parse_ahead_behind(
            run(["git", "rev-list", "--left-right", "--count", f"HEAD...{upstream}"])
        )

    if remote_last_commit and (behind_count or 0) > 0:
        git_last_commit = remote_last_commit
        git_last_commit_at = remote_last_commit_at
    else:
        git_last_commit = local_last_commit
        git_last_commit_at = local_last_commit_at

    # Uncommitted changes
    status = run(["git", "status", "--porcelain"])
    has_uncommitted = bool(status)

    return {
        "git_last_commit": git_last_commit,
        "git_last_commit_at": git_last_commit_at,
        "git_local_last_commit": local_last_commit,
        "git_local_last_commit_at": local_last_commit_at,
        "git_remote_last_commit": remote_last_commit,
        "git_remote_last_commit_at": remote_last_commit_at,
        "git_remote_branch": upstream,
        "git_ahead_count": ahead_count,
        "git_behind_count": behind_count,
        "git_branch": branch or None,
        "git_uncommitted": has_uncommitted,
        "_git_local_sha": local_sha or None,
    }


# ── GitHub public API ─────────────────────────────────────────────────────────

def parse_github_owner_repo(url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a GitHub URL."""
    pattern = r"github\.com[:/]([^/]+)/([^/\s\.]+?)(?:\.git)?$"
    match = re.search(pattern, url)
    if match:
        return match.group(1), match.group(2)
    return None


async def get_github_stats(github_url: str) -> dict:
    """
    Fetch public repo stats from the GitHub API.
    No auth required for public repos (60 req/hour unauthenticated).
    """
    parsed = parse_github_owner_repo(github_url)
    if not parsed:
        return {}
    owner, repo = parsed

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code != 200:
                return {}
            data = resp.json()

            latest_commit: str | None = None
            latest_commit_at: datetime | None = None
            latest_sha: str | None = None
            default_branch = data.get("default_branch")
            if default_branch:
                commit_resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/commits/{quote(default_branch, safe='')}",
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                if commit_resp.status_code == 200:
                    commit_data = commit_resp.json()
                    latest_sha = commit_data.get("sha") or None
                    sha = (latest_sha or "")[:7]
                    message = commit_data.get("commit", {}).get("message") or ""
                    subject = message.splitlines()[0].strip()
                    if sha and subject:
                        latest_commit = f"{sha} {subject}"
                    date_raw = commit_data.get("commit", {}).get("author", {}).get("date")
                    if date_raw:
                        try:
                            latest_commit_at = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
                        except ValueError:
                            pass
    except httpx.RequestError:
        return {}

    pushed_at = None
    if data.get("pushed_at"):
        try:
            pushed_at = datetime.fromisoformat(data["pushed_at"].replace("Z", "+00:00"))
        except ValueError:
            pass

    return {
        "github_stars": data.get("stargazers_count"),
        "github_open_issues": data.get("open_issues_count"),
        "github_last_push": pushed_at,
        "_github_default_branch": default_branch,
        "_github_latest_sha": latest_sha,
        "_github_latest_commit": latest_commit,
        "_github_latest_commit_at": latest_commit_at,
    }


async def refresh_stats(local_path: str | None, github_url: str | None) -> GitStats:
    """
    Refresh both local git and GitHub stats for a project.
    Either source may be None.
    """
    combined: dict = {}

    if local_path:
        combined.update(get_local_git_stats(local_path))

    if github_url:
        gh = await get_github_stats(github_url)
        combined.update(gh)
        default_branch = gh.get("_github_default_branch")
        latest_sha = gh.get("_github_latest_sha")
        latest_commit = gh.get("_github_latest_commit")
        latest_commit_at = gh.get("_github_latest_commit_at")
        local_branch = combined.get("git_branch")
        local_sha = combined.get("_git_local_sha")
        if latest_commit and latest_commit_at and (not local_path or local_branch == default_branch):
            if local_sha and latest_sha and local_sha != latest_sha:
                try:
                    async with httpx.AsyncClient(timeout=8.0) as client:
                        owner_repo = parse_github_owner_repo(github_url)
                        if owner_repo:
                            owner, repo = owner_repo
                            compare_ref = f"{quote(local_sha, safe='')}...{quote(str(default_branch), safe='')}"
                            compare_resp = await client.get(
                                f"https://api.github.com/repos/{owner}/{repo}/compare/{compare_ref}",
                                headers={"Accept": "application/vnd.github.v3+json"},
                            )
                            if compare_resp.status_code == 200:
                                compare_data = compare_resp.json()
                                combined["git_behind_count"] = compare_data.get("ahead_by")
                                combined["git_ahead_count"] = compare_data.get("behind_by")
                except httpx.RequestError:
                    pass
            combined["git_last_commit"] = latest_commit
            combined["git_last_commit_at"] = latest_commit_at
            combined["git_remote_last_commit"] = latest_commit
            combined["git_remote_last_commit_at"] = latest_commit_at
            combined["git_remote_branch"] = default_branch

    combined["stats_updated_at"] = datetime.utcnow()
    return GitStats(**{k: combined.get(k) for k in GitStats.model_fields})
