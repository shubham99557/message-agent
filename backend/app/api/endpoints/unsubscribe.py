import html
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.unsubscribe_service import process_unsubscribe_token

router = APIRouter()


@router.get("/{token}")
def unsubscribe_get_endpoint(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Hosted one-click/confirmation unsubscribe endpoint for email recipients."""
    try:
        res = process_unsubscribe_token(db=db, token=token, source="hosted_link")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    accept = (request.headers.get("accept") or "").lower()
    if "application/json" in accept:
        return JSONResponse(content=res, status_code=200)

    safe_email = html.escape(res["email"])
    body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Unsubscribed — ActTrident</title></head>
<body style="font-family: system-ui, sans-serif; max-width: 520px; margin: 48px auto; padding: 24px; color: #0f172a;">
  <h2 style="margin-bottom: 8px;">You have been unsubscribed</h2>
  <p>The address <strong>{safe_email}</strong> has been added to our suppression list and will not receive further outreach emails.</p>
</body>
</html>"""
    return HTMLResponse(content=body, status_code=200)


@router.post("/{token}")
def unsubscribe_one_click_post_endpoint(
    token: str,
    db: Session = Depends(get_db),
):
    """RFC 8058 List-Unsubscribe=One-Click POST endpoint."""
    try:
        res = process_unsubscribe_token(db=db, token=token, source="one_click_post")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return JSONResponse(content=res, status_code=200)
