# Deploy Toilet Map to Google Cloud Run

Keep SQLite and serve the web app and existing FastAPI endpoints from one Docker
image. GitHub Actions runs the Ministry of Environment (MOENV) ETL, publishes
the image to a private Artifact Registry repository, and deploys it to Cloud
Run in Taiwan (`asia-east1`). This plan uses no PostgreSQL service.

## One-time setup

1. Create a GCP project with billing enabled. Create a private Docker repository
   in Artifact Registry in `asia-east1`. Create a separate private Cloud Storage
   bucket for the ETL database checkpoint. Use `us-central1` for the bucket to
   qualify for Cloud Storage's regional free allowance. Only the GitHub runner
   needs the checkpoint during routine operation.
2. Seed the bucket with a consistent SQLite backup of the current dataset,
   including raw MOENV snapshots, import history, normalized source records,
   and aggregation versions. Create it with SQLite's backup API or
   `.backup` so committed data in a journal is included. Record the source
   counts and latest successful sync timestamp for the first-run comparison.
3. Configure [Workload Identity Federation](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
   for GitHub Actions. Restrict the trust policy to the numeric GitHub
   repository ID, `refs/heads/main`, and the deployment workflow. Give the
   deployment identity access to the checkpoint bucket, image write access
   on the registry repository, deploy and traffic-update access for Cloud Run,
   and permission to use the designated runtime service account. Keep the
   runtime account separate and give it no checkpoint-bucket access.
4. Add a Dockerfile that installs the locked backend dependencies with Python
   3.13 and uv, copies the app and bundled web assets, and includes the
   validated SQLite snapshot as a build input. Exclude local databases,
   credentials, and unrelated files from the build context. Build for
   `linux/amd64`. Start Uvicorn on `0.0.0.0` using Cloud Run's `PORT`.
   Give SQLite a writable instance-local path through `TOILET_DB_PATH`, since
   startup and aggregation bookkeeping use writes. Leave
   `TOILET_ADMIN_TOKEN` unset so the public service cannot run the ETL.
   [Cloud Run container contract](https://docs.cloud.google.com/run/docs/container-contract)
5. Configure the Cloud Run service for public HTTPS, request-based billing,
   and zero minimum instances. Use 1 vCPU and 512 MiB as initial test settings.
   Measure peak memory with the bundled dataset and time the first nearby
   search after the service has scaled to zero.

## GitHub Actions

Keep the existing [backend CI](../.github/workflows/backend-ci.yml) for lint,
Python tests, and the Node web regression test. Add a release workflow on
`main` with a daily schedule and `workflow_dispatch`. Start at **04:17 Taipei
time** (`17 20 * * *` in UTC, the previous evening). Use one concurrency
group for manual and scheduled releases, without canceling a run in progress.
Require the CI checks for the commit being released to pass. Restrict OIDC
permissions to the release job that accesses GCP. Scheduled runs can be delayed,
and GitHub disables scheduled workflows in public repos after 60 days without
repository activity. Track ETL freshness independently of the cron schedule.
[GitHub Actions schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

1. **Restore.** Check out `main`, install locked dependencies, and download
   the last validated SQLite checkpoint into the runner's temporary directory.
   Fail if the checkpoint is missing or corrupt. Before the first scheduled
   run, verify from a GitHub-hosted runner that both MOENV city requests
   succeed with TLS verification.
2. **Sync and group.** From `backend/`, run
   `uv run --locked python -m app.ingestion.sync_moenv` with `TOILET_DB_PATH`
   pointing to the restored copy. The existing command fetches Taipei
   (`63000`) and New Taipei (`10001`), archives raw responses, upserts source
   records, and refreshes facility groups. Preserve the current rule that a
   source record missing from a day's feed stays in the database.
3. **Validate and checkpoint.** Confirm both city responses are nonempty and
   check fetched counts in this run's archived responses against the last
   good run. Upserts retain older rows, so a healthy total in SQLite alone
   cannot detect a partial feed. Run `PRAGMA integrity_check` and
   `PRAGMA foreign_key_check`, verify the new sync timestamp and aggregation
   version, and confirm facility cards have source records.
   Back up the validated database to the private bucket and retain a previous
   recoverable generation. Condition the upload on the generation restored in
   step 1 so a concurrent change cannot be overwritten. Keep this checkpoint
   independent of the serving image so registry cleanup never removes the ETL
   history.
4. **Build and publish.** Build the image from the tested commit and the
   checkpoint's SQLite snapshot. Run it locally in the job and smoke-test
   `/health`, `/v1/meta`, `/web/`, and
   `/v1/toilets/nearby?lat=25.033&lng=121.5654&radius_m=1000&aggregate=true`.
   Check that the nearby query returns facility cards with source details and
   that the timestamp matches the checkpoint. Push to
   `asia-east1-docker.pkg.dev/PROJECT_ID/REPOSITORY/toilet-map` with a unique
   tag per workflow run. Deploy by image digest.
5. **Deploy and promote.** For the initial release, smoke-test the new service
   before sharing its URL. For later releases, deploy a tagged candidate
   revision with production traffic pinned to the current revision. Run the
   same smoke checks on the candidate URL and then shift 100% of traffic to the
   candidate. Record the image digest, Cloud Run revision, and sync timestamp
   in the workflow summary. [Cloud Run rollout and rollback](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration)

## Failures, rollback, and costs

- A failed sync or data validation leaves the existing checkpoint and live
  revision in place. If publishing or rollout fails after checkpoint validation,
  the new data remains available for a rerun and the current revision keeps
  serving. If a problem appears after promotion, route traffic back to the
  previous Cloud Run revision.
- Verify the first deployment on iPhone Safari over HTTPS. Check geolocation,
  nearby results, filters, facility details, and directions. Watch
  `/v1/meta` for a stale sync timestamp and track cold-start latency.
- Enable a [registry cleanup policy](https://docs.cloud.google.com/artifact-registry/docs/repositories/cleanup-policy)
  after previewing it in dry-run mode. Keep the active image and a small
  rollback set. Monitor the checkpoint size as raw and aggregation history
  grows. Limit redundant backup generations while keeping the full history
  inside the current checkpoint.
- Cloud Run's compute free tier applies within its quotas. Its documented free
  internet transfer allowance is for North America, so serving Taipei users
  from Taiwan can incur network charges. Artifact Registry has a separate
  **0.5 GiB-month** free allowance. Track registry, bucket, and Cloud Run
  usage with billing alerts. [Cloud Run pricing](https://cloud.google.com/run/pricing)
  · [Artifact Registry pricing](https://cloud.google.com/artifact-registry/pricing)
  · [Cloud Storage free tier](https://docs.cloud.google.com/free/docs/free-cloud-features#cloud-storage)
