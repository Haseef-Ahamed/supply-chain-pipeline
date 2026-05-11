# Complete Workflow Explanation
# Every YAML File — Line by Line — With Real World Examples

---

## THE BIG PICTURE FIRST

Before reading any file, understand this story:

Imagine you work at a medicine factory.
Your job is to make sure every medicine bottle that reaches a patient is:
  1. Safe (no harmful ingredients)
  2. Properly checked (configuration is correct)
  3. Officially stamped (signed by the factory)
  4. Verified before shipping (seal is intact)

Your project does the EXACT same thing — but for software.
Instead of medicine bottles, you have Docker images.
Instead of harmful ingredients, you have CVE vulnerabilities.
Instead of a factory stamp, you have a Cosign signature.

Every time you push code to GitHub:
  - A robot (GitHub Actions runner) wakes up on your laptop
  - It builds your app into a Docker image
  - It runs 4 security checks (gates)
  - If ALL pass, it deploys the app to Kubernetes
  - If ANY fail, everything stops

---

## FILE 1: Dockerfile
## Location: Dockerfile (at the root of your project)

---

### What is a Dockerfile?

Think of it as a recipe card.
It tells Docker: "Here is how to build my app into a sealed box (container)."
Every line is one instruction in the recipe.

---

```
FROM python:3.11-slim
```

WHAT IT DOES:
  This is the starting point of your container.
  "FROM" means: start building ON TOP OF this existing base image.
  "python:3.11-slim" is a pre-built image from Docker Hub that has:
    - Linux operating system (Debian)
    - Python 3.11 already installed
    - Only the minimum packages needed

WHY python:3.11-slim and NOT python:3.11?
  python:3.11 (full) = 900MB, hundreds of extra packages
  python:3.11-slim    = 150MB, only what Python needs
  Fewer packages = fewer CVEs = Trivy finds less problems
  This is your FIRST security decision.

REAL WORLD EXAMPLE:
  Imagine building a sandwich.
  FROM = choosing your bread.
  If you use plain white bread (slim), it has 5 ingredients.
  If you use fancy stuffed bread (full), it has 50 ingredients.
  More ingredients = more chances something goes bad.

CONNECTS TO:
  Gate 1 (Trivy scan) — the base image directly affects how many
  CVEs Trivy finds. Bad base image = pipeline fails here.

---

```
WORKDIR /app
```

WHAT IT DOES:
  Sets the working directory INSIDE the container to /app.
  All commands after this line will run FROM this folder.
  If /app does not exist, Docker creates it automatically.

WHY:
  Keeps your app files organised in one place inside the container.
  Without this, files would scatter across the root filesystem.

REAL WORLD EXAMPLE:
  Imagine moving to a new office.
  WORKDIR = "put everything on my desk (at /app)"
  Instead of dumping everything on the floor.

CONNECTS TO:
  The COPY lines below — they copy files INTO this /app folder.
  The CMD line at the bottom — it runs from this folder.

---

```
COPY app/requirements.txt .
```

WHAT IT DOES:
  Copies the file "app/requirements.txt" from your laptop
  INTO the container at the current working directory (/app).
  The dot (.) means "current directory inside the container" = /app.

WHY copy requirements BEFORE the app code?
  This is a Docker layer caching trick.
  Docker builds images in layers. Each line = one layer.
  If requirements.txt does not change between builds,
  Docker skips re-running pip install (saves time).
  If you copied everything at once, any code change would
  force a full re-install of all packages.

REAL WORLD EXAMPLE:
  Imagine packing a lunch box.
  You pack the napkins and utensils first (requirements.txt).
  Then you pack the food (app code).
  If you only change the food, you do not repack the utensils.
  Docker works the same way — unchanged layers are cached.

CONNECTS TO:
  The next line (RUN pip install) uses this file.
  Must come BEFORE copying app code for caching to work.

---

```
RUN pip install --no-cache-dir -r requirements.txt
```

WHAT IT DOES:
  RUN executes a shell command INSIDE the container during build.
  "pip install" installs Python packages.
  "-r requirements.txt" means: install everything listed in that file.
  "--no-cache-dir" means: do not save the download cache.

WHY --no-cache-dir?
  Without it, pip saves downloaded packages to a cache folder.
  We never need that cache again after building.
  Removing it makes the final image smaller.

WHAT GETS INSTALLED:
  fastapi==0.109.0   (the web framework)
  uvicorn==0.27.0    (the web server that runs FastAPI)

REAL WORLD EXAMPLE:
  RUN = "do this action during construction"
  Like installing a kitchen sink while building a house.
  You do it once during construction, not every time someone uses the house.

CONNECTS TO:
  The previous COPY line — pip reads requirements.txt that was just copied.
  The CMD line — uvicorn (installed here) is used to start the app.

---

```
COPY app/ .
```

WHAT IT DOES:
  Copies EVERYTHING inside the "app/" folder on your laptop
  into the current directory inside the container (/app).
  So app/main.py becomes /app/main.py inside the container.

WHY AFTER requirements.txt?
  Because of Docker layer caching.
  Your app code changes often. Requirements change rarely.
  If you copied app/ first, every code change would bust the cache
  and force pip to re-install all packages from scratch.

REAL WORLD EXAMPLE:
  After installing the sink (pip install),
  now bring in the furniture (your app code).
  Furniture changes often. The sink stays.

CONNECTS TO:
  The CMD line — runs main.py which was copied here.
  The WORKDIR line — files land in /app because of WORKDIR.

---

```
RUN adduser --disabled-password --gecos "" appuser
```

WHAT IT DOES:
  Creates a new Linux user called "appuser" inside the container.
  "--disabled-password" = this user has no password (cannot log in)
  "--gecos """ = skip the full name/contact info fields

WHY create a non-root user?
  By default, containers run as root (the superuser).
  If an attacker exploits your app, they would have root access
  to the container — they could do anything.
  Running as a normal user limits the damage.
  This is required to pass Trivy IaC scan (Gate 2).

REAL WORLD EXAMPLE:
  Imagine a security guard at a bank.
  If the guard has a master key to every vault (root),
  a thief who overpowers the guard gets everything.
  If the guard only has keys to the lobby (normal user),
  the thief gets much less.

CONNECTS TO:
  The next line (USER appuser) — we create the user HERE,
  then switch to that user on the next line.
  deployment.yaml — runAsUser: 1000 matches this user.

---

```
USER appuser
```

WHAT IT DOES:
  Switches the current user INSIDE the container to "appuser".
  All commands after this line (including CMD) run as appuser.

WHY:
  The RUN adduser line created the user.
  This line activates that user.
  Without USER, everything still runs as root.

IMPORTANT ORDER:
  You must RUN pip install BEFORE switching to USER appuser.
  pip needs to write to system folders — only root can do that.
  After switching to appuser, you can no longer write to system folders.

CONNECTS TO:
  deployment.yaml: "runAsNonRoot: true" and "runAsUser: 1000"
  These settings in Kubernetes confirm the container is running
  as a non-root user. They connect to this USER line.

---

```
EXPOSE 8000
```

WHAT IT DOES:
  Documents that this container listens on port 8000.
  This is DOCUMENTATION only — it does not actually open the port.
  The actual port opening happens in Kubernetes service.yaml.

WHY document it?
  Other developers reading the Dockerfile immediately know
  which port the app uses.
  Docker and Kubernetes tools use this as a hint.

REAL WORLD EXAMPLE:
  Like writing "Front door is on the north side" on a building blueprint.
  It tells you where the door is, but you still need a key to open it.
  The actual door (port) is opened by the Service in Kubernetes.

