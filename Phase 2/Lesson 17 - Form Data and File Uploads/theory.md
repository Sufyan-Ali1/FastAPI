# Lesson 17 — Form Data & File Uploads

> **Goal of this lesson:** Accept HTML form fields and uploaded files in FastAPI — for login forms, profile pictures, document uploads, and anything multipart.

---

## 0. Required Dependency

Form data and file uploads use `multipart/form-data` encoding. Install the parser first:

```bash
pip install python-multipart
```

Without it, FastAPI raises a `RuntimeError` the moment you use `Form()` or `UploadFile`.

---

## 1. Why Forms Are Different from JSON Bodies

| | JSON Body | Form Data |
|---|---|---|
| Content-Type | `application/json` | `multipart/form-data` or `application/x-www-form-urlencoded` |
| Supports files? | ❌ No | ✅ Yes |
| Used by | APIs, mobile apps, SPAs | HTML `<form>` elements, file upload UIs |
| FastAPI tool | `BaseModel` / `Body()` | `Form()` + `UploadFile` |

> ⚠️ You **cannot** mix a Pydantic body model with `Form()` in the same endpoint. They use different content types.

---

## 2. `Form()` — Reading Form Fields

```python
from fastapi import Form

@app.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
):
    return {"username": username}
```

The client sends:
```
POST /login
Content-Type: application/x-www-form-urlencoded

username=sufyan&password=secret
```

`Form()` accepts all the same validators as `Query()` and `Field()`:
```python
username: str = Form(..., min_length=3, max_length=50)
age: int = Form(..., ge=18)
email: str = Form(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
```

---

## 3. `UploadFile` — Receiving a File

```python
from fastapi import UploadFile

@app.post("/upload")
async def upload_file(file: UploadFile):
    contents = await file.read()
    return {
        "filename":     file.filename,
        "content_type": file.content_type,
        "size_bytes":   len(contents),
    }
```

### `UploadFile` attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `file.filename` | `str` | Original filename from the client |
| `file.content_type` | `str` | MIME type (`image/png`, `application/pdf`, etc.) |
| `file.size` | `int \| None` | Size in bytes (may be `None` for streaming uploads) |
| `file.file` | `SpooledTemporaryFile` | The underlying file-like object |

### Reading the file

```python
contents = await file.read()          # read entire file into memory (bytes)
await file.seek(0)                    # rewind to start if you need to read again
chunk = await file.read(1024)         # read in chunks (for large files)
```

---

## 4. `File()` — With Validation

`UploadFile` is fine for most cases. Use `File()` when you need to add metadata to the parameter (title, description for docs):

```python
from fastapi import File, UploadFile

@app.post("/upload")
async def upload(
    file: UploadFile = File(..., description="The file to upload"),
):
    ...
```

For bytes instead of a file object (small files only):

```python
@app.post("/upload-bytes")
async def upload_bytes(data: bytes = File(...)):
    return {"size": len(data)}
```

Use `UploadFile` for large files — it spools to disk automatically instead of loading everything into RAM.

---

## 5. Multiple Files

```python
from typing import Annotated

@app.post("/upload-many")
async def upload_many(files: list[UploadFile]):
    result = []
    for f in files:
        contents = await f.read()
        result.append({"filename": f.filename, "size": len(contents)})
    return result
```

The client sends:
```
POST /upload-many
Content-Type: multipart/form-data

files=@photo1.jpg
files=@photo2.jpg
```

---

## 6. Combining Form Fields and Files

Both can live in the same endpoint:

```python
@app.post("/profile")
async def update_profile(
    username: str     = Form(...),
    bio: str          = Form(""),
    avatar: UploadFile = File(...),
):
    contents = await avatar.read()
    return {
        "username": username,
        "bio":      bio,
        "avatar":   avatar.filename,
        "size":     len(contents),
    }
```

> ✅ `Form()` + `UploadFile` can coexist in the same endpoint.
> ❌ `Form()` + Pydantic `BaseModel` body **cannot** coexist.

---

## 7. Validating File Type and Size

FastAPI doesn't validate file type by default. Do it yourself:

```python
from fastapi import HTTPException

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB = 5

@app.post("/avatar")
async def upload_avatar(file: UploadFile):
    # Validate content type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file.content_type}' not allowed. Use: {ALLOWED_TYPES}",
        )

    # Validate size
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Max is {MAX_SIZE_MB} MB.",
        )

    return {"filename": file.filename, "size_mb": round(size_mb, 2)}
```

> ⚠️ `content_type` comes from the client and can be spoofed. For real security, inspect the file's magic bytes or use a library like `python-magic`.

---

## 8. Saving Files to Disk

```python
import shutil
from pathlib import Path

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.post("/save")
async def save_file(file: UploadFile):
    dest = UPLOAD_DIR / file.filename
    with dest.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)   # stream copy — memory efficient
    return {"saved_to": str(dest)}
```

Use `shutil.copyfileobj` instead of `await file.read()` for large files — it streams the data instead of loading everything into RAM.

---

## 9. Returning a File as a Response

```python
from fastapi.responses import FileResponse

@app.get("/download/{filename}")
def download(filename: str):
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=path,
        filename=filename,                     # sets Content-Disposition header
        media_type="application/octet-stream",
    )
```

---

## 10. Real-World Use Case — Document Upload API

```python
import uuid
from pathlib import Path
from fastapi import UploadFile, Form, HTTPException

ALLOWED_DOCS = {"application/pdf", "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
UPLOAD_DIR = Path("documents")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.post("/documents", status_code=201)
async def upload_document(
    title:    str        = Form(..., min_length=1, max_length=200),
    category: str        = Form(...),
    document: UploadFile = File(...),
):
    if document.content_type not in ALLOWED_DOCS:
        raise HTTPException(status_code=400, detail="Only PDF and Word documents allowed")

    safe_name = f"{uuid.uuid4().hex}_{document.filename}"
    dest = UPLOAD_DIR / safe_name

    contents = await document.read()
    dest.write_bytes(contents)

    return {
        "title":    title,
        "category": category,
        "filename": safe_name,
        "size_kb":  round(len(contents) / 1024, 1),
    }
```

Note `uuid4().hex` prefix — never save files with client-provided names directly (path traversal risk).

---

## 11. Mini Task

Open `main.py`:

1. Run: `uvicorn main:app --reload`
2. In `/docs`:
   - **POST `/login`** → test form fields
   - **POST `/upload`** → upload any file, check filename/content_type/size in response
   - **POST `/avatar`** → upload a `.jpg` → success; upload a `.txt` → 400
   - **POST `/profile`** → combines form fields + file in one request
   - **POST `/documents`** → upload a `.pdf`; check the `uploads/` folder for the saved file
3. **Bonus:** Add a `GET /files` endpoint that lists all filenames in the `uploads/` folder.

---

## 12. Key Takeaways

- Install `python-multipart` — required for `Form()` and `UploadFile`.
- `Form()` reads individual form fields; all `Query()`/`Field()` validators apply.
- `UploadFile` is preferred over `bytes = File()` for large files (streams to disk, not RAM).
- You **cannot** mix a Pydantic body model with `Form()` in the same endpoint.
- Validate content type and size manually — FastAPI doesn't do it for you.
- Never use the client-provided filename directly — prefix with UUID.
- Use `shutil.copyfileobj` for memory-efficient file saving.
- `FileResponse` sends a file as a download.

---

## ➡️ Next Lesson

**Lesson 18 — Headers & Cookies**
- Reading request headers
- Setting response headers
- Reading and setting cookies
- Secure cookie flags
