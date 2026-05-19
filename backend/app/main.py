from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from app.api.routes import auth, health, inventory, modules, pos, procurement, superadmin, users
from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.services.seed import seed_default_plans


@asynccontextmanager
async def lifespan(_: FastAPI):
    db = SessionLocal()
    try:
        if inspect(engine).has_table("planes"):
            seed_default_plans(db)
    finally:
        db.close()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(modules.router)
app.include_router(inventory.router)
app.include_router(procurement.router)
app.include_router(pos.router)
app.include_router(superadmin.router)