CONNECTS TO:
  service.yaml: "targetPort: 8000" — this is the port the service
  routes traffic to. Must match EXPOSE here.
  app/main.py: uvicorn runs on port 8000.

---

```
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

WHAT IT DOES:
  Defines the command that runs when the container STARTS.
  "uvicorn" = the web server program
  "main:app" = run the "app" object from the "main.py" file
  "--host", "0.0.0.0" = accept connections from any IP address
  "--port", "8000" = listen on port 8000

WHY --host 0.0.0.0 and not localhost?
  "localhost" (127.0.0.1) only accepts connections from inside the container.
  "0.0.0.0" accepts connections from anywhere — including Kubernetes routing.
  Without this, the app runs but nothing outside can reach it.

WHY CMD and not RUN?
  RUN runs during BUILD time (when creating the image).
  CMD runs at START time (when the container is launched).
  You build once, start many times.

REAL WORLD EXAMPLE:
  RUN = construction work done while building the house
  CMD = the instruction "turn on the lights when you move in"
  The instruction is set once during construction,
  but executes every time someone moves in (starts the container).

CONNECTS TO:
  EXPOSE 8000 — both must use the same port number (8000).
  service.yaml: targetPort: 8000 — Kubernetes sends traffic here.
  livenessProbe in deployment.yaml — checks /health on port 8000.

---
---

## FILE 2: app/main.py
## Location: app/main.py

---

### What is main.py?

This is your actual application — a tiny web API built with FastAPI.
It has three URL endpoints (web addresses) that respond to requests.
This is the app that runs inside the Docker container.

---

```python
from fastapi import FastAPI
```

WHAT IT DOES:
  Imports the FastAPI library so you can use it.
  FastAPI is a Python web framework — it helps you build web APIs easily.

REAL WORLD EXAMPLE:
  Like picking up a tool from your toolbox before starting work.
  You cannot use a hammer until you pick it up.

---

```python
import os
```

WHAT IT DOES:
  Imports Python's built-in "os" module.
  This lets you read environment variables from the system.

CONNECTS TO:
  The /info endpoint below — uses os.getenv() to read APP_ENV variable.
  deployment.yaml could set this variable, and main.py would read it.

---

```python
app = FastAPI(
    title="Supply Chain Security Demo",
    description="Demo app for supply chain security pipeline",
    version="1.0.0"
)
```

WHAT IT DOES:
  Creates the FastAPI application object.
  Stores it in a variable called "app".
  title, description, version appear in the auto-generated API docs.

CONNECTS TO:
  CMD in Dockerfile: "main:app" means "find the app object in main.py"
  That "app" is exactly this object.

---

```python
@app.get("/")
def root():
    return {
        "message": "Supply Chain Security Pipeline — Demo App",
        "version": "1.0.0",
        "status": "running"
    }
```

WHAT IT DOES:
  @app.get("/") means: when someone visits the root URL (http://localhost:30080/)
  run the function below it and return the result as JSON.

TEST IT:
  curl http://localhost:30080/
  Returns: {"message": "...", "version": "1.0.0", "status": "running"}

---

```python
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "supply-chain-demo"
    }
```

WHAT IT DOES:
  Creates a health check endpoint at /health.
  Returns a simple JSON response confirming the app is alive.

WHY this endpoint is CRITICAL for Kubernetes:
  deployment.yaml uses this endpoint for livenessProbe and readinessProbe.
  Kubernetes calls /health every 15 seconds.
  If it gets no response, Kubernetes restarts the pod.
  If it gets a response, Kubernetes keeps the pod running.

CONNECTS TO:
  deployment.yaml:
    livenessProbe: httpGet path: /health port: 8000
    readinessProbe: httpGet path: /health port: 8000
  This exact URL path "/health" must match what is in deployment.yaml.

---

```python
@app.get("/info")
def info():
    return {
        "app": "FastAPI Supply Chain Demo",
        "environment": os.getenv("APP_ENV", "local"),
        "description": "Secured by Trivy scanning and Cosign signing"
    }
```

WHAT IT DOES:
  Creates an /info endpoint.
  os.getenv("APP_ENV", "local") reads the APP_ENV environment variable.
  If APP_ENV is not set, it defaults to "local".

---
---

## FILE 3: app/requirements.txt
## Location: app/requirements.txt

---

```
fastapi==0.109.0
uvicorn==0.27.0
```

WHAT IT DOES:
  Lists the Python packages your app needs to run.
  The "==" pins the exact version.

WHY pin exact versions?
  Without pinning: "pip install fastapi" might install version 0.200.0 tomorrow.
  With pinning: always installs exactly 0.109.0 — reproducible every time.
  This is a supply chain security practice — you know EXACTLY what is installed.

CONNECTS TO:
  Dockerfile: "RUN pip install -r requirements.txt" reads this file.
  Trivy scan: Trivy checks these exact versions against the CVE database.
  If fastapi==0.109.0 had a CRITICAL CVE, Gate 1 would block the pipeline.

---
---

## FILE 4: k8s/namespace.yaml
## Location: k8s/namespace.yaml

---

### What is a Namespace?

In Kubernetes, a namespace is like a folder or a room.
It keeps your app's resources (pods, services) separate from other things.
Without a namespace, everything goes into "default" — messy and hard to manage.

---

```yaml
apiVersion: v1
```

WHAT IT DOES:
  Tells Kubernetes which API version to use for this resource.
  "v1" is the original, stable API version.
  Different resources use different API versions.
  Namespace is a basic resource, so it uses the original "v1".

REAL WORLD EXAMPLE:
  Like saying "I am writing this form using Form Version 1".
  Kubernetes needs to know which version so it reads it correctly.

---

```yaml
kind: Namespace
```

WHAT IT DOES:
  Tells Kubernetes WHAT TYPE of resource this YAML file is creating.
  "Namespace" means: create a namespace (a container for other resources).

WHY kind matters:
  Kubernetes has many resource types: Namespace, Deployment, Service, Pod, etc.
  Without "kind", Kubernetes does not know what to create.

REAL WORLD EXAMPLE:
  Like the title of a form: "EMPLOYEE REGISTRATION FORM"
  The title tells you what the form is for.
  kind: Namespace tells Kubernetes what the YAML is for.

---

```yaml
metadata:
  name: supply-chain-demo
```

WHAT IT DOES:
  "metadata" = information ABOUT this resource (not what it does).
  "name: supply-chain-demo" = the name of this namespace.
  Every resource in Kubernetes must have a unique name within its type.

WHY this name?
  All k8s resources (pods, services) use "-n supply-chain-demo" to
  indicate they belong to this namespace.
  If this name changes here, it must change everywhere else too.

CONNECTS TO:
  deployment.yaml: "namespace: supply-chain-demo" — must match
  service.yaml: "namespace: supply-chain-demo" — must match
  pipeline.yml: "kubectl rollout status ... --namespace supply-chain-demo" — must match
  kubectl commands: "kubectl get pods -n supply-chain-demo" — must match

---

```yaml
  labels:
    purpose: security-demo
    managed-by: github-actions
