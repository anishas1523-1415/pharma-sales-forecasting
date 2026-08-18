"""
Lightweight API-key auth — appropriate for an internal analytics API
serving non-PII, non-sensitive aggregate sales data (unlike a system
handling patient records, where JWT + per-user RBAC would be the right
call). This is the standard pattern for machine-to-machine / internal
tool access: a small set of issued keys, checked on every request.

Set API_KEYS (comma-separated) in the environment to enable enforcement.
Left unset, auth is a no-op — so local development and CI never need a
key. The deployed demo instance ships a published "demo" key (see
README) precisely so the live pitch isn't gated behind credentials
nobody but the team has.
"""
import os

from fastapi import Header, HTTPException

_configured_keys = {k.strip() for k in os.environ.get("API_KEYS", "").split(",") if k.strip()}


def require_api_key(x_api_key: str | None = Header(default=None)):
    if not _configured_keys:
        return  # auth not configured — local dev / CI
    if x_api_key not in _configured_keys:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")
