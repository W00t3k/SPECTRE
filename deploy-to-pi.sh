#!/usr/bin/env bash
# deploy-to-pi.sh — run on YOUR MAC to push SPECTRE to a Raspberry Pi
# Usage: bash deploy-to-pi.sh [--host pi@192.168.x.x] [--port 22] [--init]
#
#   --host  SSH target (default: pi@raspberrypi.local)
#   --port  SSH port   (default: 22)
#   --init  First-time setup: create bare repo + hook on Pi, then push
#           Omit on subsequent deploys (just does git push)

set -euo pipefail

PI_HOST="pi@raspberrypi.local"
PI_SSH_PORT=22
INIT=0
REMOTE_NAME="pi"
BARE_REPO="~/spectre.git"
WORK_DIR="~/spectre"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)   PI_HOST="$2";     shift 2 ;;
        --port)   PI_SSH_PORT="$2"; shift 2 ;;
        --init)   INIT=1;           shift   ;;
        *) echo "[!] Unknown flag: $1"; shift ;;
    esac
done

SSH="ssh -p $PI_SSH_PORT $PI_HOST"
GIT_REMOTE="ssh://$PI_HOST:$PI_SSH_PORT/home/${PI_HOST##*@}/spectre.git"

echo "═══════════════════════════════════════════════════════════"
echo "  SPECTRE  →  deploy to $PI_HOST"
echo "═══════════════════════════════════════════════════════════"

# ── Make sure we're in the repo root ────────────────────────
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

# ── Init local git if needed ────────────────────────────────
if [[ ! -d ".git" ]]; then
    echo "[*] Initialising local git repo..."
    git init
    git add .
    git commit -m "SPECTRE initial commit"
fi

# ── First-time Pi setup ─────────────────────────────────────
if [[ "$INIT" -eq 1 ]]; then
    echo "[*] Setting up bare repo + post-receive hook on Pi..."

    $SSH bash -s <<REMOTE
set -e
mkdir -p $BARE_REPO
cd $BARE_REPO
git init --bare
mkdir -p hooks
cat > hooks/post-receive <<'HOOK'
#!/bin/bash
TARGET="$HOME/spectre"
GIT_DIR="$HOME/spectre.git"
BRANCH="main"
while read oldrev newrev ref; do
    if [[ "\$ref" == "refs/heads/\$BRANCH" ]]; then
        echo "[SPECTRE] Deploying branch \$BRANCH to \$TARGET..."
        git --work-tree="\$TARGET" --git-dir="\$GIT_DIR" checkout -f
        # Restart server if running
        if systemctl is-active --quiet spectre 2>/dev/null; then
            sudo systemctl restart spectre
            echo "[SPECTRE] systemd service restarted."
        fi
        echo "[SPECTRE] Deploy complete."
    fi
done
HOOK
chmod +x hooks/post-receive
mkdir -p $WORK_DIR
echo "[Pi] Bare repo ready at $BARE_REPO"
REMOTE

    # Add remote if not present
    if ! git remote get-url "$REMOTE_NAME" &>/dev/null; then
        echo "[*] Adding git remote '$REMOTE_NAME' → $GIT_REMOTE"
        git remote add "$REMOTE_NAME" "$GIT_REMOTE"
    fi

    echo "[*] Running pi-setup.sh on Pi (install deps)..."
    scp -P "$PI_SSH_PORT" pi-setup.sh "$PI_HOST:~/pi-setup.sh"
    $SSH "bash ~/pi-setup.sh"
fi

# ── Ensure all changes are committed ────────────────────────
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "[*] Staging uncommitted changes..."
    git add .
    git commit -m "deploy $(date '+%Y-%m-%d %H:%M')"
fi

# ── Push ────────────────────────────────────────────────────
echo "[*] Pushing to Pi..."
BRANCH=$(git rev-parse --abbrev-ref HEAD)
git push "$REMOTE_NAME" "$BRANCH:main" --force

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ✓  Deployed!  Dashboard → http://$PI_HOST:5003"
echo "     To run:   ssh $PI_HOST 'cd ~/spectre && bash run.sh --skip-tests'"
echo "     To watch: ssh $PI_HOST 'journalctl -u spectre -f'"
echo "═══════════════════════════════════════════════════════════"