```

WHAT IT DOES:
  Labels are key-value tags attached to resources.
  "purpose: security-demo" — describes what this namespace is for.
  "managed-by: github-actions" — documents that the pipeline manages this.

WHY use labels?
  Labels help you filter and find resources.
  Example: kubectl get namespaces -l managed-by=github-actions
  They are optional but good documentation practice.

REAL WORLD EXAMPLE:
  Like sticky notes on a file folder.
  "PURPOSE: Security Demo" and "MANAGED BY: CI/CD Pipeline"
  Helps anyone who picks up the folder understand what it is.

---
---

## FILE 5: k8s/deployment.yaml
## Location: k8s/deployment.yaml

---

### What is a Deployment?

A Deployment tells Kubernetes:
  "Run THIS app, keep THIS many copies running,
   use THIS image, with THESE security settings."

If a pod crashes, the Deployment automatically restarts it.
If you push a new image, the Deployment replaces the old pods one by one.

---

```yaml
apiVersion: apps/v1
```

WHAT IT DOES:
  Deployment is a more complex resource than Namespace.
  It lives in the "apps" API group, version "v1".
  So apiVersion is "apps/v1" instead of just "v1".

CONNECTS TO:
  namespace.yaml uses "v1" (no group prefix) because Namespace
  is a core resource. Deployment is in the "apps" group.

---

```yaml
kind: Deployment
```

WHAT IT DOES:
  Tells Kubernetes this YAML creates a Deployment resource.

---

```yaml
metadata:
  name: hsf-app
  namespace: supply-chain-demo
  labels:
    app: hsf-app
    version: "1.0"
```

WHAT EACH LINE DOES:

  name: hsf-app
    The name of this Deployment.
    Used in pipeline.yml: "kubectl rollout status deployment/hsf-app"
    IMPORTANT: No underscores allowed. Use hyphens only.
    (You learned this the hard way with hsf_app!)

  namespace: supply-chain-demo
    Places this Deployment inside the supply-chain-demo namespace.
    MUST match the name in namespace.yaml.
    If you write a different namespace name, Kubernetes looks for a
    namespace that does not exist and fails.

  labels:
    app: hsf-app
    Labels on the Deployment itself (not the pods it creates).
    Used for identification and filtering.
    version: "1.0" helps track which version is deployed.

CONNECTS TO:
  namespace.yaml: name must match namespace.yaml's metadata.name
  pipeline.yml: "kubectl rollout status deployment/hsf-app" uses this name
  service.yaml: selector app: hsf-app finds pods created by this deployment

---

```yaml
spec:
  replicas: 1
```

WHAT IT DOES:
  "spec" = the specification — what you actually want Kubernetes to do.
  "replicas: 1" = run exactly 1 copy (pod) of this app.

WHY only 1?
  This is a demo project. In production you would use 3+ replicas
  so if one pod crashes, the others keep serving traffic.

REAL WORLD EXAMPLE:
  Like telling a store manager: "Keep 1 cashier at register 5."
  If that cashier calls in sick (pod crashes),
  the manager (Kubernetes) immediately finds a replacement.

---

```yaml
  selector:
    matchLabels:
      app: hsf-app
```

WHAT IT DOES:
  The selector tells the Deployment HOW TO FIND its own pods.
  "matchLabels: app: hsf-app" means:
  "I own and manage all pods that have the label app=hsf-app"

WHY this matters:
  The Deployment and the pods it creates are separate objects in Kubernetes.
  The selector is the connection between them.
  The Deployment uses this to count pods, restart crashed ones, etc.

CONNECTS TO:
  template.metadata.labels below — the pods MUST have the label
  "app: hsf-app" so that the selector can find them.
  service.yaml selector — the Service also uses "app: hsf-app" to
  find which pods to send traffic to.

REAL WORLD EXAMPLE:
  Imagine a manager (Deployment) and employees (pods).
  All employees wear a badge that says "app: hsf-app".
  The manager looks for anyone with that badge.
  selector.matchLabels is the rule: "find everyone with this badge".

---

```yaml
  template:
    metadata:
      labels:
        app: hsf-app
```

WHAT IT DOES:
  "template" = the blueprint for creating pods.
  Everything under template describes what each pod should look like.
  "labels: app: hsf-app" = stamp every pod with this label.

WHY this MUST match selector.matchLabels:
  The selector looks for pods with "app: hsf-app".
  The template stamps pods with "app: hsf-app".
  If they do not match, the Deployment cannot find its own pods.
  This would cause an error when applying the YAML.

---

```yaml
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        seccompProfile:
          type: RuntimeDefault
```

WHAT IT DOES:
  This is the POD-LEVEL security context.
  It applies to ALL containers inside this pod.

  runAsNonRoot: true
    Kubernetes refuses to start the pod if the container tries to run as root.
    Even if the Dockerfile said USER root, Kubernetes would block it.
    This is a safety net on top of the Dockerfile's USER appuser line.

  runAsUser: 1000
    Forces the container to run as user ID 1000.
    Linux user IDs are numbers. Root = 0. Regular users = 1000+.
    When you ran "adduser appuser" in the Dockerfile, Linux assigned
    it user ID 1000 by default.
    This setting ENFORCES that ID at the Kubernetes level.

  seccompProfile: type: RuntimeDefault
    seccomp = secure computing mode.
    It limits which system calls (low-level OS functions) the container can make.
    RuntimeDefault = use Docker's/Kubernetes's built-in safe list.
    This prevents the container from doing dangerous things like
    loading kernel modules or changing system time.
    Required to pass Trivy IaC scan KSV-0118.

CONNECTS TO:
  Dockerfile: "RUN adduser ... appuser" and "USER appuser"
  These create and activate user 1000 in the image.
  The securityContext here ENFORCES it at the Kubernetes level.
  Both must agree — Dockerfile creates user 1000, Kubernetes requires user 1000.

REAL WORLD EXAMPLE:
  The Dockerfile says "our factory worker is Alice (user 1000)".
  The securityContext says "ONLY Alice is allowed to operate this machine".
  If someone tries to log in as the factory manager (root),
  Kubernetes blocks them at the door.

---

```yaml
      containers:
        - name: hsf-app
```

WHAT IT DOES:
  "containers" = list of containers inside this pod.
  Most pods have just one container.
  "- name: hsf-app" = the name of this specific container.
  The hyphen (-) indicates this is the first item in a list.

WHY name matters:
  Used in kubectl commands: "kubectl logs ... -c hsf-app"
  Must follow Kubernetes naming rules: lowercase, hyphens only, no underscores.

---

```yaml
          image: ghcr.io/haseef-ahamed/hsf-app:IMAGE_TAG
```

WHAT IT DOES:
  Tells Kubernetes WHICH Docker image to pull and run.
  "ghcr.io" = GitHub Container Registry (where your image is stored)
  "haseef-ahamed" = your GitHub username (lowercase)
  "hsf-app" = image name
  "IMAGE_TAG" = a PLACEHOLDER — not a real tag

WHY IMAGE_TAG and not a real tag?
  This file is committed to the repository.
  The actual commit SHA is only known at pipeline runtime.
  The pipeline replaces IMAGE_TAG with the real SHA using this command:
    sed "s|IMAGE_TAG|${{ github.sha }}|g" k8s/deployment.yaml
  So IMAGE_TAG becomes something like:
    ghcr.io/haseef-ahamed/hsf-app:a3f8c91d2b4e...

WHY use commit SHA and not "latest"?
  "latest" is dangerous — it could pull a DIFFERENT image next time.
  Commit SHA is unique and permanent — always the same image.
  This is called image pinning — a supply chain security best practice.

CONNECTS TO:
  pipeline.yml deploy job:
    sed "s|IMAGE_TAG|${{ github.sha }}|g" k8s/deployment.yaml
  This is the line that replaces IMAGE_TAG with the real value.
  The image must exist in ghcr.io — pushed in Job 1 of the pipeline.

---

```yaml
          imagePullPolicy: Always
```

WHAT IT DOES:
  Tells Kubernetes to ALWAYS download the image from ghcr.io when starting a pod.
  Even if the same tag already exists locally, pull it again.

WHY Always?
  If you use "IfNotPresent", Kubernetes might use a cached old image.
  With "Always", you guarantee the latest version of that tag is used.
  Important for security — you want the exact signed image, not a cached one.

---

```yaml
          ports:
            - containerPort: 8000
              protocol: TCP
