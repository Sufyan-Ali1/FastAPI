# Lesson 47 — Security Best Practices

> **Goal of this lesson:** Consolidate the security threads from across the course and add the production essentials: **HTTPS everywhere**, **secure headers**, **input validation & sanitization**, **SQL-injection prevention**, and **secret management**. This is the hardening checklist every production API needs.
>
> `main.py` adds a secure-headers middleware and **demonstrates a real SQL injection** — showing the unsafe query getting exploited and the parameterized query defeating it.

---

## 1. The Security Mindset

Security isn't one feature; it's a set of habits applied everywhere. Three principles underlie all of it:

- **Never trust input.** Anything from a client — body, query, header, cookie, file — is potentially hostile.
- **Defense in depth.** Layer protections; assume any single one can fail.
- **Least privilege.** Every user, token, and database account gets the minimum access it needs.

You've already built pieces of this: auth (Lesson 29), CORS (Lesson 33), rate limiting (Lesson 34), config/secrets (Lesson 45). This lesson fills the remaining gaps and ties them together.

> 🔑 Security is a **mindset applied consistently**, not a checkbox. Assume all input is malicious, layer your defenses, and grant the least access necessary.

---

## 2. HTTPS Everywhere

**HTTPS** (HTTP over TLS) encrypts traffic between client and server. Without it, passwords, tokens, and data travel in **plaintext** — anyone on the network path can read or tamper with them. HTTPS is non-negotiable for any real API.

Key practices:

- **Serve only over HTTPS** in production. Redirect HTTP → HTTPS.
- **HSTS** (`Strict-Transport-Security` header) tells browsers "only ever use HTTPS for this site," preventing downgrade attacks.
- TLS termination is usually handled by a **reverse proxy / load balancer** (Nginx, a cloud LB) *in front of* your app, not by FastAPI itself.

FastAPI/Starlette can enforce it at the app level too:

```python
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(HTTPSRedirectMiddleware)                    # HTTP -> HTTPS
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["api.example.com"])
```

> 🔑 **Always HTTPS in production**, redirect HTTP, and send **HSTS**. Tokens and passwords must never cross the wire in plaintext. TLS is usually terminated at a proxy/load balancer.

---

## 3. Secure Headers

Browsers respect a set of **security response headers** that harden how your responses are handled. Add them via middleware to every response:

| Header | Protects against | Typical value |
|---|---|---|
| `Strict-Transport-Security` | Protocol downgrade | `max-age=63072000; includeSubDomains` |
| `X-Content-Type-Options` | MIME-sniffing | `nosniff` |
| `X-Frame-Options` | Clickjacking (framing) | `DENY` |
| `Content-Security-Policy` | XSS, injection | `default-src 'self'` (tune per app) |
| `Referrer-Policy` | Referrer leakage | `no-referrer` |
| `Permissions-Policy` | Unwanted browser features | `geolocation=(), camera=()` |

```python
@app.middleware("http")
async def secure_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

These matter most when your API serves anything a browser renders. Even for pure JSON APIs, `X-Content-Type-Options: nosniff` and HSTS are cheap wins.

> 🔑 Add **secure headers** to every response via middleware. `nosniff`, `X-Frame-Options: DENY`, a `Content-Security-Policy`, and HSTS are the core set.

---

## 4. Input Validation vs Sanitization

Two related-but-different defenses:

- **Validation** — reject input that doesn't match the expected shape/type/range. **Pydantic already does this** (Lesson 6/9): types, `min_length`, `gt`, patterns, enums. Invalid input never reaches your logic.
- **Sanitization** — clean/escape input before using it in a **dangerous context** (HTML, SQL, a shell command, a file path). It's about *how you use* the value, not just its shape.

```python
class CommentIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)   # validation
    # Sanitization happens when you USE body in a risky context (e.g. rendering
    # to HTML -> escape it; building SQL -> parameterize it).
