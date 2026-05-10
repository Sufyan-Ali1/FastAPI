"""
Lesson 17 — Form Data & File Uploads
--------------------------------------
Demonstrates:
  - Form() for login and profile forms
  - UploadFile for single and multiple file uploads
  - File type + size validation
  - Combining Form() + UploadFile in one endpoint
  - Saving files to disk with UUID prefix (safe naming)
  - FileResponse for serving downloads
  - shutil.copyfileobj for memory-efficient saving

Run:
    pip install python-multipart   ← required for forms & file uploads
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs
"""

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

app = FastAPI(title="Lesson 17 - Form Data & File Uploads")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ============================================================
# 1. Basic form fields (login)
# ============================================================

@app.post("/login")
def login(
    username: str = Form(..., min_length=3, max_length=50),
    password: str = Form(..., min_length=6),
):
    """
    Accepts application/x-www-form-urlencoded.
    NOTE: you can't use a Pydantic BaseModel here — that's JSON only.
    """
    if username == "sufyan" and password == "secret123":
        return {"message": f"Welcome, {username}!"}
    raise HTTPException(status_code=401, detail="Invalid credentials")


# ============================================================
# 2. Single file upload — returns metadata
# ============================================================

@app.post("/upload")
async def upload_file(file: UploadFile):
    """Upload any file and get back its metadata."""
    contents = await file.read()
    return {
        "filename":     file.filename,
        "content_type": file.content_type,
        "size_bytes":   len(contents),
    }


# ============================================================
# 3. Multiple files at once
# ============================================================

@app.post("/upload-many")
async def upload_many(files: list[UploadFile]):
    """Upload multiple files in one request."""
    results = []
    for f in files:
        contents = await f.read()
        results.append({
            "filename":     f.filename,
            "content_type": f.content_type,
            "size_bytes":   len(contents),
        })
    return {"uploaded": len(results), "files": results}


# ============================================================
# 4. Avatar upload — validates type and size
# ============================================================

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_AVATAR_MB = 2


@app.post("/avatar")
async def upload_avatar(file: UploadFile):
    """
    Validates:
    - Content type must be an image
    - File size must be ≤ 2 MB
    Then saves with a UUID prefix.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"'{file.content_type}' is not an allowed image type",
                "allowed": list(ALLOWED_IMAGE_TYPES),
            },
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)

    if size_mb > MAX_AVATAR_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({size_mb:.2f} MB). Maximum is {MAX_AVATAR_MB} MB.",
        )

    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    (UPLOAD_DIR / safe_name).write_bytes(contents)

    return {
        "saved_as":   safe_name,
        "size_mb":    round(size_mb, 3),
        "type":       file.content_type,
    }


# ============================================================
# 5. Profile update — Form fields + file together
# ============================================================

@app.post("/profile")
async def update_profile(
    username: str      = Form(..., min_length=3),
    bio: str           = Form("", max_length=300),
    avatar: UploadFile = File(..., description="Profile picture"),
):
    """
    Mix of Form() fields and UploadFile in one multipart request.
    Cannot use a Pydantic body model alongside Form().
    """
    if avatar.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Avatar must be an image")

    contents = await avatar.read()
    safe_name = f"{uuid.uuid4().hex}_{avatar.filename}"
    (UPLOAD_DIR / safe_name).write_bytes(contents)

    return {
        "username": username,
        "bio":      bio,
        "avatar":   safe_name,
        "size_kb":  round(len(contents) / 1024, 1),
    }


# ============================================================
# 6. Document upload — PDF/Word only, stream to disk
# ============================================================

ALLOWED_DOC_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@app.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    title:    str        = Form(..., min_length=1, max_length=200),
    category: str        = Form(...),
    document: UploadFile = File(...),
):
    """
    Saves document using shutil.copyfileobj — streams data to disk
    without loading the entire file into memory.
    """
    if document.content_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and Word documents (.pdf, .doc, .docx) are accepted",
        )

    safe_name = f"{uuid.uuid4().hex}_{document.filename}"
    dest = UPLOAD_DIR / safe_name

    with dest.open("wb") as buffer:
        shutil.copyfileobj(document.file, buffer)

    return {
        "title":    title,
        "category": category,
        "filename": safe_name,
        "saved_to": str(dest),
    }


# ============================================================
# 7. List and download uploaded files
# ============================================================

@app.get("/files")
def list_files():
    """Lists all filenames in the uploads/ folder."""
    files = [f.name for f in UPLOAD_DIR.iterdir() if f.is_file()]
    return {"count": len(files), "files": files}


@app.get("/files/{filename}")
def download_file(filename: str):
    """Serves an uploaded file as a download."""
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=path,
        filename=filename,
        media_type="application/octet-stream",
    )
