# Lesson 51 — Deployment Options

> **Goal of this lesson:** Decide **where** to run your FastAPI app in production. Survey the options — a self-managed **VPS**, easy **PaaS** platforms (Render / Railway / Fly.io), managed containers/serverless (**GCP Cloud Run**, **AWS** ECS/Lambda), and **Kubernetes** — understand their trade-offs, and pick the right one for your situation.
>
> This is a **decision** lesson. The deliverables are real deployment configs (`Procfile`, `render.yaml`, `fly.toml`) you'd commit alongside your app, validated for correctness.

---

## 1. The Deployment Spectrum — Control vs Convenience

Every hosting option trades **control** for **convenience**. More control means more you manage (and more that can break); more convenience means the platform handles the ops for you.

```
more control  ◄─────────────────────────────────────────►  more convenience
   Kubernetes    VPS (EC2)    Managed containers    PaaS
   (you run       (you run     (Cloud Run,           (Render,
    everything)    the server)  ECS/Fargate)          Railway, Fly.io)
```

- **PaaS** — you push code; the platform builds, runs, scales, and gives you HTTPS. Easiest.
- **Managed containers / serverless** — you provide a container; the platform runs and autoscales it.
- **VPS / IaaS** — you get a Linux box and manage everything (OS, server, Nginx, TLS, updates).
- **Kubernetes** — you orchestrate many containers across many machines. Most powerful, most complex.

> 🔑 There's no single "best" — pick the point on the **control ↔ convenience** spectrum that matches your team's ops appetite, scale, and budget. Most small/medium apps should start toward the **convenient** end.

---

## 2. VPS — Your Own Linux Server

A **VPS** (Virtual Private Server — DigitalOcean, Linode, AWS EC2, Hetzner) gives you a raw Linux machine. You control everything and manage everything:

