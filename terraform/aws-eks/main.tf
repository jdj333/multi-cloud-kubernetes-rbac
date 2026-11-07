terraform {
  required_version = ">= 1.6, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  description = "AWS region containing the existing EKS cluster."
  type        = string
}
variable "cluster_name" {
  description = "Existing EKS cluster with access entries enabled."
  type        = string
}
variable "trusted_role_arn" {
  description = "Exact existing IAM role allowed to assume this reader role. Never an account root or wildcard."
  type        = string
  validation {
    condition     = can(regex("^arn:[a-z-]+:iam::[0-9]{12}:role/[^*]+$", var.trusted_role_arn))
    error_message = "Supply an exact IAM role ARN, without wildcards."
  }
}
variable "role_name" {
  description = "New IAM reader role name; must be unique in this account."
  type        = string
  default     = "eks-team-a-workload-reader"
}

data "aws_eks_cluster" "target" {
  name = var.cluster_name
}

resource "aws_iam_role" "reader" {
  name                 = var.role_name
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { AWS = var.trusted_role_arn }
    }]
  })
}

# Describing one cluster permits kubeconfig discovery, not Kubernetes object access.
resource "aws_iam_role_policy" "discovery" {
  name = "describe-target-cluster"
  role = aws_iam_role.reader.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["eks:DescribeCluster"]
      Resource = data.aws_eks_cluster.target.arn
    }]
  })
}

resource "aws_eks_access_entry" "reader" {
  cluster_name      = var.cluster_name
  principal_arn     = aws_iam_role.reader.arn
  type              = "STANDARD"
  kubernetes_groups = ["platform-readers"]

  lifecycle {
    precondition {
      condition     = contains(["API", "API_AND_CONFIG_MAP"], data.aws_eks_cluster.target.access_config[0].authentication_mode)
      error_message = "The cluster owner must enable EKS access entries before using this example."
    }
  }
}

# No EKS managed access policy: the namespace Role is the authorization boundary.
output "kubernetes_group" {
  value = one(aws_eks_access_entry.reader.kubernetes_groups)
}
output "reader_role_arn" {
  value = aws_iam_role.reader.arn
}
