# Multi-cloud Kubernetes RBAC

[![RBAC checks](https://github.com/jdj333/multi-cloud-kubernetes-rbac/actions/workflows/ci.yml/badge.svg)](https://github.com/jdj333/multi-cloud-kubernetes-rbac/actions/workflows/ci.yml)

One namespace access policy across **AWS EKS, Azure AKS, and Google GKE**. This project demonstrates how cloud identity authentication connects to Kubernetes authorization, and how to prove both allowed and rejected operations.

The example gives an operations team read access to workloads and logs in `team-a`. Terraform configures the cloud identity bridge against an **existing cluster**. Shared Kubernetes manifests define the permissions. A local kind cluster exercises the policy without cloud credentials or cloud infrastructure costs.

## Identity model

| Platform | Authentication / discovery | RoleBinding group |
| --- | --- | --- |
| EKS | Assumed IAM role, cluster-scoped `eks:DescribeCluster`, EKS STANDARD access entry | `platform-readers` |
| AKS | Managed Microsoft Entra sign-in, AKS Cluster User management-plane role | Entra group object UUID |
| GKE | Google user sign-in, Google Groups for RBAC, custom IAM discovery role | Team Google Workspace group email |

Each path ends at a namespace `RoleBinding` referencing the same `workload-reader` **Role**. The AKS example uses Kubernetes RBAC authorization; Azure RBAC for Kubernetes is a different model. This project covers human access to the Kubernetes API. Pod access to AWS, Azure, or Google APIs requires a separate workload identity design.

## Permission contract

| Operation | `team-a` | Other namespaces / cluster scope |
| --- | --- | --- |
| Get/list/watch pods, services, events, deployments, replicasets | Allow | Deny |
| Read pod logs | Allow | Deny |
| Read/list secrets | Deny | Deny |
| Execute in pods, port-forward, mint service account tokens | Deny | Deny |
| Create, patch, or delete workloads | Deny | Deny |
| Change RBAC, bind/escalate roles, impersonate users | Deny | Deny |
| List nodes, namespaces, or all namespaces' pods | N/A | Deny |

Kubernetes RBAC is additive: a missing grant is not an explicit deny. Other RoleBindings, EKS access policies, or GKE IAM permissions can broaden effective access. Use a dedicated test identity without unrelated grants. Log access is still sensitive because applications may log confidential data.

## Run the local demonstration

Prerequisites: Python 3.10+, Docker, [kind](https://kind.sigs.k8s.io/docs/user/quick-start/), and kubectl compatible with the test cluster.

```bash
git clone https://github.com/jdj333/multi-cloud-kubernetes-rbac.git
cd multi-cloud-kubernetes-rbac
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
make test
make demo
```

`make demo` creates a dedicated cluster named `rbac-demo`, applies the Role and binding, creates an unbound `team-b` namespace, and runs the tests using admin-authorized impersonation. The test suite performs **25 authorization checks, three real API reads, and one unbound-identity check**. A genuine forbidden response passes a denial test; a connection failure or authentication error fails it. Expected terminal result: `Result: 0 failure(s). Mode: impersonation.`

```bash
make clean-demo  # deletes only the local rbac-demo cluster
```

## Use a cloud example

See [the cloud setup guide](docs/cloud-setup.md) for provider prerequisites and real-user login commands. Use a disposable sandbox cluster with a separate bootstrap administrator.

```bash
# Choose aws-eks, azure-aks, or google-gke.
cd terraform/aws-eks
cp terraform.tfvars.example terraform.tfvars
# Edit the example values for your own sandbox.
terraform init
terraform plan -out=access.tfplan
terraform apply access.tfplan
cd ../..

mkdir -p build
python scripts/render.py \
  --group "$(terraform -chdir=terraform/aws-eks output -raw kubernetes_group)" \
  > build/rbac.yaml

# Use your bootstrap administrator context for this one-time configuration.
kubectl --context YOUR_SANDBOX_ADMIN_CONTEXT apply -f build/rbac.yaml
```

After signing in as the reader, run the same matrix **without impersonation**:

```bash
python scripts/check_access.py --context YOUR_SANDBOX_READER_CONTEXT
```

For cloud tests, the bootstrap administrator should create an empty `team-b` namespace first. Keep admin and reader kubeconfigs separate. Do not grant the reader impersonation rights just to make tests pass. The test script requires an explicit context and never applies resources or changes permissions.

## Repository map

| Path | Purpose |
| --- | --- |
| `terraform/aws-eks/` | Narrow IAM trust, discovery permission, EKS access entry |
| `terraform/azure-aks/` | Entra group assignment and AKS authorization-mode checks |
| `terraform/google-gke/` | Minimal discovery IAM role and Google Groups configuration check |
| `kubernetes/` | Namespace, Role, and local Group RoleBinding |
| `scripts/render.py` | YAML-safe rendering for a cloud group and namespace |
| `scripts/check_access.py` | Live authorization matrix and resource endpoint checks |
| `tests/` | Safety invariants and permission matrix |
| `.github/workflows/ci.yml` | Terraform validation and live kind tests on pull requests |

## Verification boundaries

Offline Python checks validate policy safety and fail-closed test behavior. CI validates each Terraform provider schema and exercises real Kubernetes RBAC on kind. Neither kind nor `terraform validate` proves cloud login, tenant group membership, inherited IAM permissions, network reachability, or production readiness. Run the real-identity test in each cloud before claiming end-to-end validation. No cloud resources are deployed by CI.

Terraform state may contain sensitive cluster information, including kubeconfig material returned by provider data sources. State, plans, local variables, kubeconfigs, and generated output are ignored. Use encrypted remote state with restricted access for shared environments. Provider lock files are committed; review dependency updates before applying.

## Design decisions to discuss

* Why namespace Roles and group bindings reduce access scope and simplify joiner/leaver workflows.
* Why an IAM identity, a cluster discovery permission, and a Kubernetes Role solve different problems.
* Why negative tests and actual API responses matter as much as successful reads.
* Why this reader has no workload write access: workload creation can indirectly access secrets or stronger service accounts.
* How additive grants and cached group membership complicate revocation and verification.

## References

* [Kubernetes RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
* [Kubernetes RBAC security practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/)
* [EKS access entries with Kubernetes groups](https://docs.aws.amazon.com/eks/latest/userguide/create-k8s-group-access-entry.html)
* [Microsoft Entra authentication with Kubernetes RBAC on AKS](https://learn.microsoft.com/en-us/azure/aks/kubernetes-rbac-entra-id)
* [Google Groups for GKE RBAC](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/google-groups-rbac)
* [GKE RBAC and minimum IAM permissions](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/role-based-access-control)

Maintained by [James Jenkins](https://github.com/jdj333).
