#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
runtime_directory="/etc/therapist-dashboard"
runtime_identifiers="$runtime_directory/runtime-identifiers.env"
secret_resolver="$repository_root/deploy/hosted-demo/asm-exec"
revision="${1:-$(git -C "$repository_root" rev-parse --short=12 HEAD)}"

for required_file in "$runtime_identifiers" "$secret_resolver"; do
  if [[ ! -r "$required_file" ]]; then
    echo "Missing required root-readable runtime file: $required_file" >&2
    exit 1
  fi
done

set -a
# This file contains identifiers only and is safe to source. Secret values are
# resolved immediately before each child process starts.
source "$runtime_identifiers"
set +a

for required_identifier in APP_RUNTIME_SECRET_ARN DATABASE_SECRET_ARN DATABASE_HOST DATABASE_NAME; do
  if [[ -z "${!required_identifier:-}" ]]; then
    echo "Missing required runtime identifier: $required_identifier" >&2
    exit 1
  fi
done

if [[ ! "$revision" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Revision may contain only letters, numbers, dots, underscores, and hyphens." >&2
  exit 1
fi

api_image="therapist-dashboard-api:$revision"
frontend_image="therapist-dashboard-frontend:$revision"
migration_image="therapist-dashboard-migration:$revision"

docker build --file "$repository_root/api-container/Dockerfile" --tag "$api_image" "$repository_root"
docker build --file "$repository_root/frontend/Dockerfile" --tag "$frontend_image" "$repository_root/frontend"
docker build --file "$repository_root/database/migration-container/Dockerfile" --tag "$migration_image" "$repository_root"

docker volume create therapist_dashboard_recordings >/dev/null

wait_for_url() {
  local url="$1"
  for _ in $(seq 1 30); do
    if curl --fail --silent "$url" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

start_api() {
  local image="$1"
  export AUTH0_DOMAIN="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_DOMAIN}}"
  export AUTH0_AUDIENCE="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_AUDIENCE}}"
  export ORGANIZATION_STORAGE_ENABLED="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:ORGANIZATION_STORAGE_ENABLED}}"
  export HEALTHSCRIBE_MAX_SPEAKERS="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:HEALTHSCRIBE_MAX_SPEAKERS}}"

  python3 "$secret_resolver" -- docker run -d \
    --name therapist-dashboard-api \
    --network host \
    --restart unless-stopped \
    --env-file "$runtime_identifiers" \
    --env AUTH0_DOMAIN \
    --env AUTH0_AUDIENCE \
    --env ORGANIZATION_STORAGE_ENABLED \
    --env HEALTHSCRIBE_MAX_SPEAKERS \
    --mount type=volume,source=therapist_dashboard_recordings,target=/app/recordings \
    "$image" >/dev/null
}

start_frontend() {
  local image="$1"
  export AUTH0_DOMAIN="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_DOMAIN}}"
  export AUTH0_CLIENT_ID="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_CLIENT_ID}}"
  export AUTH0_CLIENT_SECRET="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_CLIENT_SECRET}}"
  export AUTH0_SECRET="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_SECRET}}"
  export AUTH0_AUDIENCE="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_AUDIENCE}}"
  export APP_BASE_URL="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:APP_BASE_URL}}"
  export API_ORIGIN="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:API_ORIGIN}}"

  python3 "$secret_resolver" -- docker run -d \
    --name therapist-dashboard-frontend \
    --network host \
    --restart unless-stopped \
    --env AUTH0_DOMAIN \
    --env AUTH0_CLIENT_ID \
    --env AUTH0_CLIENT_SECRET \
    --env AUTH0_SECRET \
    --env AUTH0_AUDIENCE \
    --env APP_BASE_URL \
    --env API_ORIGIN \
    "$image" >/dev/null
}

run_migrations() {
  export DATABASE_USERNAME="{{resolve:secretsmanager:$DATABASE_SECRET_ARN:SecretString:username}}"
  export DATABASE_PASSWORD="{{resolve:secretsmanager:$DATABASE_SECRET_ARN:SecretString:password}}"

  python3 "$secret_resolver" -- docker run --rm \
    --network host \
    --env DATABASE_USERNAME \
    --env DATABASE_PASSWORD \
    --env DATABASE_HOST \
    --env DATABASE_NAME \
    "$migration_image"

  unset DATABASE_USERNAME DATABASE_PASSWORD
}

run_migrations

previous_api_image="$(docker inspect --format '{{.Config.Image}}' therapist-dashboard-api 2>/dev/null || true)"
docker rm -f therapist-dashboard-api >/dev/null 2>&1 || true
start_api "$api_image"
if ! wait_for_url http://127.0.0.1:8000/healthz; then
  docker logs --tail 100 therapist-dashboard-api >&2 || true
  docker rm -f therapist-dashboard-api >/dev/null 2>&1 || true
  if [[ -n "$previous_api_image" ]]; then
    start_api "$previous_api_image"
  fi
  echo "The new API did not become healthy; the previous API image was restored when available." >&2
  exit 1
fi

previous_frontend_image="$(docker inspect --format '{{.Config.Image}}' therapist-dashboard-frontend 2>/dev/null || true)"
docker rm -f therapist-dashboard-frontend >/dev/null 2>&1 || true
start_frontend "$frontend_image"
if ! wait_for_url http://127.0.0.1:3000/; then
  docker logs --tail 100 therapist-dashboard-frontend >&2 || true
  docker rm -f therapist-dashboard-frontend >/dev/null 2>&1 || true
  if [[ -n "$previous_frontend_image" ]]; then
    start_frontend "$previous_frontend_image"
  fi
  echo "The new frontend did not become healthy; the previous frontend image was restored when available." >&2
  exit 1
fi

echo "Deployed hosted demo revision $revision."
