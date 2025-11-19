"""Entrypoint for the FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, products, progress, upload
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="CSV Import Platform with background processing via RabbitMQ and Celery",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Register API routers
app.include_router(health.router)  # Health checks at root level
app.include_router(upload.router, prefix=settings.api_prefix)
app.include_router(progress.router, prefix=settings.api_prefix)
app.include_router(products.router, prefix=settings.api_prefix)
