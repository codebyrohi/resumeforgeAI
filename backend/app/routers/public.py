from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse

from app.clients.storage_client import get_storage
from app.services.export_service import cinematic_key

router = APIRouter(tags=["public"])

# The page is our own template with escaped user content; the CSP is defence in depth.
_CSP = ("default-src 'none'; img-src * data:; style-src 'unsafe-inline'; "
        "script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'")


@router.get("/r/{slug}", response_class=HTMLResponse)
def public_resume(slug: str):
    html = get_storage().get(cinematic_key(slug))
    if html is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not published")
    return HTMLResponse(html.decode("utf-8"), headers={
        "Content-Security-Policy": _CSP,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-cache",
    })
