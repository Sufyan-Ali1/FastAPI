"""
Lesson 1 — What is FastAPI?
---------------------------
Your very first FastAPI application.

How to run (from inside this folder):

    uvicorn main:app --reload

Then open in your browser:
    http://127.0.0.1:8000/        -> hello message
    http://127.0.0.1:8000/about   -> about info
    http://127.0.0.1:8000/docs    -> auto-generated Swagger UI
    http://127.0.0.1:8000/redoc   -> auto-generated ReDoc
"""

from fastapi import FastAPI


# 1. Create the FastAPI application instance.
#    The metadata below is shown in the auto-generated docs.
app = FastAPI(
    title="My First API",
    description="Learning FastAPI step by step",
    version="1.0.0",
)


# 2. A simple GET endpoint at the root URL "/".
#    The decorator tells FastAPI: "When a GET request hits '/', run this function."
@app.get("/")
def read_root():
    # FastAPI converts this dict to a JSON response automatically.
    return {"message": "Hello, FastAPI!"}


# 3. Another GET endpoint at "/about".
@app.get("/about")
def about():
    return {
        "name": "Your Name",
        "role": "FastAPI Learner",
        "lesson": 1,
    }
