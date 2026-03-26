"""API key authentication dependency.

Protected routes use Depends(require_api_key) to enforce the x-api-key header.
The expected key is read from APP_API_KEY in the environment.
"""

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key != settings.app_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing x-api-key header.",
        )
