# Pipeline Details

## File Location

```
.github/workflows/pipeline.yml
```

## Trigger

```yaml
on:
  push:
    branches:
      - main
```

Runs automatically on every push to the `main` branch.
No manual trigger needed.

## Permissions

```yaml
permissions:
  contents: read    # Read repository files
  packages: write   # Push images to ghcr.io
```

`packages: write` is required to push Docker images to
GitHub Container Registry (ghcr.io).

---

## Job Structure and Dependencies

```
build
  └── scan-image        (needs: build)
        └── scan-iac    (needs: scan-image)
              └── sign-image    (needs: [scan-iac, build])
                    └── verify-signature  (needs: [sign-image, build])
                          └── deploy      (needs: [verify-signature, build])
```

Each job only runs if the previous one succeeded.
`build` is listed in multiple `needs` arrays because later jobs
need the image output that `build` produces.

---

## Job 1 — Build Image

**Purpose:** Build the Docker image and push it to ghcr.io.

**Key steps:**
1. Checkout source code from GitHub
2. Log in to ghcr.io using `GITHUB_TOKEN` (automatically provided)
3. Build image with two tags:
   - `:COMMIT_SHA` — unique, traceable to exact code
   - `:latest` — convenient for manual testing
4. Push both tags to ghcr.io
5. Set image reference as output for downstream jobs

**Why push in Job 1 (not Job 4)?**
Cosign signs the image that already exists in the registry.
The image must be pushed before it can be signed.
Later scan jobs pull the image from ghcr.io by SHA tag.

**Output:**
```
image=ghcr.io/haseef-ahamed/hsf-app:abc123...
```

---

## Job 2 — Scan Image (Gate 1)

**Purpose:** Check the Docker image for known security vulnerabilities.

**Key steps:**
1. Pull image reference from Job 1 output
2. Run Trivy image scan:
   ```bash
   trivy image \
     --exit-code 1 \
     --severity CRITICAL \
     --ignore-unfixed \
     --no-progress \
     ghcr.io/haseef-ahamed/hsf-app:SHA
   ```
3. Save full report to `security/trivy-report.json` (always runs)

**`--exit-code 1`** — makes Trivy return a non-zero exit code
on findings, which causes GitHub Actions to mark the step as failed.

**`--ignore-unfixed`** — only reports vulnerabilities that have
a fix available. Unfixed CVEs are excluded to reduce noise.

**`--severity CRITICAL`** — only fails on CRITICAL level.
HIGH, MEDIUM, LOW are still scanned and saved to the report.

**Gate 1 result:** CRITICAL found → pipeline stops. Zero CRITICAL → continues.

---

## Job 3 — Scan IaC (Gate 2)

**Purpose:** Check Kubernetes YAML files for dangerous misconfigurations.

**Key steps:**
1. Checkout repository (to access k8s/ folder)
2. Run Trivy config scan:
   ```bash
   trivy config \
     --exit-code 1 \
     --severity CRITICAL,HIGH \
     ./k8s/
   ```

**What Trivy checks in YAML files:**

| Check ID | Description | Severity |
|----------|-------------|----------|
| KSV-0001 | Container running as root | HIGH |
| KSV-0014 | Root filesystem not read-only | HIGH |
| KSV-0015 | Privilege escalation allowed | HIGH |
| KSV-0016 | Memory limit not set | LOW |
| KSV-0018 | Capabilities not dropped | MEDIUM |
| KSV-0118 | Default security context (root privileges) | HIGH |

Our deployment.yaml is hardened to pass all HIGH and CRITICAL checks.

**Gate 2 result:** HIGH/CRITICAL misconfiguration → pipeline stops.
Zero findings → continues.

---

## Job 4 — Sign Image (Gate 3)

**Purpose:** Attach a cryptographic signature to the image in ghcr.io.

**Key steps:**
1. Log in to ghcr.io
2. Write private key from GitHub Secret to temp file:
   ```bash
   echo "${{ secrets.COSIGN_KEY }}" > /tmp/cosign.key
   ```
3. Sign the image:
   ```bash
   cosign sign \
     --key /tmp/cosign.key \
     --yes \
     ghcr.io/haseef-ahamed/hsf-app:SHA
   ```
4. Delete the private key immediately:
   ```bash
   rm -f /tmp/cosign.key
   ```

**Why delete the key immediately?**
The private key must never linger on disk beyond the signing step.
Deleting it immediately after use minimises the window of exposure.

**Where is the signature stored?**
Cosign stores the signature as an OCI artifact in ghcr.io alongside
the image. It is visible in the package's tags list.

**Gate 3 result:** Signing fails → pipeline stops. Success → continues.

---

## Job 5 — Verify Signature (Gate 4)

**Purpose:** Confirm the image signature is valid before allowing deployment.

**Key steps:**
1. Checkout repository (to access security/cosign.pub)
2. Verify the signature:
   ```bash
   cosign verify \
     --key security/cosign.pub \
     ghcr.io/haseef-ahamed/hsf-app:SHA
   ```

**What verification checks:**
- Does a signature exist for this image in ghcr.io?
- Was it created using the private key that matches `cosign.pub`?
- Does the signed digest match the current image content?

If all three pass: image is authentic and unmodified.
If any fail: image was tampered with or was never signed.

**Gate 4 result:** Invalid/missing signature → pipeline stops.
Valid signature → deployment allowed.

---

## Job 6 — Deploy to Kubernetes

**Purpose:** Apply Kubernetes manifests and roll out the verified image.

**Key steps:**
1. Apply namespace manifest
2. Replace `IMAGE_TAG` placeholder with actual commit SHA:
   ```bash
   sed "s|IMAGE_TAG|${{ github.sha }}|g" \
     k8s/deployment.yaml | kubectl apply -f -
   ```
3. Apply service manifest
4. Wait for rollout to complete:
   ```bash
   kubectl rollout status deployment/hsf-app \
     --namespace supply-chain-demo \
     --timeout=120s
   ```
5. Print final status summary

**Why `sed` for IMAGE_TAG?**
The deployment.yaml in the repository contains `IMAGE_TAG` as a
placeholder. The pipeline replaces it at runtime with the actual
commit SHA. This ensures the running pod uses the exact image that
was scanned and signed in this pipeline run.

**Why not use `latest` tag for deployment?**
`latest` could point to a different image version on the next run.
Using the commit SHA pins the deployment to a specific, verified image.

---

## How the Image Reference Passes Between Jobs

```
Job 1 (build):
  steps.set-image.outputs.image = "ghcr.io/haseef-ahamed/hsf-app:abc123"
        │
        │  accessed in later jobs as:
        │  ${{ needs.build.outputs.image }}
        ▼
Job 2 (scan-image):
  trivy image ... ${{ needs.build.outputs.image }}

Job 4 (sign-image):
  cosign sign ... ${{ needs.build.outputs.image }}

Job 5 (verify-signature):
  cosign verify ... ${{ needs.build.outputs.image }}
```

All jobs operate on the exact same image reference,
ensuring consistency through the entire pipeline.