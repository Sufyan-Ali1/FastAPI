"""
Lesson 33 - CORS (Cross-Origin Resource Sharing)
------------------------------------------------
A runnable app with CORSMiddleware configured, so you can inspect the exact
CORS headers a browser looks for.

Try (simulating what a browser sends via the Origin header):

    # Allowed origin -> response carries Access-Control-Allow-Origin
    curl -i -H "Origin: http://localhost:3000" http://127.0.0.1:8000/api/data

    # Preflight for a DELETE with an auth header (the browser sends this
    # automatically before the real request):
    curl -i -X OPTIONS http://127.0.0.1:8000/api/data \
      -H "Origin: http://localhost:3000" \
      -H "Access-Control-Request-Method: DELETE" \
      -H "Access-Control-Request-Headers: authorization"

    # A disallowed origin -> no Access-Control-Allow-Origin (browser blocks it)
    curl -i -H "Origin: http://evil.com" http://127.0.0.1:8000/api/data

No extra installs - CORSMiddleware ships with FastAPI/Starlette.

    pip install fastapi uvicorn

How to run (from inside this folder):

    uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Lesson 33 - CORS")

# The origins your frontend(s) are served from. In production these come from
# configuration (Lesson 45), not hardcoded, and never include "*" when you use
# credentials.
ALLOWED_ORIGINS = [
    "http://localhost:3000",       # e.g. a local React/Vue dev server
    "https://app.example.com",     # e.g. the deployed frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,        # allow cookies / Authorization cross-origin
    allow_methods=["*"],           # GET, POST, PUT, DELETE, OPTIONS, ...
    allow_headers=["*"],           # e.g. Authorization, Content-Type
    expose_headers=["X-Total-Count"],  # response headers the frontend JS may read
    max_age=600,                   # cache the preflight for 10 minutes
)


# The middleware handles OPTIONS preflight and CORS headers for ALL routes
# below automatically - you don't write any CORS logic in the endpoints.
@app.get("/api/data")
def get_data():
    return {"items": [1, 2, 3], "note": "CORS headers were added by the middleware"}


@app.post("/api/data")
def create_data(payload: dict):
    return {"created": payload}


@app.delete("/api/data")
def delete_data():
    return {"deleted": True}


@app.get("/")
def root():
    return {
        "message": "CORS demo. Send an Origin header to see the CORS response headers.",
        "allowed_origins": ALLOWED_ORIGINS,
    }
