terraform {
  required_version = ">= 1.6, < 2.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id                 = var.subscription_id
  resource_provider_registrations = "none"
}

variable "subscription_id" {
  description = "Subscription containing the existing AKS cluster."
  type        = string
}
variable "resource_group_name" {
  description = "Resource group containing the existing AKS cluster."
  type        = string
}
variable "cluster_name" {
  description = "Existing AKS cluster using managed Entra authentication and Kubernetes RBAC."
  type        = string
}
variable "reader_group_object_id" {
  description = "Object ID of an existing Entra security group in the cluster's tenant (not display name)."
  type        = string
  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.reader_group_object_id))
    error_message = "Use the Entra group object UUID."
  }
}

data "azurerm_kubernetes_cluster" "target" {
  name                = var.cluster_name
  resource_group_name = var.resource_group_name
}

# This management-plane role permits retrieving a user kubeconfig.
# It is NOT the Azure Kubernetes Service RBAC Reader data-plane role.
resource "azurerm_role_assignment" "cluster_user" {
  scope                = data.azurerm_kubernetes_cluster.target.id
  role_definition_name = "Azure Kubernetes Service Cluster User Role"
  principal_id         = var.reader_group_object_id
  principal_type       = "Group"

  lifecycle {
    precondition {
      condition = try(
        data.azurerm_kubernetes_cluster.target.azure_active_directory_role_based_access_control[0].azure_rbac_enabled == false,
        false
      )
      error_message = "This example requires Entra authentication with Kubernetes RBAC, not Azure RBAC for Kubernetes."
    }
    precondition {
      condition     = data.azurerm_kubernetes_cluster.target.role_based_access_control_enabled
      error_message = "Kubernetes RBAC must be enabled."
    }
  }
}

output "kubernetes_group" {
  value = var.reader_group_object_id
}
