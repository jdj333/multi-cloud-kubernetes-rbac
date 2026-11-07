# Cloud setup and verification

These Terraform roots configure access to existing sandbox clusters. They do not create clusters, change cluster authentication modes, create users, or manage group membership. Each root has separate state. Run as a platform administrator with permission to read the target cluster and manage the indicated IAM resources. Plan and review before applying.

## AWS EKS

1. The cluster owner enables access entries (`API` or `API_AND_CONFIG_MAP`) in the existing cluster's infrastructure configuration. Preserve bootstrap admin access; authentication-mode transitions have migration constraints.
2. Set `trusted_role_arn` to an exact existing federation role. Terraform creates a new role trusting only that principal, a policy allowing `eks:DescribeCluster` on one cluster ARN, and an EKS access entry mapping that role to `platform-readers`.
3. The source role must be authorized to assume the new reader role. For cross-account access this requires an identity policy in the source account as well as the destination trust policy. This example does not edit the source role or configure your identity provider's MFA/session policy.
4. Apply Terraform and the rendered namespace policy as described in the root README. Do not attach an EKS managed access policy to this reader; those permissions are additive.

Configure a separate AWS profile that assumes the output `reader_role_arn` using your existing SSO/federation source profile. Then:

```bash
export KUBECONFIG="$PWD/build/eks-reader.kubeconfig"
AWS_PROFILE=example-reader aws sts get-caller-identity
AWS_PROFILE=example-reader aws eks update-kubeconfig \
  --region us-west-2 --name example-eks --alias eks-reader
AWS_PROFILE=example-reader python scripts/check_access.py --context eks-reader
```

The profile must resolve to the new reader role when kubectl invokes the AWS token helper. An STS assumed-role session ARN is not a valid `trusted_role_arn` input; use the underlying IAM role ARN.

## Azure AKS

1. Use an existing AKS cluster with managed Microsoft Entra authentication, Kubernetes RBAC enabled, and `azure_rbac_enabled = false`. The Terraform precondition rejects the Azure RBAC for Kubernetes authorization mode. Do not change a live cluster's mode casually to run this demo.
2. Create a dedicated security group through your normal identity administration process. Add the test user. Pass the group's **object ID**, not its display name or application ID. The group must be in the cluster's Entra tenant and must not be the cluster admin group.
3. Terraform assigns `Azure Kubernetes Service Cluster User Role` at the cluster resource scope. This permits user credential retrieval. The namespace Role supplies Kubernetes permissions.
4. Apply the rendered policy with the bootstrap administrator. Use a separate Azure CLI configuration directory to test as the reader; install the Azure `kubelogin` helper.

```bash
export AZURE_CONFIG_DIR="$HOME/.azure-rbac-reader-demo"
export KUBECONFIG="$PWD/build/aks-reader.kubeconfig"
az login --tenant YOUR_TENANT_ID
az account set --subscription YOUR_SUBSCRIPTION_ID
az aks get-credentials --resource-group example-rg --name example-aks --context aks-reader
kubelogin convert-kubeconfig -l azurecli
python scripts/check_access.py --context aks-reader
```

Do not use `az aks get-credentials --admin`: that would test administrator access instead of the reader. Inherited cloud roles, Entra admin group membership, and unrelated Kubernetes bindings must also be reviewed.

## Google GKE

1. A Workspace administrator creates `gke-security-groups@YOUR_DOMAIN` and a dedicated team subgroup such as `platform-readers@YOUR_DOMAIN`, then nests the team group under the umbrella group. Follow Google's group visibility/membership prerequisites in the linked documentation.
2. The cluster owner configures Google Groups for RBAC using the umbrella group. Terraform checks the cluster's `authenticator_groups_config` but does not modify it or verify Workspace membership.
3. Terraform creates a project custom role containing only `container.clusters.get`, then adds a group IAM member. Discovery is **project scoped**, so members can retrieve metadata for other clusters in the project when their names are known. Use a dedicated project if this is too broad. Namespace authorization comes from the shared Role.
4. Render the binding with the **team subgroup email**, not the umbrella group. Use a reader with no project Editor/Owner, `container.viewer`, `container.developer`, or other inherited permissions granting Kubernetes object access. GKE IAM and Kubernetes RBAC grants are additive.

Install `gke-gcloud-auth-plugin` and sign in as the group member in an isolated CLI configuration:

```bash
export CLOUDSDK_CONFIG="$HOME/.gcloud-rbac-reader-demo"
export KUBECONFIG="$PWD/build/gke-reader.kubeconfig"
gcloud auth login
gcloud config set project example-project-id
gcloud container clusters get-credentials example-gke --location us-central1
python scripts/check_access.py \
  --context gke_example-project-id_us-central1_example-gke
```

Groups and credentials can be cached. Allow for propagation, refresh the reader session, and retest revocation. `container.clusters.get` is sufficient for the documented get-credentials route; alternative routes such as Connect Gateway or DNS endpoint access can require additional permissions and are outside this example.

## Troubleshooting

| Failure | Investigate |
| --- | --- |
| Timeout / connection refused | API endpoint network access, VPN, DNS, private cluster routing |
| Unauthorized | Expired cloud session, wrong profile/tenant/account, missing auth helper |
| Intended reads denied | Group mapping, propagation, namespace, roleRef, cluster authentication mode |
| Intended denials unexpectedly allowed | Inherited IAM, extra RoleBindings/ClusterRoleBindings, admin group membership, EKS access policies |
| Impersonation denied | Use the real-identity mode; impersonation is only for an authorized bootstrap test administrator |

## Cleanup

Switch back to the bootstrap administrator's credentials and explicit context. Delete only this demo binding and Role from the sandbox namespace, then run `terraform plan -destroy` and `terraform destroy` separately in the root you applied. Check the plan first: state must contain only this example's resources. Do not delete a namespace containing unrelated workloads. Deleting the EKS access entry or cloud discovery assignment does not revoke every possible grant; review inherited permissions and cached credentials. Group membership lifecycle stays with your identity administrators.

## Evidence to retain

Record cloud, cluster/context, test identity (redacted as needed), date, commit SHA, Terraform plan summary, and output from the real-identity matrix. CI's kind run is evidence of Kubernetes policy behavior; cloud identity integration needs its own result for each provider. This repository does not claim successful live-cloud validation until that evidence exists.
