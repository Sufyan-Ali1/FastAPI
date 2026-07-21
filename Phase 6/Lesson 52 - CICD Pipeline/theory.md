# Lesson 52 — CI/CD Pipeline

> **Goal of this lesson:** Automate the whole path from a commit to production: **test → build → deploy**. Build on Lesson 43's CI with a full **GitHub Actions** pipeline that runs tests, builds a Docker image, and deploys — safely and repeatably, on every push to `main`.
>
> The deliverable is a real, multi-job workflow (`ci-cd.yml`) plus a small app and tests. The test stage is verified locally; the pipeline is validated end to end.

---

## 1. CI vs CD vs CD

Three overlapping terms, often abbreviated together as "CI/CD":

| Term | Means | You automate |
|---|---|---|
| **CI — Continuous Integration** | Every change is automatically **tested** on a clean machine | test, lint, coverage (Lesson 43) |
| **CD — Continuous Delivery** | Every change is automatically **built and ready to deploy** (a human clicks "release") | build, package, stage |
| **CD — Continuous Deployment** | Every change that passes automatically **deploys to production** | the full path, no human step |

The distinction between the two "CD"s: **Delivery** stops at "ready to ship" (deploy is a manual approval); **Deployment** goes all the way to production automatically. Both build on CI.

> 🔑 **CI** = automated testing on every change. **CD** = automated build + deploy (Delivery = deploy on approval; Deployment = deploy automatically). CI/CD turns "hope it works" into a repeatable, gated pipeline.

---

## 2. Why Automate Deployment?

Manual deployment — SSH in, pull code, restart, hope — is slow, error-prone, and unrepeatable. An automated pipeline gives you:

- **Repeatability** — the same steps every time; no "did I remember to run migrations?"
- **Safety** — deploy only if tests pass; automatic rollback on failure.
- **Speed** — a commit reaches production in minutes, not a manual afternoon.
- **Auditability** — every deploy is logged, tied to a commit, and reviewable.
- **Confidence** — small, frequent, tested deploys beat rare, scary big-bang releases.

> 🔑 An automated pipeline makes deployment **boring** — repeatable, tested, and reversible. Boring deployments are the goal; exciting deployments mean something went wrong.

---

## 3. The Pipeline Stages

A typical FastAPI CI/CD pipeline runs these stages, each gating the next:

```
push to main
   │
   ▼
1. TEST     ── install deps, run pytest (+ coverage, lint)   ── ❌ fail? STOP
   │ ✅
   ▼
2. BUILD    ── build the Docker image, tag it, push to a registry
   │ ✅
   ▼
3. MIGRATE  ── run `alembic upgrade head` against production DB
   │ ✅
   ▼
4. DEPLOY   ── release the new image; platform health-checks it
   │ ✅
   ▼
5. VERIFY   ── confirm health; roll back if unhealthy
```

Each stage only runs if the previous one succeeded. A failing test **never** reaches build or deploy — that's the whole point.

---

## 4. Multi-Job GitHub Actions Workflow

Lesson 43 had one `test` job. A CI/CD pipeline has **multiple jobs** that depend on each other via **`needs`**. The `deploy` job runs **only after** `test` passes, and **only on `main`**:

```yaml
name: CI/CD

on:
  push:
    branches: [main]        # deploy pipeline runs on main
  pull_request:             # PRs run tests only (no deploy)

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: pytest --cov=. --cov-fail-under=80

  deploy:
    needs: test                                  # only if `test` passed
    if: github.ref == 'refs/heads/main'          # only on main, not PRs
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "build image, push, migrate, deploy..."
```

- **`needs: test`** — the `deploy` job waits for `test` and runs only if it succeeded.
- **`if: github.ref == 'refs/heads/main'`** — tests run on every PR, but **deploy only on `main`**.
- Jobs run on separate clean machines; they don't share state (pass artifacts explicitly if needed).

> 🔑 **`needs`** chains jobs so deploy runs only after tests pass; **`if`** conditions restrict deploy to the `main` branch. PRs get tested; only merged code deploys.

---

## 5. Secrets in CI

The pipeline needs credentials — a registry password, a deploy token, `SECRET_KEY` — but you **never hardcode them** (Lesson 47). GitHub stores them as **encrypted secrets** (repo/org/environment settings), and workflows reference them via `${{ secrets.NAME }}`:

```yaml
      - name: Log in to the registry
        run: docker login -u ${{ secrets.REGISTRY_USER }} -p ${{ secrets.REGISTRY_TOKEN }}
      - name: Deploy
        env:
          DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}
        run: ./deploy.sh
```

Secrets are **masked** in logs (they show as `***`) and never exposed to workflows triggered by forks. Set them in **Settings → Secrets and variables → Actions**.

> 🔑 CI credentials live in **GitHub Secrets**, referenced as `${{ secrets.X }}` — never in the workflow file. They're encrypted, masked in logs, and set in repo settings.

---

## 6. Building & Pushing the Image in CI

The build stage turns your code into a deployable **Docker image** (Lesson 49) and pushes it to a **registry** (Docker Hub, GitHub Container Registry, AWS ECR) tagged with the commit:

```yaml
  build:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
```

