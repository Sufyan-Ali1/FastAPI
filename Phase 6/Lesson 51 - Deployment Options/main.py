"""
Lesson 51 - Deployment Options (the app to deploy)
--------------------------------------------------
A minimal, deploy-ready FastAPI app. It reads config from the environment
(Lesson 45) and exposes a health check - the two things every deployment
platform needs. The Procfile / render.yaml / fly.toml in this folder show how
different platforms run this same app.
"""

import os

from fastapi import FastAPI

app = FastAPI(title="Lesson 51 - Deployable API")


@app.get("/")
def root():
    return {
        "message": "Deployable anywhere.",
        "environment": os.getenv("ENVIRONMENT", "dev"),
        "database_configured": bool(os.getenv("DATABASE_URL")),
    }


@app.get("/health")
def health():
    # Platforms poll this to route traffic only to healthy instances.
    return {"status": "ok"}
