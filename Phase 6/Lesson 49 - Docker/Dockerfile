# Lesson 49 - a multi-stage Dockerfile for a FastAPI app.
#
# Stage 1 (builder) installs dependencies. Stage 2 (runtime) starts clean and
# copies ONLY the installed packages + app code, so build tooling never ships
# in the final image -> smaller, safer.

# ---- Stage 1: builder ------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

# Copy ONLY requirements first so this layer is cached and reused across code
# changes (deps change rarely; code changes often).
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---- Stage 2: runtime (clean, small) --------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Copy only the installed packages from the builder stage.
COPY --from=builder /install /usr/local

# Run as a non-root user (production best practice).
RUN useradd --create-home appuser
USER appuser

# Now copy the application code.
COPY --chown=appuser:appuser app ./app

# Document the port and bind uvicorn to 0.0.0.0 (NOT 127.0.0.1) so the app is
# reachable from outside the container.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
