# Demo Guide

Step-by-step script for demonstrating the supply chain security pipeline.
Follow this guide during a live demo or evaluation.

---

## Before the Demo — Pre-flight Checklist

Run all of these before starting:

```bash
# 1. Runner is listening
ps aux | grep run.sh | grep -v grep
# Must show a process — if empty, start with:
# cd ~/actions-runner && ./run.sh

# 2. Cluster is healthy
kubectl get nodes
# Both nodes must show Ready

# 3. App is deployed and running
kubectl get pods -n supply-chain-demo
# Must show: 1/1 Running

# 4. App is responding
curl http://localhost:30080/health
# Must return: {"status":"healthy","service":"supply-chain-demo"}

# 5. Image signature is valid
cosign verify \
  --key security/cosign.pub \
  ghcr.io/haseef-ahamed/hsf-app:latest 2>/dev/null \
  && echo "Signature: VALID" || echo "Signature: INVALID"
```

All five must show the expected result before starting.

---

## Demo Part 1 — Happy Path (Full Pipeline Success)

**Goal:** Show the complete pipeline running successfully with all 4 gates passing.

### Step 1: Trigger the pipeline

```bash
cd ~/supply-chain-pipeline
echo "# Demo run $(date)" >> README.md
git add README.md
git commit -m "demo: trigger full pipeline happy path"
git push origin main
```

### Step 2: Open GitHub Actions in browser

```
https://github.com/Haseef-Ahamed/supply-chain-pipeline/actions
```

Click on the running pipeline. Point out each job:

```
🔨 Build Image              ← Building the Docker image, pushing to ghcr.io
      │
      ▼
🔍 Scan Image — Gate 1      ← Trivy scanning for CVE vulnerabilities
      │
      ▼
📋 Scan IaC — Gate 2        ← Trivy checking Kubernetes YAML files
      │
      ▼
✍️  Sign Image — Gate 3      ← Cosign signing with private key
      │
      ▼
✅ Verify Signature — Gate 4 ← Cosign verifying the signature
      │
      ▼
🚀 Deploy to Kubernetes      ← kubectl applying manifests
```

**Points to make while waiting:**
- Each job only runs if the previous one passed
- The pipeline is fully automatic — no manual steps
- The self-hosted runner on our laptop executes all steps

### Step 3: After all jobs go green, show the running app

```bash
# Show pod is running
kubectl get pods -n supply-chain-demo

# Show all resources
kubectl get all -n supply-chain-demo

# Test all endpoints
echo "=== /health ===" && curl http://localhost:30080/health
echo ""
echo "=== / ===" && curl http://localhost:30080/
echo ""
echo "=== /info ===" && curl http://localhost:30080/info
```

### Step 4: Show the image signature locally

```bash
cosign verify \
  --key security/cosign.pub \
  ghcr.io/haseef-ahamed/hsf-app:latest
```

Point out in the output:
```
- The cosign claims were validated
- The signatures were verified against the specified public key
```

**Say:** "This proves the image was built by our pipeline and has
not been modified since signing."

---

## Demo Part 2 — Gate 1 Blocks a Vulnerable Image

**Goal:** Prove that the pipeline rejects images with critical vulnerabilities.

### Step 1: Explain what you are about to do

"I'm going to change the Dockerfile to use Python 3.8, an old version
with known critical vulnerabilities. Watch what happens when I push this."

### Step 2: Introduce the vulnerability

```bash
# Change base image to vulnerable version
sed -i "s|FROM python:3.11-slim|FROM python:3.8|g" Dockerfile

# Confirm the change
head -3 Dockerfile
# Should show: FROM python:3.8

# Push to trigger pipeline
git add Dockerfile
git commit -m "demo: Gate 1 block — vulnerable base image python:3.8"
git push origin main
```

### Step 3: Watch Gate 1 fail in GitHub Actions

In the browser, watch Job 2 (Scan Image — Gate 1) fail.

