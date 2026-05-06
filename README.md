# Supply Chain Security Pipeline

![Pipeline](https://github.com/Haseef-Ahamed/supply-chain-pipeline/actions/workflows/pipeline.yml/badge.svg)
![Security](https://img.shields.io/badge/security-Trivy%20%2B%20Cosign-blue)
![Kubernetes](https://img.shields.io/badge/kubernetes-k3d-blue)
![Platform](https://img.shields.io/badge/platform-fully%20local-orange)

A fully automated, locally hosted software supply chain security pipeline.
Every code push triggers a 6-job CI/CD pipeline that builds, scans,
signs, verifies, and deploys a containerized FastAPI application —
ensuring only trusted, vulnerability-free images reach Kubernetes.

---

## Table of Contents

- [Overview](#overview)
- [The Problem This Solves](#the-problem-this-solves)
- [Objectives](#objectives)
- [Architecture](#architecture)
- [Tools Used](#tools-used)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Local Environment Setup](#local-environment-setup)
- [GitHub Configuration](#github-configuration)
- [Running the Pipeline](#running-the-pipeline)
- [Security Scanning — Trivy](#security-scanning--trivy)
- [Image Signing and Verification — Cosign](#image-signing-and-verification--cosign)
- [Deployment to Kubernetes](#deployment-to-kubernetes)
- [Demonstrating Blocked Deployments](#demonstrating-blocked-deployments)
- [Testing Commands](#testing-commands)
- [Troubleshooting](#troubleshooting)
- [Future Improvements](#future-improvements)
- [License](#license)

---

## Overview

This project implements a complete software supply chain security pipeline
running fully locally on a single machine. It uses GitHub for source control,
GitHub Actions with a self-hosted runner for CI/CD, GitHub Container Registry
(ghcr.io) for image storage, Trivy for vulnerability and IaC scanning,
Cosign for cryptographic image signing, and k3d (local Kubernetes) for
deployment.

The pipeline enforces four sequential security gates on every code push.
No image reaches the Kubernetes cluster without passing all four gates.

---

## The Problem This Solves

In 2020, the SolarWinds attack compromised thousands of organisations by
injecting malicious code into a software build process. Nobody checked
whether the deployed software was the same as what was built.

This project addresses that exact gap:

```
WITHOUT supply chain security:
  Code pushed → Image built → Deployed (no checks, no trust)

WITH this pipeline:
  Code pushed
    → Gate 1: Trivy scans for CVE vulnerabilities
    → Gate 2: Trivy scans Kubernetes YAML for misconfigurations
    → Gate 3: Cosign signs the image cryptographically
    → Gate 4: Cosign verifies the signature
    → Only then: deployed to Kubernetes
```

---

## Objectives

- Implement a secure CI/CD pipeline using GitHub Actions
- Perform container vulnerability scanning with Trivy
- Scan Infrastructure as Code (Kubernetes YAML) for misconfigurations
- Sign container images cryptographically using Cosign
- Verify image signatures before every deployment
- Block any deployment that fails a security check
- Run the entire system fully locally with no cloud Kubernetes

---

## Architecture

### Pipeline Flow

```
Developer (git push)
        |
        v
GitHub Repository
        |
        | triggers
        v
GitHub Actions (self-hosted runner on laptop)
        |
        |----> Job 1: Build Image
        |         Build Docker image
        |         Push to ghcr.io with commit SHA tag
        |
        |----> Job 2: Scan Image (Gate 1)
        |         Trivy scans image for CVE vulnerabilities
        |         BLOCKS if CRITICAL CVEs found
        |
        |----> Job 3: Scan IaC (Gate 2)
        |         Trivy scans k8s/ YAML files
        |         BLOCKS if CRITICAL/HIGH misconfigs found
        |
        |----> Job 4: Sign Image (Gate 3)
        |         Cosign signs image with private key
        |         Signature stored in ghcr.io
        |
        |----> Job 5: Verify Signature (Gate 4)
        |         Cosign verifies signature with public key
        |         BLOCKS if signature invalid or missing
        |
        |----> Job 6: Deploy to Kubernetes
                  kubectl apply -f k8s/
                  App running at localhost:30080
```

### Security Gates

| Gate | Tool | Checks | Blocks On |
|------|------|--------|-----------|
| Gate 1 | Trivy | Docker image CVEs | CRITICAL vulnerabilities |
| Gate 2 | Trivy | Kubernetes YAML | CRITICAL/HIGH misconfigs |
| Gate 3 | Cosign | Image signing | Key unavailable |
| Gate 4 | Cosign | Signature verify | Invalid/missing signature |

### Port Map

| Service | Port | URL |
|---------|------|-----|
| GitHub Actions Runner | — | self-hosted on laptop |
| ghcr.io registry | 443 | ghcr.io/haseef-ahamed/hsf-app |
| k3d Kubernetes | — | kubectl context: k3d-mycluster |
| FastAPI app | 30080 | http://localhost:30080 |

---

## Tools Used

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | 24.x | Containerize the application |
| k3d / k3s | 5.x | Local Kubernetes cluster |
| GitHub | — | Source code repository |
| GitHub Actions | — | CI/CD automation (self-hosted runner) |
| ghcr.io | — | Container image registry |
| Trivy | 0.5x | Vulnerability and IaC scanner |
| Cosign | 2.x | Image signing and verification |
| kubectl | 1.2x | Kubernetes CLI |
| FastAPI | 0.109 | Sample application |
| Python | 3.11 | Application runtime |

---

## Project Structure

```
supply-chain-pipeline/
|
|-- app/
|   |-- main.py               # FastAPI application
|   +-- requirements.txt      # Pinned Python dependencies
|
|-- .github/
|   +-- workflows/
|       +-- pipeline.yml      # 6-job CI/CD pipeline definition
|
|-- k8s/
|   |-- namespace.yaml        # Kubernetes namespace
|   |-- deployment.yaml       # App deployment with security context
|   +-- service.yaml          # NodePort service on port 30080
|
|-- security/
|   |-- cosign.pub            # Public key for verification
|   +-- trivy-report.json     # Generated vulnerability scan report
|
|-- docs/
|   |-- overview.md
|   |-- architecture.md
|   |-- pipeline-details.md
|   |-- security-scan-and-signing.md
|   |-- setup-guide.md
|   +-- demo-guide.md
|
|-- Dockerfile                # python:3.11-slim, non-root user
|-- .gitignore                # Excludes cosign.key
+-- README.md                 # This file
```

---

## Prerequisites

Install these tools before starting:

```bash
# Docker
sudo apt install -y docker.io
sudo usermod -aG docker $USER

# k3d
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -Ls \
  https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/

# Trivy
sudo apt install -y wget apt-transport-https gnupg
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key \
  | sudo apt-key add -
echo "deb https://aquasecurity.github.io/trivy-repo/deb generic main" \
  | sudo tee /etc/apt/sources.list.d/trivy.list
sudo apt update && sudo apt install -y trivy

# Cosign
COSIGN_VERSION=$(curl -s \
  https://api.github.com/repos/sigstore/cosign/releases/latest \
  | grep tag_name | cut -d '"' -f 4)
curl -Lo cosign \
  "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign-linux-amd64"
chmod +x cosign && sudo mv cosign /usr/local/bin/
```

Verify all tools:

```bash
docker --version && k3d --version && kubectl version --client && \
trivy --version | head -1 && cosign version 2>/dev/null | grep GitVersion
```

---

## Local Environment Setup

### Step 1 — Create Kubernetes Cluster

```bash
k3d cluster create mycluster \
  --port "30080:30080@loadbalancer" \
  --agents 1

kubectl get nodes
# Both nodes must show Ready
```

### Step 2 — Clone Repository

```bash
git clone https://github.com/Haseef-Ahamed/supply-chain-pipeline.git
cd supply-chain-pipeline
```

### Step 3 — Generate Cosign Key Pair

```bash
cd ~
cosign generate-key-pair
# Creates cosign.key (private) and cosign.pub (public)
# NEVER commit cosign.key
```

### Step 4 — Start the Self-Hosted Runner

```bash
cd ~/actions-runner
./run.sh
# Must show: Listening for Jobs
```

---

## GitHub Configuration

### Repository Secrets

Go to: Settings → Secrets and variables → Actions

| Secret Name | Value |
|-------------|-------|
| `COSIGN_KEY` | Contents of `~/cosign.key` |
| `COSIGN_PASSWORD` | Password chosen during key generation |

### Workflow Permissions

Go to: Settings → Actions → General → Workflow permissions

Select: **Read and write permissions**

---

## Running the Pipeline

Push any commit to the `main` branch:

```bash
git add .
git commit -m "your message"
git push origin main
```

Monitor at:
```
https://github.com/Haseef-Ahamed/supply-chain-pipeline/actions
```

### Pipeline Jobs

| Job | Name | Depends On | Purpose |
|-----|------|------------|---------|
| 1 | Build Image | — | Build and push Docker image |
| 2 | Scan Image Gate 1 | Job 1 | Trivy CVE scan |
| 3 | Scan IaC Gate 2 | Job 2 | Trivy config scan |
| 4 | Sign Image Gate 3 | Job 3 | Cosign sign |
| 5 | Verify Signature Gate 4 | Job 4 | Cosign verify |
| 6 | Deploy to Kubernetes | Job 5 | kubectl apply |

---

## Security Scanning — Trivy

### Image Scan (Gate 1)

Trivy checks every OS package and Python library inside the
Docker image against the CVE vulnerability database.

```bash
# Run manually
trivy image \
  --severity CRITICAL,HIGH \
  --ignore-unfixed \
  ghcr.io/haseef-ahamed/hsf-app:latest
```

Pipeline behavior:
- CRITICAL found → pipeline fails, image blocked
- No CRITICAL → pipeline continues

### IaC Scan (Gate 2)

Trivy reads Kubernetes YAML files and checks for dangerous
misconfigurations such as running as root, missing resource
limits, or allowing privilege escalation.

```bash
# Run manually
trivy config --severity CRITICAL,HIGH ./k8s/
```

### Reading the Scan Report

```bash
cat security/trivy-report.json | python3 -m json.tool | head -50
```

Severity levels:
- **CRITICAL** — blocks pipeline immediately
- **HIGH** — blocks IaC scan, reported for image scan
- **MEDIUM/LOW** — reported only, pipeline continues

---

## Image Signing and Verification — Cosign

### How It Works

```
Key generation (once):
  cosign generate-key-pair
    cosign.key  → stored as GitHub Secret (never committed)
    cosign.pub  → committed to security/cosign.pub

Pipeline signing (Gate 3):
  cosign sign --key cosign.key <image>
    → signature stored in ghcr.io alongside image

Verification (Gate 4):
  cosign verify --key cosign.pub <image>
    → mathematically confirms image is authentic
    → confirms image was not modified after signing
```

### Verify an Image Manually

```bash
# Pipeline-built image — PASSES
cosign verify \
  --key security/cosign.pub \
  ghcr.io/haseef-ahamed/hsf-app:latest

# Manually pushed image — FAILS
cosign verify \
  --key security/cosign.pub \
  ghcr.io/haseef-ahamed/hsf-app:unsigned
```

---

## Deployment to Kubernetes

### Automatic (via Pipeline)

The pipeline runs `kubectl apply -f k8s/` automatically
after all 4 security gates pass.

### Manual Verification After Deploy

```bash
kubectl get all -n supply-chain-demo
kubectl get pods -n supply-chain-demo
kubectl logs -l app=hsf-app -n supply-chain-demo
curl http://localhost:30080/health
curl http://localhost:30080/
curl http://localhost:30080/info
```

---

## Demonstrating Blocked Deployments

### Demo 1 — Gate 1 Blocks Vulnerable Image

```bash
sed -i "s|FROM python:3.11-slim|FROM python:3.8|g" Dockerfile
git add Dockerfile
git commit -m "demo: Gate 1 block — vulnerable image"
git push origin main

# Revert after demo
sed -i "s|FROM python:3.8|FROM python:3.11-slim|g" Dockerfile
git add Dockerfile
git commit -m "fix: revert to secure base image"
git push origin main
```

### Demo 2 — Gate 4 Blocks Unsigned Image

```bash
docker build -t ghcr.io/haseef-ahamed/hsf-app:unsigned .
docker push ghcr.io/haseef-ahamed/hsf-app:unsigned

cosign verify \
  --key security/cosign.pub \
  ghcr.io/haseef-ahamed/hsf-app:unsigned
# Error: no signatures found for image
```

---

## Testing Commands

```bash
# Full status check
kubectl get all -n supply-chain-demo

# Application health
curl http://localhost:30080/health

# Image signature
cosign verify --key security/cosign.pub \
  ghcr.io/haseef-ahamed/hsf-app:latest

# Vulnerability scan
trivy image --severity CRITICAL \
  ghcr.io/haseef-ahamed/hsf-app:latest

# IaC scan
trivy config --severity CRITICAL,HIGH ./k8s/

# Trigger new pipeline run
echo "# test" >> README.md && git add README.md && \
git commit -m "test: trigger pipeline" && git push origin main
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `permission denied` on docker | Not in docker group | `sudo usermod -aG docker $USER` then re-login |
| Pipeline stuck at Waiting for runner | Runner not started | `cd ~/actions-runner && ./run.sh` |
| `ImagePullBackOff` | Image not public or wrong name | Check ghcr.io package visibility |
| `invalid pem block` on cosign sign | COSIGN_KEY secret malformed | Re-save secret from `cat ~/cosign.key` |
| Kubernetes name error with underscore | `_` not allowed in k8s names | Use `-` (hyphen) instead |
| `no signatures found` | Image not signed by pipeline | Always push via pipeline, not manually |
| IaC scan fails KSV-0118 | Missing pod security context | Add `securityContext` at spec level |
| Pod stuck in `Pending` | Resource limits too tight | Increase memory/cpu in deployment.yaml |
| Runner stops after reboot | Not installed as service | `sudo ~/actions-runner/svc.sh install` |

---

## Future Improvements

- **Admission controller** — use Kyverno to enforce signature verification at the cluster level
- **Keyless signing** — use Sigstore OIDC tokens instead of a static key pair
- **SBOM generation** — use Syft to generate a Software Bill of Materials
- **Multi-environment** — separate staging and production namespaces
- **Distroless images** — eliminate the OS shell entirely to reduce attack surface
- **Dependabot** — automatically flag outdated dependencies in requirements.txt

---

## Project Summary

This project implements a fully automated software supply chain security pipeline
running entirely on a local machine. Using GitHub, GitHub Actions with a
self-hosted runner, Trivy, Cosign, and Kubernetes (k3d), every code push
triggers a 6-job pipeline that enforces four sequential security gates. Gate 1
blocks images with critical CVEs. Gate 2 blocks dangerous Kubernetes
misconfigurations. Gate 3 cryptographically signs every passing image. Gate 4
verifies the signature before deployment. Only images that pass all four gates
reach the running Kubernetes cluster.

---

## License

MIT License — see LICENSE file for details.

---

*Built as a practical DevSecOps learning project.*
*All tools used are free and open source.*
*Fully local — no cloud services required for Kubernetes.*