```

WHAT IT DOES:
  Documents that this container listens on port 8000.
  TCP is the network protocol (standard for web traffic).

CONNECTS TO:
  Dockerfile: EXPOSE 8000 — both must use the same port.
  CMD in Dockerfile: "--port", "8000" — uvicorn runs on this port.
  service.yaml: targetPort: 8000 — Service sends traffic to this port.
  health probes below: port: 8000 — health checks use this port.

---

```yaml
          resources:
            requests:
              memory: "64Mi"
              cpu: "100m"
            limits:
              memory: "128Mi"
              cpu: "200m"
```

WHAT IT DOES:
  Sets CPU and memory boundaries for this container.

  requests = minimum guaranteed resources
    memory: "64Mi" = guarantee 64 megabytes of RAM
    cpu: "100m" = guarantee 0.1 CPU core (100 millicores = 1/10th of a core)
    Kubernetes uses this to decide which node to place the pod on.

  limits = maximum allowed resources
    memory: "128Mi" = never use more than 128MB of RAM
    cpu: "200m" = never use more than 0.2 CPU cores
    If the container exceeds limits, Kubernetes kills and restarts it.

WHY this matters for security:
  Without limits, one pod can consume all available resources,
  starving other pods — called a "resource exhaustion attack".
  Trivy IaC scan checks for resource limits. Without them, Gate 2 fails.

REAL WORLD EXAMPLE:
  requests = "I need at least a desk and a computer to work"
  limits = "I am not allowed to take over the entire office floor"
  Kubernetes enforces both.

---

```yaml
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
```

WHAT IT DOES:
  This is the CONTAINER-LEVEL security context.
  It adds MORE security settings on top of the pod-level securityContext.

  runAsNonRoot: true
    Same as pod level — belt and suspenders approach.
    Confirmed again at the container level.

  runAsUser: 1000
    Same as pod level — confirmed again at container level.

  allowPrivilegeEscalation: false
    The process inside the container CANNOT gain more permissions
    than it was started with.
    Even if an attacker exploits the app, they cannot become root.
    Without this, a hacked container could escalate to root.

  readOnlyRootFilesystem: true
    The container cannot write to its own filesystem.
    Malware often needs to write files — this blocks that.
    Important: your app cannot write files either (which is fine for an API).

  capabilities: drop: [ALL]
    Linux capabilities are special permissions (like opening ports below 1024,
    changing system time, loading kernel modules).
    "drop: ALL" removes every single capability from this container.
    The container has zero special Linux permissions.
    This is the most restrictive possible setting.

WHY TWO securityContext blocks?
  Pod-level securityContext applies to ALL containers in the pod.
  Container-level adds per-container restrictions.
  Having both is belt-and-suspenders security.
  This is what makes Trivy's IaC scan (Gate 2) pass with zero findings.

CONNECTS TO:
  Pod-level securityContext above — works together
  Dockerfile: USER appuser (user 1000) — must be consistent
  Trivy IaC scan: these settings are what Trivy checks for
  Without these settings, Trivy finds HIGH misconfigurations and Gate 2 fails

---

```yaml
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 15
```

WHAT IT DOES:
  The liveness probe tells Kubernetes: "Is this container still alive?"
  Kubernetes calls GET /health on port 8000 to check.

  httpGet: path: /health, port: 8000
    Kubernetes makes an HTTP GET request to http://POD_IP:8000/health
    If it gets a 200 response → container is alive
    If it gets no response or an error → container is dead

  initialDelaySeconds: 10
    Wait 10 seconds after the container starts before the first health check.
    This gives uvicorn time to start up before Kubernetes checks it.
    Without this delay, Kubernetes checks too early and kills the pod
    before it has time to start.

  periodSeconds: 15
    Check every 15 seconds.

WHAT HAPPENS if liveness probe fails?
  Kubernetes kills the pod and starts a new one.
  This is automatic self-healing.

CONNECTS TO:
  app/main.py: @app.get("/health") — this endpoint must exist and return 200.
  containerPort: 8000 — the probe uses this port.
  If /health returns an error or the app crashes, the pod is restarted.

---

```yaml
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
```

WHAT IT DOES:
  The readiness probe tells Kubernetes: "Is this container READY to receive traffic?"
  Similar to liveness but different purpose.

  initialDelaySeconds: 5
    Start checking after 5 seconds (sooner than liveness).

  periodSeconds: 10
    Check every 10 seconds.

DIFFERENCE between liveness and readiness:
  Liveness = "Is the container alive?" → if NO, kill and restart it
  Readiness = "Is the container ready for traffic?" → if NO, stop sending traffic
              but do NOT kill it. Wait for it to become ready.

REAL WORLD EXAMPLE:
  Imagine a restaurant:
  Liveness = "Is the kitchen on fire?" → if yes, evacuate (restart)
  Readiness = "Is the chef ready to cook?" → if no, do not seat new customers yet
              but do not close the restaurant (do not kill the pod)

CONNECTS TO:
  app/main.py: same /health endpoint serves both probes.
  service.yaml: Service only routes traffic to pods where readiness passes.

---
---

## FILE 6: k8s/service.yaml
## Location: k8s/service.yaml

---

### What is a Service?

A pod has an IP address, but it changes every time the pod restarts.
A Service gives a STABLE way to reach pods regardless of restarts.
It also exposes the app OUTSIDE the cluster (to your laptop browser).

---

```yaml
apiVersion: v1
kind: Service
```

WHAT IT DOES:
  Service is a core Kubernetes resource, so apiVersion is "v1".
  kind: Service tells Kubernetes this creates a networking Service.

---

```yaml
metadata:
  name: hsf-app-service
  namespace: supply-chain-demo
  labels:
    app: hsf-app
```

WHAT EACH LINE DOES:

  name: hsf-app-service
    The name of this Service.
    Used in kubectl commands: "kubectl get service hsf-app-service -n supply-chain-demo"

  namespace: supply-chain-demo
    MUST match the namespace where your pods are running.
    If the Service is in a different namespace than the pods,
    it cannot find them and traffic routing fails.

  labels: app: hsf-app
    Labels this Service for identification.

CONNECTS TO:
  namespace.yaml: namespace name must match
  deployment.yaml: namespace must match so Service can find the pods

---

```yaml
spec:
  type: NodePort
```

WHAT IT DOES:
  Defines HOW this Service exposes the app.
  NodePort = expose the app on a port on every node in the cluster.
  Since k3d runs on your laptop, this makes the app accessible at localhost:30080.

THREE types of Services:
  ClusterIP (default) = only accessible inside the cluster
  NodePort = accessible from outside the cluster on a specific port
  LoadBalancer = creates a cloud load balancer (cloud only, not useful locally)

WHY NodePort for this project:
  We need to access the app from our laptop browser.
  NodePort maps a cluster port directly to a laptop port.
  When you created the k3d cluster with "--port 30080:30080@loadbalancer",
  that connected the k3d cluster port 30080 to your laptop port 30080.

REAL WORLD EXAMPLE:
  The cluster is a gated building.
  ClusterIP = internal phone extension (only works inside)
  NodePort = a door in the fence with a specific street address

---

```yaml
  selector:
    app: hsf-app
