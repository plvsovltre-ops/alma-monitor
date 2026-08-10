# ALMA Monitor

ALMA Monitor receives new field incidents from a private Mergin Maps project.
It checks the incident location against orchard layers. It uses Gemini to prepare
a bilingual draft response. It sends one email with Russian and Kazakh text. It
then records the completed result in Mergin Maps and Google Sheets.

The monitor is designed to run as a scheduled Google Cloud Run Job. It does not
need a personal computer after deployment.

## System boundary

- **Mergin Maps Cloud** is the source of GIS data and incident status.
- **Cloud Run Job** is the processing worker.
- **Cloud Scheduler** starts the worker every 30 minutes.
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
   Mergin Maps and verify the email, Mergin Maps update, and Google Sheets row.

The first Terraform command uses `-target` only to create the registry and empty
secret containers before the first image exists. All later changes use a normal
`terraform apply`.

## Operations

- Use Cloud Logging to review every job execution.
- Scheduled checks with no new incidents do not call Gemini or consume model
  quota.
- Configure an alert for failed Cloud Run Job executions.
- Keep one task and one parallel worker. The worker must not process the same
  Mergin Maps project from two locations at once.
- Update the Gemini model before a published model shutdown date.
- Review generated legal drafts before they are used as official submissions.

## Citizen science publication readiness

See [the readiness note](docs/UN_CITIZEN_SCIENCE_READINESS.md). It defines the
minimum documentation, privacy controls, and quality evidence needed before a
public release.
