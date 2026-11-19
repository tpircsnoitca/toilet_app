#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT:?Set GCP_PROJECT_ID}"
: "${CHECKPOINT_BUCKET:?Set GCP_CHECKPOINT_BUCKET}"
: "${RUNTIME_SERVICE_ACCOUNT:?Set GCP_RUNTIME_SERVICE_ACCOUNT}"
region=asia-east1
service=toilet-app
registry="$region-docker.pkg.dev"
image="$registry/$PROJECT/toilet-app/toilet-map:gh-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
checkpoint_uri="gs://$CHECKPOINT_BUCKET/checkpoint.sqlite3"
work=$(mktemp -d "$RUNNER_TEMP/toilet-release.XXXXXX")
container_id=
trap 'if [[ -n $container_id ]]; then docker stop "$container_id" >/dev/null 2>&1 || true; fi' EXIT

echo "::group::Restore the last validated checkpoint"
generation=$(gcloud storage objects describe "$checkpoint_uri" --format='value(generation)')
[[ $generation =~ ^[0-9]+$ ]]
gcloud storage cp "$checkpoint_uri#$generation" "$work/restored.sqlite3"
(
    cd backend
    uv run --locked --no-dev python -m scripts.release_checkpoint "$work/restored.sqlite3"
) | tee "$work/previous.json"
echo "::endgroup::"

echo "::group::Fetch and validate both MOENV feeds"
# The same TLS-verified fetches used in production also verify GitHub runner connectivity.
export TOILET_DB_PATH="$work/restored.sqlite3"
(
    cd backend
    uv run --locked --no-dev python -m app.ingestion.sync_moenv
    uv run --locked --no-dev python -m scripts.release_checkpoint "$TOILET_DB_PATH" \
        --previous "$work/previous.json" --backup "$work/checkpoint.sqlite3" |
        tee "$work/validated.json"
)
unset TOILET_DB_PATH
last_sync=$(jq -er .last_synced_at "$work/validated.json")
metadata=$(jq -er '"taipei-features=\(.feed_counts["63000"]),new-taipei-features=\(.feed_counts["10001"]),last-synced-at=\(.last_synced_at)"' "$work/validated.json")
gcloud storage cp "$work/checkpoint.sqlite3" "$checkpoint_uri" \
    --if-generation-match="$generation" --custom-metadata="$metadata"
echo "::endgroup::"

echo "::group::Build, smoke-test and publish the image"
cp "$work/checkpoint.sqlite3" checkpoint.sqlite3
docker build --platform=linux/amd64 --tag="$image" .
container_id=$(docker run --rm --detach --cpus=1 --memory=512m --publish=127.0.0.1::8080 "$image")
local_address=$(docker port "$container_id" 8080/tcp)
if ! python .github/scripts/smoke_release.py "http://$local_address" "$last_sync"; then
    docker logs "$container_id"
    exit 1
fi
docker stop "$container_id" >/dev/null
container_id=
gcloud auth configure-docker "$registry" --quiet
docker push "$image"
digest=$(gcloud artifacts docker images describe "$image" --project="$PROJECT" \
    --format='value(image_summary.fully_qualified_digest)')
[[ $digest == "$registry/$PROJECT/toilet-app/toilet-map@sha256:"* ]]
echo "::endgroup::"

echo "::group::Deploy and smoke-test the candidate"
run_flags=(--project="$PROJECT" --region="$region")
suffix="gh-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
revision="$service-$suffix"
gcloud run deploy "$service" "${run_flags[@]}" --image="$digest" \
    --service-account="$RUNTIME_SERVICE_ACCOUNT" --no-traffic --tag=candidate \
    --revision-suffix="$suffix" --quiet
candidate_url=$(gcloud run services describe "$service" "${run_flags[@]}" --format=json |
    jq -er --arg revision "$revision" \
        '.status.traffic[] | select(.tag == "candidate" and .revisionName == $revision) | .url')
python .github/scripts/smoke_release.py "$candidate_url" "$last_sync"
gcloud run services update-traffic "$service" "${run_flags[@]}" \
    --to-revisions="$revision=100" --remove-tags=candidate --quiet
gcloud run services describe "$service" "${run_flags[@]}" --format=json |
    jq -e --arg revision "$revision" \
        'any(.status.traffic[]; .revisionName == $revision and .percent == 100)'
echo "::endgroup::"

{
    echo '## Toilet Map release'
    printf -- '- Commit: `%s`\n' "$GITHUB_SHA"
    printf -- '- Image: `%s`\n' "$digest"
    printf -- '- Cloud Run revision: `%s`\n' "$revision"
    printf -- '- Last successful MOENV sync (UTC): `%s`\n' "$last_sync"
    jq -r '"- Feed features: Taipei \(.feed_counts["63000"]), New Taipei \(.feed_counts["10001"])"' "$work/validated.json"
} >> "$GITHUB_STEP_SUMMARY"
