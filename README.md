# ALMA Monitor

> **Release status:** the code is publicly inspectable, but the public Legal
> Core mode remains fail-closed until the author/legal-editor review, a separate
> independent-lawyer review, and final hash-bound activation are committed.

ALMA Monitor receives new field incidents from a private Mergin Maps project.
It resolves a reviewed territory and authority route from orchard layers before
Gemini is used. Gemini describes only observable facts. The recipient, subject,
short request, territory name, and monitoring purpose come from the local
reviewed `config/territory_catalog.json`. The public-interest context and next
steps come from the separately reviewed `config/response_catalog.json`. These
catalogs cause no API call and no Gemini token use. Deterministically selected
Legal Core provisions appear only as a short legal basis in the draft request;
full citations and audit metadata remain in the private incident state. The
worker sends one email with Russian and Kazakh text, then records the result in
private Cloud Storage state and Google Sheets.

The worker treats the Mergin Maps project as read-only. It never writes generated
text or delivery fields back to a field GeoPackage and never pushes the downloaded
project. This boundary prevents the cloud worker from conflicting with mobile
survey edits.

The monitor is designed to run as a scheduled Google Cloud Run Job. It does not
need a personal computer after deployment.

## System boundary

- **Mergin Maps Cloud** is the read-only source of field observations and media.
- **Cloud Run Job** is the processing worker.
- **Cloud Scheduler** starts the watcher every 15 minutes.
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

`ALMA_RELEASE_MODE` defaults to `controlled_pilot`. Do not set it to
`public_legal_release` until the exact governance records under
`governance/public/` are approved. A premature public setting fails before
Gemini is called.

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
- The watcher reads the Mergin Maps project version every 15 minutes. If the version
  did not change, it does not download the GIS project and it does not call
  Gemini.
- If the version changed, the worker downloads and scans the project. It calls
  Gemini only when it finds an unsent incident.
- Before Gemini is called, the runtime Legal Core policy must match the exact
  reviewed release and carry controlled-pilot approval by Yernar Sailybayev.
  A pending, changed, missing, or differently reviewed policy blocks processing.
- The exact field value `incident_type` selects a reviewed rule list. Free text,
  photos, coordinates, and model output never select article numbers.
- Before Gemini is called, the incident point must intersect an exact GeoPackage
  filename listed in the reviewed territory catalog. An unknown or unmatched
  layer is quarantined as `spatial_review_required`; no recipient or legal result
  is guessed and no Gemini tokens are spent. When the row carries an explicit
  volunteer email, the worker sends one deterministic bilingual correction
  notice explaining how to check the marker and collect a new observation. It
  never tells the volunteer to falsify or move truthful coordinates.
- A spatially quarantined incident is checked again when its point or exact field
  signal changes, even if the reviewed catalog itself is unchanged. Unchanged
  input remains quarantined without a Gemini call.
- Field mode requires an explicit volunteer email, a non-empty signal type, and at least one readable image
  explicitly related to the incident. The mobile QGIS form makes the image,
  relation, and signal type mandatory and stores attachment paths under `DCIM/`.
  The cloud worker independently verifies that the path stays inside the Mergin
  project and that the file is a readable image. Incomplete evidence is kept as
  `evidence_review_required`; it consumes no Gemini tokens and sends one
  deterministic correction notice to an explicit volunteer email.
  The incident is retried automatically only after its related photo fields
  change.
- Missing and unsupported signal types use the same correction-notice channel.
  These operational notices are not legal assessments, do not enter the ALMA
  Registry as completed observations, and are deduplicated by the exact rejected
  input, reason, and recipient. A delivery interrupted after SMTP starts is
  marked uncertain and is never resent automatically. The v1.3.1 watcher-state
  migration performs one full scan so previously quarantined observations also
  receive the notice when an explicit email is present.
- The active v0.2 catalog deterministically routes all five exact field signal
  types: `waste` and `soil_damage` to Almaty land-resources control, `logging`
  to the Almaty Ecology and Environment Department, `construction` to Almaty
  Urban Planning Control, and `water_pollution` to the Balkhash-Alakol Basin
  Inspection. The presence of a Legal Core mapping alone never selects an
  authority.
- Volunteer-facing emails use a reviewed human-response structure: greeting,
  public-interest context, facts, cautious assessment, practical next step, a
  short draft request, and contribution acknowledgement. They do not contain a
  reviewer name, GIS source terminology, or a long list of unknown circumstances.
  The draft request names only provisions selected by the approved Legal Core
  policy and says that final applicability is determined by the competent organ.
  Full citations and audit metadata remain in the private Cloud Storage card.
- The first territory catalog with SHA-256
  `68bb08dabda87343286879be6cb699cda26dfc2bf5d072208a75dbdfa2d5a32a` was
  approved by Yernar Sailybayev on 2026-08-13 as author and legal editor, only
  for the private controlled pilot. A changed catalog invalidates its separate
  approval record and blocks the worker before registry writes or Gemini calls.
  After reviewing a future exact diff, the author can bind a new private-pilot
  approval with
  `python scripts/approve_territory_catalog.py --catalog config/territory_catalog.json --approval config/territory_catalog.approval.json --reviewer "Yernar Sailybayev" --capacity AUTHOR_AND_LEGAL_EDITOR --reviewed-on YYYY-MM-DD`.
