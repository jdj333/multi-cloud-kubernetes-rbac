terraform {
  required_version = ">= 1.6, < 2.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

provider "google" {
  project = var.project_id
}

variable "project_id" {
  description = "Project containing the existing GKE cluster."
  type        = string
}
variable "cluster_name" {
  description = "Existing GKE cluster with Google Groups for RBAC enabled."
  type        = string
}
variable "location" {
  description = "Cluster region or zone."
  type        = string
}
variable "reader_group_email" {
  description = "Existing Workspace group nested in gke-security-groups@your-domain."
  type        = string
  validation {
    condition     = can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", var.reader_group_email))
    error_message = "Use the team's Google Workspace group email."
  }
}
variable "security_group_email" {
  description = "Existing umbrella group configured on this GKE cluster."
  type        = string
  validation {
    condition     = can(regex("^gke-security-groups@[^@[:space:]]+\\.[^@[:space:]]+$", var.security_group_email))
    error_message = "The umbrella group must be named gke-security-groups@your-domain."
  }
}
variable "discovery_role_id" {
  description = "Unique project custom role ID, reused only if already managed by this state."
  type        = string
  default     = "gkeRbacClusterDiscovery"
}

data "google_container_cluster" "target" {
  name     = var.cluster_name
  location = var.location
}

# Minimum documented IAM permission for get-credentials. It applies project-wide
# and exposes cluster metadata, but grants no pod/secret/object permissions.
resource "google_project_iam_custom_role" "discovery" {
  project     = var.project_id
  role_id     = var.discovery_role_id
  title       = "GKE RBAC cluster discovery"
  description = "Retrieve cluster connection metadata; object access uses Kubernetes RBAC."
  permissions = ["container.clusters.get"]

  lifecycle {
    precondition {
      condition = try(
        data.google_container_cluster.target.authenticator_groups_config[0].security_group == var.security_group_email,
        false
      )
      error_message = "Cluster Google Groups configuration must match the specified umbrella group."
    }
    precondition {
      condition     = var.reader_group_email != var.security_group_email
      error_message = "Bind the team subgroup, not the umbrella security group."
    }
  }
}

# Additive member resource avoids replacing unrelated IAM bindings.
resource "google_project_iam_member" "discovery" {
  project = var.project_id
  role    = google_project_iam_custom_role.discovery.name
  member  = "group:${var.reader_group_email}"
}

output "kubernetes_group" {
  value = var.reader_group_email
}
