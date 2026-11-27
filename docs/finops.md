# FinOps guide (docs/finops.md)

Goal: finish the project without running out of Learner Lab budget. This file is the reference for issues S1-M02 (billing alert), S2-M07 (`make up` / `make down`) and S7-M05 (final cleanup).

## 1. The golden rules

1. Never leave a session without running `make down` and the verification commands (section 5).
2. Test cheap things in cheap places first (section 3, the testing ladder).
3. Create nothing by hand in the console. If it is not in Terraform or Git, we will forget to delete it.
4. Check the budget meter on the Learner Lab page at the start and the end of every session. Write the number in the team chat.
5. One cluster per person at a time. Never leave a cluster running overnight.

## 2. What costs money

Approximate on-demand prices from memory (us-east-1). Check the current AWS pricing pages before relying on them.

| Resource | About | Note |
|---|---|---|
| EKS control plane | $0.10/h | $0.60/h if the Kubernetes version is in extended support: always use a STANDARD_SUPPORT version |
| 2 x t3.medium nodes | about $0.08/h total | |
| Jenkins t3.small | about $0.02/h | |
| Load balancer (Service type LoadBalancer) | about $0.03/h | Created by Kubernetes, NOT by Terraform: easy to forget |
| EBS volumes (Prometheus, Grafana) | cents per day | Created by PVCs, NOT by Terraform: easy to forget |
| DynamoDB (on-demand), Lambda, SNS, one alarm, S3, ECR | cents | At our scale these are almost free |
| NAT Gateway | about $35/month | We do NOT use one (public subnets) |

Rough total while everything runs: about $0.25 per hour, so about $1 for a 4-hour session. The real danger is forgetting resources, not the hourly rate.

## 3. The testing ladder (cheapest first)

Always climb from the bottom. Only go up when the lower step works.

| Step | Where | What to test there | Cost |
|---|---|---|---|
| 1 | Your laptop | `terraform fmt`, `validate`, `plan`; reading and editing manifests; `kubectl kustomize k8s/`; Lambda code with sample events (`lambda/events/`); Jenkinsfile syntax review | free |
| 2 | Local Kubernetes on your laptop (kind, minikube or Docker Desktop) | Manifests, kustomize patches, probes, HPA logic, Helm charts, PrometheusRule syntax | free |
| 3 | AWS Academy Cloud Foundations Sandbox | Network module (VPC, subnets, IGW), Jenkins EC2 (user-data, Docker, Trivy, webhook, Jenkins configuration as code), CloudWatch alarm, SNS, Lambda writing to S3 | sandbox is wiped when the timer ends |
| 4 | Learner Lab | Everything that needs EKS, ECR, EBS gp3, the load balancer or the DynamoDB cart: the real thing | our real budget |

### What the sandbox can and cannot do

From the sandbox instructions:

- Allowed: EC2 (t2/t3 up to t3.medium, gp2 volumes up to 35 GB, maximum 9 running instances), Elastic Load Balancing, Lambda (use LabRole), SNS, CloudWatch, S3, SSM, CloudFormation, read-only IAM.
- Same names as Learner Lab: `LabRole` and `LabInstanceProfile`.
- NOT listed: EKS, ECR, DynamoDB. So the cluster, image push and cart tests must happen in Learner Lab.
- Everything is deleted when the session timer reaches 0:00.
- Open question: we do not know whether the sandbox has a separate budget from Learner Lab. Check the budget meter in both before relying on it.

### Using the sandbox

1. Start the lab and open the browser VS Code (the LabIDEURL shown under Details). Its terminal already has AWS credentials: run `aws sts get-caller-identity`.
2. Clone the repo, run `make bootstrap` (the state bucket is wiped each session, so the script must be safe to re-run).
3. Apply only the modules the sandbox supports (network, jenkins, alerting without DynamoDB). Destroy at the end even though it will be wiped anyway: it keeps the habit.
4. For the Lambda test in the sandbox, enable the "skip DynamoDB" flag (an environment variable). Remove the flag when testing in Learner Lab.

### Notes on local testing

- A local cluster can run the shop and kube-prometheus-stack only if the laptop has enough memory (several GB free). If not, test pieces separately.
- LocalStack (free tier) can imitate S3, SNS, Lambda and DynamoDB on a laptop. Check its coverage page before depending on it.

## 4. Session routine (Learner Lab)

Before:
1. Start the lab, copy the credentials (access key, secret, session token) into `~/.aws/credentials`.
2. Run `aws sts get-caller-identity` and check the budget meter. Post the amount in the team chat.
3. Know your goal for the session (one or two issues). Do not start a session "to see what happens".

During:
4. `make up` (cluster creation takes 10-15 minutes: prepare the next task meanwhile).
5. Work on the planned issues. Commit often.
6. Every hour, check `kubectl top nodes` and the budget meter.

After (at least 15 minutes before the timer ends):
7. Evidence first: take screenshots, export dashboards, commit your work.
8. `make down`.
9. Run the verification commands (section 5) and confirm they are all empty.
10. Check the budget meter again and post it in the team chat.

## 5. Cleanup order and verification

Order matters. Kubernetes creates AWS resources that Terraform does not know about (load balancers from Services, EBS volumes from PVCs). Delete them first or `terraform destroy` can hang on the VPC and the resources keep billing.

```bash
kubectl delete svc --all -n retail
helm uninstall monitoring -n monitoring
kubectl delete pvc --all -n monitoring
# wait until no load balancer remains, then:
cd terraform/envs/lab && terraform destroy -auto-approve
```

`make down` runs this for you through `scripts/cleanup.sh` (issue S2-M07).

Verification (every command must return an empty result):

```bash
aws eks list-clusters --query clusters
aws elb describe-load-balancers --query 'LoadBalancerDescriptions[].LoadBalancerName'
aws elbv2 describe-load-balancers --query 'LoadBalancers[].LoadBalancerName'
aws ec2 describe-instances --filters Name=instance-state-name,Values=running,pending --query 'Reservations[].Instances[].InstanceId'
aws ec2 describe-volumes --filters Name=status,Values=available --query 'Volumes[].VolumeId'
aws ec2 describe-nat-gateways --filter Name=state,Values=available --query 'NatGateways[].NatGatewayId'
aws ecr describe-repositories --query 'repositories[].repositoryName'
```

Left on purpose: the Terraform state bucket and the lock table (a few cents). Delete them only at the very end of the course.

## 6. Billing alert

Issue S1-M02 asks for a $10 AWS Budget with an email alert.

- Try it with the console (Billing, Budgets) or `aws budgets create-budget`.
- If AWS Budgets is blocked in Learner Lab (AccessDenied), do not fight it. Save a screenshot of the error in `docs/finops/`, rely on the Learner Lab budget meter, and tell the professor.

## 7. Advice we decided NOT to follow

"Use tiny VMs and configure everything by hand, avoid AWS services."

- The rubric requires EKS, ECR, DynamoDB, CloudWatch, SNS and Lambda.
- Manual configuration loses the Infrastructure as Code marks and our reproducibility.
- The managed services we use (DynamoDB on-demand, Lambda, SNS, S3, one alarm) cost cents at our scale.
- The big costs are the cluster and forgotten resources, and `make down` plus verification handles both.

## 8. Quick checklist (copy into each session)

- [ ] Credentials copied, `aws sts get-caller-identity` works
- [ ] Budget meter checked and posted
- [ ] Goal for this session written down
- [ ] Evidence (screenshots, exports) committed before cleanup
- [ ] `make down` done
- [ ] Verification commands all empty
- [ ] Budget meter checked again and posted