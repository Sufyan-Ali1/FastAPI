# 🚀 FastAPI — From Beginner to Advanced

> A complete, hands-on learning journey to master **FastAPI** — from your very first endpoint to production-grade APIs.

This repository documents my step-by-step progress through a structured FastAPI course. Every lesson is self-contained with **deep theory** and **clean, runnable code**.

---

## 📖 What's Inside?

Each topic gets its own folder with:

| File | Purpose |
|------|---------|
| `theory.md` | The **Why / What / How** — concepts explained in simple language |
| `main.py` | **Clean, runnable** FastAPI code demonstrating the concept |

The full roadmap (60+ topics across 6 phases) lives in [`SYLLABUS.md`](./SYLLABUS.md).

---

## 📂 Folder Structure

```
Claude/
├── README.md                          ← you are here
├── SYLLABUS.md                        ← full course roadmap
│
├── Lesson 1 - What is FastAPI/
│   ├── theory.md
│   └── main.py
│
├── Lesson 2 - Installation & Setup/
│   ├── theory.md
│   └── main.py
│
├── Lesson 3 - First API GET and POST/
│   ├── theory.md
│   └── main.py
│
├── Lesson 4 - Path Parameters/
│   ├── theory.md
│   └── main.py
│
├── Lesson 5 - Query Parameters/
│   ├── theory.md
│   └── main.py
│
└── ... (more lessons added as I progress)
```

---

## ✅ Progress Tracker

### 🟢 Phase 1 — Fundamentals
- [x] Lesson 1 — What is FastAPI
- [x] Lesson 2 — Installation & Setup
- [x] Lesson 3 — First API: GET & POST (+ REST deep dive)
- [x] Lesson 4 — Path Parameters
- [x] Lesson 5 — Query Parameters
- [x] Lesson 6 — Request Body with Pydantic Models
- [x] Lesson 7 — Combining Path + Query + Body
- [x] Lesson 8 — Response Basics

### 🟡 Phase 2 — Core Features (Intermediate)
- [x] Lesson 9 — Pydantic Deep Dive
- [x] Lesson 10 — Response Models
- [x] Lesson 11 — Multiple Models per Route
- [x] Lesson 12 — Status Codes & HTTP Exceptions
- [x] Lesson 13 — Error Handling
- [x] Lesson 14 — Dependency Injection
- [x] Lesson 15 — Middleware
- [x] Lesson 16 — Routers (APIRouter)
- [x] Lesson 17 — Form Data & File Uploads
- [x] Lesson 18 — Headers & Cookies
- [x] Lesson 19 — Static Files & Templates (Jinja2)

### 🔵 Phase 3 — Database Integration
*Coming soon…*

### 🟣 Phase 4 — Advanced Features
*Coming soon…*

### 🔴 Phase 5 — Testing & Quality
*Coming soon…*

### 🟠 Phase 6 — Production & Deployment
*Coming soon…*

> 📍 See [`SYLLABUS.md`](./SYLLABUS.md) for the **complete 60+ topic roadmap**.

---

## 🛠️ Tech Stack

- **Python 3.10+**
- **FastAPI** — modern async web framework
- **Uvicorn** — ASGI server
- **Pydantic** — data validation & serialization
- *(Coming later)* SQLAlchemy, Alembic, JWT, Docker, Pytest

---

## ▶️ How to Run Any Lesson

Each lesson is independent. To run any one of them:

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>/Claude
```

### 2. Create & activate a virtual environment
```bash
python -m venv venv

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Windows (Git Bash / cmd)
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install fastapi uvicorn
```

### 4. Move into any lesson folder
```bash
cd "Lesson 5 - Query Parameters"
```

### 5. Start the server
```bash
uvicorn main:app --reload
```

### 6. Open your browser
- **App:** http://127.0.0.1:8000
- **Swagger UI (auto docs):** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

---

## 🎯 Learning Goals

By the end of this journey, I will be able to:

- ✅ Build clean, production-grade REST APIs with FastAPI
- ✅ Understand async Python and the request/response lifecycle
- ✅ Validate inputs and serialize outputs with Pydantic
- ✅ Integrate databases using SQLAlchemy + Alembic
- ✅ Implement authentication (JWT, OAuth2)
- ✅ Write tests with pytest & TestClient
- ✅ Containerize APIs with Docker
- ✅ Deploy to cloud platforms

---

## 📚 How to Read Each Lesson

For best results:

1. **Read** the `theory.md` first — understand the *why*.
2. **Open** `main.py` and read the code line by line.
3. **Run** the server and hit `/docs` to test every endpoint.
4. **Modify** the code — break things, fix them, learn deeper.
5. **Complete** the *Mini Task* at the bottom of every `theory.md`.

---

## 🤝 Contributing / Suggestions

This is a personal learning repo, but feedback and suggestions are welcome!
Feel free to open an issue if you spot a mistake or want to suggest improvements.

---

## 📜 License

This project is open-source and free to use under the **MIT License**.

---

## 👤 Author

**Sufyan Ali**
- 📧 sufyanjatts199@gmail.com
- 🌍 Currently learning FastAPI to build production-grade backends

---

> *"The best way to learn is to build, break, and rebuild."*

⭐ If this repo helps you on your FastAPI journey, please consider starring it!
