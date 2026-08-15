import json

from fastapi import HTTPException, Response, status

from app.core.config import settings
from app.core.security import create_jwt, hash_password, verify_password
from app.features.auth.schemas import AuthResponse, LoginRequest, RegisterRequest
from app.features.settings.defaults import get_default_settings
from app.shared.id_utils import generate_id


class AuthService:
    def __init__(self, db):
        self.db = db

    def register(self, req: RegisterRequest) -> AuthResponse:
        cursor = self.db.cursor()

        cursor.execute("SELECT id FROM users WHERE email = ?", (req.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        cursor.execute("SELECT id FROM users WHERE username = ?", (req.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

        user_id = generate_id()
        password_hash = hash_password(req.password)

        cursor.execute(
            "INSERT INTO users (id, email, username, password_hash) VALUES (?, ?, ?, ?)",
            (user_id, req.email, req.username, password_hash),
        )

        cursor.execute(
            "INSERT INTO user_settings (user_id, settings) VALUES (?, ?)",
            (user_id, json.dumps(get_default_settings("medium"))),
        )

        self.db.commit()

        token = create_jwt(user_id)
        return AuthResponse(
            token=token,
            user={"id": user_id, "email": req.email, "username": req.username},
        )

    def login(self, req: LoginRequest, response: Response) -> AuthResponse:
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT id, email, username, password_hash FROM users WHERE email = ? OR username = ?",
            (req.identifier, req.identifier),
        )
        row = cursor.fetchone()

        if not row or not verify_password(req.password, row["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email/username or password",
            )

        token = create_jwt(row["id"])

        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            max_age=settings.JWT_EXPIRE_MINUTES * 60,
            samesite="lax",
            secure=settings.COOKIE_SECURE,
        )

        return AuthResponse(
            token=token,
            user={"id": row["id"], "email": row["email"], "username": row["username"]},
        )
