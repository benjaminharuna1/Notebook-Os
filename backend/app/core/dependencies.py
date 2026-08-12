from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer

from app.core.database import get_chroma_client, get_sqlite_connection
from app.core.security import decode_jwt, hash_password, verify_password

bearer_scheme = HTTPBearer(auto_error=False)


def get_db():
    conn = get_sqlite_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_vector_store():
    return get_chroma_client()


def get_current_user(
    request: Request,
    bearer: str | None = Depends(bearer_scheme),
) -> dict:
    token = None

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]

    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    conn = get_sqlite_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, username FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return dict(user)
    finally:
        conn.close()
