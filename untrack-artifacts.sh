#!/usr/bin/env bash
# Stop tracking files that are build output, editor state, runtime artifacts or
# stale copies. Files stay on disk; .gitignore now covers them so they will not
# come back. Run once, then review `git status` and commit.
#
#   bash untrack-artifacts.sh
#
# To undo before committing:  git reset

set -euo pipefail
cd "$(dirname "$0")"

untrack() {
  # -r for directories, --ignore-unmatch so a missing path is not fatal
  git rm -r --cached --quiet --ignore-unmatch "$@"
}

# Build output / archives
untrack backend.zip frontend.zip build_log.txt
untrack frontend/tsconfig.tsbuildinfo frontend/tsconfig.node.tsbuildinfo

# Editor state
untrack .idea

# Runtime output committed by accident
untrack backend/agent/reports
untrack backend/generator/generated
untrack backend/output
untrack backend/airflow/dags/pipeline_demo_1.py

# Sample datasets (already listed in .gitignore)
untrack Dataset

# Auto-generated DAG that was committed at the repo root by mistake
untrack test_router.py

echo
echo "Done. Files remain on disk; they are now untracked."
echo "Review with: git status"
