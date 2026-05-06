# Setup Guide

Complete setup instructions from a fresh Ubuntu machine.
Follow every step in order.

---

## Step 1 — Install Docker

```bash
sudo apt update
sudo apt install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group
# This lets you run docker without sudo
sudo usermod -aG docker $USER

# IMPORTANT: log out and log back in now
# Then verify:
docker run hello-world
```

Expected output: `Hello from Docker!`

---

## Step 2 — Install k3d

k3d creates a lightweight Kubernetes cluster inside Docker containers.

```bash
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# Verify
k3d --version
```

Expected output: `k3d version v5.x.x`

---

## Step 3 — Install kubectl

kubectl is the command-line tool for Kubernetes.

```bash
curl -LO "https://dl.k8s.io/release/$(curl -Ls \
  https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Verify
kubectl version --client
```

Expected output: `Client Version: v1.xx.x`

---

## Step 4 — Install Trivy

```bash
sudo apt install -y wget apt-transport-https gnupg

wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key \
  | sudo apt-key add -

echo "deb https://aquasecurity.github.io/trivy-repo/deb generic main" \
  | sudo tee /etc/apt/sources.list.d/trivy.list

sudo apt update
sudo apt install -y trivy

# Verify
trivy --version
```

Expected output: `Version: 0.5x.x`

**macOS alternative:** `brew install trivy`

---

## Step 5 — Install Cosign

```bash
COSIGN_VERSION=$(curl -s \
  https://api.github.com/repos/sigstore/cosign/releases/latest \
  | grep tag_name | cut -d '"' -f 4)

curl -Lo cosign \
  "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign-linux-amd64"

chmod +x cosign
sudo mv cosign /usr/local/bin/

# Verify
cosign version
```

Expected output: `GitVersion: v2.x.x`

**macOS alternative:** `brew install cosign`

---

## Step 6 — Verify All Tools

Run this block to confirm everything is ready:

```bash
echo "===== Tool Check =====" && \
docker --version && \
k3d --version && \
kubectl version --client 2>/dev/null | head -1 && \
trivy --version | head -1 && \
cosign version 2>/dev/null | grep GitVersion && \
git --version && \
echo "===== All tools ready ====="
```

All six must print version numbers without errors.

---

## Step 7 — Create the k3d Kubernetes Cluster

```bash
k3d cluster create mycluster \
  --port "30080:30080@loadbalancer" \
  --agents 1

# Verify both nodes are Ready
kubectl get nodes
```

Expected output:
```
NAME                     STATUS   ROLES                  AGE
k3d-mycluster-server-0   Ready    control-plane,master   30s
k3d-mycluster-agent-0    Ready    <none>                 25s
```

Wait until both show `Ready` before continuing.

```bash
# Confirm kubectl context
kubectl config current-context
# Expected: k3d-mycluster
```

---

## Step 8 — Set Up GitHub Repository

1. Go to `https://github.com/new`
2. Repository name: `supply-chain-pipeline`
3. Visibility: Public
4. Initialize with README: checked
5. Click **Create repository**

---

## Step 9 — Configure GitHub Permissions

In your repository:
```
Settings → Actions → General → Workflow permissions
Select: Read and write permissions
Click: Save
```

This allows the pipeline to push images to ghcr.io.

---

## Step 10 — Generate Cosign Key Pair

```bash
cd ~
cosign generate-key-pair
# Choose a password and remember it
# Creates: cosign.key (private) and cosign.pub (public)
```

Check the files were created:
```bash
ls -la ~/cosign.key ~/cosign.pub
```

**Security rule:** Never commit `cosign.key` to any repository.

---

## Step 11 — Add GitHub Secrets

Go to:
```
https://github.com/YOUR_USERNAME/supply-chain-pipeline
→ Settings → Secrets and variables → Actions → New repository secret
```

Add these two secrets:

**Secret 1:**
- Name: `COSIGN_KEY`
- Value: paste the entire contents of `~/cosign.key`
```bash
cat ~/cosign.key
# Copy everything from -----BEGIN to -----END
```

**Secret 2:**
- Name: `COSIGN_PASSWORD`
- Value: the password you chose in Step 10

---

## Step 12 — Clone and Set Up Repository

```bash
git clone https://github.com/YOUR_USERNAME/supply-chain-pipeline.git
cd supply-chain-pipeline

# Copy public key into project
mkdir -p security
cp ~/cosign.pub security/cosign.pub

# Create .gitignore
cat > .gitignore << 'EOF'
cosign.key
*.key
__pycache__/
*.pyc
.env
.DS_Store
EOF

# Safety check — cosign.key must NOT appear
git status
# Should NOT show cosign.key
```

---

## Step 13 — Set Up GitHub Actions Self-Hosted Runner

In your repository:
```
Settings → Actions → Runners → New self-hosted runner
Select: Linux, x64
```

Follow the commands GitHub shows you exactly (they contain your unique token):

```bash
mkdir actions-runner && cd actions-runner

# Download (use the exact version GitHub shows you)
curl -o actions-runner-linux-x64-2.x.x.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.x.x/...

tar xzf ./actions-runner-linux-x64-2.x.x.tar.gz

# Configure (use YOUR token from GitHub)
./config.sh \
  --url https://github.com/YOUR_USERNAME/supply-chain-pipeline \
  --token YOUR_TOKEN_FROM_GITHUB

# Start the runner
./run.sh
```

Expected output:
```
√ Connected to GitHub
Listening for Jobs
```

**Keep this terminal open** while running the pipeline.

**To start automatically on boot:**
```bash
cd ~/actions-runner
sudo ./svc.sh install
sudo ./svc.sh start
```

---

## Step 14 — Verify the Full Setup

Run this checklist before pushing any code:

```bash
echo "=== Pre-flight Check ==="

# 1. Docker running
docker info > /dev/null 2>&1 && echo "Docker: OK" || echo "Docker: FAIL"

# 2. k3d cluster healthy
kubectl get nodes --no-headers | grep -q "Ready" && \
  echo "Cluster: OK" || echo "Cluster: FAIL"

# 3. Public key in project
ls security/cosign.pub > /dev/null 2>&1 && \
  echo "cosign.pub: OK" || echo "cosign.pub: MISSING"

# 4. Private key NOT in project
ls cosign.key > /dev/null 2>&1 && \
  echo "cosign.key: DANGER - do not commit!" || echo "cosign.key: Safe (not in project)"

# 5. GitHub Secrets
echo "Check manually at:"
echo "https://github.com/YOUR_USERNAME/supply-chain-pipeline/settings/secrets/actions"
echo "Must have: COSIGN_KEY and COSIGN_PASSWORD"

echo "=== Check Complete ==="
```

All checks must pass before pushing code.

---

## Common Setup Problems

| Problem | Solution |
|---------|----------|
| `permission denied` on docker | Log out and log back in after `usermod` |
| k3d nodes show `NotReady` | Wait 30 seconds and check again |
| Runner shows `Offline` on GitHub | Restart with `cd ~/actions-runner && ./run.sh` |
| cosign.key appears in `git status` | Add `cosign.key` to `.gitignore` immediately |
| ghcr.io push fails | Check Workflow permissions set to Read and write |
| `cosign: command not found` | Check `/usr/local/bin/cosign` exists and is executable |