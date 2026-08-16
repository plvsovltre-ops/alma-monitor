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

variable "release_mode" {
  description = "Legal release gate. Public mode remains fail-closed until both exact reviews are approved."
  type        = string
  default     = "controlled_pilot"

  validation {
    condition     = contains(["controlled_pilot", "public_legal_release"], var.release_mode)
    error_message = "release_mode must be controlled_pilot or public_legal_release."
  }
}

variable "schedule" {
  description = "Low-cost cron schedule for monitoring Mergin Maps. Fifteen minutes leaves Cloud Run free-tier headroom for manual executions."
  type        = string
  default     = "*/15 * * * *"
}
