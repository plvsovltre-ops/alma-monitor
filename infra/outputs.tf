output "artifact_registry_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.alma_monitor.repository_id}"
}

output "monitor_service_account" {
  value = google_service_account.monitor.email
}

output "scheduler_name" {
  value = google_cloud_scheduler_job.monitor.name
}