```

WHAT IT DOES:
  This is THE MOST IMPORTANT part of the Service.
  It tells the Service: "Send traffic to pods that have label app=hsf-app"
  The Service finds pods by looking for this label.

WHY this MUST match deployment.yaml:
  deployment.yaml template.metadata.labels has "app: hsf-app"
  That label is stamped on every pod the Deployment creates.
  This Service's selector looks for "app: hsf-app".
  If they match → traffic flows to the pods.
  If they do not match → Service cannot find any pods → connection refused.

REAL WORLD EXAMPLE:
  The Service is a receptionist at a company.
  When a customer (HTTP request) arrives, the receptionist asks:
  "Which department handles this?" (selector: app: hsf-app)
  Then routes the customer to the right employee (pod).

CONNECTS TO:
  deployment.yaml: template.metadata.labels app: hsf-app — MUST MATCH
  The pod must have this label for the Service to find it.

---

```yaml
  ports:
    - name: http
      protocol: TCP
      port: 8000
      targetPort: 8000
      nodePort: 30080
```

WHAT EACH LINE DOES:

  name: http
    A name for this port mapping. Just a label for readability.

  protocol: TCP
    The network protocol. TCP is standard for web traffic.

  port: 8000
    The port the SERVICE listens on INSIDE the cluster.
    Other pods in the cluster could reach this Service on port 8000.

  targetPort: 8000
    The port on the POD to forward traffic to.
    Traffic arriving at Service port 8000 is forwarded to pod port 8000.
    MUST match containerPort in deployment.yaml AND the CMD in Dockerfile.

  nodePort: 30080
    The port exposed on EVERY NODE in the cluster.
    This is what you access from your laptop: http://localhost:30080
    Valid range: 30000-32767 (Kubernetes rule)
    MUST match the port you specified when creating the k3d cluster:
    "k3d cluster create mycluster --port 30080:30080@loadbalancer"

HOW TRAFFIC FLOWS (the full path):
  You type: curl http://localhost:30080/health

  Step 1: localhost:30080
    Your laptop sends request to port 30080 on your machine.

  Step 2: k3d loadbalancer
    k3d's loadbalancer receives it (you set --port 30080:30080 when creating cluster)
    Routes it into the cluster on port 30080.

  Step 3: nodePort: 30080
    The Service receives it on nodePort 30080.

  Step 4: port: 8000
    Service internally maps 30080 → 8000.

  Step 5: targetPort: 8000
    Service forwards to the pod on port 8000.

  Step 6: Pod
    uvicorn receives the request on port 8000.
    Returns {"status": "healthy"}.

CONNECTS TO:
  deployment.yaml containerPort: 8000 — MUST match targetPort
  Dockerfile CMD "--port", "8000" — MUST match targetPort
  Dockerfile EXPOSE 8000 — documents the same port
  k3d cluster creation "--port 30080:30080@loadbalancer" — MUST match nodePort

---
---

## FILE 7: .github/workflows/pipeline.yml
## Location: .github/workflows/pipeline.yml

---

### What is pipeline.yml?

This is the automation engine.
It is the file that makes everything run automatically.
When you push code to GitHub, GitHub reads this file and follows every instruction.

Think of it as a recipe for robots.
The robot (GitHub Actions runner on your laptop) reads every line and executes it.

---

```yaml
name: Supply Chain Security Pipeline
```

WHAT IT DOES:
  The display name of this workflow.
  This name appears in the GitHub Actions tab in the browser.
  It is purely cosmetic — does not affect behaviour.

---

```yaml
on:
  push:
    branches:
      - main
```

WHAT IT DOES:
  "on" = WHEN should this pipeline trigger?
  "push" = trigger when someone pushes commits.
  "branches: - main" = ONLY trigger when pushing to the "main" branch.

WHY only main?
  If you push to a feature branch (e.g. "feature/login"),
  the pipeline does NOT run.
  Only code that reaches "main" gets built, scanned, signed, and deployed.
  This ensures only reviewed, approved code goes through the full pipeline.

REAL WORLD EXAMPLE:
  Like a conveyor belt that only starts when the "main" button is pressed.
  Pushing to other branches presses other buttons — the belt stays still.

---

```yaml
permissions:
  contents: read
  packages: write
```

WHAT IT DOES:
  Defines what the pipeline is ALLOWED to do with your GitHub account.

  contents: read
    The runner can READ your repository files (checkout code, read YAML files).
    Cannot make commits or change repository settings.

  packages: write
    The runner can PUSH Docker images to GitHub Container Registry (ghcr.io).
    Without this, the "docker push" step would fail with "permission denied".

WHY be specific about permissions?
  Security principle of least privilege.
  Give the pipeline only what it needs, nothing more.
  If the pipeline is compromised, it cannot do unexpected things.

CONNECTS TO:
  Job 1 (build): docker push uses packages: write permission.
  Job 1 (build): docker/login-action uses GITHUB_TOKEN which gets these permissions.

---

```yaml
env:
  IMAGE_BASE: ghcr.io/haseef-ahamed/hsf-app
```

WHAT IT DOES:
  Defines an environment variable available to ALL jobs in this pipeline.
  IMAGE_BASE stores the base image path (without the tag).

WHY define it here and not inside each job?
  DRY principle — Don't Repeat Yourself.
  If the image name changes, you change it in ONE place here.
  Without this, you would have to update it in 5+ places.

HOW it is used:
  In jobs: ${{ env.IMAGE_BASE }}:${{ github.sha }}
  This becomes: ghcr.io/haseef-ahamed/hsf-app:a3f8c91d...

CONNECTS TO:
  Every job that references the image uses ${{ env.IMAGE_BASE }}.
  deployment.yaml: image field matches this base path.

---

## JOB 1: build

```yaml
  build:
    name: 🔨 Build Image
    runs-on: self-hosted
```

WHAT IT DOES:
  "build" = the job ID (used internally to reference this job).
  "name: 🔨 Build Image" = the display name shown in GitHub Actions UI.
  "runs-on: self-hosted" = run this job on YOUR laptop runner (not GitHub's cloud).

WHY self-hosted and not ubuntu-latest?
  "ubuntu-latest" would use GitHub's cloud runner.
  GitHub's cloud runner cannot reach your local k3d cluster.
  "self-hosted" means YOUR laptop runner runs this job.
  Since the runner IS on your laptop, it can run kubectl directly against k3d.

REAL WORLD EXAMPLE:
  runs-on = "which workshop should do this job?"
  "self-hosted" = "my personal workshop at home"
  "ubuntu-latest" = "a rented workshop in the cloud"
  Since your Kubernetes cluster is at home, you need your home workshop.

---

```yaml
    outputs:
      image: ${{ steps.set-image.outputs.image }}
```

WHAT IT DOES:
  Declares that this job PRODUCES an output called "image".
  Other jobs can read this output using: ${{ needs.build.outputs.image }}

WHY outputs exist:
  Jobs run independently, each in their own environment.
  Job 2 needs to know which image to scan.
  Without outputs, Job 2 would have to reconstruct the image name itself.
  Outputs share information cleanly between jobs.

CONNECTS TO:
  steps.set-image.outputs.image — a step below sets this value.
  All downstream jobs use ${{ needs.build.outputs.image }} to get it.

---

```yaml
      - name: Checkout source code
        uses: actions/checkout@v4.2.2
