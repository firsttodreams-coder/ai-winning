"""Cloudflare Python Worker entry point for the FastAPI application."""
from workers import WorkerEntrypoint
import asgi

from src.api.main import app


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return await asgi.fetch(app, request.js_object, self.env)
