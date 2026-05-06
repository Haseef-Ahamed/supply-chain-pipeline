# Project Overview

## What Is This Project?

This project builds a software supply chain security pipeline — a system
that automatically checks, stamps, and verifies software before it runs
on a server. Every time a developer pushes code, an automated pipeline
runs a series of security checks. If any check fails, the deployment
stops immediately.

The pipeline has four security gates:

```
Gate 1 — Trivy image scan      Blocks images with known vulnerabilities
Gate 2 — Trivy IaC scan        Blocks dangerous Kubernetes configurations
Gate 3 — Cosign signing         Stamps the image with a cryptographic seal
Gate 4 — Cosign verification    Confirms the seal before deployment
```

Only code that passes all four gates reaches the running Kubernetes cluster.

---

## Why Does Supply Chain Security Matter?

In 2020, attackers compromised the SolarWinds build system and injected
malicious code into a software update. Over 18,000 organisations installed
the update without knowing it was compromised. Nobody checked whether the
deployed software matched what was built.

This project builds exactly the system that would have caught that attack:
a pipeline that scans every image for known vulnerabilities, signs it with
a cryptographic key, and verifies the signature before deployment.

### The Problem in Simple Terms

Imagine a medicine factory. The recipe (your code) goes into production.
But what if someone changes the recipe after it is approved? Or adds a
dangerous ingredient without anyone noticing?

Supply chain security is the quality control system that prevents this:
- Scanning = X-ray machine that finds contaminants
- Signing = official seal proving who made it
- Verification = checking the seal before it reaches patients

---

## What Does This Project Demonstrate?

- How to automate security checks in a CI/CD pipeline
- How to use Trivy to find vulnerabilities before deployment
- How to use Cosign to prove image authenticity
- How to block untrusted images from reaching Kubernetes
- How to run a production-grade security pipeline locally

---

## Technology Choices

| Choice | Why |
|--------|-----|
| GitHub | Industry standard, real-world CI/CD experience |
| GitHub Actions | Most widely used CI/CD platform, integrates with ghcr.io |
| Self-hosted runner | Allows pipeline to deploy to local k3d cluster |
| ghcr.io | Native GitHub registry, seamless authentication |
| Trivy | Free, fast, industry standard CVE scanner |
| Cosign | Part of Sigstore, backed by Google and Red Hat |
| k3d | Lightweight Kubernetes that runs on a laptop |
| FastAPI | Minimal Python app, easy to Dockerize |
| python:3.11-slim | Small base image, fewer packages, fewer CVEs |

---

## Key Outcome

After this pipeline runs, you can prove with certainty that the running
application was:

- Built from known, version-controlled source code
- Scanned clean (zero CRITICAL vulnerabilities)
- Checked for Kubernetes misconfigurations
- Signed by the official pipeline with a cryptographic key
- Verified authentic before deployment

All automatically, on every single push to the main branch.

---

## Project Summary (for report)

This project implements a fully automated software supply chain security
pipeline running entirely on a local machine. Using GitHub, GitHub Actions
with a self-hosted runner, Trivy, Cosign, and Kubernetes (k3d), every code
push triggers a 6-job pipeline that enforces four sequential security gates.
Gate 1 blocks images with critical CVEs. Gate 2 blocks dangerous Kubernetes
misconfigurations. Gate 3 cryptographically signs every passing image.
Gate 4 verifies the signature before deployment. Only images that pass all
four gates reach the running Kubernetes cluster — demonstrating the key
practices of modern DevSecOps supply chain security.