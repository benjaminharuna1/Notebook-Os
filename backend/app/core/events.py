from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import init_sqlite_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_sqlite_db()
    yield
