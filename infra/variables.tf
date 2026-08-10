variable "project_id" {
  description = "Google Cloud project ID that hosts ALMA Monitor."
  type        = string
  default     = "alma-monitor-prod-2026"
}

variable "region" {
  description = "Google Cloud region for the Cloud Run Job and its container registry."
  type        = string
  default     = "europe-west1"
}

variable "scheduler_region" {
  description = "Google Cloud region for Cloud Scheduler."
  type        = string
  default     = "europe-west1"
}

variable "image" {
  description = "Container image for ALMA Monitor, stored in Artifact Registry."
  type        = string
}

variable "gemini_model" {
  description = "Primary Gemini model. The application uses a stable fallback if it is unavailable."
  type        = string
  default     = "gemini-3.6-flash"
}

variable "schedule" {
  description = "Unix cron schedule for monitoring Mergin Maps."
  type        = string
  default     = "* * * * *"
}
