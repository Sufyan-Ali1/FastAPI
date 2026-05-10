"""
Lesson 2 — Installation & Project Setup
---------------------------------------
This file is intentionally similar to Lesson 1.
The focus of THIS lesson is the SETUP, not the code.

Setup checklist (do these once inside this folder):

  1. Create a virtual environment:
        python -m venv venv

  2. Activate it:
        Windows (PowerShell):    venv\\Scripts\\Activate.ps1
        Windows (Git Bash/cmd):  venv\\Scripts\\activate
        macOS / Linux:           source venv/bin/activate

  3. Install FastAPI + Uvicorn:
        pip install fastapi uvicorn

  4. Freeze dependencies (so others can reproduce your env):
        pip freeze > requirements.txt

  5. Run the server:
        uvicorn main:app --reload

  6. Open in browser:
        http://127.0.0.1:8000/         -> root message
        http://127.0.0.1:8000/health   -> health check (common in real APIs)
        http://127.0.0.1:8000/docs     -> Swagger UI (auto-generated)
"""

from fastapi import FastAPI


app = FastAPI(
    title="Lesson 2 - Setup Demo",
    description="Confirms the environment is installed correctly.",
    version="1.0.0",
)


@app.get("/")
def root():
    return {"message": "Setup complete! FastAPI is running."}


# A "health check" endpoint is a real-world convention.
# Cloud platforms (AWS, GCP, Kubernetes) hit this URL to verify the app is alive.
@app.get("/health")
def health_check():
    return {"status": "ok"}
