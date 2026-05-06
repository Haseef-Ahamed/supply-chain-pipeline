# Security Scanning and Signing

## Part 1 — Trivy Vulnerability Scanner

### What Is Trivy?

Trivy is a free, open-source security scanner made by Aqua Security.
It scans Docker images and configuration files for known security
problems. It is the most widely used container scanner in the industry.

### What Is a CVE?

CVE stands for Common Vulnerabilities and Exposures. It is a public
database where security researchers record known software vulnerabilities.

Every CVE has:
- A unique ID (e.g. CVE-2023-1234)
- A severity rating (CRITICAL, HIGH, MEDIUM, LOW)
- A description of the vulnerability
- A list of affected software versions
- Information about which version fixes it

When Trivy scans your image, it checks every installed package against
this database. If you have a package version that matches a known CVE,
Trivy reports it.

### Severity Levels Explained

| Level | Description | Real-World Example | Pipeline Action |
|-------|-------------|-------------------|-----------------|
| CRITICAL | Can be exploited remotely, full system compromise | Remote code execution without authentication | Blocks pipeline |
| HIGH | Significant impact, likely exploitable with some effort | Privilege escalation, sensitive data exposure | Blocks IaC scan |
| MEDIUM | Limited impact or requires special conditions | Cross-site scripting, partial info disclosure | Reported only |
| LOW | Minimal real-world impact | Theoretical attack vectors, unlikely to be exploited | Reported only |

### Image Scan — How It Works

```
trivy image ghcr.io/haseef-ahamed/hsf-app:latest
        │
        ├── Pulls image layers from ghcr.io
        ├── Extracts all installed packages
        │     OS packages (apt/dpkg)
        │     Python packages (pip)
        │     Node packages (npm) — if present
        │
        ├── Checks each package + version against CVE database
        │
        └── Produces report:
              Target: debian 13.4
              Total: 0 (CRITICAL: 0, HIGH: 0, MEDIUM: 0)
```

### Why python:3.11-slim Has Zero CVEs

The `slim` variant contains only:
- Python runtime
- Minimal C libraries
- pip and setuptools

The full `python:3.11` image adds:
- Development tools (gcc, make, etc.)
- System utilities (curl, wget, etc.)
- Documentation packages
- Hundreds of additional libraries

Each additional package is a potential CVE. Fewer packages = smaller
attack surface = fewer vulnerabilities for Trivy to find.

### Sample Trivy Report Output (Clean Image)

```
Report Summary
┌─────────────────────────────────┬────────────┬─────────────────┐
│            Target               │    Type    │ Vulnerabilities │
├─────────────────────────────────┼────────────┼─────────────────┤
│ hsf-app:latest (debian 13.4)    │   debian   │        0        │
├─────────────────────────────────┼────────────┼─────────────────┤
│ fastapi-0.109.0                 │ python-pkg │        0        │
├─────────────────────────────────┼────────────┼─────────────────┤
│ uvicorn-0.27.0                  │ python-pkg │        0        │
└─────────────────────────────────┴────────────┴─────────────────┘
```

All zeros means no known vulnerabilities in any package.

### Sample Trivy Report Output (Vulnerable Image — python:3.8)

```
python:3.8 (debian 11.x)
Total: 12 (CRITICAL: 3, HIGH: 9)

┌──────────────┬────────────────┬──────────┬──────────────────┐
│   Library    │ Vulnerability  │ Severity │    Fixed In      │
├──────────────┼────────────────┼──────────┼──────────────────┤
│ libssl1.1    │ CVE-2023-0465  │ CRITICAL │ 1.1.1v-0+deb11u1 │
│ libssl1.1    │ CVE-2023-0466  │ CRITICAL │ 1.1.1v-0+deb11u1 │
│ libcrypto1.1 │ CVE-2023-2650  │ CRITICAL │ 1.1.1u-0+deb11u1 │
└──────────────┴────────────────┴──────────┴──────────────────┘
```

This is what Gate 1 blocks. The pipeline fails here and stops.

### IaC Scan — How It Works

```
trivy config ./k8s/
        │
        ├── Reads every .yaml file in k8s/ folder
        ├── Parses Kubernetes resource definitions
        │
        ├── Checks against misconfiguration rules:
        │     Is the container running as root?
        │     Is privilege escalation allowed?
        │     Are resource limits set?
        │     Is the root filesystem read-only?
        │     Are dangerous capabilities granted?
        │
        └── Produces report with pass/fail per check
```

### Common IaC Findings and Fixes