- The `kz-almaty-orchard-routes-0.3.0` catalog is the active controlled-pilot
  routing release. Its approval sidecar binds the author/legal decision to the
  exact catalog SHA-256; a changed, pending, missing, or differently reviewed
  catalog blocks the worker before registry writes or Gemini calls. The routing
  matrix and its official sources are recorded in
  `docs/COMPETENT_AUTHORITY_ROUTING.md`.
- The `kz-alma-human-response-0.1.0` catalog is the active controlled-pilot
  human-response release. It binds orchard public-interest context and practical
  next steps for all five exact field signal types to an author/legal-editor
  approval. A changed catalog, missing approval, unofficial source, or incomplete
  mapping blocks processing before Gemini is called.
- The worker uses the incident ID and Cloud Storage state to prevent duplicate
  email delivery and Google Sheets rows. A delivered result can restore a
  missing registry row without sending the email again.
- A worker interruption after email delivery starts is quarantined as
  `delivery_uncertain`; it requires manual review and is never resent
  automatically. Configure a Cloud Logging alert for
  `manual review is required`. The durable quarantine lets the watcher record
  the scanned field version instead of failing and downloading the same project
  every minute.
- A model draft containing an unapproved legal reference or a specific authority
  is quarantined as `draft_review_required`. The rejected draft is not stored or
  emailed, and scheduled executions do not call Gemini for that incident again.
  An operator must review the reason and explicitly reset that incident's private
  Cloud Storage state before another attempt. Configure a Cloud Logging alert for
  `Incident draft requires manual review`.
- Legacy `is_sent=1` rows remain readable during migration, but all new runtime
  state is kept outside the field GeoPackage.
- Configure an alert for failed Cloud Run Job executions.
- Apply the field form safeguards to a cloned Mergin project with
  `python scripts/configure_field_project.py /path/to/alma_bot.qgz`, inspect the
  resulting QGIS form, and then synchronise that project through Mergin Maps.
- The recorded source version comes from the downloaded project's own Mergin
  metadata, not from a later server lookup.
- Keep one task and one parallel worker. A Cloud Storage lock stops overlapping
  executions from processing the same Mergin Maps version.
- The production Scheduler polls Mergin Maps every 15 minutes. Cloud Run Jobs
  have a one-minute minimum billable duration, so minute-by-minute polling costs
  about 15 times more while most runs find no new project version. Immediate
  Cloud Run and Scheduler retries are disabled; a transient failure is retried
  by the next scheduled poll. Manual executions remain available for urgent
  checks.
- Update the Gemini model before a published model shutdown date.
- Review generated legal drafts before they are used as official submissions.

## Citizen science publication readiness

See [the readiness note](docs/UN_CITIZEN_SCIENCE_READINESS.md). It defines the
minimum documentation, privacy controls, and quality evidence needed before a
public release.

The public-release workflow and second-lawyer procedure are documented in
[`docs/PUBLIC_RELEASE_GOVERNANCE.md`](docs/PUBLIC_RELEASE_GOVERNANCE.md). The
operational gate is in
[`docs/PUBLIC_RELEASE_CHECKLIST.md`](docs/PUBLIC_RELEASE_CHECKLIST.md).

## Kazakhstan Legal Core

The versioned Kazakhstan Legal Core release candidate is documented in
[`legal_core/README.md`](legal_core/README.md). It contains 122 owner-accepted
cards from `ALMA Legal Review — Kazakhstan v1.2`, their official Adilet links,
a source registry, an author/legal-editor review record, a manifest, and checksums.
The catalog verifies these artifacts and every reviewed card hash before a
citation can be returned.

Yernar Sailybayev approved the reviewed cards as author and legal editor only
for a private controlled pilot. Independent lawyer review remains pending and
public legal release is blocked.

The proposed public overlay reviews only the 32 objects actually used by the
current worker: 18 Legal Core cards, five deterministic mappings, four authority
routes, and five request templates. Its initial records deliberately state
`PUBLIC_LEGAL_RELEASE_BLOCKED`. Editing a legacy card flag cannot unlock it.

The runtime integration uses a separate five-row policy under
`legal_core/policies/kz/0.1.0-rc1/`. The policy remains an immutable proposal
artifact with SHA-256
`dff20191ef26409fa23c1c43130961a9987b081b88b35c79605e94441c4c26b6`.
The separate approval record states that Yernar Sailybayev approved that exact
artifact on 2026-08-12 as author and legal editor for the private controlled
pilot only. Changing the policy invalidates the approval and blocks the worker.
The model receives no article-selection interface. It prepares only the factual
draft; the application validates that the draft contains no legal citations and
then appends exact reviewed cards and official links.

ALMA was initiated and originally designed by Yernar Sailybayev in Almaty,
Kazakhstan.

## Licenses and name

Software and machine-executable configuration are offered under the Apache
License 2.0. Original documentation and educational material are offered under
CC BY 4.0 as described in [`LICENSE-CONTENT.md`](LICENSE-CONTENT.md). Official
laws, government data, third-party material, personal data, and the ALMA name
are outside those grants. See [`NOTICE`](NOTICE) and
[`TRADEMARKS.md`](TRADEMARKS.md).
