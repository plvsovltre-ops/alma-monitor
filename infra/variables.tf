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

variable "mail_from" {
  description = "Approved public sender address displayed to ALMA volunteers."
  type        = string
  default     = "monitor@alma.eco"

  validation {
    condition     = lower(var.mail_from) == "monitor@alma.eco"
    error_message = "mail_from must remain monitor@alma.eco."
  }
}

variable "mail_from_name" {
  description = "Human-readable sender name displayed to ALMA volunteers."
  type        = string
  default     = "ALMA Monitor"
}

variable "smtp_host" {
  description = "Verified SMTP2GO endpoint used for ALMA delivery."
  type        = string
  default     = "mail-eu.smtp2go.com"

  validation {
    condition     = lower(var.smtp_host) == "mail-eu.smtp2go.com"
    error_message = "smtp_host must remain mail-eu.smtp2go.com."
  }
}

variable "smtp_port" {
  description = "SMTP submission port used with STARTTLS."
  type        = number
  default     = 587

  validation {
    condition     = var.smtp_port == 587
    error_message = "smtp_port must remain the approved STARTTLS port 587."
  }
}

variable "schedule" {
  description = "Low-cost cron schedule for monitoring Mergin Maps. Fifteen minutes leaves Cloud Run free-tier headroom for manual executions."
  type        = string
  default     = "*/15 * * * *"
}
