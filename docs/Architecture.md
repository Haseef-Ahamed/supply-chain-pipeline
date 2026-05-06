# Architecture

## Component Summary

| Component | Where It Runs | Role in Pipeline |
|-----------|--------------|-----------------|
| GitHub repository | GitHub cloud | Stores code, triggers pipeline on push |
| GitHub Actions runner | Your laptop | Executes all pipeline steps |
| ghcr.io | GitHub cloud | Stores signed Docker images |
| Trivy | Inside runner | Scans for CVEs and misconfigurations |
| Cosign | Inside runner | Signs and verifies images |
| k3d cluster | Your laptop | Runs the deployed application |
| Kubernetes YAML | Repository | Describes how app runs in k3d |

---

## Big Picture Diagram

```
╔═══════════════════════════════════════════════════════════════╗
║                       GITHUB CLOUD                            ║
║                                                               ║
║   ┌──────────────────┐    push    ┌───────────────────────┐  ║
║   │  GitHub Repo     │──────────▶│  GitHub Actions        │  ║
║   │  (source code)   │  triggers  │  (self-hosted runner)  │  ║
║   └──────────────────┘           └───────────┬───────────┘  ║
║                                              │               ║
║   ┌──────────────────────────────────────────▼────────────┐  ║
║   │              6-Job Pipeline                            │  ║
║   │  Job1:Build → Job2:ScanImage → Job3:ScanIaC           │  ║
║   │           → Job4:Sign → Job5:Verify → Job6:Deploy      │  ║
║   └──────────────────────────────┬────────────────────────┘  ║
║                                  │                            ║
║   ┌──────────────────────────────▼────────────────────────┐  ║
║   │  GitHub Container Registry (ghcr.io)                   │  ║
║   │  ghcr.io/haseef-ahamed/hsf-app:SHA                     │  ║
║   │  [ signed image + cosign signature stored here ]       │  ║
║   └──────────────────────────────┬────────────────────────┘  ║
╚═════════════════════════════════╪═════════════════════════════╝
                                  │ kubectl apply
                                  │ image pull from ghcr.io
╔═════════════════════════════════╪═════════════════════════════╗
║            YOUR LAPTOP          │                             ║
║                                 ▼                             ║
║          ┌──────────────────────────────────────────┐        ║
║          │  k3d Kubernetes Cluster                   │        ║
║          │                                          │        ║
║          │  Namespace: supply-chain-demo            │        ║
║          │  ├── Deployment: hsf-app                 │        ║
║          │  │     └── Pod: FastAPI container         │        ║
║          │  └── Service: hsf-app-service:30080       │        ║
║          └──────────────────────────────────────────┘        ║
║                                                               ║
║          curl http://localhost:30080/health ✓                 ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## Security Gates Diagram

```
git push origin main
        │
        ▼
╔══════════════════════════════════════════════════════╗
║  GATE 1 — Trivy Image Scan                           ║
║                                                      ║
║  Scans every package inside the Docker image         ║
║  Checks against CVE vulnerability database           ║
║                                                      ║
║  CRITICAL CVE found?                                 ║
║    YES ───────────────────────▶ PIPELINE STOPS ✗     ║
║    NO  ──▶ continue                                  ║
╚══════════════════════════════════════════════════════╝
        │ pass
        ▼
╔══════════════════════════════════════════════════════╗
║  GATE 2 — Trivy IaC Scan                             ║
║                                                      ║
║  Scans k8s/*.yaml for dangerous misconfigurations    ║
║  Checks: root user, privilege escalation, limits     ║
║                                                      ║
║  CRITICAL/HIGH misconfiguration found?               ║
║    YES ───────────────────────▶ PIPELINE STOPS ✗     ║
║    NO  ──▶ continue                                  ║
╚══════════════════════════════════════════════════════╝
        │ pass
        ▼
╔══════════════════════════════════════════════════════╗
║  GATE 3 — Cosign Image Signing                       ║
║                                                      ║
║  Signs image using private key from GitHub Secrets   ║
║  Signature stored in ghcr.io alongside image         ║
║                                                      ║
║  Signing successful?                                 ║
║    NO  ───────────────────────▶ PIPELINE STOPS ✗     ║
║    YES ──▶ image signed                              ║
╚══════════════════════════════════════════════════════╝
        │ signed
        ▼
╔══════════════════════════════════════════════════════╗
║  GATE 4 — Cosign Signature Verification              ║
║                                                      ║
║  Verifies signature using public key from repo       ║
║  Confirms image has not been tampered with           ║
║                                                      ║
║  Valid signature found?                              ║
║    NO  ───────────────────────▶ PIPELINE STOPS ✗     ║
║    YES ──▶ verified                                  ║
╚══════════════════════════════════════════════════════╝
        │ verified
        ▼
┌──────────────────────────────────────────────────────┐
│  DEPLOYMENT — kubectl apply -f k8s/                  │
│                                                      │
│  All 4 gates passed:                                 │
│    ✓ No CRITICAL CVEs in image                       │
│    ✓ No dangerous YAML misconfigurations             │
│    ✓ Image cryptographically signed                  │
│    ✓ Signature verified authentic                    │
│                                                      │
│  FastAPI pod running in k3d ✓                        │
│  Accessible at localhost:30080 ✓                     │
└──────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
YOUR LAPTOP                        GITHUB CLOUD
───────────────                    ──────────────────────────────────

┌─────────────┐  git push          ┌──────────────────────────────┐
│  Developer  │───────────────────▶│  GitHub Repository            │
│  (You)      │                    │  app/  k8s/  Dockerfile       │
└─────────────┘                    └──────────────┬───────────────┘
                                                  │ triggers
                                                  ▼
                                   ┌──────────────────────────────┐
                                   │  GitHub Actions Runner        │
                                   │  (running on your laptop)     │
                                   │                              │
                                   │  reads: COSIGN_KEY (secret)  │
                                   │  reads: COSIGN_PASSWORD       │
                                   │  reads: GITHUB_TOKEN (auto)  │
                                   │                              │
                                   │  produces:                   │
                                   │    Docker image              │
                                   │    Trivy scan report         │
                                   │    Cosign signature          │
                                   └──────────────┬───────────────┘
                                                  │ push + sign
                                                  ▼
                                   ┌──────────────────────────────┐
                                   │  ghcr.io                      │
                                   │  hsf-app:SHA (image)         │
                                   │  hsf-app:sha256-... (sig)    │
                                   └──────────────┬───────────────┘
                   ┌───────────────────────────────┘
                   │ kubectl apply + image pull
                   ▼
┌──────────────────────────────────┐
│  k3d Cluster (YOUR LAPTOP)       │
│                                  │
│  Namespace: supply-chain-demo    │
│  ├── Deployment: hsf-app         │
│  │     └── Pod (FastAPI)         │
│  └── Service (NodePort: 30080)   │
│                                  │
│  localhost:30080/health ✓        │
└──────────────────────────────────┘
```

---

## Security Context in Kubernetes

The deployment YAML enforces these security settings:

```yaml
# Pod level — applies to all containers
securityContext:
  runAsNonRoot: true        # No root processes
  runAsUser: 1000           # Specific non-root user
  seccompProfile:
    type: RuntimeDefault    # System call filtering

# Container level — additional restrictions
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  allowPrivilegeEscalation: false   # Cannot gain more permissions
  readOnlyRootFilesystem: true      # Cannot write to filesystem
  capabilities:
    drop:
      - ALL                         # All Linux capabilities removed
```

These settings are what make Trivy's IaC scan pass at Gate 2.
Without them, Trivy flags the deployment as HIGH severity misconfiguration.