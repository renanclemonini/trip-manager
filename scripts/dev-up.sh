#!/usr/bin/env bash
# Bring the development environment up (detached), forwarding all arguments
# to `docker compose up` (e.g. `dev-up --build`).
set -euo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
cd "$(dirname "$(dirname "$SCRIPT_PATH")")"

docker compose up -d "$@"
