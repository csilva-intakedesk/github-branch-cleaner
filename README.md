# GitHub Branch Cleaner
A small CLI tool to prune local git branches that are already merged into a base branch or whose upstreams are gone.

## Requirements
- Python 3.8+
- git

Install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Configuration
Environment variables (optional, with defaults):
- `PROTECTED_BRANCHES`: comma-separated list of protected branches. Default: `main,master,develop,dev,release,staging,production`
- `CRITICAL_BRANCHES`: comma-separated list of branches that can never be deleted. Default: `master,dev`
- `BASE_BRANCH_FOR_COMMIT_CHECK`: base branch for merge/closure checks. Default: `dev`

You can set these in `.env` (see `.env.dist` for an example).

## Usage
Required flag: `--repo`

```bash
python3 ./cleanup_stale_branches.py --repo /path/to/repo
```

Help output:
```text
 Usage: cleanup_stale_branches.py [OPTIONS] COMMAND [ARGS]...                                                                                                                                                                                  
                                                                                                                                                                                                                                               
 Clean local git branches safely                                                                                                                                                                                                               
                                                                                                                                                                                                                                               
                                                                                                                                                                                                                                               
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                                                                                                                                                 │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ clean   Default (fast): delete local branches whose tip commit is already contained in `base`. Optional checks can be enabled via flags.                                                                                                    │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯


Clean command options:

                                                                                                                                                                                                                                               
 Usage: cleanup_stale_branches.py [OPTIONS]                                                                                                                                                                                                    
                                                                                                                                                                                                                                               
 Default (fast): delete local branches whose tip commit is already contained in `base`. Optional checks can be enabled via flags.                                                                                                              
                                                                                                                                                                                                                                               
                                                                                                                                                                                                                                               
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --repo                          PATH  Path to git repository [default: None] [required]                                                                                                                                                  │
│    --remote                        TEXT  Remote name (default: origin) [default: origin]                                                                                                                                                    │
│    --base                          TEXT  Base branch to check commit containment (default from BASE_BRANCH_FOR_COMMIT_CHECK env or 'dev') [default: dev]                                                                                    │
│    --dry-run                             Print actions without deleting                                                                                                                                                                     │
│    --force                               Force delete (git branch -D)                                                                                                                                                                       │
│    --protect                       TEXT  Additional protected branch name(s). Can be passed multiple times.                                                                                                                                 │
│    --fetch                               Run 'git fetch <remote> --prune' before checks (slower, but fresher)                                                                                                                               │
│    --check-upstream-missing              Only consider branches that have an upstream on the chosen remote                                                                                                                                  │
│    --check-remote-missing                Only delete if branch is missing on remote (uses ls-remote; slower)                                                                                                                                │
│    --check-issue-closure                 If branch name starts with issue id, delete only if base contains "closes #<id>" (slower)                                                                                                          │
│    --help                                Show this message and exit.                                                                                                                                                                        │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

```

Common options:
- `--repo`                          PATH  Path to git repository [default: None] [required]
- `--remote`                        TEXT  Remote name (default: origin) [default: origin]
- `--base`                          TEXT  Base branch to check commit containment (default from BASE_BRANCH_FOR_COMMIT_CHECK env or 'dev') [default: dev]
- `--dry-run`                             Print actions without deleting
- `--force`                               Force delete (git branch -D)
- `--protect`                       TEXT  Additional protected branch name(s). Can be passed multiple times.
- `--fetch`                               Run 'git fetch <remote> --prune' before checks (slower, but fresher)
- `--check-upstream-missing`              Only consider branches that have an upstream on the chosen remote
- `--check-remote-missing`                Only delete if branch is missing on remote (uses ls-remote; slower)
- `--check-issue-closure`                 If branch name starts with issue id, delete only if base contains "closes #<id>" (slower)
- `--help`                                Show this message and exit. 

## Examples
Dry run with extra safety checks:
```bash
python3 ./cleanup_stale_branches.py clean \
  --repo /path/to/repo \
  --dry-run \
  --check-upstream \
  --check-remote-missing
```

Include issue-closure heuristic and extra protected branch:
```bash
python3 ./cleanup_stale_branches.py clean \
  --repo /path/to/repo \
  --check-issue-closure \
  --protect release-2024
```

## Sample Output
```text
[SKIP] 1684-test-branch-1 (not found in dev)
[DEL ] 2159-test-branch-2 (tip 1a2b3c4d is in dev)
[SKIP] dev (protected)
```

## Note

To determine whether an issue has already been merged into the base branch, the script assumes that the issue (ticket) number is embedded in the branch name.

Example:

GitHub Issue: `1234-test-issue-2`

Branch Name: `1234-fixing-test-issue-2`

In this case, the shared numeric prefix (`1234`) is used to associate the branch with the corresponding issue.