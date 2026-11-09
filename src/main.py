"""Cloudflare Python Worker entry point for the FastAPI application."""
from workers import asgi
from api.main import app

# Cloudflare's Python Workers runtime supplies the ASGI server.
Default = asgi.entrypoint(app)
