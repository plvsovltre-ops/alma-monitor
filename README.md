# ALMA Monitor

ALMA Monitor receives new field incidents from a private Mergin Maps project.
It checks the incident location against orchard layers. It uses Gemini to prepare
a bilingual draft response. It sends one email with Russian and Kazakh text. It
then records the result in private Cloud Storage state and Google Sheets.

The worker treats the Mergin Maps project as read-only. It never writes generated
text or delivery fields back to a field GeoPackage and never pushes the downloaded
project. This boundary prevents the cloud worker from conflicting with mobile
survey edits.

The monitor is designed to run as a scheduled Google Cloud Run Job. It does not
need a personal computer after deployment.

## System boundary

- **Mergin Maps Cloud** is the read-only source of field observations and media.
- **Cloud Run Job** is the processing worker.
- **Cloud Scheduler** starts the watcher every minute.
- **Cloud Storage** keeps per-incident processing and delivery state, the last
  scanned Mergin Maps version, and an atomic execution lock.
- **Secret Manager** stores credentials.
- **Google Sheets** is a secondary registry. A Sheets failure does not resend a
  completed email.
- **GitHub** stores code and deployment files. Do not store field data, photos,
  credentials, or a Mergin Maps project folder in this repository.

Do not keep the active QGIS/Mergin Maps project folder in Google Drive or
OneDrive. Keep it on a local disk and synchronise it through Mergin Maps.

## Runtime configuration

The worker needs these secrets:

| Name | Purpose |
| --- | --- |
| `MERGIN_USER` | Dedicated Mergin Maps worker account |
| `MERGIN_PASS` | Password for the worker account |
| `GMAIL_USER` | Email account that sends replies |
| `GMAIL_APP_PASS` | App password for the sender account |
| `GEMINI_API_KEY` | Gemini API key |

Terraform sets `STATE_BUCKET` as a normal environment variable. Do not create a
Secret Manager entry for it.

Set `GEMINI_MODEL` only when a different supported model is needed. The default
is `gemini-3.6-flash`. The worker uses `gemini-2.5-flash` as a fallback.

Never commit secret values. Use `.env.example` only as a list of variable names.

The Cloud Run service account is used for Google Sheets. Share `ALMA_Registry`
with `alma-monitor@alma-monitor-prod-2026.iam.gserviceaccount.com` as an editor.
This avoids a long-lived service-account JSON key.

## Google Cloud deployment

The prepared Terraform configuration is in `infra/`. It uses the project ID
`alma-monitor-prod-2026` by default.

1. Install and authenticate the Google Cloud CLI and Terraform.
   Enable the Cloud Resource Manager API once before Terraform manages the
   remaining project services:

   ```sh
   gcloud services enable cloudresourcemanager.googleapis.com \
     --project=alma-monitor-prod-2026
   ```
2. Create the Cloud APIs, container registry, service accounts, and empty Secret
   Manager entries:

   ```sh
   cd infra
   terraform init
   terraform apply \
     -target=google_artifact_registry_repository.alma_monitor \
     -target=google_service_account.monitor \
     -target=google_service_account.scheduler \
     -target=google_secret_manager_secret.runtime \
     -var='image=placeholder.invalid/alma-monitor:unbuilt'
   ```

3. Add one version to each empty secret in Google Cloud Console. Do not put the
   secret values in Terraform files or command history.
4. Build and upload the container image:

   ```sh
   gcloud builds submit .. \
     --tag europe-west1-docker.pkg.dev/alma-monitor-prod-2026/alma-monitor/alma-monitor:1.0.0
   ```

5. Deploy the Cloud Run Job and scheduler:

   ```sh
   terraform apply \
     -var='image=europe-west1-docker.pkg.dev/alma-monitor-prod-2026/alma-monitor/alma-monitor:1.0.0'
   ```

6. In Google Cloud Console, run `alma-monitor` once. Add one test incident in
   Mergin Maps and verify the email, Cloud Storage incident state, and Google
   Sheets row. Verify that the worker did not create a new Mergin Maps version.

The first Terraform command uses `-target` only to create the registry and empty
secret containers before the first image exists. All later changes use a normal
`terraform apply`.

## Operations

- Use Cloud Logging to review every job execution.
- The watcher reads the Mergin Maps project version each minute. If the version
  did not change, it does not download the GIS project and it does not call
  Gemini.
- If the version changed, the worker downloads and scans the project. It calls
  Gemini only when it finds an unsent incident.
- The worker uses the incident ID and Cloud Storage state to prevent duplicate
  email delivery and Google Sheets rows. A delivered result can restore a
  missing registry row without sending the email again.
- A worker interruption after email delivery starts is quarantined as
  `delivery_uncertain`; it requires manual review and is never resent
  automatically. Configure a Cloud Logging alert for
  `manual review is required`. The durable quarantine lets the watcher record
  the scanned field version instead of failing and downloading the same project
  every minute.
- Legacy `is_sent=1` rows remain readable during migration, but all new runtime
  state is kept outside the field GeoPackage.
- Configure an alert for failed Cloud Run Job executions.
- The recorded source version comes from the downloaded project's own Mergin
  metadata, not from a later server lookup.
- Keep one task and one parallel worker. A Cloud Storage lock stops overlapping
  executions from processing the same Mergin Maps version.
- Update the Gemini model before a published model shutdown date.
- Review generated legal drafts before they are used as official submissions.

## Citizen science publication readiness

See [the readiness note](docs/UN_CITIZEN_SCIENCE_READINESS.md). It defines the
minimum documentation, privacy controls, and quality evidence needed before a
public release.

## Kazakhstan Legal Core

The versioned Kazakhstan Legal Core release candidate is documented in
[`legal_core/README.md`](legal_core/README.md). It contains 122 owner-accepted
cards from `ALMA Legal Review — Kazakhstan v1.2`, their official Adilet links,
a source registry, a manifest, and checksums.
The catalog verifies these artifacts and every reviewed card hash before a
citation can be returned.

This release candidate is eligible only for controlled pilot development. An
independent lawyer review is pending and public legal release is blocked. The
current `main.py` still uses the legacy text knowledge folder; connecting the
new deterministic card catalog to incident processing is intentionally deferred
to a separate reviewed change.

ALMA was initiated and originally designed by Yernar Sailybayev in Almaty,
Kazakhstan.
