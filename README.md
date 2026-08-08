# ShopFlow — Microservices E-commerce Platform with Full DevOps Lifecycle

A production-style microservices application deployed to Kubernetes through a complete
GitOps pipeline — from infrastructure provisioning to automated deployment with HTTPS.

> **This project is about the DevOps, not the app.** The application itself is intentionally
> simple; the value is in the end-to-end delivery pipeline built around it.

**Live demo:** `https://ecommerce-shop.duckdns.org` (HTTPS via Let's Encrypt)

---

## Architecture

```
                                 ┌─────────────┐
                Developer  ──────▶│   GitHub    │  (single source of truth)
                 git push         └──────┬──────┘
                                         │
                 ┌───────────────────────┼───────────────────────┐
                 │ CI: GitHub Actions    │  CD: ArgoCD (GitOps)   │
                 │ matrix build → ghcr.io│  git → cluster         │
                 └───────────────────────┼───────────────────────┘
                                         ▼
                          ┌──────────────────────────┐
                          │  Kubernetes (k3s) cluster │
                          │  Hetzner Cloud            │
                          │                           │
   Internet ──▶ Traefik ──┤  frontend (nginx)         │
   HTTPS/TLS   (Ingress)  │     │                     │
                          │     ├─▶ catalog ─▶ Postgres (StatefulSet + PVC)
                          │     ├─▶ cart    ─▶ Redis
                          │     └─▶ orders  ─▶ RabbitMQ ─▶ worker
                          │                           │
                          │  Observability:           │
                          │  Prometheus + Grafana     │
                          └──────────────────────────┘
```

The whole platform is reproducible from code: `terraform apply` + `ansible-playbook`
brings up an identical server with k3s, ArgoCD, cert-manager and Sealed Secrets;
ArgoCD then deploys the application straight from this git repository.

---

## Tech Stack

| Layer | Tools |
|-------|-------|
| **Application** | React (frontend), catalog / cart / orders / worker (microservices) |
| **Data** | PostgreSQL, Redis, RabbitMQ |
| **Containerization** | Docker (multi-stage builds), Docker Compose (local) |
| **Infrastructure as Code** | Terraform (Hetzner Cloud provisioning) |
| **Configuration Management** | Ansible (server hardening, k3s, controllers) |
| **Orchestration** | Kubernetes (k3s), StatefulSets, PVC, Ingress |
| **CI** | GitHub Actions (matrix build → ghcr.io) |
| **CD / GitOps** | ArgoCD (automated sync, prune, self-heal) |
| **Secrets** | Sealed Secrets (encrypted secrets in git) |
| **TLS** | cert-manager + Let's Encrypt (HTTP-01) |
| **Observability** | Prometheus, Grafana |
| **Security** | ufw firewall, fail2ban, SSH key-only auth |

---

## What's Implemented

**Infrastructure as Code**
- Terraform provisions the server, SSH key and networking on Hetzner Cloud.
- Server is disposable: `terraform destroy` / `apply` recreates it in ~2 minutes.

**Configuration Management (Ansible)**
- Server hardening first: `ufw` (only required ports incl. k3s 6443 / Flannel 8472), `fail2ban`, unattended-upgrades.
- Installs k3s, ArgoCD, cert-manager, Sealed Secrets controller and prometheus-operator CRDs — idempotently.

**CI/CD**
- GitHub Actions builds all service images in parallel via a **matrix strategy** and pushes to `ghcr.io`.
- ArgoCD watches this repo and deploys manifests automatically (GitOps) — no manual `kubectl apply`.

**Kubernetes**
- Stateless services (frontend, catalog, cart, orders, worker) as Deployments.
- Stateful services (PostgreSQL, RabbitMQ) as StatefulSets with PersistentVolumeClaims.
- Traefik Ingress with automatic Let's Encrypt TLS.

**Secrets (GitOps-safe)**
- Application/DB secrets are encrypted with Sealed Secrets and committed to git;
  only the cluster can decrypt them. Plain secrets never touch the repository.

**Observability**
- kube-prometheus-stack (Prometheus + Grafana) deployed via ArgoCD + Helm, tuned to fit
  the resource budget (reduced retention and memory limits).

---

## Repository Structure

```
ecommerce-platform/
├── apps/           # application source (frontend, catalog, cart, orders, worker)
├── infra/
│   ├── terraform/  # Hetzner server provisioning
│   └── ansible/    # server hardening + k3s + controllers
├── k8s/            # Kubernetes manifests (Deployments, StatefulSets, Services, Ingress, SealedSecrets)
├── argocd/         # ArgoCD Application definitions (GitOps)
└── .github/workflows/  # CI pipeline (matrix build → ghcr.io)
```

---

## How to Deploy

```bash
# 1. Provision the server
cd infra/terraform
terraform init && terraform apply

# 2. Configure it (hardening + k3s + ArgoCD + cert-manager + sealed-secrets)
cd ../ansible
ansible-playbook playbook.yml

# 3. Deploy the app via GitOps
kubectl apply -f argocd/application.yaml
# ArgoCD syncs everything from git automatically
```

---

## Notes & Trade-offs

Engineering decisions made consciously for a learning/budget environment:

- **Shared PostgreSQL** between catalog and orders (separate tables) instead of database-per-service —
  a deliberate resource trade-off; production would use a DB per service.
- **Monitoring tuned down** (retention, memory limits) to fit a 4 GB node — real-world
  "observability on a budget"; a production node would be larger.
- Image tag `latest` for simplicity — production would pin by git SHA.