| Finding | Problem | Fix in deployment.yaml |
|---------|---------|------------------------|
| KSV-0001 | Running as root | `runAsNonRoot: true` |
| KSV-0014 | Writable root filesystem | `readOnlyRootFilesystem: true` |
| KSV-0015 | Privilege escalation allowed | `allowPrivilegeEscalation: false` |
| KSV-0118 | Default security context | Add `securityContext` at pod spec level |
| KSV-0018 | Capabilities not dropped | `capabilities: drop: [ALL]` |

Our deployment.yaml addresses all of these.

### Viewing the Saved Report

```bash
# Human readable summary
cat security/trivy-report.json | python3 -m json.tool | grep -A3 '"Severity"'

# Count findings by severity
cat security/trivy-report.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for result in data.get('Results', []):
    vulns = result.get('Vulnerabilities', [])
    for v in vulns:
        print(v['Severity'], v['VulnerabilityID'], v['PkgName'])
"
```

---

## Part 2 — Cosign Image Signing

### What Is Cosign?

Cosign is a tool from the Sigstore project, backed by Google, Red Hat,
and the Linux Foundation. It uses cryptography to sign container images
and verify those signatures. It is the industry standard for supply
chain signing.

### How Public Key Cryptography Works

Cosign uses a pair of mathematically linked keys:

```
PRIVATE KEY (cosign.key)
  ├── Used to CREATE signatures
  ├── Must be kept secret
  ├── Stored as GitHub Secret COSIGN_KEY
  └── Never committed to repository

PUBLIC KEY (cosign.pub)
  ├── Used to VERIFY signatures
  ├── Safe to share with everyone
  ├── Committed to security/cosign.pub
  └── Anyone can use it to check authenticity
```

The mathematics work like this: data signed with the private key can
only be verified with the matching public key. It is computationally
impossible to fake a signature without the private key.

### What Gets Signed?

Cosign does not sign the entire image file. Instead:

1. Docker calculates a SHA256 digest of the image content
2. Cosign signs this digest with the private key
3. The signature (encrypted digest) is stored in ghcr.io

```
Image content → SHA256 → "sha256:763c3d6996..."
                               │
                    cosign sign (private key)
                               │
                               ▼
               Signature stored in ghcr.io as OCI artifact
```

### What Verification Checks

When `cosign verify` runs:

```
Step 1: Fetch signature from ghcr.io
Step 2: Decrypt signature using public key
Step 3: Compare decrypted digest to current image digest
        ├── Match → image is authentic and unmodified ✓
        └── No match → image was tampered with ✗
```

### Generating Your Key Pair

```bash
cosign generate-key-pair
# Prompts for a password
# Creates:
#   cosign.key  (private — keep secret)
#   cosign.pub  (public — commit to repo)
```

### Signing an Image (Gate 3)

```bash
# How the pipeline signs:
cosign sign \
  --key /tmp/cosign.key \
  --yes \
  ghcr.io/haseef-ahamed/hsf-app:SHA

# The --yes flag skips the confirmation prompt
# in automated pipeline environments
```

### Verifying an Image (Gate 4)

```bash
# Successful verification (pipeline-built image):
cosign verify \
  --key security/cosign.pub \
  ghcr.io/haseef-ahamed/hsf-app:latest

# Output:
# Verification for ghcr.io/haseef-ahamed/hsf-app:latest --
# The following checks were performed on each of these signatures:
#   - The cosign claims were validated
#   - The signatures were verified against the specified public key

# Failed verification (unsigned image):
cosign verify \
  --key security/cosign.pub \
  ghcr.io/haseef-ahamed/hsf-app:unsigned

# Output:
# Error: no signatures found for image
```

### Key Security Rules

```
RULE 1: cosign.key must NEVER be committed to the repository
        Add it to .gitignore immediately after generating

RULE 2: cosign.pub should be committed to security/cosign.pub
        This allows anyone to verify your images

RULE 3: Store COSIGN_KEY and COSIGN_PASSWORD only as GitHub Secrets
        Never put them in environment files or pipeline YAML directly

RULE 4: Delete the private key file immediately after signing
        rm -f /tmp/cosign.key  (included in pipeline)
```

### Verifying the Key Is Not in the Repository

```bash
# Run these to confirm safety:
git log --all --full-history -- cosign.key
# Should return nothing (no commits containing this file)

grep -r "BEGIN ENCRYPTED" .
# Should return nothing from tracked files
# Only acceptable in security/cosign.pub (public key)
```