#!/bin/bash
# Weekly stock refresh — runs from launchd every Saturday at 06:00 local time.
# Refreshes data/stock_events.json and pushes to origin/main (Vercel auto-deploy).
#
# Install:
#   ln -sfn "/Users/mini/Routine AI Tools/Semi Dashboard/.claude/worktrees/peaceful-robinson-8b9712/scripts/com.rui.semi-dashboard.weekly.plist" ~/Library/LaunchAgents/
#   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.rui.semi-dashboard.weekly.plist
#   launchctl enable gui/$(id -u)/com.rui.semi-dashboard.weekly
#
# Manually trigger (test):
#   launchctl kickstart -k gui/$(id -u)/com.rui.semi-dashboard.weekly
#
# Disable:
#   launchctl bootout gui/$(id -u)/com.rui.semi-dashboard.weekly

set -euo pipefail

REPO_DIR="/Users/mini/Routine AI Tools/Semi Dashboard/.claude/worktrees/peaceful-robinson-8b9712"
LOG_DIR="$HOME/Library/Logs/semi-dashboard"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/weekly_refresh_$(date +%Y%m%d_%H%M%S).log"

# Ensure PATH includes Homebrew + Python user-bin (launchd has minimal env)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/Library/Python/3.9/bin:$HOME/.local/bin:$PATH"

cd "$REPO_DIR"

{
  echo "=== Weekly stock refresh — $(date) ==="
  echo "REPO: $REPO_DIR"
  echo

  echo "→ Pulling latest main..."
  git fetch origin main
  git reset --hard origin/main

  echo "→ Running update_stocks.py..."
  python3 scripts/update_stocks.py

  echo "→ Committing data/stock_events.json..."
  if git diff --quiet -- data/stock_events.json; then
    echo "  No changes — skipping commit."
    exit 0
  fi

  git add data/stock_events.json
  git -c user.name='Stock Refresh Bot' \
      -c user.email='noreply@anthropic.com' \
      commit -m "Weekly stock refresh — $(date +%Y-%m-%d)"
  git push origin HEAD:main
  echo "→ Done. Pushed to origin/main."
} >> "$LOG" 2>&1
