import json
import sqlite3

import pytest
from fastapi import HTTPException

from app.features.auth.schemas import LoginRequest, RegisterRequest
from app.features.auth.service import AuthService


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        """CREATE TABLE user_settings (
            user_id TEXT PRIMARY KEY,
            settings TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.commit()
    return conn


def test_register_success():
    conn = _db()
    service = AuthService(conn)
    req = RegisterRequest(email="test@example.com", username="testuser", password="password123")
    resp = service.register(req)
    assert resp.token
    assert resp.user["email"] == "test@example.com"
    assert resp.user["username"] == "testuser"
    assert resp.user["id"]


def test_register_duplicate_email():
    conn = _db()
    service = AuthService(conn)
    req = RegisterRequest(email="test@example.com", username="user1", password="password123")
    service.register(req)
    req2 = RegisterRequest(email="test@example.com", username="user2", password="password123")
    with pytest.raises(HTTPException) as excinfo:
        service.register(req2)
    assert excinfo.value.status_code == 409
    assert "Email already registered" in excinfo.value.detail


def test_register_duplicate_username():
    conn = _db()
    service = AuthService(conn)
    req = RegisterRequest(email="test1@example.com", username="testuser", password="password123")
    service.register(req)
    req2 = RegisterRequest(email="test2@example.com", username="testuser", password="password123")
    with pytest.raises(HTTPException) as excinfo:
        service.register(req2)
    assert excinfo.value.status_code == 409
    assert "Username already taken" in excinfo.value.detail


def test_login_with_email():
    conn = _db()
    service = AuthService(conn)
    req = RegisterRequest(email="test@example.com", username="testuser", password="password123")
    service.register(req)
    login_req = LoginRequest(identifier="test@example.com", password="password123")
    from fastapi import Response
    resp = Response()
    login_resp = service.login(login_req, resp)
    assert login_resp.token
    assert login_resp.user["email"] == "test@example.com"


def test_login_with_username():
    conn = _db()
    service = AuthService(conn)
    req = RegisterRequest(email="test@example.com", username="testuser", password="password123")
    service.register(req)
    login_req = LoginRequest(identifier="testuser", password="password123")
    from fastapi import Response
    resp = Response()
    login_resp = service.login(login_req, resp)
    assert login_resp.token
    assert login_resp.user["username"] == "testuser"


def test_login_wrong_password():
    conn = _db()
    service = AuthService(conn)
    req = RegisterRequest(email="test@example.com", username="testuser", password="password123")
    service.register(req)
    login_req = LoginRequest(identifier="test@example.com", password="wrongpassword")
    from fastapi import Response
    resp = Response()
    with pytest.raises(HTTPException) as excinfo:
        service.login(login_req, resp)
    assert excinfo.value.status_code == 401
    assert "Invalid" in excinfo.value.detail


def test_login_nonexistent_user():
    conn = _db()
    service = AuthService(conn)
    login_req = LoginRequest(identifier="nonexistent@example.com", password="password123")
    from fastapi import Response
    resp = Response()
    with pytest.raises(HTTPException) as excinfo:
        service.login(login_req, resp)
    assert excinfo.value.status_code == 401
