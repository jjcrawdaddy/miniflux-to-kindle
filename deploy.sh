#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_DIR="$HOME/docker/miniflux-to-kindle"

# Sync docker-compose.yml.example from live compose file
cp "$COMPOSE_DIR/docker-compose.yml" "$REPO_DIR/docker-compose.yml.example"

# Commit and push if it changed
cd "$REPO_DIR"
if ! git diff --quiet docker-compose.yml.example; then
    git add docker-compose.yml.example
    git commit -m "chore: sync docker-compose.yml.example"
    git push
fi

# Rebuild and restart
cd "$COMPOSE_DIR"
docker compose up -d --build --force-recreate