Tagging with **`github.sha`** (the commit hash) means every image is traceable to an exact commit — and rolling back is "deploy the previous image tag."

---

## 7. The Deploy Step

*How* you deploy depends on your platform (Lesson 51):

| Target | Deploy step in CI |
|---|---|
| **PaaS (Render/Railway)** | Often auto-deploys on push, or call a deploy hook/API |
| **Fly.io** | `flyctl deploy` with a `FLY_API_TOKEN` secret |
| **Cloud Run / AWS** | Official actions (`google-github-actions/deploy-cloudrun`, AWS actions) push the image and release |
| **VPS** | SSH in and pull/restart (an `appleboy/ssh-action`), or a webhook |

The deploy step should also **run migrations** (`alembic upgrade head`) against the production database before or as part of the release, and rely on the platform's **health check** to confirm the new version is good.

> 🔑 The deploy step is platform-specific but always: **push the image / trigger the platform → run migrations → let the platform health-check the new version**, with rollback on failure.

---

## 8. Environments, Approvals & Safety

For production safety, GitHub Actions offers **Environments** (e.g. `production`) with protections:

- **Required reviewers** — a human must approve before the deploy job runs (turning Continuous Deployment into gated Delivery).
- **Environment secrets** — production credentials scoped to that environment.
- **Wait timers / branch restrictions** — extra guardrails.

```yaml
  deploy:
    needs: [test, build]
    environment: production        # can require manual approval
    runs-on: ubuntu-latest
    steps: ...
```

Combined with **zero-downtime rolling deploys** and **automatic rollback** (Lesson 51), this makes production releases safe: tested, gated, health-checked, and reversible.

> 🔑 Use a protected **`environment`** for production to add manual approval and scoped secrets. Deploys should be **zero-downtime** and **auto-rollback** on a failed health check.

---

## 9. Real-World Use Case — The Auction API Pipeline

A developer opens a PR on the auction API:

1. **CI runs on the PR** — pytest + coverage on a clean machine. A red check **blocks the merge** (Lesson 43).
2. The PR is reviewed and **merged to `main`**.
3. The **CI/CD pipeline fires on `main`**: tests pass → the Docker image is **built and pushed** to the registry tagged with the commit SHA → **`alembic upgrade head`** runs against the production database → the new image is **deployed** to Cloud Run.
4. Cloud Run **health-checks** `/health`, shifts traffic to the new version, and retires the old one — **zero downtime**. If the health check fails, traffic stays on the old version (**automatic rollback**).
5. The whole thing took ~4 minutes, is logged, and is tied to an exact commit.

No SSH, no manual steps, no "hope it works." That's a production CI/CD pipeline — the culmination of everything in Phase 6.

---

## 10. Mini Task

This lesson ships a full pipeline plus an app and tests.

1. Read `ci-cd.yml` — note the **`test`**, **`build`**, and **`deploy`** jobs, the **`needs`** chain, and the **`if: github.ref == 'refs/heads/main'`** condition.
2. Run the **test stage locally** (what CI runs): `pytest -v` → it passes, exactly as the pipeline's `test` job would.
3. Trace the flow: a PR runs only `test`; a push to `main` runs `test → build → deploy`.
4. **Experiment (conceptually):**
   - Identify which steps use `${{ secrets.X }}` and why they can't be hardcoded.
   - Add a `lint` step (e.g. `ruff`) to the test job.
   - Point the deploy job at a platform from Lesson 51 (Fly `flyctl deploy`, Cloud Run action, etc.).
5. **Bonus:** Add a `production` environment with a required reviewer so deploys need manual approval.

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Deploying even when tests fail | Gate deploy with `needs: test`. |
| Deploying from every branch/PR | Restrict with `if: github.ref == 'refs/heads/main'`. |
| Hardcoding credentials in the workflow | Use `${{ secrets.X }}`; set them in repo settings. |
| No migrations step in the pipeline | Run `alembic upgrade head` before/at deploy. |
| Untraceable image tags (`:latest` only) | Tag with the commit SHA for traceability and rollback. |
| No health check / rollback | Rely on the platform's health check; roll back on failure. |
| No approval gate for production | Use a protected `environment` with required reviewers. |

---

## 12. Key Takeaways

- **CI** automates testing; **CD** automates build + deploy (Delivery = on approval, Deployment = automatic). CI/CD makes releases repeatable, safe, and fast.
- A pipeline runs **test → build → migrate → deploy → verify**, each stage gating the next; a failing test never reaches deploy.
- In **GitHub Actions**, chain jobs with **`needs`** and restrict deploy to `main` with **`if: github.ref == 'refs/heads/main'`**.
- Store credentials in **GitHub Secrets** (`${{ secrets.X }}`) — never in the workflow; they're masked in logs.
- **Build a Docker image**, tag it with the **commit SHA**, push to a registry; deploy via platform-specific actions.
- Always **run migrations** at deploy and rely on the platform's **health check + rollback**.
- Protect production with a gated **`environment`** (manual approval, scoped secrets).

---

## ➡️ Next Lesson

**Lesson 53 — Monitoring & Observability**
- Health check endpoints and uptime monitoring
- Metrics (Prometheus + Grafana) and error tracking (Sentry)
- OpenTelemetry tracing