Typical setup (pulling together Phase 6):
1. **SSH** into the server, create a non-root user, configure a **firewall** (`ufw`).
2. Install Python, your app, and dependencies (or run your Docker image).
3. Run the app with **Gunicorn + Uvicorn workers** (Lesson 50), supervised by **`systemd`** (auto-restart, start on boot).
4. Put **Nginx** in front for TLS (Let's Encrypt / Certbot) and reverse proxying.
5. Run a managed or self-hosted **PostgreSQL** + **Redis**.
6. Set up log rotation, backups, and OS security updates.

| Pro | Con |
|---|---|
| Full control, no platform limits | **You** manage the OS, security, updates, backups |
| Cheap for steady load | More ops work; easier to misconfigure |
| Predictable, fixed cost | No automatic scaling |

> 🔑 A **VPS** is maximum control and low cost, but **you own all the ops** (security patches, backups, scaling, TLS renewal). Great when you have the skills/time; a burden when you don't.

---

## 3. PaaS — Push-to-Deploy (Render / Railway / Fly.io)

**Platform-as-a-Service** platforms remove almost all ops. You connect a Git repo (or push a container); they build, deploy, give you HTTPS, and often provide managed Postgres/Redis add-ons.

- **Render** — connect a repo; it detects Python or builds your Dockerfile; free TLS, managed Postgres/Redis, health checks. Config via a dashboard or `render.yaml`.
- **Railway** — very fast setup; deploy from GitHub; managed databases; usage-based pricing.
- **Fly.io** — runs your **container** close to users (edge), globally; config in `fly.toml`; good for low latency and persistent apps.

The workflow is roughly: `git push` → the platform builds and deploys → you get a URL with HTTPS. Databases are one-click add-ons; secrets are set in the dashboard as env vars (Lesson 45).

| Pro | Con |
|---|---|
| Almost zero ops; HTTPS + scaling handled | Less control; platform limits |
| Fast from repo to live URL | Can get pricey at high scale |
| Managed databases included | Some vendor lock-in |

> 🔑 **PaaS (Render/Railway/Fly.io)** is the fastest path to production and the right default for most solo devs, startups, and side projects — you write code, they run it. Trade some control and cost-at-scale for enormous ops savings.

---

## 4. Serverless & Managed Containers

Between PaaS and raw servers sit **managed container** and **serverless** platforms that run your container and **autoscale** it — often **to zero** when idle (you pay per request).

### GCP Cloud Run

You give **Cloud Run** a container image; it runs it behind an HTTPS URL, **autoscales** based on traffic (including down to **zero** — no cost when idle), and you pay per request/CPU-time. Excellent fit for a containerized FastAPI app: push your Lesson 49 image, get a scaling HTTPS endpoint.

### AWS options

AWS offers a **spectrum** rather than one product:

| AWS service | Kind | FastAPI fit |
|---|---|---|
| **EC2** | Virtual machines (VPS-like) | Full control; manage it yourself |
| **ECS / Fargate** | Managed containers | Run your Docker image, autoscaled (Fargate = no servers to manage) |
| **Lambda** | Serverless functions | FastAPI via an adapter (**Mangum**); great for spiky/low traffic; cold starts |
| **Elastic Beanstalk** | PaaS-like | Simplified app deployment on AWS |

> 🔑 **Serverless / managed containers** (Cloud Run, ECS/Fargate, Lambda) autoscale your container with little ops — often **scale-to-zero** so you pay only for traffic. Ideal for variable or spiky loads; watch **cold starts** on true serverless (Lambda).

---

## 5. Kubernetes (Optional)

**Kubernetes (K8s)** orchestrates many containers across many machines: it handles scaling, self-healing (restart failed containers), rolling deploys, service discovery, and load balancing at scale. It's incredibly powerful — and incredibly complex.

- **When you need it:** many services, large teams, multi-region, complex scaling, an org already standardized on K8s.
- **When you don't (most of the time):** a single FastAPI app, a small team, or early-stage products. K8s is massive operational overhead for a simple API.

> 🔑 **Kubernetes** is for large-scale, multi-service systems. For a single FastAPI service or a small team, it's usually **overkill** — a PaaS or Cloud Run does the job with a fraction of the complexity. Don't adopt K8s by default.

---

## 6. Side-by-Side

| Option | Ops effort | Scaling | Cost model | Best for |
|---|---|---|---|---|
| **PaaS** (Render/Railway/Fly) | Very low | Automatic | Per-usage / tier | Solo devs, startups, most apps |
| **Cloud Run** | Low | Auto (to zero) | Per-request | Containerized apps, spiky traffic |
| **AWS Lambda** | Low | Auto (to zero) | Per-invocation | Spiky/low traffic, event-driven |
| **ECS/Fargate** | Medium | Auto | Per-resource | Container apps on AWS |
| **VPS / EC2** | High | Manual | Fixed | Full control, steady load |
| **Kubernetes** | Very high | Auto (configured) | Cluster | Large multi-service systems |

---

## 7. Choosing Where to Deploy

A practical decision guide:

- **Solo / side project / MVP** → **PaaS** (Render/Railway) or **Cloud Run**. Fastest, cheapest to start, near-zero ops.
- **Startup scaling up** → **Cloud Run** or **ECS/Fargate** (container-based, autoscaling) as traffic grows.
- **Need full control / compliance / steady heavy load** → **VPS/EC2**, managed properly.
- **Spiky or event-driven** → **serverless** (Cloud Run scale-to-zero, or Lambda).
- **Large org, many services, dedicated platform team** → **Kubernetes**.

> 🔑 **Start simple, scale later.** Begin on a PaaS or Cloud Run; move toward containers/K8s only when real scale or requirements demand it. Premature infrastructure complexity kills more projects than it saves.

---

## 8. What Every Deployment Needs

Regardless of platform, production requires the same essentials (all from Phase 6):

- **Config via environment variables** (Lesson 45) — no secrets in code; set them in the platform.
- **A managed database** (not SQLite) — a real Postgres, plus Redis if you cache/rate-limit.
- **Migrations run at deploy** (`alembic upgrade head`, Lesson 24) — not `create_all`.
- **HTTPS** — provided by the platform, or Nginx + Let's Encrypt on a VPS.
- **A health check endpoint** — so the platform knows the app is alive and routes traffic only to healthy instances.
- **Logs** shipped to stdout (Lesson 46) — the platform/orchestrator collects them.
- **Secrets** from the platform's secret store (Lesson 47).
- **Multiple workers / instances** (Lesson 50) for concurrency and availability.

> 🔑 Deployment isn't just "run the app" — it's env config, a managed database, migrations at release, HTTPS, health checks, log collection, and secret management. The platform handles some; you configure the rest.

---

## 9. The Deploy Workflow

The typical release pipeline (automated in Lesson 52):

```
1. Build   -> build the container image (or the platform builds from your repo)
2. Push    -> push the image to a registry (or the PaaS pulls your repo)
3. Migrate -> run `alembic upgrade head` against the production database
4. Release -> the platform starts the new version, health-checks it, shifts traffic
5. Verify  -> confirm health; roll back if the new version is unhealthy
```

Good platforms make this a **zero-downtime** rolling deploy: start the new version, health-check it, shift traffic over, retire the old one — with automatic rollback if the new version fails its health check.

---

## 10. Real-World Use Case — Shipping the Auction API

You've built and containerized the auction API. Deployment decisions:

- **Day one (MVP):** deploy the container to **Cloud Run** (or Render). Add a managed Postgres and Redis. Set `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` as env vars. Cloud Run gives an HTTPS URL, autoscales with traffic, and scales to zero overnight — pennies while you validate the idea.
- **Traffic grows:** stay on Cloud Run (it autoscales), or move to **ECS/Fargate** for more AWS integration. Migrations run on each deploy; logs stream to the platform.
- **Big scale, many services:** *if* you reach that point, consider **Kubernetes** — but not before.
- You would **not** start on a hand-managed VPS or K8s for an MVP — that's ops burden with no payoff yet.

Start simple, let the platform handle scaling, and only add infrastructure complexity when real needs justify it.

---

## 11. Mini Task

This lesson ships example deploy configs and a small app.

1. Read the three deployment configs:
   - `Procfile` — how PaaS platforms (Railway, Render, Heroku-style) start your app.
   - `render.yaml` — Render's infrastructure-as-code (web service + managed Postgres).
   - `fly.toml` — Fly.io's app config.
2. Note they all ultimately run the **same production command** (Gunicorn/Uvicorn workers, Lesson 50) and read config from **env vars** (Lesson 45).
3. **Pick a target for a hypothetical MVP** and justify it (likely a PaaS or Cloud Run).
4. **Experiment (conceptually):**
   - List which Phase 6 essentials (§8) the platform provides vs which you configure.
   - Sketch how you'd run migrations at deploy on each platform.
   - Compare monthly cost of a small VPS vs a PaaS free/starter tier vs Cloud Run scale-to-zero for a low-traffic app.
5. **Bonus:** Write down the deploy workflow (§9) for your chosen platform, including rollback.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| Reaching for Kubernetes for one small app | Use a PaaS or Cloud Run; adopt K8s only at real scale. |
| Deploying with SQLite / local files | Use a managed Postgres; files vanish on ephemeral platforms. |
| Secrets committed or in the image | Set them as platform env vars / secrets. |
| No migrations step at deploy | Run `alembic upgrade head` on release. |
| Assuming local disk persists | Most platforms have ephemeral disks; use a DB / object storage. |
| No health check | Add one so the platform routes only to healthy instances. |
| Over-provisioning early | Start small; let autoscaling grow with real traffic. |

---

## 13. Key Takeaways

- Deployment options trade **control for convenience**: Kubernetes → VPS → managed containers/serverless → PaaS.
- **VPS** = full control, full ops burden (you manage OS, TLS, backups, scaling).
- **PaaS** (Render/Railway/Fly.io) = push-to-deploy, near-zero ops — the right default for most apps.
- **Serverless / managed containers** (Cloud Run, ECS/Fargate, Lambda) autoscale your container, often **to zero**; great for spiky loads (mind cold starts on Lambda).
- **AWS** is a spectrum: EC2 (VMs), ECS/Fargate (containers), Lambda (serverless).
- **Kubernetes** is for large, multi-service systems — usually **overkill** for a single API.
- Every deployment needs: **env config, a managed DB, migrations at deploy, HTTPS, health checks, log collection, secrets, multiple workers**.
- **Start simple** (PaaS/Cloud Run); add infrastructure complexity only when real scale demands it.

---

## ➡️ Next Lesson

**Lesson 52 — CI/CD Pipeline**
- Automating test → build → deploy
- A GitHub Actions deployment pipeline
- Safe, repeatable releases