```

WHAT IT DOES:
  Downloads (clones) your repository code onto the runner machine.
  Without this, the runner has no access to your files.
  "uses" means: use a pre-built action from GitHub's marketplace.
  "actions/checkout@v4.2.2" is an official GitHub action for checking out code.

WHY v4.2.2 specifically?
  Pinning to a specific version prevents unexpected changes.
  If GitHub releases v4.3.0 with a breaking change, your pipeline is protected.
  This is supply chain security for your pipeline itself.

REAL WORLD EXAMPLE:
  The runner starts as an empty folder.
  Checkout = "go to the library (GitHub) and bring all the books (code) here"

---

```yaml
      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3.4.0
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
```

WHAT IT DOES:
  Authenticates Docker to push/pull from ghcr.io.
  Without login, "docker push" would say "permission denied".

  registry: ghcr.io
    Tell Docker we are logging into GitHub's container registry.

  username: ${{ github.actor }}
    ${{ github.actor }} = the person or bot who triggered the pipeline.
    In your case: "Haseef-Ahamed" (your GitHub username).
    This is a built-in GitHub Actions variable — no setup needed.

  password: ${{ secrets.GITHUB_TOKEN }}
    GITHUB_TOKEN = a temporary access token automatically created by GitHub
    for every pipeline run. It expires after the run finishes.
    No manual setup needed — GitHub creates it automatically.
    "secrets.GITHUB_TOKEN" reads it from the secrets vault.

WHY not use your actual password?
  Tokens are temporary and scoped (limited permissions).
  Your real password would give full account access — dangerous.

CONNECTS TO:
  permissions: packages: write — this permission is what GITHUB_TOKEN
  uses to push images. The token inherits the permissions defined above.

---

```yaml
      - name: Build Docker image
        run: |
          docker build \
            -t ${{ env.IMAGE_BASE }}:${{ github.sha }} \
            -t ${{ env.IMAGE_BASE }}:latest \
            .
          echo "Built: ${{ env.IMAGE_BASE }}:${{ github.sha }}"
```

WHAT IT DOES:
  "run:" executes shell commands directly (not a pre-built action).
  "docker build" builds a Docker image from the Dockerfile.

  -t ${{ env.IMAGE_BASE }}:${{ github.sha }}
    Tags the image with the commit SHA.
    ${{ github.sha }} = the full Git commit hash (40 characters).
    Example: ghcr.io/haseef-ahamed/hsf-app:a3f8c91d2b4e...
    This tag is unique and permanent — links the image to exact code.

  -t ${{ env.IMAGE_BASE }}:latest
    Also tags the same image as "latest".
    Useful for quick testing — "give me the most recent image".

  The dot (.) at the end:
    Tells Docker to use the current directory as the build context.
    Docker looks for the Dockerfile in this directory.
    The Dockerfile is at the root of the project, so "." works.

  echo "Built: ..."
    Prints a confirmation message in the pipeline logs.
    Useful for debugging and proof of execution.

${{ github.sha }} EXPLAINED:
  This is a GitHub Actions built-in variable.
  It contains the full SHA (hash) of the commit that triggered the pipeline.
  Example value: "a3f8c91d2b4e5f67890abcdef1234567890abcde"
  Every commit has a unique SHA — it is like a fingerprint for that code.

CONNECTS TO:
  deployment.yaml: image field will use this SHA after sed replacement.
  Cosign sign/verify steps: sign and verify this exact image SHA.
  The "." requires the Dockerfile to be at the repository root.

---

```yaml
      - name: Push image to GitHub Container Registry
        run: |
          docker push ${{ env.IMAGE_BASE }}:${{ github.sha }}
          docker push ${{ env.IMAGE_BASE }}:latest
          echo "Pushed: ${{ env.IMAGE_BASE }}:${{ github.sha }}"
```

WHAT IT DOES:
  Uploads both image tags to ghcr.io.
  After this step, the image is available at ghcr.io for:
    - Trivy to scan (Job 2)
    - Cosign to sign (Job 4)
    - Kubernetes to pull and run (Job 6)

WHY push in Job 1 and not later?
  Cosign signs images IN THE REGISTRY — not local images.
  Trivy can scan local images, but scanning from the registry
  confirms the exact image that will be deployed.
  All subsequent jobs work with the same registry image.

---

```yaml
      - name: Set image output for downstream jobs
        id: set-image
        run: |
          echo "image=${{ env.IMAGE_BASE }}:${{ github.sha }}" \
            >> $GITHUB_OUTPUT
          echo "Image reference set for downstream jobs"
```

WHAT IT DOES:
  Sets the "image" output value that other jobs can read.
  "id: set-image" = gives this step an ID so outputs can reference it.
  "$GITHUB_OUTPUT" = a special file GitHub Actions reads to get step outputs.
  "echo key=value >> $GITHUB_OUTPUT" = the correct way to set an output.

HOW OTHER JOBS USE IT:
  ${{ needs.build.outputs.image }}
  This reads the "image" output from the "build" job.
  It expands to: ghcr.io/haseef-ahamed/hsf-app:a3f8c91d...

CONNECTS TO:
  The "outputs:" section at the top of the build job definition.
  Every downstream job (scan-image, sign-image, verify-signature, deploy)
  uses needs.build.outputs.image to reference this exact image.

---

## JOB 2: scan-image (Gate 1)

```yaml
  scan-image:
    name: 🔍 Scan Image — Gate 1
    runs-on: self-hosted
    needs: build
```

WHAT IT DOES:
  "needs: build" = DO NOT START this job until the "build" job SUCCEEDS.
  If "build" fails, this job is automatically SKIPPED.
  The chain: build → scan-image → scan-iac → sign-image → verify → deploy

WHY needs: build?
  Two reasons:
  1. We need the image to exist in ghcr.io before we can scan it.
  2. We need the image reference (output) from the build job.

REAL WORLD EXAMPLE:
  The quality inspector (Job 2) cannot inspect a product
  until the factory (Job 1) actually makes the product.
  "needs: build" enforces this natural dependency.

---

```yaml
      - name: Scan image for CVE vulnerabilities (Trivy)
        run: |
          echo "================================================"
          echo "  GATE 1: Trivy Image Vulnerability Scan"
          echo "  Image: ${{ needs.build.outputs.image }}"
          echo "================================================"
          trivy image \
            --exit-code 1 \
            --severity CRITICAL \
            --ignore-unfixed \
            --no-progress \
            ${{ needs.build.outputs.image }}
          echo "Gate 1 PASSED — no CRITICAL vulnerabilities found"
```

WHAT EACH FLAG DOES:

  ${{ needs.build.outputs.image }}
    The image to scan — reads the output from Job 1.
    Expands to: ghcr.io/haseef-ahamed/hsf-app:a3f8c91d...

  --exit-code 1
    If Trivy finds CRITICAL vulnerabilities, exit with code 1.
    Exit code 1 = failure in shell.
    GitHub Actions sees exit code 1 → marks step as failed → pipeline stops.
    This is THE LINE that makes Gate 1 actually block the pipeline.
    Without "--exit-code 1", Trivy would just print findings but not fail.

  --severity CRITICAL
    Only scan for CRITICAL severity vulnerabilities.
    Ignore HIGH, MEDIUM, LOW for this scan.
    Why? To reduce noise. Many images have LOW/MEDIUM CVEs that are
    acceptable risks. CRITICAL ones are genuinely dangerous.

  --ignore-unfixed
    Skip vulnerabilities that have no available fix yet.
    If no fix exists, there is nothing actionable to do about it.
    This focuses the scan on vulnerabilities you can actually fix.

  --no-progress
    Do not show the download progress bar in logs.
    Cleaner, more readable pipeline output.

GATE 1 DECISION LOGIC:
  Trivy finds CRITICAL CVE → exits with code 1 → step fails → job fails
    → scan-iac, sign-image, verify-signature, deploy are ALL SKIPPED
  Trivy finds zero CRITICAL CVEs → exits with code 0 → step passes → next job runs

---

```yaml
      - name: Save Trivy scan report
        if: always()
        run: |
          mkdir -p security
          trivy image \
            --format json \
            --output security/trivy-report.json \
            ...
