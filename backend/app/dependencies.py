"""Clerk JWT validation dependency.

Validates the Bearer token from the Authorization header against Clerk's
JWKS endpoint. Extracts and returns the user_id (sub claim).

Clerk JWTs are RS256 signed. We fetch the public key from Clerk's JWKS
URL and verify locally — no round-trip to Clerk on every request.
"""

import httpx
import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

_bearer = HTTPBearer()
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        issuer = settings.CLERK_JWT_ISSUER.rstrip("/")
        jwks_uri = f"{issuer}/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_uri, cache_keys=True)
    return _jwks_client


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """FastAPI dependency — returns the authenticated Clerk user ID.

    Usage in a router:
        @router.get("/example")
        async def example(user_id: str = Depends(get_current_user_id)):
            ...
    """
    token = credentials.credentials
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        expected_issuer = settings.CLERK_JWT_ISSUER.rstrip("/")

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
            leeway=60,
        )

        token_issuer = str(payload.get("iss", "")).rstrip("/")
        if expected_issuer and token_issuer != expected_issuer:
            raise jwt.InvalidIssuerError(f"Issuer mismatch: got {token_issuer}, expected {expected_issuer}")

        user_id: str = payload.get("sub", "")
        if not user_id:
            raise ValueError("Missing sub claim")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
        )
    except (jwt.InvalidTokenError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {exc}",
        )