The Trivy output will show:
```
CRITICAL CVEs found in python:3.8
Pipeline fails here — Jobs 3-6 skipped
```

**Say:** "Gate 1 caught the vulnerability. The image was never signed,
never pushed as production, and never deployed. All subsequent jobs
are automatically skipped."

**Screenshot this failure.**

### Step 4: Revert immediately

```bash
sed -i "s|FROM python:3.8|FROM python:3.11-slim|g" Dockerfile
git add Dockerfile
git commit -m "fix: revert to secure base image python:3.11-slim"
git push origin main
```

Watch the pipeline go green again.

---

## Demo Part 3 — Gate 4 Blocks an Unsigned Image

**Goal:** Prove that images pushed without signing are rejected.

### Step 1: Explain what you are about to do

"I'm going to build an image and push it directly to the registry,
bypassing the pipeline and skipping the signing step. Watch what
happens when I try to verify it."

### Step 2: Build and push without signing

```bash
# Build image
docker build -t ghcr.io/haseef-ahamed/hsf-app:unsigned .

# Push directly to registry — no signing
docker push ghcr.io/haseef-ahamed/hsf-app:unsigned

echo "Image pushed without signing"
```

### Step 3: Try to verify — show it failing

```bash
echo "=== Attempting to verify UNSIGNED image ==="
cosign verify \
  --key security/cosign.pub \
  ghcr.io/haseef-ahamed/hsf-app:unsigned
```

Expected output:
```
Error: no signatures found for image:
ghcr.io/haseef-ahamed/hsf-app:unsigned
```

**Screenshot this output.**

### Step 4: Contrast with the signed image

```bash
echo "=== Verifying SIGNED image (pipeline-built) ==="
cosign verify \
  --key security/cosign.pub \
  ghcr.io/haseef-ahamed/hsf-app:latest \
  > /dev/null 2>&1 \
  && echo "VERIFIED — image is trusted and authentic" \
  || echo "FAILED"
```

**Say:** "The unsigned image is rejected. Only images that went through
our pipeline — scanned, then signed — pass the verification gate.
An attacker who gains write access to the registry cannot deploy
malicious images because they do not have the signing key."

---

## Demo Part 4 — Show Security Evidence

### Trivy scan report

```bash
# Show the saved scan report
cat security/trivy-report.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('Results', [])
total_vulns = sum(len(r.get('Vulnerabilities') or []) for r in results)
print(f'Total vulnerabilities found: {total_vulns}')
print(f'Targets scanned: {len(results)}')
for r in results[:3]:
    print(f'  - {r[\"Target\"]}: {len(r.get(\"Vulnerabilities\") or [])} findings')
"
```

### IaC scan result

```bash
trivy config --severity CRITICAL,HIGH ./k8s/
# Show all zeros — clean configuration
```

### Pod security context

```bash
kubectl get pod \
  -l app=hsf-app \
  -n supply-chain-demo \
  -o jsonpath='{.items[0].spec.securityContext}' \
  | python3 -m json.tool
```

Shows: `runAsNonRoot: true`, `runAsUser: 1000`, `seccompProfile`

---

## Key Points to Emphasise During Demo

1. **Automatic** — everything runs on git push, no manual steps
2. **Sequential gates** — each gate only runs if the previous passed
3. **Traceable** — every deployed image links to an exact git commit
4. **Provable** — the signature is mathematical proof of authenticity
5. **Local** — entire system runs on one laptop, no cloud Kubernetes

---

## Quick Recovery Commands

If something goes wrong during the demo:

```bash
# Restart runner if it stopped
cd ~/actions-runner && ./run.sh

# Restart cluster if it stopped
k3d cluster start mycluster

# Re-deploy manually if needed
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/service.yaml
sed "s|IMAGE_TAG|latest|g" k8s/deployment.yaml \
  | kubectl apply -f -
kubectl rollout status deployment/hsf-app -n supply-chain-demo

# Verify app after recovery
curl http://localhost:30080/health
```