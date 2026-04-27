#!/usr/bin/env bash
# deploy-proxy.sh
# ════════════════════════════════════════════════════════════════════════════
# Installs xoa-proxy.py on the XCP-ng Dom0 host and (optionally) builds +
# deploys the updated XO-Lite bundle.
#
# Usage:
#   ./deploy-proxy.sh                          # uses HOST from environment
#   ./deploy-proxy.sh root@192.168.0.85        # explicit host
#   ./deploy-proxy.sh root@192.168.0.85 --app  # also build & deploy XO-Lite
#
# Requirements on your dev machine: ssh, rsync, (npx yarn if using --app)
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
HOST="${1:-${XO_HOST:-root@192.168.0.85}}"
DEPLOY_APP=false

# Parse optional flags
for arg in "$@"; do
  [[ "$arg" == "--app" ]] && DEPLOY_APP=true
done

XOLITE_DIR="$(cd "$(dirname "$0")/.." && pwd)"  # project root (one level up from xoa-proxy/)
PROXY_SCRIPT="$(dirname "$0")/xoa-proxy.py"
SERVICE_FILE="$(dirname "$0")/xoa-proxy.service"
REMOTE_WWW="/opt/xensource/www"
REMOTE_SERVICE="/etc/systemd/system/xoa-proxy.service"

echo "▶ Target host : $HOST"
echo "▶ Deploy app  : $DEPLOY_APP"
echo ""

# ── Step 1: Install the proxy script on Dom0 ──────────────────────────────────
echo "── [1/3] Copying xoa-proxy.py to $HOST:$REMOTE_WWW/"
rsync -av --checksum "$PROXY_SCRIPT" "$HOST:$REMOTE_WWW/"

# ── Step 2: Install and enable the systemd service ────────────────────────────
echo "── [2/3] Installing systemd unit"
rsync -av --checksum "$SERVICE_FILE" "$HOST:$REMOTE_SERVICE"

ssh "$HOST" bash <<'REMOTE'
  set -e
  systemctl daemon-reload
  systemctl enable xoa-proxy
  # Restart if already running, start if not
  if systemctl is-active --quiet xoa-proxy; then
    systemctl restart xoa-proxy
    echo "  ✔ xoa-proxy restarted"
  else
    systemctl start xoa-proxy
    echo "  ✔ xoa-proxy started"
  fi
  # Verify it came up
  sleep 1
  systemctl is-active xoa-proxy && echo "  ✔ xoa-proxy is running" || echo "  ✘ xoa-proxy failed to start — check: journalctl -u xoa-proxy"
REMOTE

# ── Step 3 (optional): Build and deploy XO-Lite ───────────────────────────────
if [[ "$DEPLOY_APP" == "true" ]]; then
  echo "── [3/3] Building XO-Lite"
  (cd "$XOLITE_DIR" && npx yarn build)

  echo "      Deploying dist/ to $HOST:$REMOTE_WWW/"
  rsync -av --delete "$XOLITE_DIR/dist/" "$HOST:$REMOTE_WWW/"
  echo "  ✔ XO-Lite deployed"
else
  echo "── [3/3] Skipping XO-Lite build (pass --app to include)"
fi

echo ""
echo "✔ Done. Proxy endpoint: http://127.0.0.1:9001/image.xva?src=<https-url>"
echo "  Logs: ssh $HOST journalctl -u xoa-proxy -f"