```

WHAT IT DOES:
  Saves the full scan report as a JSON file.
  "if: always()" = run this step NO MATTER WHAT — even if the previous step failed.

WHY always()?
  If Gate 1 finds CRITICAL vulnerabilities and fails the pipeline,
  you still want the report to know WHAT was found.
  Without "always()", this step would be skipped when the scan fails —
  exactly when you most need the report.

CONNECTS TO:
  security/trivy-report.json in your repository.
  This becomes evidence that scanning was performed.
  Required project deliverable.

---

## JOB 3: scan-iac (Gate 2)

```yaml
  scan-iac:
    name: 📋 Scan IaC — Gate 2
    runs-on: self-hosted
    needs: scan-image
```

WHAT IT DOES:
  "needs: scan-image" = only run if Gate 1 (scan-image) passed.
  If Gate 1 blocked a vulnerable image, this job is skipped too.

---

```yaml
      - name: Scan Kubernetes YAML for misconfigurations (Trivy)
        run: |
          trivy config \
            --exit-code 1 \
            --severity CRITICAL,HIGH \
            ./k8s/
```

WHAT EACH PART DOES:

  trivy config
    "config" subcommand = scan configuration files (not container images).
    Trivy changes mode: instead of scanning packages, it reads YAML files.

  --exit-code 1
    Same as Gate 1 — fail the pipeline if findings are found.

  --severity CRITICAL,HIGH
    Block on BOTH CRITICAL and HIGH misconfigurations.
    Stricter than the image scan because YAML misconfigs are directly
    in your control — you can fix them by editing the YAML file.

  ./k8s/
    Scan ALL files in the k8s/ folder.
    Finds: namespace.yaml, deployment.yaml, service.yaml
    Checks each one against the misconfiguration rules.

WHAT TRIVY CHECKS (examples):
  Is the container running as root? (KSV-0001) — HIGH
  Is readOnlyRootFilesystem set? (KSV-0014) — HIGH
  Is allowPrivilegeEscalation: false? (KSV-0015) — HIGH
  Is a pod-level securityContext set? (KSV-0118) — HIGH

This is why deployment.yaml has all those securityContext settings.
Each security setting in deployment.yaml maps to a specific Trivy check here.

DEPENDENCY CHAIN EXAMPLE:
  deployment.yaml securityContext → makes Trivy happy → Gate 2 passes
  If you remove securityContext from deployment.yaml → Gate 2 fails → no deploy

---

## JOB 4: sign-image (Gate 3)

```yaml
  sign-image:
    name: ✍️ Sign Image — Gate 3
    runs-on: self-hosted
    needs: [scan-iac, build]
```

WHAT IT DOES:
  "needs: [scan-iac, build]" = wait for BOTH scan-iac AND build to finish.
  Two jobs listed in needs because:
    scan-iac = must have passed Gate 2 before signing
    build = needs the image output (${{ needs.build.outputs.image }})
  If you only listed scan-iac, you could not access build outputs.

---

```yaml
      - name: Sign image with Cosign
        env:
          COSIGN_PASSWORD: ${{ secrets.COSIGN_PASSWORD }}
        run: |
          echo "Signing: ${{ needs.build.outputs.image }}"
          echo "${{ secrets.COSIGN_KEY }}" > /tmp/cosign.key
          cosign sign \
            --key /tmp/cosign.key \
            --yes \
            ${{ needs.build.outputs.image }}
          rm -f /tmp/cosign.key
          echo "Image signed successfully"
```

WHAT EACH LINE DOES:

  env: COSIGN_PASSWORD: ${{ secrets.COSIGN_PASSWORD }}
    Makes COSIGN_PASSWORD available as an environment variable.
    Cosign reads this automatically when using a key file.
    It needs the password to decrypt the encrypted private key.

  echo "${{ secrets.COSIGN_KEY }}" > /tmp/cosign.key
    Reads the COSIGN_KEY secret and writes it to a temporary file.
    ${{ secrets.COSIGN_KEY }} contains the full contents of your cosign.key.
    Writing to /tmp because it is a temporary directory.
    "/tmp" = the system's temporary folder — cleared on restart.
    "> /tmp/cosign.key" = write (overwrite) that content to the file.

  cosign sign --key /tmp/cosign.key --yes ...
    Signs the image using the private key file.
    "--yes" = skip the interactive confirmation prompt (needed in automation).
    Cosign contacts ghcr.io, reads the image digest,
    signs it with the private key, stores the signature back in ghcr.io.

  rm -f /tmp/cosign.key
    Immediately deletes the private key file.
    "-f" = force (do not error if file does not exist).
    The key is only needed for the sign command.
    Keeping it on disk longer is a security risk.
    This is a security best practice: use-and-destroy.

CONNECTS TO:
  GitHub Secrets COSIGN_KEY — stores the private key
  GitHub Secrets COSIGN_PASSWORD — stores the key password
  security/cosign.pub — the matching public key committed to the repo
  verify-signature job below — uses the public key to verify what this step signed

---

## JOB 5: verify-signature (Gate 4)

```yaml
  verify-signature:
    name: ✅ Verify Signature — Gate 4
    runs-on: self-hosted
    needs: [sign-image, build]
```

WHAT IT DOES:
  "needs: [sign-image, build]" = wait for signing to finish AND access build outputs.

---

```yaml
      - name: Verify image signature (Cosign)
        run: |
          cosign verify \
            --key security/cosign.pub \
            ${{ needs.build.outputs.image }}
          echo "Signature verified — image is authentic"
```

WHAT IT DOES:
  --key security/cosign.pub
    Use the PUBLIC key from your repository (committed to security/cosign.pub).
    Public key = safe to commit, safe to share.
    Cosign uses this to check the signature.

  ${{ needs.build.outputs.image }}
    The image to verify (same one that was signed in Job 4).

HOW VERIFICATION WORKS:
  1. Cosign contacts ghcr.io and looks for the signature attached to this image.
  2. Finds the signature stored by the sign step.
  3. Uses the public key to decrypt the signature → gets the original digest.
  4. Compares decrypted digest to the current image digest.
  5. If they MATCH: image is authentic ✓
  6. If they DO NOT MATCH: image was tampered ✗ → pipeline stops

WHY verify after signing in the SAME pipeline run?
  To prove the gate mechanism works.
  But more importantly: in a real scenario, the verify step would run
  in a SEPARATE deployment pipeline, or be enforced by a Kubernetes
  admission controller. Even in the same pipeline, it catches:
    - Key misconfiguration (wrong key)
    - Signing failures that silently succeeded
    - Registry tampering between push and deploy

GATE 4 DECISION:
  Signature valid → exit code 0 → step passes → deploy job runs
  No signature / invalid signature → exit code 1 → step fails → deploy NEVER runs

---

## JOB 6: deploy

```yaml
  deploy:
    name: 🚀 Deploy to Kubernetes
    runs-on: self-hosted
    needs: [verify-signature, build]
```

WHAT IT DOES:
  "needs: [verify-signature, build]" = only deploy after ALL gates passed.
  Listing "build" gives access to build outputs for the image reference.
  By the time this runs:
    ✓ Gate 1: Trivy found zero CRITICAL CVEs
    ✓ Gate 2: Trivy found zero HIGH/CRITICAL YAML misconfigs
    ✓ Gate 3: Image was successfully signed
    ✓ Gate 4: Signature was verified as authentic

---

```yaml
      - name: Deploy verified image to Kubernetes
        run: |
          kubectl apply -f k8s/namespace.yaml
          sed "s|IMAGE_TAG|${{ github.sha }}|g" \
            k8s/deployment.yaml | kubectl apply -f -
          kubectl apply -f k8s/service.yaml
          kubectl rollout status deployment/hsf-app \
            --namespace supply-chain-demo \
            --timeout=120s
