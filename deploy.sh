#!/usr/bin/env bash
set -euo pipefail

COMPOSE_DIR="$HOME/docker/miniflux-to-kindle"

# Rebuild and restart
cd "$COMPOSE_DIR"
docker compose up -d --build --force-recreate
