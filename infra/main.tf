locals {
  required_apis = toset([
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudscheduler.googleapis.com",
    "logging.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
  ])

  runtime_secrets = toset([
    "MERGIN_USER",
    "MERGIN_PASS",
    "GMAIL_USER",
    "GMAIL_APP_PASS",
    "GEMINI_API_KEY",
    "GOOGLE_CREDENTIALS_JSON",
  ])
}

resource "google_project_service" "required" {
  for_each = local.required_apis

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "alma_monitor" {
  project       = var.project_id
  location      = var.region
  repository_id = "alma-monitor"
  description   = "Container images for ALMA Monitor"
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

resource "google_service_account" "monitor" {
  project      = var.project_id
  account_id   = "alma-monitor"
  display_name = "ALMA Monitor Cloud Run Job"
}

resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = "alma-monitor-scheduler"
  display_name = "ALMA Monitor Cloud Scheduler"
}

# Terraform creates only empty secret containers. Add secret values in Google
# Cloud Console or with gcloud. This keeps secret values out of Git and state.
resource "google_secret_manager_secret" "runtime" {
  for_each = local.runtime_secrets

  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "monitor_access" {
  for_each = local.runtime_secrets

  project   = var.project_id
  secret_id = google_secret_manager_secret.runtime[each.value].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.monitor.email}"
}

resource "google_cloud_run_v2_job" "monitor" {
  name                = "alma-monitor"
  location            = var.region
  deletion_protection = true

  template {
    task_count = 1
    parallelism = 1

    template {
      service_account = google_service_account.monitor.email
      timeout         = "840s"
      # Two 14-minute attempts fit inside the 30-minute schedule interval.
      # This prevents two job executions from editing the same Mergin project.
      max_retries     = 1

      containers {
        image = var.image

        resources {
          limits = {
            cpu    = "1"
            memory = "2Gi"
          }
        }

        env {
          name  = "GEMINI_MODEL"
          value = var.gemini_model
        }

        env {
          name  = "LOG_LEVEL"
          value = "INFO"
        }

        dynamic "env" {
          for_each = local.runtime_secrets
          content {
            name = env.value
            value_source {
              secret_key_ref {
                secret  = google_secret_manager_secret.runtime[env.value].secret_id
                version = "latest"
              }
            }
          }
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_iam_member.monitor_access]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_job.monitor.location
  name     = google_cloud_run_v2_job.monitor.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "monitor" {
  project          = var.project_id
  region           = var.scheduler_region
  name             = "alma-monitor-every-30-minutes"
  description      = "Runs ALMA Monitor without a personal computer"
  schedule         = var.schedule
  time_zone        = "Asia/Almaty"
  attempt_deadline = "600s"

  retry_config {
    retry_count = 2
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.monitor.name}:run"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode("{}")

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_invoker]
}
