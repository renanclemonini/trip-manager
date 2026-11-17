#!/usr/bin/env bash
# Bring the development environment down, forwarding all arguments to
# `docker compose down` (e.g. `dev-down -v` to also remove the dev volume).
set -euo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
cd "$(dirname "$(dirname "$SCRIPT_PATH")")"

docker compose down "$@"
