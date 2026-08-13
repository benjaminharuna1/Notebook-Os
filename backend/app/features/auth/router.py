from fastapi import APIRouter, Depends, Response

from app.core.dependencies import get_current_user, get_db
from app.core.ratelimit import rate_limited
from app.features.auth.schemas import LoginRequest, RegisterRequest, AuthResponse
from app.features.auth.service import AuthService

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db=Depends(get_db), _: None = Depends(rate_limited("register"))):
    service = AuthService(db)
    return service.register(req)


@router.post("/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest, response: Response, db=Depends(get_db), _: None = Depends(rate_limited("login"))):
    service = AuthService(db)
    return service.login(req, response)


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"success": True}


@router.get("/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
