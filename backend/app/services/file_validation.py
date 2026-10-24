"""Upload validation: type, size and magic bytes. Never trust the client's filename/MIME alone."""
import io
import zipfile

from fastapi import HTTPException, UploadFile, status

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _reject(msg: str, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(code, msg)


async def read_limited(file: UploadFile, max_bytes: int) -> bytes:
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise _reject(f"File too large (max {max_bytes // (1024 * 1024)} MB)",
                      status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    if not data:
        raise _reject("File is empty")
    return data


def detect_resume_kind(filename: str, data: bytes) -> str:
    """Return 'pdf' or 'docx' based on content, cross-checked with the extension."""
    name = (filename or "").lower()
    if data.startswith(b"%PDF-"):
        kind = "pdf"
    elif data.startswith(b"PK\x03\x04") and _is_docx(data):
        kind = "docx"
    else:
        raise _reject("Only PDF or DOCX files are accepted")
    if not name.endswith("." + kind):
        raise _reject("File extension does not match its contents")
    return kind


def _is_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return "word/document.xml" in z.namelist()
    except zipfile.BadZipFile:
        return False


IMAGE_SIGNATURES = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG\r\n\x1a\n": "png",
}


def detect_image_kind(data: bytes) -> str:
    for sig, kind in IMAGE_SIGNATURES.items():
        if data.startswith(sig):
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    raise _reject("Photo must be a JPEG, PNG or WEBP image")
