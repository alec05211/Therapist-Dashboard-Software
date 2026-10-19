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

for required_identifier in APP_RUNTIME_SECRET_ARN CLINICAL_SYNTHESIS_SECRET_ARN DATABASE_SECRET_ARN DATABASE_HOST DATABASE_NAME; do
  if [[ -z "${!required_identifier:-}" ]]; then
    echo "Missing required runtime identifier: $required_identifier" >&2
    exit 1
  fi
done

ensure_secret_provider() {
  local token_file="/var/run/awssmatoken"

  if ! rpm --query aws-workload-credentials-provider >/dev/null 2>&1; then
    dnf install -y aws-workload-credentials-provider
  fi

  for _ in $(seq 1 30); do
    if [[ -s "$token_file" ]] && timeout 1 bash -c '</dev/tcp/127.0.0.1/2773' 2>/dev/null; then
      export AWS_SECRETS_MANAGER_AGENT_TOKEN_FILE="$token_file"
      export ASM_EXEC_REQUIRE_SMA="true"
      return 0
    fi
    sleep 1
  done

  echo "The local AWS Workload Credentials Provider did not become ready." >&2
  return 1
}

if [[ ! "$revision" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Revision may contain only letters, numbers, dots, underscores, and hyphens." >&2
  exit 1
fi

ensure_secret_provider

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

create_api() {
  local image="$1"
  local container_name="$2"
  export AUTH0_DOMAIN="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_DOMAIN}}"
  export AUTH0_AUDIENCE="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_AUDIENCE}}"
  export ORGANIZATION_STORAGE_ENABLED="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:ORGANIZATION_STORAGE_ENABLED}}"
  export HEALTHSCRIBE_MAX_SPEAKERS="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:HEALTHSCRIBE_MAX_SPEAKERS}}"
  export OPENAI_API_KEY="{{resolve:secretsmanager:$CLINICAL_SYNTHESIS_SECRET_ARN}}"
  export INSIGHTS_MODEL="gpt-5"
  export PRE_SESSION_MODEL="gpt-5"
  export JOURNEY_PROPOSAL_MODEL="gpt-5"
  export INSURANCE_CARD_MODEL="${INSURANCE_CARD_MODEL:-gpt-6-astra}"
  export INSURANCE_CARD_OPENAI_APPROVED="${INSURANCE_CARD_OPENAI_APPROVED:-false}"
  export CLINICAL_SYNTHESIS_WORKER_ENABLED="true"

  python3 "$secret_resolver" -- docker create \
    --name "$container_name" \
    --network host \
    --restart unless-stopped \
    --env-file "$runtime_identifiers" \
    --env AUTH0_DOMAIN \
    --env AUTH0_AUDIENCE \
    --env ORGANIZATION_STORAGE_ENABLED \
    --env HEALTHSCRIBE_MAX_SPEAKERS \
    --env OPENAI_API_KEY \
    --env INSIGHTS_MODEL \
    --env PRE_SESSION_MODEL \
    --env JOURNEY_PROPOSAL_MODEL \
    --env INSURANCE_CARD_MODEL \
    --env INSURANCE_CARD_OPENAI_APPROVED \
    --env CLINICAL_SYNTHESIS_WORKER_ENABLED \
    --mount type=volume,source=therapist_dashboard_recordings,target=/app/recordings \
    "$image" >/dev/null

  unset OPENAI_API_KEY
}

create_frontend() {
  local image="$1"
  local container_name="$2"
  export AUTH0_DOMAIN="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_DOMAIN}}"
  export AUTH0_CLIENT_ID="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_CLIENT_ID}}"
  export AUTH0_CLIENT_SECRET="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_CLIENT_SECRET}}"
  export AUTH0_SECRET="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_SECRET}}"
  export AUTH0_AUDIENCE="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:AUTH0_AUDIENCE}}"
  export APP_BASE_URL="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:APP_BASE_URL}}"
  export API_ORIGIN="{{resolve:secretsmanager:$APP_RUNTIME_SECRET_ARN:SecretString:API_ORIGIN}}"

  python3 "$secret_resolver" -- docker create \
    --name "$container_name" \
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

container_exists() {
  docker inspect "$1" >/dev/null 2>&1
}

recover_interrupted_rollout() {
  local container_name="$1"
  local previous_name="$2"

  if ! container_exists "$container_name" && container_exists "$previous_name"; then
    docker rename "$previous_name" "$container_name"
    docker start "$container_name" >/dev/null
  fi
}

promote_container() {
  local container_name="$1"
  local candidate_name="$2"
  local previous_name="$3"
  local health_url="$4"
  local had_previous="false"

  recover_interrupted_rollout "$container_name" "$previous_name"

  if container_exists "$container_name"; then
    docker rm -f "$previous_name" >/dev/null 2>&1 || true
    docker stop "$container_name" >/dev/null
    docker rename "$container_name" "$previous_name"
    had_previous="true"
  fi

  if ! docker rename "$candidate_name" "$container_name" \
    || ! docker start "$container_name" >/dev/null \
    || ! wait_for_url "$health_url"; then
    docker logs --tail 100 "$container_name" >&2 2>/dev/null || true
    docker rm -f "$container_name" >/dev/null 2>&1 || true
    docker rm -f "$candidate_name" >/dev/null 2>&1 || true
    if [[ "$had_previous" == "true" ]]; then
      docker rename "$previous_name" "$container_name"
      docker start "$container_name" >/dev/null
    fi
    return 1
  fi

  return 0
}

restore_previous_container() {
  local container_name="$1"
  local previous_name="$2"

  if container_exists "$previous_name"; then
    docker rm -f "$container_name" >/dev/null 2>&1 || true
    docker rename "$previous_name" "$container_name"
    docker start "$container_name" >/dev/null
  fi
}

discard_previous_container() {
  docker rm -f "$1" >/dev/null 2>&1 || true
}

run_migrations

api_candidate="therapist-dashboard-api-candidate"
api_previous="therapist-dashboard-api-previous"
recover_interrupted_rollout therapist-dashboard-api "$api_previous"
docker rm -f "$api_candidate" >/dev/null 2>&1 || true
if ! create_api "$api_image" "$api_candidate"; then
  echo "The API candidate could not be created; the current release was left running." >&2
  exit 1
fi
if ! promote_container therapist-dashboard-api "$api_candidate" "$api_previous" http://127.0.0.1:8000/healthz; then
  echo "The new API did not become healthy; the preserved API container was restored when available." >&2
  exit 1
fi

frontend_candidate="therapist-dashboard-frontend-candidate"
frontend_previous="therapist-dashboard-frontend-previous"
recover_interrupted_rollout therapist-dashboard-frontend "$frontend_previous"
docker rm -f "$frontend_candidate" >/dev/null 2>&1 || true
if ! create_frontend "$frontend_image" "$frontend_candidate"; then
  restore_previous_container therapist-dashboard-api "$api_previous"
  echo "The frontend candidate could not be created; the preserved release was restored when available." >&2
  exit 1
fi
if ! promote_container therapist-dashboard-frontend "$frontend_candidate" "$frontend_previous" http://127.0.0.1:3000/; then
  restore_previous_container therapist-dashboard-api "$api_previous"
  echo "The new frontend did not become healthy; the preserved frontend container was restored when available." >&2
  exit 1
fi

discard_previous_container "$api_previous"
discard_previous_container "$frontend_previous"

echo "Deployed hosted demo revision $revision."
