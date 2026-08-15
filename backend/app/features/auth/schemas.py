from pydantic import BaseModel


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str


class LoginRequest(BaseModel):
    identifier: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict
