# Lesson 2 — Installation & Project Setup

> **Goal of this lesson:** Set up a clean, professional FastAPI development environment that you'll reuse for every future project.

---

## 1. What are we setting up?

Three things you need before writing any FastAPI code:

| Tool | Job |
|------|-----|
| **Python 3.10+** | The language itself |
| **Virtual environment** | An isolated folder for project dependencies |
| **FastAPI + Uvicorn** | The framework + the server that runs it |

That's it. No databases, no Docker — just the bare minimum to run an API.

---

## 2. Why a virtual environment?

When you `pip install` a package globally, it goes into your *system* Python.
That causes 3 big problems:

1. **Version conflicts** — Project A needs `fastapi==0.100`, Project B needs `fastapi==0.115`. They cannot coexist globally.
2. **Hard to reproduce** — A teammate (or production server) doesn't know what versions you used.
3. **System pollution** — You end up with hundreds of unrelated packages on your computer.

### ✅ Solution: virtual environment

A virtual environment is just a **folder** that contains its own Python + its own packages.
Each project gets its own venv → no conflicts, easy to reproduce, easy to delete.

```
my_project/
├── venv/             ← isolated Python + packages live here
├── main.py
└── requirements.txt  ← a list of packages this project needs
```

---

## 3. How to create a virtual environment

There are 3 popular tools. Pick **one**:

### Option A — `venv` (built-in, recommended for beginners) ⭐
Comes with Python. No installation needed.

```bash
# Create a venv folder named "venv"
python -m venv venv

# Activate it
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# Windows (Git Bash / cmd):
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# When activated, your terminal prompt shows (venv)
# To leave:
deactivate
```

### Option B — `uv` (modern, ultra-fast) 🚀
Written in Rust. 10-100× faster than pip. Becoming the new standard.

```bash
# Install once (globally)
pip install uv

# Create venv
uv venv

# Activate (same as above)
.venv\Scripts\activate    # Windows
source .venv/bin/activate # macOS/Linux

# Install packages
uv pip install fastapi uvicorn
```

### Option C — `poetry` (full project manager)
Manages venv + dependencies + packaging. More features, more learning curve.

```bash
pip install poetry
poetry new my_project
cd my_project
poetry add fastapi uvicorn
poetry shell
```

> **For this course we will use `venv`** — it's built-in, simple, and works everywhere.

---

## 4. Installing FastAPI + Uvicorn

Once your venv is **activated**, install the packages:

```bash
pip install fastapi uvicorn
```

What gets installed:

| Package | Purpose |
|---------|---------|
| `fastapi` | The framework itself |
| `uvicorn` | The ASGI server that actually runs your app |
| (auto) `pydantic` | Validation library — installed as a FastAPI dependency |
| (auto) `starlette` | The underlying web toolkit |

### What is Uvicorn (and why do we need it)?

FastAPI is a **framework** — it doesn't actually listen on a port.
**Uvicorn** is the **server** that:
1. Listens on `http://127.0.0.1:8000`
2. Receives raw HTTP requests
3. Hands them to FastAPI
4. Sends the response back to the client

> Think of it like:
> - **FastAPI** = the chef (writes the meal logic)
> - **Uvicorn** = the waiter (takes orders, delivers food)

---

## 5. The standard project folder

For now, keep it simple:

```
Lesson 2 - Installation & Setup/
├── venv/                ← created by `python -m venv venv`
├── main.py              ← your FastAPI code
└── requirements.txt     ← list of dependencies
```

### `requirements.txt`
A plain text file listing every package your project needs.

```
fastapi
uvicorn
```

To **freeze exact versions** (recommended for production):
```bash
pip freeze > requirements.txt
```

To **install from it later** (e.g. on a new machine):
```bash
pip install -r requirements.txt
```

---

## 6. Running the FastAPI server

Once `main.py` exists and `fastapi` + `uvicorn` are installed:

```bash
uvicorn main:app --reload
```

Breakdown:

| Part | Meaning |
|------|---------|
| `uvicorn` | the server command |
| `main` | the file `main.py` |
| `app` | the variable inside `main.py` (`app = FastAPI()`) |
| `--reload` | auto-restart on code change (**dev only**, never in production) |

You should see:
```
Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Visit:
- `http://127.0.0.1:8000` → your endpoint
- `http://127.0.0.1:8000/docs` → free Swagger UI ✨

---

## 7. Real-World Use Case

Every real Python project — without exception — uses a virtual environment.

In a real team workflow:

1. **Developer A** writes the app, freezes `requirements.txt`.
2. **Developer B** clones the repo, runs `python -m venv venv` + `pip install -r requirements.txt`.
3. **Production server** (or Docker container) does the same — exact reproducibility.

Skipping venv = guaranteed "works on my machine" bugs.

---

## 8. Mini Task

1. Create a **new venv** inside this lesson folder:
   ```bash
   python -m venv venv
   ```
2. **Activate** it (your prompt should show `(venv)`).
3. **Install** FastAPI and Uvicorn:
   ```bash
   pip install fastapi uvicorn
   ```
4. **Freeze** the dependencies:
   ```bash
   pip freeze > requirements.txt
   ```
5. **Run** the included `main.py`:
   ```bash
   uvicorn main:app --reload
   ```
6. Open `http://127.0.0.1:8000/docs` → you should see Swagger UI ✅

---

## 9. Key Takeaways

- **Always** use a virtual environment, one per project.
- `venv` is built-in and beginner-friendly. `uv` is the modern fast alternative.
- `pip install fastapi uvicorn` is enough to start.
- `uvicorn main:app --reload` is the dev command you'll use 1000 times.
- `requirements.txt` lets others (and future-you) reproduce the environment.

---

## ➡️ Next Lesson

**Lesson 3 — First API: GET & POST**
- All HTTP method decorators
- Return types & status codes
- Difference between GET, POST, PUT, DELETE
