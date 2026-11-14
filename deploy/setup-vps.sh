#!/usr/bin/env bash
# Bootstrap Cravix on an Ubuntu VPS (22.04 / 24.04).
# Run from the repo root on the server:
#   chmod +x deploy/setup-vps.sh
#   ./deploy/setup-vps.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Installing Docker (if missing)"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  sudo usermod -aG docker "$USER" || true
  echo "Docker installed. You may need to log out/in for group changes."
fi

if [ ! -f .env.production ]; then
  cp .env.production.example .env.production
  echo "==> Created .env.production — EDIT IT before continuing (passwords, SECRET_KEY, PUBLIC_BASE_URL)"
  echo "    nano .env.production"
  exit 1
fi

# Basic sanity checks
if grep -q "CHANGE_ME" .env.production; then
  echo "ERROR: .env.production still contains CHANGE_ME placeholders. Edit it first."
  exit 1
fi

echo "==> Building and starting production stack"
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

echo "==> Waiting for API health"
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health/live >/dev/null 2>&1; then
    echo "API is up."
    curl -fsS http://127.0.0.1:8000/health/ready || true
    echo
    echo "Done. Next: set up Nginx + SSL (see docs/VPS.md)"
    exit 0
  fi
  sleep 2
done

echo "API did not become healthy in time. Check logs:"
echo "  docker compose -f docker-compose.prod.yml --env-file .env.production logs --tail=100"
exit 1