```

WHAT EACH LINE DOES:

  kubectl apply -f k8s/namespace.yaml
    Creates (or updates) the namespace.
    "apply" = create if not exists, update if already exists.
    "Unchanged" message = already exists and nothing changed. That is fine.

  sed "s|IMAGE_TAG|${{ github.sha }}|g" k8s/deployment.yaml | kubectl apply -f -
    This is the most complex line. Let us break it down:

    sed "s|IMAGE_TAG|${{ github.sha }}|g" k8s/deployment.yaml
      sed = stream editor — processes text.
      "s|IMAGE_TAG|a3f8c91d...|g" = replace IMAGE_TAG with the commit SHA.
      k8s/deployment.yaml = the file to process.
      Output: the deployment YAML with IMAGE_TAG replaced by the real SHA.

    | (pipe symbol)
      Sends the output of sed directly to the next command.
      Nothing is written to disk.

    kubectl apply -f -
      "kubectl apply" = apply a Kubernetes manifest.
      "-f -" = read from stdin (the pipe, not a file).
      So kubectl reads the modified YAML and applies it.

    WHY not just sed -i (edit file directly)?
      If you edit the file, it gets committed with a hardcoded SHA.
      Next pipeline run, the SHA would be wrong.
      Using the pipe keeps deployment.yaml clean with IMAGE_TAG placeholder.

  kubectl apply -f k8s/service.yaml
    Creates or updates the Kubernetes Service.

  kubectl rollout status deployment/hsf-app --namespace supply-chain-demo --timeout=120s
    Waits for the deployment to complete.
    "rollout status" = watch the deployment until all pods are running.
    "--timeout=120s" = wait maximum 2 minutes, then fail.
    If the pod does not start within 2 minutes:
      - Might be the image pull failing (wrong tag, wrong permissions)
      - Might be resource limits too tight
      - Might be a startup crash
    The pipeline fails here with a clear error message.

CONNECTS TO:
  deployment.yaml: name: hsf-app must match "deployment/hsf-app" here.
  namespace.yaml: name: supply-chain-demo must match "--namespace supply-chain-demo".
  IMAGE_TAG in deployment.yaml must be exactly "IMAGE_TAG" — sed looks for this string.

---

```yaml
      - name: Show deployment result
        run: |
          echo "╔══════════════════════════════════════════╗"
          echo "║   SUPPLY CHAIN PIPELINE — ALL PASSED     ║"
          ...
          kubectl get pods -n supply-chain-demo
          curl -s http://localhost:30080/health
```

WHAT IT DOES:
  Prints a summary box with all 4 gates marked as passed.
  Runs "kubectl get pods" to show the running pod in the logs.
  Runs "curl" to confirm the app is responding at localhost:30080.
  This final curl is proof-of-life — the deployed app is actually serving traffic.

---
---

## THE COMPLETE DEPENDENCY MAP

How all files connect to each other:

```
Dockerfile
  └── FROM python:3.11-slim ──────────────── affects Trivy scan (Gate 1)
  └── EXPOSE 8000 ─────────────────────────── must match service.yaml targetPort
  └── CMD ["uvicorn"... "--port" "8000"] ──── must match containerPort
  └── USER appuser (id: 1000) ───────────────── must match runAsUser: 1000

app/main.py
  └── @app.get("/health") ──────────────────── must match livenessProbe path
  └── @app.get("/health") ──────────────────── must match readinessProbe path

app/requirements.txt
  └── fastapi==0.109.0 ─────────────────────── scanned by Trivy in Gate 1
  └── uvicorn==0.27.0 ──────────────────────── scanned by Trivy in Gate 1

k8s/namespace.yaml
  └── name: supply-chain-demo ──────────────── must match all other k8s files
                                               must match pipeline --namespace flag

k8s/deployment.yaml
  └── namespace: supply-chain-demo ─────────── must match namespace.yaml name
  └── selector: app: hsf-app ────────────────── must match template labels
  └── template labels: app: hsf-app ─────────── must match service selector
  └── image: .../hsf-app:IMAGE_TAG ───────────── IMAGE_TAG replaced by pipeline sha
  └── containerPort: 8000 ────────────────────── must match service targetPort
  └── securityContext (full) ─────────────────── required for Gate 2 to pass
  └── livenessProbe: /health port: 8000 ─────── must match main.py endpoint
  └── readinessProbe: /health port: 8000 ─────── must match main.py endpoint

k8s/service.yaml
  └── namespace: supply-chain-demo ─────────── must match namespace.yaml name
  └── selector: app: hsf-app ────────────────── must match deployment pod labels
  └── targetPort: 8000 ──────────────────────── must match containerPort
  └── nodePort: 30080 ────────────────────────── must match k3d cluster port mapping

pipeline.yml
  └── env: IMAGE_BASE ────────────────────────── base path for all image references
  └── github.sha ──────────────────────────────── replaces IMAGE_TAG in deployment
  └── needs: build → scan-image → scan-iac
                → sign-image → verify-signature → deploy
  └── --exit-code 1 ──────────────────────────── makes Gate 1 and Gate 2 blocking
  └── COSIGN_KEY secret ──────────────────────── private key from GitHub Secrets
  └── COSIGN_PASSWORD secret ─────────────────── key password from GitHub Secrets
  └── security/cosign.pub ────────────────────── public key committed to repo
```

---
---

## THE FLOW IN ONE STORY

You type: git push origin main

1. GitHub sees the push to "main" branch.
2. GitHub wakes up your self-hosted runner on your laptop.
3. Runner starts Job 1 (Build Image):
   - Downloads your code from GitHub
   - Logs into ghcr.io
   - Runs "docker build" using your Dockerfile
   - Tags the image with the commit SHA
   - Pushes the image to ghcr.io
   - Saves the image reference as an output

4. Job 2 (Gate 1 — Trivy Image Scan) starts:
   - Downloads Trivy's CVE database
   - Pulls the image from ghcr.io
   - Checks every package against known vulnerabilities
   - ZERO CRITICAL CVEs found → Gate 1 PASSES
   - Saves report to security/trivy-report.json

5. Job 3 (Gate 2 — Trivy IaC Scan) starts:
   - Reads k8s/deployment.yaml, k8s/service.yaml, k8s/namespace.yaml
   - Checks for dangerous configurations
   - ZERO misconfigurations found (because of securityContext settings)
   - Gate 2 PASSES

6. Job 4 (Gate 3 — Sign Image) starts:
   - Reads COSIGN_KEY from GitHub Secrets
   - Writes it to /tmp/cosign.key
   - Cosign signs the image in ghcr.io
   - Deletes /tmp/cosign.key immediately
   - Signature stored in ghcr.io alongside the image

7. Job 5 (Gate 4 — Verify Signature) starts:
   - Reads security/cosign.pub from the repository
   - Cosign verifies the signature against the public key
   - Signature is VALID → Gate 4 PASSES

8. Job 6 (Deploy) starts:
   - Creates the supply-chain-demo namespace
   - Replaces IMAGE_TAG in deployment.yaml with the commit SHA
   - Applies all Kubernetes manifests
   - Kubernetes pulls the signed image from ghcr.io
   - Pod starts running
   - Waits for rollout to complete
   - Confirms app is alive at localhost:30080/health

Total time: ~2 minutes

You type: curl http://localhost:30080/health
You get: {"status":"healthy","service":"supply-chain-demo"}

Your code is running. It was scanned, signed, verified, and deployed.
All automatically. All provably secure.