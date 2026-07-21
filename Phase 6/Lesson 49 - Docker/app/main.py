"""
Lesson 49 - Docker (the app to containerize)
--------------------------------------------
A minimal FastAPI app. It reads DATABASE_URL and REDIS_URL from the environment
(Lesson 45) so that, under docker-compose, it points at the `db` and `redis`
SERVICE NAMES - not localhost. It does not require them to be up to start, so
`docker run` works standalone too.

Health endpoint included so an orchestrator (or a compose healthcheck) can tell
the app is alive.
"""

import os

from fastapi import FastAPI

app = FastAPI(title="Lesson 49 - Dockerized API")


@app.get("/")
def root():
    return {
        "message": "Running inside a container.",
        # Under compose these resolve to the service names (db, redis).
        "database_url": os.getenv("DATABASE_URL", "not set"),
        "redis_url": os.getenv("REDIS_URL", "not set"),
    }


@app.get("/health")
def health():
    # Liveness probe for orchestrators / compose healthchecks.
    return {"status": "ok"}
