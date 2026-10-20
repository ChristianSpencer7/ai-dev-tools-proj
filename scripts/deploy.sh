#!/usr/bin/env bash
# Deploys the latest main on the server: run by GitHub Actions over SSH, or by hand as ./scripts/deploy.sh.
# The server never has changes of its own to keep; .env isn't tracked by git, so it survives the reset.
set -euo pipefail
cd "$(dirname "$0")/.."

git fetch --quiet origin main
git reset --hard --quiet origin/main
echo "Deploying $(git log -1 --format='%h %s')"

compose() { docker compose -f docker-compose.yml -f docker-compose.prod.yml "$@"; }
# --wait: return only once every service is running, and healthy where it has a health check.
compose up -d --build --remove-orphans --wait --wait-timeout 300
compose ps
docker image prune -f > /dev/null  # old images from earlier deploys