```

> 🔑 **Validation** (Pydantic) ensures input has the right *shape*; **sanitization/escaping** protects the *context* you use it in (SQL, HTML, shell). You need both — validation alone doesn't stop injection.

---

## 5. SQL Injection — The Classic Attack

**SQL injection** happens when user input is concatenated into a SQL string, letting an attacker alter the query. The textbook example:

```python
# ❌ CATASTROPHIC - never build SQL with string formatting
username = request.query["username"]      # attacker sends:  ' OR '1'='1
cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
# becomes:  SELECT * FROM users WHERE username = '' OR '1'='1'   -> returns EVERY row
```

The attacker's `' OR '1'='1` turns a lookup into "return everything" (or with `;DROP TABLE`, worse). The fix is **parameterized queries** (a.k.a. bound parameters): pass values *separately* from the SQL so they're always treated as **data**, never as SQL.

```python
# ✅ SAFE - parameterized: the value can never become SQL
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
```

**With SQLAlchemy (Phase 3), you're protected by default** — the ORM parameterizes everything:

```python
db.scalars(select(User).where(User.username == username))   # safe, always parameterized
```

The `main.py` demo shows this concretely: the unsafe string-formatted query gets exploited by `' OR '1'='1`, while the parameterized version treats it as a literal (harmless) username and returns nothing.

> 🔑 **Never build SQL with string formatting/f-strings.** Use **parameterized queries** (or an ORM, which does it for you). This single rule prevents SQL injection. The same idea applies to shell commands, LDAP, and any interpreted context.

---

## 6. Other Injection & Traversal Risks

The "never trust input, escape for the context" rule generalizes:

| Attack | What it abuses | Prevention |
|---|---|---|
| **SQL injection** | SQL string building | Parameterized queries / ORM |
| **Command injection** | Building shell commands from input | Avoid shells; pass args as a list; never `os.system(f"...")` |
| **Path traversal** | User-controlled file paths (`../../etc/passwd`) | Validate/normalize paths; never join raw user input to a filesystem path |
| **XSS** | Unescaped input rendered as HTML | Escape output; CSP header (APIs returning JSON are lower-risk) |
| **SSRF** | User-supplied URLs your server fetches | Allowlist destinations; block internal addresses |

> 🔑 Every injection class is the same bug: **untrusted input used unescaped in an interpreter.** Validate the input and **escape/parameterize for the specific context** (SQL, shell, filesystem, HTML, URL).

---

## 7. Secret Management

Secrets — the JWT `SECRET_KEY`, database passwords, API keys — must be handled carefully (Lesson 45 set the foundation):

- **Never in code or version control.** Load from environment/config (Lesson 45).
- **Never in logs.** Redact them (Lesson 46).
- **Never sent to the client.** Not in responses, not in JWT payloads (JWTs are readable — Lesson 29).
- **Use a secret manager** in production — AWS Secrets Manager, GCP Secret Manager, Vault, or your platform's env-var/secret store — rather than plain `.env` files on servers.
- **Rotate** secrets periodically and immediately if one leaks. A committed secret is compromised forever — rotate, don't just delete.
- **Least privilege** for credentials: the app's database user should only have the permissions it needs, not superuser.

> 🔑 Secrets live in the **environment / a secret manager**, never in code, logs, responses, or JWTs. Rotate them, and give each credential the least privilege it needs.

---

## 8. Auth & API Hardening Recap

Pulling together the security you've already built, plus a few additions:

| Area | Practice | Lesson |
|---|---|---|
| Passwords | Hash with **bcrypt** (salted, slow); never plaintext | 29 |
| Tokens | Short-lived JWTs; signed not encrypted; refresh tokens | 29 |
| Authorization | RBAC; least privilege; check ownership | 29 |
| CORS | Explicit origins; no `*` with credentials | 33 |
| Rate limiting | Throttle login/expensive endpoints | 34 |
| Errors | Generic messages; don't leak stack traces or "user not found" vs "wrong password" | 12/13 |
| Payload size | Limit request body / upload size | — |
| Dependencies | Keep libraries updated (known CVEs) | — |

> 💡 A generic "incorrect username or password" (not "no such user") avoids **user enumeration**. Small wording choices are part of security.

---

## 9. The OWASP Top 10

The **OWASP Top 10** is the industry reference list of the most critical web app security risks (broken access control, injection, cryptographic failures, security misconfiguration, etc.). You don't need to memorize it, but knowing it exists — and mapping your app against it — is how professionals audit security. Most of this lesson maps directly onto OWASP categories.

> 💡 Use the **OWASP Top 10** as a checklist when reviewing an API's security. It's the standard vocabulary for talking about web risks.

---

## 10. Real-World Use Case — Hardening the Auction API

Shipping the Phase 4 auction API to production, the security pass:

- **HTTPS** enforced at the load balancer; HSTS + secure headers added via middleware.
- All queries go through **SQLAlchemy** → SQL injection is off the table by design.
- Inputs are **validated** by Pydantic; file uploads are size-limited.
- **Secrets** (JWT key, DB password) come from the platform's secret manager, never the repo; they're redacted in logs and absent from responses.
- **Rate limiting** protects `/login` and bidding; **CORS** allows only the real frontend origin.
- Login errors are **generic**; the DB user has only the privileges the app needs.
- The team reviews the app against the **OWASP Top 10** before launch.

None of these is exotic — they're the standard hardening checklist, and skipping any one is how breaches happen.

---

## 11. Mini Task

`main.py` adds secure headers and demonstrates SQL injection.

1. Run: `uvicorn main:app --reload`
2. Inspect the secure headers:
   ```bash
   curl -i http://127.0.0.1:8000/       # see X-Content-Type-Options, X-Frame-Options, CSP, ...
   ```
3. Hit the injection demo endpoints and compare:
   - `/users/unsafe?username=' OR '1'='1` → the **unsafe** query is exploited and returns **all** users.
   - `/users/safe?username=' OR '1'='1` → the **parameterized** query treats it as a literal and returns **nothing**.
   Read the code to see the one-line difference (string-format vs bound parameter).
4. **Experiment:**
   - Add HSTS only when a config flag says production.
   - Add `TrustedHostMiddleware` with an allowed host and watch a bad `Host` header get rejected.
   - Add a payload-size limit and test it with a large body.
5. **Bonus:** Map the app against the OWASP Top 10 and note which lesson covers each item.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| Serving over plain HTTP | HTTPS only; redirect HTTP; send HSTS. |
| Building SQL with f-strings | Parameterized queries / ORM — always. |
| Secrets in code, logs, or responses | Environment / secret manager; redact; never return. |
| No secure headers | Add them via middleware. |
| Leaking which of username/password was wrong | Generic auth error messages. |
| Trusting validated input in a raw context | Validate **and** escape/parameterize for the context. |
| Superuser DB credentials | Least privilege for the app's DB account. |
| Never updating dependencies | Patch known CVEs; keep libraries current. |

---

## 13. Key Takeaways

- Security is a **mindset**: never trust input, defense in depth, least privilege.
- **HTTPS everywhere** (redirect HTTP, send **HSTS**); TLS usually terminates at a proxy/LB.
- Add **secure headers** via middleware: `nosniff`, `X-Frame-Options`, **CSP**, `Referrer-Policy`, HSTS.
- **Validation** (Pydantic) fixes shape; **sanitization/escaping** protects the context — you need both.
- **SQL injection** is prevented by **parameterized queries / the ORM** — never string-format SQL. The same rule covers command/path/HTML/URL injection.
- **Secrets** live in the environment / a secret manager — never in code, logs, responses, or JWT payloads; rotate them; least privilege.
- Recap the built-in defenses: bcrypt, short JWTs, RBAC, CORS, rate limiting, generic errors, payload limits, updated deps.
- Use the **OWASP Top 10** as your audit checklist.

---

## ➡️ Next Lesson

**Lesson 48 — Performance Optimization**
- Async I/O usage and connection pooling
- Profiling (`py-spy`) to find bottlenecks
- The N+1 query problem and how to fix it
