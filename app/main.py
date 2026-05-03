from fastapi import FastAPI
import os

app = FastAPI(
    title="Supply Chain Security Demo",
    description="Demo app for supply chain security pipeline",
    version="1.0.0"
)

@app.get("/")
def root():
    return {
        "message": "Supply Chain Security Pipeline — Demo App",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "supply-chain-demo"
    }

@app.get("/info")
def info():
    return {
        "app": "FastAPI Supply Chain Demo",
        "environment": os.getenv("APP_ENV", "local, Self Hosted"),
        "description": "Secured by Trivy scanning and Cosign signing"
    }
