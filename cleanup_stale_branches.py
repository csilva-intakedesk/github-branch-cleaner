#!/usr/bin/env python3
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Set

import typer
from typer.main import get_command 
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer(
    invoke_without_command=True,
    add_completion=False,
    help="Clean local git branches safely",
)

PROTECTED: Set[str] = {
    b.strip().lower()
    for b in os.getenv(
        "PROTECTED_BRANCHES",
        "main,master,develop,dev,release,staging,production",
    ).split(",")
    if b.strip()
}

CRITICAL: Set[str] = {
    b.strip().lower()
    for b in os.getenv(
        "CRITICAL_BRANCHES",
        "master,dev",
    ).split(",")
    if b.strip()
}

BASE_BRANCH_FOR_COMMIT_CHECK = os.getenv("BASE_BRANCH_FOR_COMMIT_CHECK", "dev").strip()

if not PROTECTED:
    raise RuntimeError(
        "PROTECTED_BRANCHES resolved to an empty set. "
        "Refusing to run to avoid deleting important branches."
    )

if not CRITICAL:
    raise RuntimeError(
        "CRITICAL_BRANCHES resolved to an empty set. "
        "Refusing to run to avoid deleting important branches."
    )

if not BASE_BRANCH_FOR_COMMIT_CHECK:
    raise RuntimeError("BASE_BRANCH_FOR_COMMIT_CHECK is required to run checks")


def run(cmd: List[str], check: bool = True) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout.strip()


def ensure_git_repo(path: Path):
    if not path.is_dir():
        raise RuntimeError(f"Path does not exist: {path}")
    if not (path / ".git").is_dir():
        raise RuntimeError(f"Not a git repo: {path}")


def current_branch() -> str:
    return run(["git", "branch", "--show-current"])


def local_branches() -> List[str]:
    out = run(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"])
    return [b for b in out.splitlines() if b]


def upstream_for(branch: str) -> Optional[str]:
    out = run(
        ["git", "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"],
        check=False,
    )
    return out if out and "fatal:" not in out else None


def remote_branch_exists(remote: str, branch: str) -> bool:
    # This can be slow on big repos; keep it optional.
    out = run(["git", "ls-remote", "--heads", remote, branch], check=False)
    return bool(out.strip())


def delete_branch(branch: str, force: bool, dry_run: bool):
    cmd = ["git", "branch", "-D" if force else "-d", branch]
    if dry_run:
        print(f"[DRY] {' '.join(cmd)}")
    else:
        run(cmd)


def tip_sha(branch: str) -> str:
    return run(["git", "rev-parse", branch])


def commit_in_base(commit: str, base: str) -> bool:
    # True if commit is reachable from base
    p = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, base],
        capture_output=True,
        text=True,
    )
    return p.returncode == 0


def issue_id_from_branch(branch: str) -> Optional[str]:
    m = re.match(r"^(\d+)[-_].+", branch)
    return m.group(1) if m else None


def base_has_issue_closure(base: str, issue_id: str) -> bool:
    # looks for "closes #123", "fixes #123", etc
    pattern = rf"(closes|closed|fixes|fixed|resolves|resolved)\s+#?{re.escape(issue_id)}\b"
    out = run(
        ["git", "log", base, "--regexp-ignore-case", f"--grep={pattern}", "-n", "1"],
        check=False,
    )
    return bool(out.strip())

@app.command()
def clean(
    repo: Path = typer.Option(..., "--repo", exists=True, help="Path to git repository"),
    remote: str = typer.Option("origin", "--remote", help="Remote name (default: origin)"),
    base: str = typer.Option(
        BASE_BRANCH_FOR_COMMIT_CHECK,
        "--base",
        help="Base branch to check commit containment (default from BASE_BRANCH_FOR_COMMIT_CHECK env or 'dev')",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print actions without deleting"),
    force: bool = typer.Option(False, "--force", help="Force delete (git branch -D)"),
    protect: List[str] = typer.Option(
        [],
        "--protect",
        help="Additional protected branch name(s). Can be passed multiple times.",
    ),
    fetch: bool = typer.Option(
        False,
        "--fetch",
        help="Run 'git fetch <remote> --prune' before checks (slower, but fresher)",
    ),
    check_upstream_missing: bool = typer.Option(
        False,
        "--check-upstream-missing",
        help="Only consider branches that have an upstream on the chosen remote",
    ),
    check_remote_missing: bool = typer.Option(
        False,
        "--check-remote-missing",
        help="Only delete if branch is missing on remote (uses ls-remote; slower)",
    ),
    check_issue_closure: bool = typer.Option(
        False,
        "--check-issue-closure",
        help='If branch name starts with issue id, delete only if base contains "closes #<id>" (slower)',
    ),
):
    """
    Default (fast): delete local branches whose tip commit is already contained in `base`.
    Optional checks can be enabled via flags.
    """
    protected = PROTECTED.union({p.strip().lower() for p in protect if p.strip()})
    critical = CRITICAL

    try:
        ensure_git_repo(repo)
        os.chdir(repo)

        if fetch:
            run(["git", "fetch", remote, "--prune"], check=False)

        cur = current_branch()
        branches = local_branches()
    except RuntimeError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)

    base_ref = base  # assume local ref; if user wants origin/dev they can pass --base origin/dev
    # quick sanity: ensure base resolves
    if run(["git", "rev-parse", "--verify", "--quiet", base_ref], check=False) == "":
        typer.echo(f"Base ref not found: {base_ref}", err=True)
        raise typer.Exit(code=2)

    for b in branches:
        b_lc = b.lower()

        if b == cur:
            print(f"[SKIP] {b} (current)")
            continue
        if b_lc in protected:
            print(f"[SKIP] {b} (protected)")
            continue
        if b_lc in critical:
            print(f"[SKIP] {b} (critical)")
            continue

        if check_upstream_missing:
            up = upstream_for(b)
            if not up or not up.startswith(f"{remote}/"):
                print(f"[SKIP] {b} (local-only or non-{remote} upstream)")
                continue

        if check_issue_closure:
            issue_id = issue_id_from_branch(b)
            if not issue_id:
                print(f"[SKIP] {b} (no issue id prefix for closure check)")
                continue
            if not base_has_issue_closure(base_ref, issue_id):
                print(f"[KEEP] {b} (no issue-closure marker on {base_ref} for #{issue_id})")
                continue

        tip = tip_sha(b)
        if not commit_in_base(tip, base_ref):
            print(f"[KEEP] {b} (tip {tip[:8]} NOT in {base_ref})")
            continue

        if check_remote_missing and remote_branch_exists(remote, b):
            print(f"[KEEP] {b} (exists on {remote})")
            continue

        print(f"[DEL ] {b} (tip {tip[:8]} is in {base_ref})")
        delete_branch(b, force, dry_run)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        # show normal top-level help
        typer.echo(ctx.get_help())

        # ✅ build click command tree and print help for "clean"
        click_root = get_command(app)
        clean_cmd = click_root.commands.get("clean")
        if clean_cmd:
            typer.echo("\nClean command options:\n")
            typer.echo(clean_cmd.get_help(ctx))

        raise typer.Exit()


if __name__ == "__main__":
    app()
