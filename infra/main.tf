# Infrastructure as Code for the backend's GCP footprint — Cloud Run service
# + Artifact Registry for its container image. Mirrors the documented
# Cognizant enterprise delivery pattern (IaC-managed cloud resources rather
# than manual console clicks) applied here on GCP's perpetual free tier:
# Cloud Run (2M requests/month free) + Artifact Registry (0.5GB free).
#
# Usage (once you have a GCP project — see infra/README.md for account
# setup, which needs to be done by you, not this script):
#   cd infra
#   terraform init
#   terraform apply -var="project_id=YOUR_PROJECT_ID"

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "frontend_origin" {
  description = "Deployed frontend origin, for backend CORS (set after the first Firebase Hosting deploy)"
  type        = string
  default     = ""
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "run" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifact_registry" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "backend" {
  location      = var.region
  repository_id = "pharma-forecast"
  format        = "DOCKER"
  depends_on    = [google_project_service.artifact_registry]
}

resource "google_cloud_run_v2_service" "backend" {
  name     = "pharma-forecast-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    scaling {
      min_instance_count = 0 # scale to zero — stays in the free tier when idle
      max_instance_count = 2
    }
    containers {
      # Built and pushed by the CI/CD pipeline (.github/workflows/ci-cd.yml);
      # this placeholder tag is only used on the very first `terraform apply`.
      image = "${var.region}-docker.pkg.dev/${var.project_id}/pharma-forecast/api:latest"
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      env {
        name  = "FRONTEND_ORIGIN"
        value = var.frontend_origin
      }
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 2
        period_seconds         = 5
        failure_threshold      = 6
      }
    }
  }

  depends_on = [google_project_service.run]
}

# Public API — unauthenticated invocations allowed (equivalent to Render's
# default). Tighten this with IAM if the API should require auth later.
resource "google_cloud_run_v2_service_iam_member" "public" {
  location = google_cloud_run_v2_service.backend.location
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "backend_url" {
  value = google_cloud_run_v2_service.backend.uri
}
